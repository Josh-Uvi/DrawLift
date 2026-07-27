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
    SlabPrimitive,
    TextPrimitive,
    WallPrimitive,
    WallSolidPrimitive,
)
from app.pipeline.steps.base import PipelineStep

LAYER_WALLS = "WALLS"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_ROOMS = "ROOMS"
LAYER_TEXT = "TEXT"
LAYER_WALLS_3D = "WALLS_3D"
LAYER_SLABS = "SLABS"
DXF_LAYERS: tuple[str, ...] = (LAYER_WALLS, LAYER_DOORS, LAYER_WINDOWS, LAYER_ROOMS, LAYER_TEXT)
DXF_3D_LAYERS: tuple[str, ...] = (LAYER_WALLS_3D, LAYER_SLABS)


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
            elif isinstance(primitive, WallSolidPrimitive):
                _add_wall_solid(modelspace, primitive)
            elif isinstance(primitive, SlabPrimitive):
                _add_slab(modelspace, primitive)

        document.saveas(output_path)

        has_3d = any(
            isinstance(primitive, WallSolidPrimitive | SlabPrimitive) for primitive in primitives
        )
        layers = list(DXF_LAYERS) + (list(DXF_3D_LAYERS) if has_3d else [])

        context.output_path = output_path
        context.metadata["output_format"] = "dxf"
        context.metadata["output_path"] = output_path
        context.metadata["dxf_layers"] = layers
        context.metadata["dxf_is_3d"] = has_3d

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
        LAYER_WALLS_3D: 8,
        LAYER_SLABS: 9,
    }
    for layer, colour in layer_colours.items():
        if layer not in document.layers:
            document.layers.add(layer, color=colour)


def _lineweight(thickness: float) -> int:
    """Map estimated wall thickness to a valid DXF lineweight value."""
    return max(13, min(211, int(round(thickness * 10))))


def _add_wall_solid(modelspace: Any, primitive: WallSolidPrimitive) -> None:
    """Render an extruded wall as top/bottom faces plus side 3DFACE walls."""
    base = [(point.x, point.y, primitive.base_z) for point in primitive.footprint]
    top = [(point.x, point.y, primitive.top_z) for point in primitive.footprint]
    if len(base) < 3:
        return

    dxfattribs = {"layer": LAYER_WALLS_3D}
    modelspace.add_3dface(base, dxfattribs=dxfattribs)
    modelspace.add_3dface(top, dxfattribs=dxfattribs)
    for index in range(len(base)):
        next_index = (index + 1) % len(base)
        side = [
            base[index],
            base[next_index],
            top[next_index],
            top[index],
        ]
        modelspace.add_3dface(side, dxfattribs=dxfattribs)


def _add_slab(modelspace: Any, primitive: SlabPrimitive) -> None:
    """Render a slab as a closed 3D polyline outline at its elevation."""
    points = [(point.x, point.y, primitive.elevation) for point in primitive.polygon]
    if len(points) < 3:
        return
    modelspace.add_polyline3d(
        [*points, points[0]],
        dxfattribs={"layer": LAYER_SLABS},
    )
    modelspace.add_3dface(points[:4], dxfattribs={"layer": LAYER_SLABS})


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
