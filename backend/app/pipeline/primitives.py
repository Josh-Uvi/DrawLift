"""CAD primitive dataclasses produced by vectorization steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class Point:
    """A 2D point in drawing coordinates."""

    x: float
    y: float


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


Primitive: TypeAlias = WallPrimitive | OpeningPrimitive | RoomPrimitive | TextPrimitive
