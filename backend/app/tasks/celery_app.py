"""Celery application instance with Redis broker and result backend."""

from celery import Celery
from celery.signals import task_failure

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_file_converter",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.placeholder", "app.tasks.cleanup"],
)


@task_failure.connect
def _mark_job_failed_on_task_failure(
    sender: object,
    task_id: str,
    exception: BaseException,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    einfo: object,
    **signal_kwargs: object,
) -> None:
    """Mark the database job as 'failed' when a task fails or a worker is lost.

    When a worker process is SIGKILL'd (e.g. OOM), the ``try/except`` block
    inside ``process_job`` never executes because the subprocess is killed
    externally.  Celery's *main* process still detects the death and fires the
    ``task_failure`` signal, so we use it as a back-stop to ensure the job row
    in the database is transitioned out of 'processing'.

    Note: ``task_acks_late`` is intentionally **False** here.  With
    ``task_acks_late=True`` the broker re-queues un-acked tasks when a worker
    process dies, which causes an *infinite* retry loop when the OOM is
    consistent (each retry also gets killed).  With ``task_acks_late=False``
    the task is acknowledged immediately; if the worker dies the task is lost
    from the queue but the ``task_failure`` signal still fires and this handler
    marks the job as 'failed'.  Task-level exceptions (raised inside the task
    function) are still retried via ``autoretry_for`` / ``max_retries``.
    """
    import asyncio
    import logging
    from uuid import UUID

    from sqlalchemy import select

    from app.core.database import async_session
    from app.models.job import Job

    logger = logging.getLogger(__name__)

    # Only the process_job task carries a job_id as its first positional arg.
    if not args:
        return

    raw_job_id = args[0]
    if not isinstance(raw_job_id, str):
        return

    try:
        job_uuid = UUID(raw_job_id)
    except (ValueError, TypeError):
        logger.warning("task_failure signal: could not parse job_id %r", raw_job_id)
        return

    async def _mark_failed() -> None:
        async with async_session() as session:
            result = await session.execute(select(Job).where(Job.id == job_uuid))
            job = result.scalar_one_or_none()
            if job is not None and job.status not in {"completed", "failed", "archived"}:
                job.status = "failed"
                job.step = "Failed"
                job.error_msg = str(exception) if str(exception) else type(exception).__name__
                job.error_trace = einfo_repr(einfo) if einfo else ""
                await session.commit()
                logger.warning(
                    "Job %s marked as failed by task_failure signal: %s",
                    raw_job_id,
                    type(exception).__name__,
                )

    asyncio.run(_mark_failed())


def einfo_repr(einfo: object) -> str:
    """Return a best-effort string representation of a Celery Einfo object."""
    formatted = getattr(einfo, "traceback", None) or repr(einfo)
    return formatted if isinstance(formatted, str) else str(formatted)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    # Ack tasks immediately so the broker does NOT re-queue them when a worker
    # process is killed (e.g. OOM SIGKILL).  With task_acks_late=True the
    # broker re-queues un-acked tasks indefinitely, causing an infinite retry
    # loop.  task_acks_late=False + autoretry_for gives us controlled retries
    # for task-level exceptions only.
    task_acks_late=False,
    # Hard / soft time limits prevent hung tasks from blocking a worker.
    task_time_limit=120,
    task_soft_time_limit=100,
    # Recycle worker child processes before they hit the container OOM limit.
    # 1 GiB is conservative enough to recycle before the ONNX model + image
    # pipeline approaches the 4 GiB mem_limit, but large enough to run a
    # single conversion job. The ONNX model is loaded lazily (not preloaded)
    # so worker startup memory is minimal.
    worker_max_memory_per_child=1 * 1024 * 1024 * 1024,
    beat_schedule={
        "cleanup-expired-jobs-daily": {
            "task": "app.tasks.cleanup.cleanup_expired_jobs",
            "schedule": 60 * 60 * 24,
        },
        "cleanup-stale-jobs": {
            "task": "app.tasks.cleanup.cleanup_stale_jobs",
            "schedule": 60 * 5,
        },
    },
)
