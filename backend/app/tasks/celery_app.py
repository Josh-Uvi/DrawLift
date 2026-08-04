"""Celery application instance with Redis broker and result backend."""

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.pipeline.steps.segmenter import preload_configured_segmentation_model

settings = get_settings()

celery_app = Celery(
    "ai_file_converter",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.placeholder", "app.tasks.cleanup"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    # Re-queue tasks if the worker process is killed (e.g. OOM SIGKILL) so
    # they can be retried on a fresh worker instead of being lost forever.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Hard / soft time limits prevent hung tasks from blocking a worker.
    task_time_limit=600,
    task_soft_time_limit=540,
    # Recycle worker child processes before they hit the container OOM limit.
    # 3 GiB leaves headroom under the 4 GiB mem_limit configured in
    # docker-compose.yml for the ONNX model + image processing pipeline.
    worker_max_memory_per_child=3 * 1024 * 1024 * 1024,
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


@worker_process_init.connect
def preload_worker_models(**_: object) -> None:
    """Load configured ML models once per worker process."""
    preload_configured_segmentation_model()
