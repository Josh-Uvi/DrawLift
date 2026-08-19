"""Classic vs ML segmentation comparison metrics (US-031, T-103).

Runs both segmentation backends over the same image and reports per-label
coverage so classic-vs-ML output-quality differences can be documented
reproducibly instead of anecdotally.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.steps.segmenter import (
    MASK_LABELS,
    ClassicCVSegmenter,
    OnnxSemanticSegmenter,
    SegmentationMasks,
)

CLASSIC_BACKEND = "classic"
ML_BACKEND = "ml"
# Matches VectorizerStep.MIN_CONTOUR_AREA: blobs below this never become
# CAD primitives, so they are excluded from "vectorizable" counts.
DEFAULT_MIN_BLOB_AREA = 12.0


@dataclass(frozen=True)
class LabelCoverage:
    """Coverage statistics for one semantic label on one page."""

    label: str
    pixel_count: int
    coverage_percent: float
    vectorizable_blob_count: int

    @property
    def has_coverage(self) -> bool:
        """True when the backend produced any foreground for this label."""
        return self.pixel_count > 0


@dataclass(frozen=True)
class SegmenterComparisonReport:
    """Per-label coverage produced by both segmentation backends."""

    image_shape: tuple[int, int]
    classic: tuple[LabelCoverage, ...]
    ml: tuple[LabelCoverage, ...]

    def coverage(self, backend: str, label: str) -> LabelCoverage:
        """Return the coverage entry for one backend and label."""
        if backend == CLASSIC_BACKEND:
            entries = self.classic
        elif backend == ML_BACKEND:
            entries = self.ml
        else:
            raise KeyError(f"unknown backend {backend!r}")
        for entry in entries:
            if entry.label == label:
                return entry
        raise KeyError(f"unknown label {label!r} for backend {backend!r}")

    def summary_markdown(self) -> str:
        """Render a Markdown table comparing both backends label by label."""
        lines = [
            "| Label | Classic px | Classic % | ML px | ML % | ML blobs (>=12 px²) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for label in MASK_LABELS:
            classic = self.coverage(CLASSIC_BACKEND, label)
            ml = self.coverage(ML_BACKEND, label)
            lines.append(
                f"| {label} | {classic.pixel_count} | {classic.coverage_percent:.2f} "
                f"| {ml.pixel_count} | {ml.coverage_percent:.2f} "
                f"| {ml.vectorizable_blob_count} |"
            )
        return "\n".join(lines)


def compare_segmenters(
    image: np.ndarray,
    *,
    model_path: Path | str | None = None,
    input_size: tuple[int, int] | None = None,
    min_blob_area: float = DEFAULT_MIN_BLOB_AREA,
) -> SegmenterComparisonReport:
    """Segment ``image`` with both backends and compare per-label coverage."""
    classic_masks = ClassicCVSegmenter().segment([image])
    ml_segmenter = OnnxSemanticSegmenter(model_path=model_path, input_size=input_size)
    ml_masks = ml_segmenter.segment([image])

    return SegmenterComparisonReport(
        image_shape=image.shape[:2],
        classic=tuple(
            _label_coverage(classic_masks, label, min_blob_area) for label in MASK_LABELS
        ),
        ml=tuple(_label_coverage(ml_masks, label, min_blob_area) for label in MASK_LABELS),
    )


def _label_coverage(masks: SegmentationMasks, label: str, min_blob_area: float) -> LabelCoverage:
    """Compute coverage statistics for one label's first-page mask."""
    mask = masks[label][0]
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    pixel_count = int(np.count_nonzero(binary))
    total_pixels = int(binary.size)
    coverage_percent = round(100.0 * pixel_count / total_pixels, 3) if total_pixels else 0.0

    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    blob_count = 0
    for component_index in range(1, component_count):  # index 0 is background
        if int(stats[component_index, cv2.CC_STAT_AREA]) >= min_blob_area:
            blob_count += 1

    return LabelCoverage(
        label=label,
        pixel_count=pixel_count,
        coverage_percent=coverage_percent,
        vectorizable_blob_count=blob_count,
    )
