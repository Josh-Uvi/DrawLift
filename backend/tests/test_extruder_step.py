"""Tests for the 3D wall extrusion step."""

from __future__ import annotations

from pathlib import Path

from app.pipeline import PipelineContext, WallExtruderStep
from app.pipeline.primitives import (
    Point,
    Primitive,
    RoomPrimitive,
    SlabPrimitive,
    WallPrimitive,
    WallSolidPrimitive,
)


class RecordingPublisher:
    """In-memory progress publisher for extruder tests."""

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


def _context(**kwargs: object) -> PipelineContext:
    """Build a pipeline context seeded with vectorized primitives."""
    primitives: list[Primitive] = [
        WallPrimitive(start=Point(0, 0), end=Point(100, 0), thickness=10),
        RoomPrimitive(polygon=(Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))),
    ]
    return PipelineContext(
        job_id="job-3d",
        input_path=Path("/tmp/input.pdf"),
        primitives=list(primitives),
        config=dict(kwargs),
    )


def test_extruder_creates_wall_solids_with_floor_height() -> None:
    """Each wall becomes a prism with floor height as its Z dimension."""
    context = _context()

    result = WallExtruderStep(floor_height_m=3.0).execute(context)

    solids = [p for p in result.primitives if isinstance(p, WallSolidPrimitive)]
    assert len(solids) == 1
    solid = solids[0]
    assert solid.height == 3.0
    assert solid.base_z == 0.0
    assert solid.top_z == 3.0
    assert solid.thickness == 10
    assert len(solid.footprint) == 4


def test_extruder_respects_original_wall_geometry() -> None:
    """The extruded footprint is centered on the original centerline and thickness."""
    context = _context()

    result = WallExtruderStep(floor_height_m=2.5).execute(context)
    solid = next(p for p in result.primitives if isinstance(p, WallSolidPrimitive))

    ys = [point.y for point in solid.footprint]
    # A horizontal 10-unit-thick wall spans y in [-5, 5] around the centerline.
    assert min(ys) == -5.0
    assert max(ys) == 5.0


def test_extruder_uses_config_floor_height_when_not_overridden() -> None:
    """Floor height falls back to job config, defaulting to 3.0m."""
    context = _context(floor_height_m=4.2)

    result = WallExtruderStep().execute(context)
    solid = next(p for p in result.primitives if isinstance(p, WallSolidPrimitive))

    assert solid.height == 4.2


def test_extruder_adds_floor_slab_and_optional_ceiling() -> None:
    """A floor slab is always emitted; ceilings only when enabled."""
    floor_only = WallExtruderStep(floor_height_m=3.0).execute(_context())
    slabs = [p for p in floor_only.primitives if isinstance(p, SlabPrimitive)]
    assert len(slabs) == 1
    assert slabs[0].level == "floor"
    assert slabs[0].elevation == 0.0

    with_ceiling = WallExtruderStep(floor_height_m=3.0, include_ceiling=True).execute(_context())
    ceiling_slabs = [
        p for p in with_ceiling.primitives if isinstance(p, SlabPrimitive) and p.level == "ceiling"
    ]
    assert len(ceiling_slabs) == 1
    assert ceiling_slabs[0].elevation == 3.0


def test_extruder_reports_eighty_five_percent_progress() -> None:
    """Execution reports the US-021 85 percent progress milestone."""
    publisher = RecordingPublisher()
    context = _context()
    context.progress_publisher = publisher

    WallExtruderStep(floor_height_m=3.0).execute(context)

    assert publisher.events[-1]["progress"] == 85
    assert publisher.events[-1]["step"] == "3D Extrusion"


def test_extruder_preserves_existing_2d_primitives() -> None:
    """Original 2D primitives remain so the DXF plan can still be written."""
    context = _context()

    result = WallExtruderStep(floor_height_m=3.0).execute(context)

    assert any(isinstance(p, WallPrimitive) for p in result.primitives)
    assert any(isinstance(p, RoomPrimitive) for p in result.primitives)
