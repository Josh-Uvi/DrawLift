"""Job API endpoints: POST /jobs, GET /jobs/{id}, GET /jobs."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import JobConfig, JobCreateResponse, JobListResponse, JobStatus
from app.storage.local import get_storage
from app.tasks.placeholder import process_job

router = APIRouter()
settings = get_settings()

DEFAULT_CONFIG = (
    '{"mode": "2d", "dpi": 300, "floor_height_m": 3.0, '
    '"output_format": "dxf", "segmenter": "classic"}'
)


@router.post("/jobs", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    file: UploadFile = File(...),
    config: str = Form(default=DEFAULT_CONFIG),
    db: AsyncSession = Depends(get_db),
) -> JobCreateResponse:
    """Upload a PDF and create a conversion job.

    Args:
        file: The uploaded PDF file.
        config: JSON string with conversion options.
        db: Database session.

    Returns:
        JobCreateResponse with the new job_id.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf files are accepted",
        )
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF (application/pdf)",
        )

    # Parse config
    try:
        raw_config = json.loads(config)
        typed_config: dict[str, Any] = JobConfig.model_validate(raw_config).model_dump()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid config JSON",
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
    # Create job in DB
    job = Job(
        status="pending",
        progress=0,
        config=typed_config,
        input_file="",  # will be set after save
    )
    db.add(job)
    await db.flush()

    # Save file to storage
    storage = get_storage()
    file_path = await storage.save(file, str(job.id))
    job.input_file = file_path
    await db.flush()

    # Enqueue Celery task
    process_job.delay(str(job.id), typed_config)

    return JobCreateResponse(job_id=str(job.id))


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JobStatus:
    """Get job status by ID.

    Args:
        job_id: The job UUID.
        db: Database session.

    Returns:
        JobStatus with full job details.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobStatus.model_validate(job)


DOWNLOAD_FORMATS: dict[str, dict[str, str]] = {
    "dxf": {"suffix": ".dxf", "filename": "output.dxf", "media_type": "application/dxf"},
    "glb": {"suffix": ".glb", "filename": "output.glb", "media_type": "model/gltf-binary"},
}


@router.get("/jobs/{job_id}/download")
async def download_job_output(
    job_id: UUID,
    format: Annotated[Literal["dxf", "glb"], Query()] = "dxf",
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the generated DXF (default) or GLB file for a completed job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job output is not ready for download",
        )

    download_path = _resolve_download_path(job, download_format=format)
    return FileResponse(
        path=str(download_path),
        media_type=DOWNLOAD_FORMATS[format]["media_type"],
        filename=f"drawlift-{job.id}.{format}",
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List all jobs with optional status filter.

    Args:
        status_filter: Optional status to filter by.
        limit: Maximum number of results.
        offset: Pagination offset.
        db: Database session.

    Returns:
        JobListResponse with jobs and total count.
    """
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    if status_filter:
        query = query.where(Job.status == status_filter)
        count_query = count_query.where(Job.status == status_filter)

    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    jobs = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return JobListResponse(
        jobs=[JobStatus.model_validate(job) for job in jobs],
        total=total,
    )


def _resolve_download_path(job: Job, *, download_format: str = "dxf") -> Path:
    """Resolve and validate a job output path before serving it to clients.

    The DXF output is derived from the persisted ``output_file`` column. Other
    formats (e.g. GLB) live alongside it in the same trusted job output
    directory, so we derive their path from the DXF's parent to keep the
    ``.resolve()`` + ``relative_to()`` containment checks intact.
    """
    if not job.output_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No output file is available for this job",
        )

    spec = DOWNLOAD_FORMATS.get(download_format)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported download format: {download_format}",
        )

    storage_base = Path(settings.STORAGE_PATH).resolve()
    job_storage_dir = (storage_base / str(job.id)).resolve()
    dxf_path = Path(job.output_file).resolve()
    candidate = (dxf_path.parent / spec["filename"]).resolve()
    try:
        job_storage_dir.relative_to(storage_base)
        candidate.relative_to(job_storage_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid output path",
        ) from None

    if candidate.suffix.lower() != spec["suffix"] or not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{download_format.upper()} output file not found",
        )
    return candidate
