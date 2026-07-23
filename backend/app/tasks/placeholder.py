"""Placeholder Celery task that simulates the conversion pipeline."""

import json
import time

import redis

from app.core.config import get_settings
from app.tasks.celery_app import celery_app

settings = get_settings()


def publish_progress(job_id: str, status: str, progress: int, step: str) -> None:
    """Publish a progress event to Redis Pub/Sub.

    Args:
        job_id: The job UUID as a string.
        status: The current job status.
        progress: Progress percentage (0-100).
        step: The current pipeline step name.
    """
    r = redis.from_url(settings.REDIS_URL)
    channel = f"job:{job_id}"
    payload = json.dumps(
        {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "step": step,
        }
    )
    r.publish(channel, payload)


@celery_app.task(name="app.tasks.placeholder.process_job")
def process_job(job_id: str, config: dict) -> str:
    """Simulate the conversion pipeline with progress updates.

    Args:
        job_id: The job UUID as a string.
        config: The job configuration dict.

    Returns:
        "completed" on success.
    """
    steps = [
        ("PDF Parsing", 20),
        ("Preprocessing", 35),
        ("Segmentation", 60),
        ("Vectorization", 80),
        ("DXF Writer", 95),
        ("Completed", 100),
    ]

    for step_name, progress in steps:
        time.sleep(2)  # simulate work
        status = "processing" if progress < 100 else "completed"
        publish_progress(job_id, status, progress, step_name)

    return "completed"
