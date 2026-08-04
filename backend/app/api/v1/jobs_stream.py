"""SSE endpoint for real-time job progress updates."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

import redis.asyncio as aioredis
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


class _ProgressPubSub(Protocol):
    """Typed subset of the redis.asyncio Pub/Sub API used by this endpoint.

    redis-py's asyncio surface is only partially annotated, so the stream
    casts to this protocol to keep strict type checking precise.
    """

    async def subscribe(self, channel: str) -> object:
        """Subscribe to a Redis Pub/Sub channel."""
        ...

    async def unsubscribe(self, channel: str) -> object:
        """Unsubscribe from a Redis Pub/Sub channel."""
        ...

    async def get_message(
        self, *, ignore_subscribe_messages: bool, timeout: float | None
    ) -> dict[str, Any] | None:
        """Return the next pending Pub/Sub message, if any."""
        ...


class _ProgressRedis(Protocol):
    """Typed subset of the redis.asyncio client API used by this endpoint."""

    def pubsub(self) -> _ProgressPubSub:
        """Return a Pub/Sub handle."""
        ...

    async def close(self) -> None:
        """Close the client and release its connection pool."""
        ...


def _open_redis() -> _ProgressRedis:
    """Create the Redis client used for progress streaming."""
    client = cast(Any, aioredis).from_url(settings.REDIS_URL)
    return cast(_ProgressRedis, client)


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str) -> EventSourceResponse:
    """Stream real-time progress updates for a job via SSE.

    Subscribes to Redis Pub/Sub channel for the job and forwards
    messages to the client as Server-Sent Events.

    Args:
        job_id: The job UUID as a string.

    Returns:
        EventSourceResponse streaming progress events.
    """
    channel = f"job:{job_id}"

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        """Generate SSE events from Redis Pub/Sub."""
        r = _open_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    raw = message["data"]
                    if isinstance(raw, bytes):
                        data = raw.decode("utf-8")
                    elif isinstance(raw, str):
                        data = raw
                    else:
                        data = str(raw)
                    yield {"event": "progress", "data": data}
                    try:
                        payload: dict[str, Any] = json.loads(data)
                        if payload.get("status") in ("completed", "failed"):
                            break
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
            await r.close()

    return EventSourceResponse(event_generator())
