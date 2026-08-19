"""Tests for classic vs ML segmentation comparison metrics (US-031, T-103)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml.comparison import (
    CLASSIC_BACKEND,
    ML_BACKEND,
    LabelCoverage,
    SegmenterComparisonReport,
    compare_segmenters,
)
from app.pipeline.steps.segmenter import MASK_LABELS

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_MODEL_PATH = BACKEND_DIR / "models" / "semantic_segmenter.onnx"


def representative_floor_plan() -> np.ndarray:
    """Build a floor plan with walls, a door arc, windows, and text dashes.

    Returns a grayscale image with foreground drawing pixels non-zero so both
    segmenters run against the same input convention used by the pipeline.
    """
    image = np.ones((240, 320), dtype=np.uint8) * 255
    ink = 0
    cv2.rectangle(image, (30, 30), (290, 210), ink, thickness=6)
    cv2.line(image, (160, 30), (160, 130), ink, thickness=6)
    cv2.line(image, (30, 120), (110, 120), ink, thickness=6)
    cv2.ellipse(image, (160, 165), (28, 28), 0, 0, 90, ink, thickness=3)
    cv2.line(image, (200, 30), (250, 30), 255, thickness=4)
    cv2.line(image, (200, 27), (250, 27), ink, thickness=2)
    cv2.line(image, (200, 33), (250, 33), ink, thickness=2)
    cv2.rectangle(image, (45, 190), (70, 198), ink, thickness=-1)
    cv2.rectangle(image, (75, 190), (100, 198), ink, thickness=-1)
    cv2.rectangle(image, (105, 190), (130, 198), ink, thickness=-1)
    return image


@pytest.fixture(scope="module")
def comparison_report() -> SegmenterComparisonReport:
    """Run both segmenters once over the representative floor plan."""
    return compare_segmenters(
        representative_floor_plan(),
        model_path=BUNDLED_MODEL_PATH,
        input_size=(128, 128),
    )


def test_ml_masks_cover_all_five_labels(comparison_report: SegmenterComparisonReport) -> None:
    """AC1/T-103: the ML backend produces non-empty masks for every label."""
    for label in MASK_LABELS:
        coverage = comparison_report.coverage(ML_BACKEND, label)
        assert coverage.has_coverage, f"ML missed label {label!r}"


def test_classic_masks_only_cover_walls_and_rooms(
    comparison_report: SegmenterComparisonReport,
) -> None:
    """Classic CV cannot emit doors, windows, or text masks."""
    assert comparison_report.coverage(CLASSIC_BACKEND, "walls").has_coverage
    for label in ("doors", "windows", "text"):
        assert not comparison_report.coverage(CLASSIC_BACKEND, label).has_coverage


def test_report_exposes_entries_for_every_label(
    comparison_report: SegmenterComparisonReport,
) -> None:
    assert len(comparison_report.classic) == len(MASK_LABELS)
    assert len(comparison_report.ml) == len(MASK_LABELS)
    assert {entry.label for entry in comparison_report.classic} == set(MASK_LABELS)
    assert {entry.label for entry in comparison_report.ml} == set(MASK_LABELS)


def test_report_coverage_accessor_rejects_unknown_labels(
    comparison_report: SegmenterComparisonReport,
) -> None:
    with pytest.raises(KeyError, match="unknown label"):
        comparison_report.coverage(ML_BACKEND, "roof")
    with pytest.raises(KeyError, match="unknown backend"):
        comparison_report.coverage("unknown", "walls")


def test_report_summary_markdown_is_stable_and_readable(
    comparison_report: SegmenterComparisonReport,
) -> None:
    markdown = comparison_report.summary_markdown()
    lines = markdown.splitlines()

    assert "| Label | Classic px | Classic % | ML px | ML % | ML blobs" in lines[0]
    assert "| --- | ---: | ---: | ---: | ---: | ---: |" in lines[1]
    assert len(lines) == len(MASK_LABELS) + 2
    for label in MASK_LABELS:
        assert any(line.startswith(f"| {label} |") for line in lines)


def test_compare_segmenters_is_deterministic() -> None:
    """The same image and model always produce the same coverage numbers."""
    image = representative_floor_plan()
    first = compare_segmenters(image, model_path=BUNDLED_MODEL_PATH, input_size=(128, 128))
    second = compare_segmenters(image, model_path=BUNDLED_MODEL_PATH, input_size=(128, 128))

    assert first == second


def test_label_coverage_fields_are_populated(
    comparison_report: SegmenterComparisonReport,
) -> None:
    walls = comparison_report.coverage(ML_BACKEND, "walls")
    assert isinstance(walls, LabelCoverage)
    assert walls.pixel_count > 0
    assert walls.coverage_percent > 0.0
    assert walls.vectorizable_blob_count > 0
