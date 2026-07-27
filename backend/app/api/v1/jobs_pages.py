"""Endpoint for serving extracted page images."""

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

    job_id_str = str(job_id)
    result = await db.execute(select(Job).where(Job.id == job_id_str))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id_str} not found",
        )

    # Construct and validate the expected page image path from safe components.
    # PdfParserStep stores pages at: {storage_path}/{job_id}/pages/page_{n:04d}.png
    storage_base = Path(settings.STORAGE_PATH).resolve()
    job_storage_dir = (storage_base / job_id_str).resolve()

    try:
        job_storage_dir.relative_to(storage_base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job path",
        )

    job_pages_dir = (job_storage_dir / "pages").resolve()

    try:
        job_pages_dir.relative_to(job_storage_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job path",
        )

    page_image = (job_pages_dir / f"page_{page_number:04d}.png").resolve()

    try:
        page_image.relative_to(job_pages_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid page path",
        )

    if not page_image.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} not found for job {job_id}",
        )

    return FileResponse(
        path=str(page_image),
        media_type="image/png",
        filename=f"page_{page_number:04d}.png",
    )
