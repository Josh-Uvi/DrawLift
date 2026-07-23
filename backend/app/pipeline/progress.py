"""Redis Pub/Sub progress publishing for conversion pipelines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol, cast

import redis

from app.core.config import get_settings


class RedisPublishClient(Protocol):
    """Minimal Redis client interface needed by the progress publisher."""

    def publish(self, channel: str, message: str) -> Any:
        """Publish a message to a Redis Pub/Sub channel."""


def _empty_metadata() -> dict[str, Any]:
    """Return an empty event metadata mapping."""
    return {}


@dataclass(frozen=True)
class ProgressEvent:
    """Serializable progress update emitted by pipeline steps."""

    job_id: str
    status: str
    progress: int
    step: str
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to the JSON payload consumed by the SSE endpoint."""
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "step": self.step,
        }
        if self.message is not None:
            payload["message"] = self.message
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def to_json(self) -> str:
        """Serialize the progress event as compact JSON."""
        return json.dumps(self.to_dict(), separators=(",", ":"))


@dataclass
class RedisProgressPublisher:
    """Publish pipeline progress events to Redis Pub/Sub channels."""

    redis_url: str | None = None
    redis_client: RedisPublishClient | None = None
    channel_prefix: str = "job"

    def __post_init__(self) -> None:
        """Create a Redis client when one was not injected by the caller."""
        if self.redis_client is None:
            url = self.redis_url or get_settings().REDIS_URL
            self.redis_client = cast(RedisPublishClient, redis.from_url(url))

    def publish(
        self,
        *,
        job_id: str,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        """Publish a progress event to the job-specific Redis channel."""
        event = ProgressEvent(
            job_id=job_id,
            status=status,
            progress=self._normalize_progress(progress),
            step=step,
            message=message,
        )
        redis_client = self.redis_client
        if redis_client is None:
            raise RuntimeError("Redis progress publisher was not initialised")

        redis_client.publish(self.channel_for(job_id), event.to_json())

    def channel_for(self, job_id: str) -> str:
        """Return the Redis Pub/Sub channel name for a job."""
        return f"{self.channel_prefix}:{job_id}"

    @staticmethod
    def _normalize_progress(progress: int) -> int:
        """Clamp progress into the 0-100 range expected by API clients."""
        return max(0, min(progress, 100))


@lru_cache
def get_progress_publisher() -> RedisProgressPublisher:
    """Return a cached Redis-backed progress publisher for worker code."""
    return RedisProgressPublisher()
