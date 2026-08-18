"""Vectorization step that converts semantic masks into CAD primitives."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, cast

import cv2
import numpy as np

from app.pipeline.context import PipelineContext
from app.pipeline.primitives import (
    OpeningPrimitive,
    Point,
    Primitive,
    RoomPrimitive,
    TextPrimitive,
    WallPrimitive,
)
from app.pipeline.steps.base import PipelineStep
from app.pipeline.steps.segmenter import MASK_LABELS

MIN_CONTOUR_AREA = 12.0
MIN_WALL_LENGTH = 8.0
DEFAULT_SIMPLIFICATION_EPSILON = 2.0


class VectorizerStep(PipelineStep):
    """Convert semantic segmentation masks into CAD-friendly primitives."""

    name = "Vectorization"
    progress = 80

    def __init__(self, *, simplification_epsilon: float = DEFAULT_SIMPLIFICATION_EPSILON) -> None:
        """Create a vectorizer with a Douglas-Peucker simplification tolerance."""
        if simplification_epsilon <= 0:
            raise ValueError("simplification_epsilon must be greater than zero")
        self.simplification_epsilon = simplification_epsilon

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Vectorize every semantic mask page into wall, opening, room, and text primitives."""
        self._validate_masks(context.masks)
        page_count = len(cast(list[np.ndarray], context.masks["walls"]))

        primitives: list[Primitive] = []
        for page_index in range(page_count):
            page_number = page_index + 1
            primitives.extend(
                self._vectorize_walls(context.masks["walls"][page_index], page_number)
            )
            primitives.extend(
                self._vectorize_openings(
                    context.masks["doors"][page_index],
                    kind="door",
                    page=page_number,
                )
            )
            primitives.extend(
                self._vectorize_openings(
                    context.masks["windows"][page_index],
                    kind="window",
                    page=page_number,
                )
            )
            primitives.extend(
                self._vectorize_rooms(context.masks["rooms"][page_index], page_number)
            )
            primitives.extend(self._vectorize_text(context.masks["text"][page_index], page_number))

        context.primitives = primitives
        # Output writers operate on primitives only. Release full-resolution mask
        # arrays as soon as they have been vectorized to reduce peak RSS before
        # DXF/GLB generation.
        context.masks = {}
        context.metadata["primitive_count"] = len(primitives)
        context.metadata["primitive_counts_by_kind"] = _count_by_kind(primitives)

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Vectorized {len(primitives)} CAD primitive(s)",
        )
        return context

    @staticmethod
    def _validate_masks(masks: dict[str, Any]) -> None:
        """Ensure the context contains one list of NumPy masks per semantic label."""
        missing_labels = [label for label in MASK_LABELS if label not in masks]
        if missing_labels:
            raise ValueError(
                f"VectorizerStep requires masks for labels: {', '.join(missing_labels)}"
            )

        page_counts = {label: len(cast(list[Any], masks[label])) for label in MASK_LABELS}
        if len(set(page_counts.values())) != 1:
            raise ValueError(f"Semantic mask page counts differ by label: {page_counts}")

    def _vectorize_walls(self, mask: np.ndarray, page: int) -> list[WallPrimitive]:
        """Thin wall masks into centerline segments with estimated thickness."""
        binary = _as_binary_mask(mask)
        thickness = _estimate_wall_thickness(binary)
        lines = _detect_hough_lines(binary)

        if not lines:
            lines = list(self._segments_from_simplified_contours(binary))

        walls: list[WallPrimitive] = []
        seen: set[tuple[int, int, int, int]] = set()
        for x1, y1, x2, y2 in lines:
            if math.hypot(x2 - x1, y2 - y1) < MIN_WALL_LENGTH:
                continue
            key = _normalise_line_key(x1, y1, x2, y2)
            if key in seen:
                continue
            seen.add(key)
            walls.append(
                WallPrimitive(
                    start=Point(float(x1), float(y1)),
                    end=Point(float(x2), float(y2)),
                    thickness=thickness,
                    page=page,
                )
            )
        return walls

    def _segments_from_simplified_contours(
        self, mask: np.ndarray
    ) -> Iterable[tuple[int, int, int, int]]:
        """Fallback wall vectorization using Douglas-Peucker contour simplification."""
        for contour in _external_contours(mask):
            if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
                continue
            approximation = cv2.approxPolyDP(contour, self.simplification_epsilon, closed=True)
            points = approximation.reshape(-1, 2)
            if len(points) < 2:
                continue
            for index, start in enumerate(points):
                end = points[(index + 1) % len(points)]
                yield int(start[0]), int(start[1]), int(end[0]), int(end[1])

    @staticmethod
    def _vectorize_openings(
        mask: np.ndarray,
        *,
        kind: str,
        page: int,
    ) -> list[OpeningPrimitive]:
        """Convert door/window masks into parametric block primitives."""
        primitives: list[OpeningPrimitive] = []
        for contour in _external_contours(_as_binary_mask(mask)):
            if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
                continue
            rect = cv2.minAreaRect(contour)
            (center_x, center_y), (width, height), angle = rect
            block_width = max(float(width), float(height))
            block_height = min(float(width), float(height)) or 1.0
            primitives.append(
                OpeningPrimitive(
                    kind=cast(Any, kind),
                    insertion=Point(float(center_x), float(center_y)),
                    width=block_width,
                    height=block_height,
                    rotation=float(angle),
                    page=page,
                )
            )
        return primitives

    def _vectorize_rooms(self, mask: np.ndarray, page: int) -> list[RoomPrimitive]:
        """Convert room masks into simplified polygon primitives."""
        rooms: list[RoomPrimitive] = []
        for contour in _external_contours(_as_binary_mask(mask)):
            if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
                continue
            approximation = cv2.approxPolyDP(contour, self.simplification_epsilon, closed=True)
            polygon = tuple(
                Point(float(point[0][0]), float(point[0][1])) for point in approximation
            )
            if len(polygon) >= 3:
                rooms.append(RoomPrimitive(polygon=polygon, page=page))
        return rooms

    @staticmethod
    def _vectorize_text(mask: np.ndarray, page: int) -> list[TextPrimitive]:
        """Convert text masks into placeholder text-region blocks."""
        text_regions: list[TextPrimitive] = []
        for contour in _external_contours(_as_binary_mask(mask)):
            if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            text_regions.append(
                TextPrimitive(
                    insertion=Point(float(x), float(y)),
                    width=float(width),
                    height=float(height),
                    page=page,
                )
            )
        return text_regions


def _as_binary_mask(mask: np.ndarray) -> np.ndarray:
    """Normalize any mask-like array into a uint8 binary mask."""
    array = np.asarray(mask)
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    return ((array > 0).astype(np.uint8)) * 255


def _external_contours(mask: np.ndarray) -> list[np.ndarray]:
    """Return external contours from a binary mask."""
    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _estimate_wall_thickness(mask: np.ndarray) -> float:
    """Estimate wall thickness from the median foreground distance transform."""
    if np.count_nonzero(mask) == 0:
        return 1.0
    distances = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    foreground_distances = distances[mask > 0]
    if foreground_distances.size == 0:
        return 1.0
    return max(1.0, float(np.median(foreground_distances) * 2.0))


def _detect_hough_lines(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detect dominant wall centerlines using probabilistic Hough transforms."""
    edges = cv2.Canny(mask, 50, 150)
    min_dimension = max(1, min(mask.shape[:2]))
    # OpenCV returns None when no probabilistic Hough lines are detected, but
    # the bundled type hints do not model that nullable runtime behavior.
    lines = cast(
        np.ndarray | None,
        cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=max(10, min_dimension // 12),
            minLineLength=max(8, min_dimension // 10),
            maxLineGap=8,
        ),
    )
    if lines is None:
        return []
    return [
        (int(line[0]), int(line[1]), int(line[2]), int(line[3])) for line in lines.reshape(-1, 4)
    ]


def _normalise_line_key(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
    """Create a direction-insensitive rounded key for de-duplicating line segments."""
    start = (round(x1 / 2) * 2, round(y1 / 2) * 2)
    end = (round(x2 / 2) * 2, round(y2 / 2) * 2)
    if start <= end:
        return (*start, *end)
    return (*end, *start)


def _count_by_kind(primitives: Iterable[Primitive]) -> dict[str, int]:
    """Count primitives by domain kind for metadata and diagnostics."""
    counts = {"wall": 0, "door": 0, "window": 0, "room": 0, "text": 0}
    for primitive in primitives:
        counts[primitive.kind] += 1
    return counts
