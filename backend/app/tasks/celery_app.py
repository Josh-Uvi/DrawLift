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
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)

celery_app.autodiscover_tasks(["app.tasks"])


@worker_process_init.connect
def preload_worker_models(**_: object) -> None:
    """Load configured ML models once per worker process."""
    preload_configured_segmentation_model()
