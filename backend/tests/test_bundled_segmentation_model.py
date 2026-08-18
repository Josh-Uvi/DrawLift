"""US-029 acceptance tests for the bundled segmentation model artifact.

These tests validate the committed ``backend/models/semantic_segmenter.onnx``
against the four acceptance criteria:

* the model file exists at ``backend/models/semantic_segmenter.onnx``
* it produces segmentation output compatible with the 5-class mask format
* it loads with ONNX Runtime on CPU without GPU dependencies
* the model file size is under 100 MB
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml.segmentation_model import (
    CPU_PROVIDER,
    MAX_MODEL_SIZE_BYTES,
    OUTPUT_CHANNELS_FIRST,
    validate_segmentation_model,
)
from app.pipeline.steps.segmenter import MASK_LABELS, OnnxSemanticSegmenter

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_MODEL_PATH = BACKEND_DIR / "models" / "semantic_segmenter.onnx"


def create_floor_plan() -> np.ndarray:
    """Create a synthetic binary floor plan with wall strokes."""
    image = np.zeros((160, 220), dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (200, 140), 255, thickness=5)
    cv2.line(image, (110, 20), (110, 100), 255, thickness=5)
    cv2.line(image, (20, 80), (85, 80), 255, thickness=5)
    return image


@pytest.fixture(scope="module")
def report():
    """Validate the bundled model once for the module."""
    return validate_segmentation_model(BUNDLED_MODEL_PATH)


def test_bundled_model_exists_at_expected_path() -> None:
    """AC: model file exists at backend/models/semantic_segmenter.onnx."""
    assert BUNDLED_MODEL_PATH.is_file()


def test_bundled_model_size_under_100mb(report) -> None:
    """AC: model file size is under 100 MB."""
    assert report.size_bytes is not None
    assert 0 < report.size_bytes < MAX_MODEL_SIZE_BYTES


def test_bundled_model_loads_on_cpu_only(report) -> None:
    """AC: loads with ONNX Runtime on CPU without GPU dependencies."""
    assert report.loads_on_cpu
    assert report.providers == (CPU_PROVIDER,)
    assert "CUDAExecutionProvider" not in report.providers


def test_bundled_model_passes_full_contract(report) -> None:
    """AC: overall US-029 contract validation passes."""
    assert report.passed
    assert report.inference_ok
    assert report.contract_ok


def test_bundled_model_output_is_five_class_compatible(report) -> None:
    """AC: output is decodable into the 5-class mask format."""
    assert report.contract_ok
    assert report.output_layout == OUTPUT_CHANNELS_FIRST
    # 6 channels = background + the 5 semantic labels.
    assert report.class_count == len(MASK_LABELS) + 1


def test_bundled_model_segments_into_five_labels() -> None:
    """The bundled model produces one mask per semantic label for a page."""
    segmenter = OnnxSemanticSegmenter(model_path=BUNDLED_MODEL_PATH, input_size=(64, 64))

    masks = segmenter.segment([create_floor_plan()])

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert len(masks[label]) == 1
        assert masks[label][0].shape == (160, 220)
        assert masks[label][0].dtype == np.uint8
    # Walls and rooms must be detected on a drawing that contains wall strokes.
    assert np.count_nonzero(masks["walls"][0]) > 0
    assert np.count_nonzero(masks["rooms"][0]) > 0


def test_bundled_model_handles_multiple_pages() -> None:
    """The bundled model segments every page in a multi-page batch."""
    segmenter = OnnxSemanticSegmenter(model_path=BUNDLED_MODEL_PATH, input_size=(64, 64))

    masks = segmenter.segment([create_floor_plan(), create_floor_plan(), create_floor_plan()])

    for label in MASK_LABELS:
        assert len(masks[label]) == 3
