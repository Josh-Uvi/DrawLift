"""Celery cleanup task for expiring old job files."""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session
from app.models.job import Job
from app.tasks.celery_app import celery_app

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_jobs")
def cleanup_expired_jobs() -> int:
    """Archive jobs and delete local files older than the configured TTL."""
    return asyncio.run(_cleanup_expired_jobs_async())


async def _cleanup_expired_jobs_async(now: datetime | None = None) -> int:
    """Async cleanup implementation used by tests and the Celery task."""
    settings = get_settings()
    cutoff = (now or datetime.now(UTC)) - timedelta(days=settings.STORAGE_TTL_DAYS)
    storage_base = Path(settings.STORAGE_PATH).resolve()
    archived_count = 0

    async with async_session() as session:
        result = await session.execute(
            select(Job).where(Job.created_at < cutoff, Job.status != "archived")
        )
        jobs = result.scalars().all()
        for job in jobs:
            _delete_job_files(storage_base=storage_base, job=job)
            job.status = "archived"
            job.step = "Archived"
            job.progress = 100
            archived_count += 1

        await session.commit()

    LOGGER.info("Archived %s expired job(s) older than %s", archived_count, cutoff.isoformat())
    return archived_count


def _delete_job_files(*, storage_base: Path, job: Job) -> None:
    """Delete a job storage directory if it is contained under the storage base."""
    job_dir = (storage_base / str(job.id)).resolve()
    try:
        job_dir.relative_to(storage_base)
    except ValueError:
        LOGGER.warning("Skipping cleanup for unsafe job path: %s", job_dir)
        return

    if job_dir.exists():
        shutil.rmtree(job_dir)
        LOGGER.info("Deleted expired job files for %s", job.id)
