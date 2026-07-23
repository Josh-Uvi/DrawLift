"""SSE endpoint for real-time job progress updates."""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


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

    async def event_generator():
        """Generate SSE events from Redis Pub/Sub."""
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield {"event": "progress", "data": data}
                    try:
                        payload = json.loads(data)
                        if payload.get("status") == "completed":
                            break
                    except (json.JSONDecodeError, KeyError):
                        pass
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
            await r.close()

    return EventSourceResponse(event_generator())
