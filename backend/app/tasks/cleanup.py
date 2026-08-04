"""Celery cleanup tasks for expiring old job files and recovering stale jobs."""

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


@celery_app.task(name="app.tasks.cleanup.cleanup_stale_jobs")
def cleanup_stale_jobs() -> int:
    """Mark jobs stuck in *processing* as *failed* so they stop blocking.

    When a Celery worker is killed by SIGKILL (e.g. an OOM kill) the task's
    exception handler never runs, leaving the job row in *processing* forever.
    This periodic sweep detects such orphaned jobs and transitions them to
    *failed* with a descriptive error message.
    """
    return asyncio.run(_cleanup_stale_jobs_async())


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


async def _cleanup_stale_jobs_async(now: datetime | None = None) -> int:
    """Mark jobs stuck in *processing* longer than the timeout as *failed*.

    Args:
        now: Optional override for the current time (used in tests).

    Returns:
        The number of jobs transitioned to *failed*.
    """
    settings = get_settings()
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=settings.JOB_STALE_TIMEOUT_SECONDS)
    failed_count = 0

    async with async_session() as session:
        result = await session.execute(
            select(Job).where(Job.status == "processing", Job.updated_at < cutoff)
        )
        stale_jobs = result.scalars().all()
        for job in stale_jobs:
            job.status = "failed"
            job.step = "Failed"
            job.error_msg = (
                f"Job timed out: was in 'processing' for longer than "
                f"{settings.JOB_STALE_TIMEOUT_SECONDS}s (worker may have been killed)."
            )
            failed_count += 1

        await session.commit()

    if failed_count:
        LOGGER.warning(
            "Marked %s stale job(s) as failed (stale timeout: %ss)",
            failed_count,
            settings.JOB_STALE_TIMEOUT_SECONDS,
        )
    return failed_count
