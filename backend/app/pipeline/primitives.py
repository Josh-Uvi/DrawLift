"""CAD primitive dataclasses produced by vectorization and extrusion steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class Point:
    """A 2D point in drawing coordinates."""

    x: float
    y: float


@dataclass(frozen=True)
class Point3D:
    """A 3D point in model coordinates (Z is the extrusion axis)."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class WallPrimitive:
    """A vectorized wall represented by a centerline and estimated thickness."""

    start: Point
    end: Point
    thickness: float
    page: int = 1
    kind: Literal["wall"] = "wall"


@dataclass(frozen=True)
class OpeningPrimitive:
    """A parametric door or window block extracted from semantic masks."""

    kind: Literal["door", "window"]
    insertion: Point
    width: float
    height: float
    rotation: float = 0.0
    page: int = 1


@dataclass(frozen=True)
class RoomPrimitive:
    """A simplified room polygon."""

    polygon: tuple[Point, ...]
    page: int = 1
    kind: Literal["room"] = "room"


@dataclass(frozen=True)
class TextPrimitive:
    """A text-region placeholder block for OCR-ready DXF output."""

    insertion: Point
    width: float
    height: float
    value: str = "TEXT"
    rotation: float = 0.0
    page: int = 1
    kind: Literal["text"] = "text"


@dataclass(frozen=True)
class WallSolidPrimitive:
    """A wall extruded into a 3D rectangular prism.

    ``footprint`` is the four-corner base rectangle (at ``z = base_z``) derived
    from the source wall centerline offset by half its thickness. The solid is
    extruded upward by ``height`` along the Z axis.
    """

    footprint: tuple[Point, ...]
    height: float
    base_z: float = 0.0
    thickness: float = 1.0
    page: int = 1
    kind: Literal["wall_solid"] = "wall_solid"

    @property
    def top_z(self) -> float:
        """Return the elevation of the wall's top face."""
        return self.base_z + self.height


@dataclass(frozen=True)
class SlabPrimitive:
    """A horizontal floor or ceiling slab extruded a small thickness in Z."""

    polygon: tuple[Point, ...]
    elevation: float
    thickness: float
    level: Literal["floor", "ceiling"] = "floor"
    page: int = 1
    kind: Literal["slab"] = "slab"


Primitive: TypeAlias = (
    WallPrimitive
    | OpeningPrimitive
    | RoomPrimitive
    | TextPrimitive
    | WallSolidPrimitive
    | SlabPrimitive
)


def wall_footprint(start: Point, end: Point, thickness: float) -> tuple[Point, ...]:
    """Return the 4-corner base rectangle for a wall centerline and thickness.

    The rectangle is centered on the ``start``→``end`` centerline and offset by
    half the wall thickness along the segment normal, preserving the original
    ``(start, end, thickness)`` geometry.
    """
    dx = end.x - start.x
    dy = end.y - start.y
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        # Degenerate wall: emit a small square so downstream writers stay robust.
        half = max(thickness, 1.0) / 2.0
        return (
            Point(start.x - half, start.y - half),
            Point(start.x + half, start.y - half),
            Point(start.x + half, start.y + half),
            Point(start.x - half, start.y + half),
        )

    half_thickness = max(thickness, 1.0) / 2.0
    # Unit normal to the centerline.
    nx = -dy / length
    ny = dx / length
    ox = nx * half_thickness
    oy = ny * half_thickness
    return (
        Point(start.x + ox, start.y + oy),
        Point(end.x + ox, end.y + oy),
        Point(end.x - ox, end.y - oy),
        Point(start.x - ox, start.y - oy),
    )


class SlabGenerator:
    """Build floor/ceiling slab primitives from detected room polygons."""

    def __init__(self, *, thickness: float = 0.2) -> None:
        """Create a slab generator with a default slab thickness in metres."""
        if thickness <= 0:
            raise ValueError("slab thickness must be greater than zero")
        self.thickness = thickness

    def floor_slab(self, rooms: list[RoomPrimitive], *, page: int = 1) -> SlabPrimitive | None:
        """Return a single slab at ``z = 0`` covering the union of room polygons."""
        footprint = _union_bounds(rooms)
        if footprint is None:
            return None
        return SlabPrimitive(
            polygon=footprint,
            elevation=0.0,
            thickness=self.thickness,
            level="floor",
            page=page,
        )

    def ceiling_slab(
        self, rooms: list[RoomPrimitive], *, elevation: float, page: int = 1
    ) -> SlabPrimitive | None:
        """Return an optional ceiling slab at ``z = elevation`` over the rooms."""
        footprint = _union_bounds(rooms)
        if footprint is None:
            return None
        return SlabPrimitive(
            polygon=footprint,
            elevation=elevation,
            thickness=self.thickness,
            level="ceiling",
            page=page,
        )


def _union_bounds(rooms: list[RoomPrimitive]) -> tuple[Point, ...] | None:
    """Return the axis-aligned bounding rectangle of the union of room polygons."""
    points = [point for room in rooms for point in room.polygon]
    if not points:
        return None
    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)
    if min_x == max_x or min_y == max_y:
        return None
    return (
        Point(min_x, min_y),
        Point(max_x, min_y),
        Point(max_x, max_y),
        Point(min_x, max_y),
    )
