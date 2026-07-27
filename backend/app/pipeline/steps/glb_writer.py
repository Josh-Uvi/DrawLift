"""GLB (binary glTF) writer step for extruded 3D primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import trimesh

from app.pipeline.context import PipelineContext
from app.pipeline.primitives import (
    Primitive,
    SlabPrimitive,
    WallSolidPrimitive,
)
from app.pipeline.steps.base import PipelineStep


class GlbWriterStep(PipelineStep):
    """Export extruded wall/slab geometry to a single self-contained GLB file.

    GLB (binary glTF) is a compact, self-contained format that opens directly in
    Blender and any online glTF viewer, satisfying US-024. The step reads the 3D
    primitives produced by :class:`WallExtruderStep` and writes ``output.glb``
    alongside the DXF output.
    """

    name = "GLB Writer"
    progress = 97

    def __init__(self, output_path: Path | str | None = None) -> None:
        """Create the writer with an optional output path override."""
        self.output_path = Path(output_path) if output_path is not None else None

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Build a mesh scene from 3D primitives and export it as GLB."""
        primitives = [cast(Primitive, primitive) for primitive in context.primitives]
        meshes = _build_meshes(primitives)
        if not meshes:
            raise ValueError("GlbWriterStep requires extruded 3D primitives on the context")

        output_path = self._resolve_output_path(context)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        scene = trimesh.Scene(meshes)
        scene.export(str(output_path), file_type="glb")

        context.metadata["glb_output_path"] = output_path
        context.metadata["glb_mesh_count"] = len(meshes)

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Wrote GLB output to {output_path.name}",
        )
        return context

    def _resolve_output_path(self, context: PipelineContext) -> Path:
        """Resolve the output GLB path under the current job storage directory."""
        if self.output_path is not None:
            return self.output_path

        configured_path: Any = context.config.get("glb_output_path")
        if configured_path is not None:
            return Path(str(configured_path))

        return context.input_path.parent / context.job_id / "output" / "output.glb"


def _build_meshes(primitives: list[Primitive]) -> list[trimesh.Trimesh]:
    """Convert 3D primitives into extruded trimesh boxes/prisms."""
    meshes: list[trimesh.Trimesh] = []
    for primitive in primitives:
        if isinstance(primitive, WallSolidPrimitive):
            mesh = _extrude_polygon(
                [(point.x, point.y) for point in primitive.footprint],
                base_z=primitive.base_z,
                height=primitive.height,
            )
            if mesh is not None:
                meshes.append(mesh)
        elif isinstance(primitive, SlabPrimitive):
            mesh = _extrude_polygon(
                [(point.x, point.y) for point in primitive.polygon],
                base_z=primitive.elevation,
                height=primitive.thickness,
            )
            if mesh is not None:
                meshes.append(mesh)
    return meshes


def _extrude_polygon(
    points: list[tuple[float, float]],
    *,
    base_z: float,
    height: float,
) -> trimesh.Trimesh | None:
    """Extrude a 2D polygon into a 3D prism between ``base_z`` and ``base_z + height``."""
    if len(points) < 3 or height <= 0:
        return None
    try:
        from shapely.geometry import Polygon
    except ImportError:  # pragma: no cover - shapely ships with trimesh extras
        return _extrude_quad(points, base_z=base_z, height=height)

    polygon = Polygon(points)
    if not polygon.is_valid or polygon.area == 0:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area == 0:
        return None

    mesh = trimesh.creation.extrude_polygon(polygon, height=height)
    mesh.apply_translation((0.0, 0.0, base_z))
    return mesh


def _extrude_quad(
    points: list[tuple[float, float]],
    *,
    base_z: float,
    height: float,
) -> trimesh.Trimesh | None:
    """Fallback prism builder for a 4-corner footprint without shapely."""
    if len(points) < 4:
        return None
    quad = points[:4]
    top_z = base_z + height
    vertices = np.array(
        [[x, y, base_z] for x, y in quad] + [[x, y, top_z] for x, y in quad],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ],
        dtype=np.int64,
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
