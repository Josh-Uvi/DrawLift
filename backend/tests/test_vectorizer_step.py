"""Tests for semantic-mask vectorization."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.pipeline import PipelineContext, VectorizerStep
from app.pipeline.primitives import OpeningPrimitive, RoomPrimitive, TextPrimitive, WallPrimitive
from app.pipeline.steps.segmenter import MASK_LABELS


class RecordingPublisher:
    """In-memory progress publisher for vectorization tests."""

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


def synthetic_masks() -> dict[str, list[np.ndarray]]:
    """Create deterministic semantic masks with all Epic 3 classes populated."""
    masks = {label: [np.zeros((160, 220), dtype=np.uint8)] for label in MASK_LABELS}
    cv2.line(masks["walls"][0], (20, 20), (200, 20), 255, thickness=6)
    cv2.line(masks["walls"][0], (20, 60), (200, 60), 255, thickness=6)
    cv2.rectangle(masks["doors"][0], (45, 18), (70, 32), 255, thickness=-1)
    cv2.rectangle(masks["windows"][0], (130, 55), (170, 65), 255, thickness=-1)
    cv2.rectangle(masks["rooms"][0], (30, 75), (190, 140), 255, thickness=-1)
    cv2.rectangle(masks["text"][0], (90, 90), (120, 105), 255, thickness=-1)
    return masks


def test_vectorizer_converts_masks_to_cad_primitives(tmp_path: Path) -> None:
    """Walls, openings, rooms, and text masks become typed CAD primitives."""
    context = PipelineContext(
        job_id="job-vector",
        input_path=tmp_path / "input.pdf",
        masks=synthetic_masks(),
    )

    result = VectorizerStep().execute(context)

    assert result is context
    assert any(isinstance(primitive, WallPrimitive) for primitive in result.primitives)
    assert any(
        isinstance(primitive, OpeningPrimitive) and primitive.kind == "door"
        for primitive in result.primitives
    )
    assert any(
        isinstance(primitive, OpeningPrimitive) and primitive.kind == "window"
        for primitive in result.primitives
    )
    assert any(isinstance(primitive, RoomPrimitive) for primitive in result.primitives)
    assert any(isinstance(primitive, TextPrimitive) for primitive in result.primitives)

    wall = next(
        primitive for primitive in result.primitives if isinstance(primitive, WallPrimitive)
    )
    assert wall.start != wall.end
    assert wall.thickness > 0
    counts = result.metadata["primitive_counts_by_kind"]
    assert counts["wall"] > 0
    assert counts["door"] == 1
    assert counts["window"] == 1
    assert counts["room"] == 1
    assert counts["text"] == 1


def test_vectorizer_simplifies_room_polygons(tmp_path: Path) -> None:
    """Douglas-Peucker simplification reduces rectangular room noise to few vertices."""
    context = PipelineContext(
        job_id="job-vector",
        input_path=tmp_path / "input.pdf",
        masks=synthetic_masks(),
    )

    VectorizerStep(simplification_epsilon=3.0).execute(context)

    room = next(
        primitive for primitive in context.primitives if isinstance(primitive, RoomPrimitive)
    )
    assert 3 <= len(room.polygon) <= 6


def test_vectorizer_publishes_eighty_percent_progress(tmp_path: Path) -> None:
    """Execution reports the US-018 80 percent progress milestone."""
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-vector",
        input_path=tmp_path / "input.pdf",
        masks=synthetic_masks(),
        progress_publisher=publisher,
    )

    VectorizerStep().execute(context)

    assert publisher.events == [
        {
            "job_id": "job-vector",
            "status": "processing",
            "progress": 80,
            "step": "Vectorization",
            "message": f"Vectorized {len(context.primitives)} CAD primitive(s)",
        }
    ]


def test_vectorizer_requires_complete_semantic_masks(tmp_path: Path) -> None:
    """Vectorizer fails clearly if segmentation has not populated all labels."""
    context = PipelineContext(
        job_id="job-vector",
        input_path=tmp_path / "input.pdf",
        masks={"walls": [np.zeros((10, 10), dtype=np.uint8)]},
    )

    with pytest.raises(ValueError, match="requires masks"):
        VectorizerStep().execute(context)
