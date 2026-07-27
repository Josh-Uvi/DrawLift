"""Tests for the GLB (binary glTF) writer step."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.pipeline import GlbWriterStep, PipelineContext
from app.pipeline.primitives import (
    Point,
    Primitive,
    SlabPrimitive,
    WallSolidPrimitive,
)


class RecordingPublisher:
    """In-memory progress publisher for GLB writer tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish(
        self,
        *,
        job_id: str,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        """Record a progress event."""
        self.events.append(
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "step": step,
                "message": message,
            }
        )


def _solids() -> list[Primitive]:
    """Return a wall solid and a floor slab for extrusion."""
    footprint = (Point(0, 0), Point(100, 0), Point(100, 10), Point(0, 10))
    slab_polygon = (Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))
    return [
        WallSolidPrimitive(footprint=footprint, height=3.0, thickness=10),
        SlabPrimitive(polygon=slab_polygon, elevation=0.0, thickness=0.2, level="floor"),
    ]


def test_glb_writer_produces_loadable_single_file(tmp_path: Path) -> None:
    """The GLB is a single self-contained file loadable by any glTF reader."""
    output_path = tmp_path / "output" / "output.glb"
    context = PipelineContext(
        job_id="job-glb",
        input_path=tmp_path / "input.pdf",
        primitives=_solids(),
    )

    result = GlbWriterStep(output_path=output_path).execute(context)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    loaded = trimesh.load(output_path, file_type="glb")
    assert loaded is not None
    assert result.metadata["glb_mesh_count"] == 2


def test_glb_writer_reports_progress(tmp_path: Path) -> None:
    """Execution reports a progress milestone for the GLB export."""
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-glb",
        input_path=tmp_path / "input.pdf",
        primitives=_solids(),
        progress_publisher=publisher,
    )

    GlbWriterStep(output_path=tmp_path / "output.glb").execute(context)

    assert publisher.events[-1]["step"] == "GLB Writer"
    assert publisher.events[-1]["progress"] == 97


def test_glb_writer_requires_3d_primitives(tmp_path: Path) -> None:
    """Writer fails clearly when no extruded geometry is present."""
    context = PipelineContext(job_id="job-glb", input_path=tmp_path / "input.pdf")

    with pytest.raises(ValueError, match="requires extruded 3D primitives"):
        GlbWriterStep(output_path=tmp_path / "output.glb").execute(context)
