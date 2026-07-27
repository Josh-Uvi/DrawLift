"""3D extrusion step that lifts 2D wall vectors into solid geometry."""

from __future__ import annotations

from typing import cast

from app.pipeline.context import PipelineContext
from app.pipeline.primitives import (
    Primitive,
    RoomPrimitive,
    SlabGenerator,
    SlabPrimitive,
    WallPrimitive,
    WallSolidPrimitive,
    wall_footprint,
)
from app.pipeline.steps.base import PipelineStep

DEFAULT_FLOOR_HEIGHT_M = 3.0
DEFAULT_SLAB_THICKNESS_M = 0.2


class WallExtruderStep(PipelineStep):
    """Extrude wall centerlines into 3D prisms and add floor/ceiling slabs.

    The step consumes the 2D ``WallPrimitive`` / ``RoomPrimitive`` output from
    vectorization and appends ``WallSolidPrimitive`` and ``SlabPrimitive``
    instances to the context. Existing 2D primitives are preserved so the DXF
    writer can still emit the layered plan alongside the 3D model.
    """

    name = "3D Extrusion"
    progress = 85

    def __init__(
        self,
        *,
        floor_height_m: float | None = None,
        slab_thickness_m: float = DEFAULT_SLAB_THICKNESS_M,
        include_ceiling: bool = False,
    ) -> None:
        """Create the extruder with optional floor height and slab settings."""
        if floor_height_m is not None and floor_height_m <= 0:
            raise ValueError("floor_height_m must be greater than zero")
        if slab_thickness_m <= 0:
            raise ValueError("slab_thickness_m must be greater than zero")
        self.floor_height_m = floor_height_m
        self.slab_thickness_m = slab_thickness_m
        self.include_ceiling = include_ceiling

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extrude walls into prisms and add slabs, then report 85% progress."""
        primitives = [cast(Primitive, primitive) for primitive in context.primitives]

        floor_height = self._resolve_floor_height(context)
        include_ceiling = bool(context.config.get("include_ceiling", self.include_ceiling))
        slab_thickness = float(context.config.get("slab_thickness_m", self.slab_thickness_m))

        walls = [primitive for primitive in primitives if isinstance(primitive, WallPrimitive)]
        rooms = [primitive for primitive in primitives if isinstance(primitive, RoomPrimitive)]

        solids: list[WallSolidPrimitive] = [
            self._extrude_wall(wall, floor_height) for wall in walls
        ]

        slabs = self._build_slabs(
            rooms,
            floor_height=floor_height,
            slab_thickness=slab_thickness,
            include_ceiling=include_ceiling,
        )

        context.primitives = [*primitives, *solids, *slabs]
        context.metadata["floor_height_m"] = floor_height
        context.metadata["slab_thickness_m"] = slab_thickness
        context.metadata["wall_solid_count"] = len(solids)
        context.metadata["slab_count"] = len(slabs)

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Extruded {len(solids)} wall(s) and {len(slabs)} slab(s)",
        )
        return context

    def _resolve_floor_height(self, context: PipelineContext) -> float:
        """Resolve the floor height from the step override or job config."""
        if self.floor_height_m is not None:
            return self.floor_height_m
        configured = context.config.get("floor_height_m", DEFAULT_FLOOR_HEIGHT_M)
        height = float(configured)
        if height <= 0:
            raise ValueError("floor_height_m must be greater than zero")
        return height

    @staticmethod
    def _extrude_wall(wall: WallPrimitive, floor_height: float) -> WallSolidPrimitive:
        """Turn one wall centerline + thickness into a rectangular prism."""
        footprint = wall_footprint(wall.start, wall.end, wall.thickness)
        return WallSolidPrimitive(
            footprint=footprint,
            height=floor_height,
            base_z=0.0,
            thickness=wall.thickness,
            page=wall.page,
        )

    def _build_slabs(
        self,
        rooms: list[RoomPrimitive],
        *,
        floor_height: float,
        slab_thickness: float,
        include_ceiling: bool,
    ) -> list[SlabPrimitive]:
        """Generate a floor slab and optional ceiling slab from room polygons."""
        generator = SlabGenerator(thickness=slab_thickness)
        slabs: list[SlabPrimitive] = []
        floor = generator.floor_slab(rooms)
        if floor is not None:
            slabs.append(floor)
        if include_ceiling:
            ceiling = generator.ceiling_slab(rooms, elevation=floor_height)
            if ceiling is not None:
                slabs.append(ceiling)
        return slabs
