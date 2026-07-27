"""Tests for DXF writer output."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from app.pipeline import DxfWriterStep, PipelineContext
from app.pipeline.primitives import (
    OpeningPrimitive,
    Point,
    RoomPrimitive,
    SlabPrimitive,
    TextPrimitive,
    WallPrimitive,
    WallSolidPrimitive,
)
from app.pipeline.steps.dxf_writer import DXF_3D_LAYERS, DXF_LAYERS


class RecordingPublisher:
    """In-memory progress publisher for DXF writer tests."""

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


def primitives() -> list[object]:
    """Return one primitive for every DXF layer."""
    return [
        WallPrimitive(start=Point(0, 0), end=Point(100, 0), thickness=5),
        OpeningPrimitive(kind="door", insertion=Point(20, 0), width=12, height=4),
        OpeningPrimitive(kind="window", insertion=Point(70, 0), width=20, height=3),
        RoomPrimitive(polygon=(Point(0, 10), Point(100, 10), Point(100, 80), Point(0, 80))),
        TextPrimitive(insertion=Point(10, 20), width=20, height=5, value="Room"),
    ]


def test_dxf_writer_generates_round_trippable_layers(tmp_path: Path) -> None:
    """Generated DXF can be read by ezdxf and contains the required semantic layers."""
    output_path = tmp_path / "output" / "output.dxf"
    context = PipelineContext(
        job_id="job-dxf",
        input_path=tmp_path / "input.pdf",
        primitives=primitives(),
    )

    result = DxfWriterStep(output_path=output_path).execute(context)

    assert result.output_path == output_path
    assert output_path.exists()
    document = ezdxf.readfile(output_path)
    layer_names = {layer.dxf.name for layer in document.layers}
    assert set(DXF_LAYERS).issubset(layer_names)
    entity_layers = {entity.dxf.layer for entity in document.modelspace()}
    assert set(DXF_LAYERS).issubset(entity_layers)


def test_dxf_writer_publishes_ninety_five_percent_progress(tmp_path: Path) -> None:
    """Execution reports the US-019 95 percent progress milestone."""
    output_path = tmp_path / "output.dxf"
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-dxf",
        input_path=tmp_path / "input.pdf",
        primitives=primitives(),
        progress_publisher=publisher,
    )

    DxfWriterStep(output_path=output_path).execute(context)

    assert publisher.events == [
        {
            "job_id": "job-dxf",
            "status": "processing",
            "progress": 95,
            "step": "DXF Writer",
            "message": "Wrote DXF output to output.dxf",
        }
    ]


def test_dxf_writer_requires_primitives(tmp_path: Path) -> None:
    """Writer fails clearly if vectorization has not produced primitives."""
    context = PipelineContext(job_id="job-dxf", input_path=tmp_path / "input.pdf")

    with pytest.raises(ValueError, match="requires primitives"):
        DxfWriterStep(output_path=tmp_path / "output.dxf").execute(context)


def test_dxf_writer_emits_3d_entities_for_solids(tmp_path: Path) -> None:
    """3D solids and slabs produce 3DFACE entities on dedicated layers."""
    output_path = tmp_path / "output" / "output.dxf"
    footprint = (Point(0, 0), Point(100, 0), Point(100, 10), Point(0, 10))
    slab_polygon = (Point(0, 0), Point(100, 0), Point(100, 80), Point(0, 80))
    context = PipelineContext(
        job_id="job-dxf-3d",
        input_path=tmp_path / "input.pdf",
        primitives=[
            WallPrimitive(start=Point(0, 5), end=Point(100, 5), thickness=10),
            WallSolidPrimitive(footprint=footprint, height=3.0, thickness=10),
            SlabPrimitive(polygon=slab_polygon, elevation=0.0, thickness=0.2, level="floor"),
        ],
    )

    result = DxfWriterStep(output_path=output_path).execute(context)

    assert result.metadata["dxf_is_3d"] is True
    document = ezdxf.readfile(output_path)
    layer_names = {layer.dxf.name for layer in document.layers}
    assert set(DXF_3D_LAYERS).issubset(layer_names)
    entity_types = {entity.dxftype() for entity in document.modelspace()}
    assert "3DFACE" in entity_types
