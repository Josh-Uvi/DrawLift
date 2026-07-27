"""DXF writer step for CAD primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import ezdxf

from app.pipeline.context import PipelineContext
from app.pipeline.primitives import (
    OpeningPrimitive,
    Primitive,
    RoomPrimitive,
    TextPrimitive,
    WallPrimitive,
)
from app.pipeline.steps.base import PipelineStep

LAYER_WALLS = "WALLS"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_ROOMS = "ROOMS"
LAYER_TEXT = "TEXT"
DXF_LAYERS: tuple[str, ...] = (LAYER_WALLS, LAYER_DOORS, LAYER_WINDOWS, LAYER_ROOMS, LAYER_TEXT)


class DxfWriterStep(PipelineStep):
    """Write vectorized primitives to a standards-compatible DXF file."""

    name = "DXF Writer"
    progress = 95

    def __init__(self, output_path: Path | str | None = None) -> None:
        """Create the writer with an optional output path override."""
        self.output_path = Path(output_path) if output_path is not None else None

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Render context primitives into an AutoCAD/LibreCAD-readable DXF file."""
        primitives = [cast(Primitive, primitive) for primitive in context.primitives]
        if not primitives:
            raise ValueError("DxfWriterStep requires primitives on the context")

        output_path = self._resolve_output_path(context)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        document = ezdxf.new("R2010")
        document.header["$INSUNITS"] = 4  # millimetres by convention for raster-derived plans
        _ensure_layers(document)
        modelspace = document.modelspace()

        for primitive in primitives:
            if isinstance(primitive, WallPrimitive):
                modelspace.add_line(
                    (primitive.start.x, primitive.start.y),
                    (primitive.end.x, primitive.end.y),
                    dxfattribs={
                        "layer": LAYER_WALLS,
                        "lineweight": _lineweight(primitive.thickness),
                    },
                )
            elif isinstance(primitive, OpeningPrimitive):
                layer = LAYER_DOORS if primitive.kind == "door" else LAYER_WINDOWS
                _add_opening_block(modelspace, primitive, layer)
            elif isinstance(primitive, RoomPrimitive):
                points = [(point.x, point.y) for point in primitive.polygon]
                if len(points) >= 3:
                    modelspace.add_lwpolyline(
                        points,
                        close=True,
                        dxfattribs={"layer": LAYER_ROOMS},
                    )
            elif isinstance(primitive, TextPrimitive):
                text = modelspace.add_text(
                    primitive.value,
                    dxfattribs={"layer": LAYER_TEXT, "height": max(primitive.height, 1.0)},
                )
                text.dxf.insert = (primitive.insertion.x, primitive.insertion.y)
                text.dxf.rotation = primitive.rotation

        document.saveas(output_path)

        context.output_path = output_path
        context.metadata["output_format"] = "dxf"
        context.metadata["output_path"] = output_path
        context.metadata["dxf_layers"] = list(DXF_LAYERS)

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Wrote DXF output to {output_path.name}",
        )
        return context

    def _resolve_output_path(self, context: PipelineContext) -> Path:
        """Resolve the output DXF path under the current job storage directory."""
        if self.output_path is not None:
            return self.output_path

        configured_path: Any = context.config.get("output_path")
        if configured_path is not None:
            return Path(str(configured_path))

        return context.input_path.parent / context.job_id / "output" / "output.dxf"


def _ensure_layers(document: ezdxf.document.Drawing) -> None:
    """Create semantic CAD layers if they do not already exist."""
    layer_colours = {
        LAYER_WALLS: 7,
        LAYER_DOORS: 3,
        LAYER_WINDOWS: 4,
        LAYER_ROOMS: 2,
        LAYER_TEXT: 1,
    }
    for layer, colour in layer_colours.items():
        if layer not in document.layers:
            document.layers.add(layer, color=colour)


def _lineweight(thickness: float) -> int:
    """Map estimated wall thickness to a valid DXF lineweight value."""
    return max(13, min(211, int(round(thickness * 10))))


def _add_opening_block(modelspace: Any, primitive: OpeningPrimitive, layer: str) -> None:
    """Draw a parametric opening as a rotated rectangle block outline."""
    x = primitive.insertion.x
    y = primitive.insertion.y
    half_width = primitive.width / 2.0
    half_height = max(primitive.height / 2.0, 0.5)
    points = [
        (x - half_width, y - half_height),
        (x + half_width, y - half_height),
        (x + half_width, y + half_height),
        (x - half_width, y + half_height),
    ]
    modelspace.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
