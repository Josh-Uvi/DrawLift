"""Tests for semantic segmentation pipeline steps."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.pipeline import Pipeline, PipelineContext, SegmenterStep
from app.pipeline.steps.segmenter import MASK_LABELS, OnnxSemanticSegmenter, SegmentationMasks


class RecordingPublisher:
    """In-memory progress publisher for segmentation tests."""

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


class StubSegmenter:
    """Deterministic segmenter used to verify backend selection."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.called = False

    def segment(self, images: Sequence[np.ndarray]) -> SegmentationMasks:
        """Return one deterministic mask per semantic label."""
        self.called = True
        masks: SegmentationMasks = {label: [] for label in MASK_LABELS}
        for image in images:
            height, width = image.shape[:2]
            for semantic_label in MASK_LABELS:
                mask = np.zeros((height, width), dtype=np.uint8)
                if semantic_label == self.label:
                    mask[1 : height - 1, 1 : width - 1] = 255
                masks[semantic_label].append(mask)
        return masks


class BrokenSegmenter:
    """Segmenter that returns an invalid mask count."""

    def segment(self, images: Sequence[np.ndarray]) -> SegmentationMasks:
        """Return only one mask regardless of the number of pages."""
        masks: SegmentationMasks = {label: [] for label in MASK_LABELS}
        shape = images[0].shape[:2]
        for label in MASK_LABELS:
            masks[label].append(np.zeros(shape, dtype=np.uint8))
        return masks


def create_simple_floor_plan() -> np.ndarray:
    """Create a synthetic binary floor plan with an enclosed room."""
    image = np.zeros((160, 220), dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (200, 140), 255, thickness=5)
    cv2.line(image, (110, 20), (110, 100), 255, thickness=5)
    cv2.line(image, (20, 80), (85, 80), 255, thickness=5)
    cv2.line(image, (135, 80), (200, 80), 255, thickness=5)
    return image


def test_classic_segmenter_returns_semantic_masks_and_saves_pngs(tmp_path: Path) -> None:
    """Classic CV segmentation returns stable per-label masks and persisted previews."""
    image = create_simple_floor_plan()
    output_dir = tmp_path / "masks"
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "classic"},
        preprocessed=[image],
    )

    result = SegmenterStep(output_dir=output_dir).execute(context)

    assert result is context
    assert set(result.masks) == set(MASK_LABELS)
    assert result.metadata["segmenter"] == "classic"
    assert result.metadata["segmentation_count"] == 1
    assert result.metadata["segmentation_mask_dir"] == output_dir

    walls = result.masks["walls"][0]
    rooms = result.masks["rooms"][0]
    assert walls.shape == image.shape
    assert rooms.shape == image.shape
    assert walls.dtype == np.uint8
    assert np.count_nonzero(walls) > 0
    assert np.count_nonzero(rooms) > 0

    mask_paths = result.metadata["segmentation_mask_paths"]
    assert set(mask_paths) == set(MASK_LABELS)
    for label in MASK_LABELS:
        path = output_dir / label / f"page_0001_{label}.png"
        assert mask_paths[label] == [path]
        assert path.read_bytes().startswith(b"\x89PNG")


def test_segmenter_publishes_sixty_percent_progress(tmp_path: Path) -> None:
    """Execution reports the US-016 60 percent progress milestone."""
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "classic"},
        preprocessed=[create_simple_floor_plan()],
        progress_publisher=publisher,
    )

    SegmenterStep(output_dir=tmp_path / "masks").execute(context)

    assert publisher.events == [
        {
            "job_id": "job-789",
            "status": "processing",
            "progress": 60,
            "step": "Semantic Segmentation",
            "message": "Segmented 1 page image(s) using classic",
        }
    ]


def test_segmenter_selects_ml_backend_from_config(tmp_path: Path) -> None:
    """The job config can select the ML segmenter backend."""
    ml_segmenter = StubSegmenter("text")
    classic_segmenter = StubSegmenter("walls")
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "ml"},
        preprocessed=[create_simple_floor_plan()],
    )

    result = SegmenterStep(
        output_dir=tmp_path / "masks",
        ml_segmenter=ml_segmenter,
        classic_segmenter=classic_segmenter,
    ).execute(context)

    assert ml_segmenter.called is True
    assert classic_segmenter.called is False
    assert result.metadata["segmenter"] == "ml"
    assert np.count_nonzero(result.masks["text"][0]) > 0
    assert np.count_nonzero(result.masks["walls"][0]) == 0


def test_segmenter_rejects_invalid_backend_name(tmp_path: Path) -> None:
    """Only supported segmenter names are accepted."""
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "unknown"},
        preprocessed=[create_simple_floor_plan()],
    )

    with pytest.raises(ValueError, match="segmenter must be either"):
        SegmenterStep(output_dir=tmp_path / "masks").execute(context)


def test_segmenter_requires_preprocessed_images(tmp_path: Path) -> None:
    """The step fails clearly when preprocessing has not run."""
    context = PipelineContext(job_id="job-789", input_path=tmp_path / "input.pdf")

    with pytest.raises(ValueError, match="requires preprocessed images"):
        SegmenterStep().execute(context)


def test_segmenter_validates_backend_mask_counts(tmp_path: Path) -> None:
    """Backend implementations must return one mask per label and page."""
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "ml"},
        preprocessed=[create_simple_floor_plan(), create_simple_floor_plan()],
    )

    with pytest.raises(ValueError, match="unexpected mask count"):
        SegmenterStep(
            output_dir=tmp_path / "masks",
            ml_segmenter=BrokenSegmenter(),
        ).execute(context)


def test_segmenter_runs_after_preprocessor_in_pipeline(tmp_path: Path) -> None:
    """Semantic segmentation plugs into the pipeline after preprocessing."""
    context = PipelineContext(
        job_id="job-789",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "classic"},
        preprocessed=[create_simple_floor_plan()],
    )
    pipeline = Pipeline.from_steps(
        SegmenterStep(output_dir=tmp_path / "masks"),
        publish_step_progress=False,
    )

    result = pipeline.run(context)

    assert set(result.masks) == set(MASK_LABELS)
    assert result.metadata["segmentation_count"] == 1


def test_onnx_segmenter_decodes_channel_masks_to_semantic_labels() -> None:
    """ONNX outputs with class channels are decoded into per-label masks."""
    output = np.zeros((1, len(MASK_LABELS), 4, 4), dtype=np.float32)
    output[0, 0, 1:3, 1:3] = 1.0
    output[0, 4, 0:2, 0:2] = 1.0

    masks = OnnxSemanticSegmenter().decode_output(output, [(8, 8)])

    assert set(masks) == set(MASK_LABELS)
    assert masks["walls"][0].shape == (8, 8)
    assert np.count_nonzero(masks["walls"][0]) > 0
    assert np.count_nonzero(masks["text"][0]) > 0
    assert np.count_nonzero(masks["doors"][0]) == 0


def test_onnx_segmenter_decodes_class_map_masks_to_semantic_labels() -> None:
    """ONNX outputs with integer class maps are decoded into per-label masks."""
    output = np.zeros((1, 4, 4), dtype=np.int64)
    output[0, 1:3, 1:3] = 1
    output[0, 0:2, 0:2] = 5

    masks = OnnxSemanticSegmenter().decode_output(output, [(8, 8)])

    assert set(masks) == set(MASK_LABELS)
    assert np.count_nonzero(masks["walls"][0]) > 0
    assert np.count_nonzero(masks["text"][0]) > 0
    assert np.count_nonzero(masks["doors"][0]) == 0
