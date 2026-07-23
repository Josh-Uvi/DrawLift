"""Tests for Redis-backed pipeline progress publishing."""

import json

from app.pipeline.progress import ProgressEvent, RedisProgressPublisher


class FakeRedisClient:
    """In-memory Redis-like client that records publish calls."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> int:
        self.messages.append((channel, message))
        return 1


def test_progress_event_serializes_required_fields() -> None:
    """ProgressEvent serializes to the SSE-compatible payload shape."""
    event = ProgressEvent(job_id="job-123", status="processing", progress=42, step="parse")

    assert json.loads(event.to_json()) == {
        "job_id": "job-123",
        "status": "processing",
        "progress": 42,
        "step": "parse",
    }


def test_progress_event_includes_optional_message_and_metadata() -> None:
    """Optional progress details are included only when supplied."""
    event = ProgressEvent(
        job_id="job-123",
        status="processing",
        progress=42,
        step="parse",
        message="completed",
        metadata={"page_count": 2},
    )

    assert json.loads(event.to_json()) == {
        "job_id": "job-123",
        "status": "processing",
        "progress": 42,
        "step": "parse",
        "message": "completed",
        "metadata": {"page_count": 2},
    }


def test_redis_progress_publisher_publishes_to_job_channel() -> None:
    """RedisProgressPublisher emits JSON progress events to job:{job_id}."""
    redis_client = FakeRedisClient()
    publisher = RedisProgressPublisher(redis_client=redis_client)

    publisher.publish(
        job_id="job-123",
        status="processing",
        progress=20,
        step="PDF Parsing",
    )

    assert len(redis_client.messages) == 1
    channel, message = redis_client.messages[0]
    assert channel == "job:job-123"
    assert json.loads(message) == {
        "job_id": "job-123",
        "status": "processing",
        "progress": 20,
        "step": "PDF Parsing",
    }


def test_redis_progress_publisher_clamps_progress_range() -> None:
    """Published progress is clamped to the API's 0-100 contract."""
    redis_client = FakeRedisClient()
    publisher = RedisProgressPublisher(redis_client=redis_client)

    publisher.publish(job_id="job-123", status="processing", progress=150, step="parse")
    publisher.publish(job_id="job-123", status="processing", progress=-10, step="parse")

    assert json.loads(redis_client.messages[0][1])["progress"] == 100
    assert json.loads(redis_client.messages[1][1])["progress"] == 0
