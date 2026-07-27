"""Pydantic request/response models for the Job API."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class JobConfig(BaseModel):
    """User-provided conversion configuration."""

    mode: Literal["2d", "3d"] = "2d"
    dpi: int = Field(default=300, ge=72, le=1200)
    floor_height_m: float = Field(default=3.0, ge=0.5, le=10.0)
    slab_thickness_m: float = Field(default=0.2, ge=0.05, le=2.0)
    include_ceiling: bool = False
    output_format: Literal["dxf", "dwg", "glb"] = "dxf"
    segmenter: Literal["ml", "classic"] = "classic"


class JobCreateResponse(BaseModel):
    """Response returned after creating a job."""

    job_id: str


class JobStatus(BaseModel):
    """Full job status representation."""

    id: UUID
    status: Literal["pending", "queued", "processing", "completed", "failed"]
    progress: int
    step: str | None = None
    config: dict[str, Any]
    input_file: str
    output_file: str | None = None
    page_count: int | None = None
    error_msg: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobStatus]
    total: int


class SSEProgressEvent(BaseModel):
    """SSE event payload for progress updates."""

    job_id: str
    status: Literal["pending", "queued", "processing", "completed", "failed"]
    progress: int
    step: str
