"""Endpoint for serving extracted page images."""

import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.job import Job

router = APIRouter()
settings = get_settings()

_PAGE_IMAGE_PATTERN = re.compile(r"^page_(\d{4})\.png$")


def _ensure_child_path(path: Path, parent: Path, detail: str) -> None:
    """Ensure a resolved path remains inside its expected resolved parent."""
    try:
        path.relative_to(parent)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from None


def _find_page_image(job_pages_dir: Path, page_number: int) -> Path | None:
    """Return a page image selected from trusted storage using an allowlisted name."""
    if not job_pages_dir.is_dir():
        return None

    for candidate in job_pages_dir.iterdir():
        match = _PAGE_IMAGE_PATTERN.fullmatch(candidate.name)
        if match is None or int(match.group(1)) != page_number:
            continue

        resolved_candidate = candidate.resolve()
        _ensure_child_path(
            resolved_candidate,
            job_pages_dir,
            "Invalid page path",
        )

        if resolved_candidate.is_file():
            return resolved_candidate

    return None


@router.get("/jobs/{job_id}/pages/{page_number}")
async def get_job_page(
    job_id: UUID,
    page_number: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve an extracted page image for a given job and page number.

    Args:
        job_id: The job UUID as a string.
        page_number: The 1-based page number.
        db: Database session.

    Returns:
        FileResponse with the page image.

    Raises:
        HTTPException 404: If the job or page image is not found.
        HTTPException 400: If the page number is invalid.
    """
    if page_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be 1 or greater",
        )

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.page_count is not None and page_number > job.page_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found for job {job_id}",
        )

    # Construct job storage paths only from configured storage and persisted job data.
    # PdfParserStep stores pages at: {storage_path}/{job_id}/pages/page_{n:04d}.png
    storage_base = Path(settings.STORAGE_PATH).resolve()
    persisted_job_dir_name = str(job.id)
    job_storage_dir = (storage_base / persisted_job_dir_name).resolve()

    _ensure_child_path(job_storage_dir, storage_base, "Invalid job path")

    job_pages_dir = (job_storage_dir / "pages").resolve()

    _ensure_child_path(job_pages_dir, job_storage_dir, "Invalid job path")

    page_image = _find_page_image(job_pages_dir, page_number)
    if page_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found for job {job_id}",
        )

    return FileResponse(
        path=str(page_image),
        media_type="image/png",
        filename=page_image.name,
    )
