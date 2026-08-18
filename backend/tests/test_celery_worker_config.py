"""Regression tests for Celery worker memory/OOM safeguards."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, cast

from app.tasks import placeholder
from app.tasks.celery_app import celery_app


def test_worker_does_not_requeue_lost_oom_tasks_forever() -> None:
    """Worker-lost jobs are marked failed instead of redelivered indefinitely."""
    celery_conf = cast(Any, celery_app.conf)

    assert celery_conf.get("task_acks_late") is False
    assert celery_conf.get("task_reject_on_worker_lost") is False
    assert celery_conf.get("worker_concurrency") == 1
    assert celery_conf.get("worker_prefetch_multiplier") == 1


def test_worker_memory_recycle_limit_is_configured_in_kib() -> None:
    """Celery expects worker_max_memory_per_child in KiB, not bytes."""
    celery_conf = cast(Any, celery_app.conf)

    assert celery_conf.get("worker_max_memory_per_child") == 3 * 1024 * 1024


def test_process_job_does_not_autoretry_permanent_value_errors() -> None:
    """Permanent validation/data errors should not create noisy retry loops."""
    dont_autoretry_for = getattr(placeholder.process_job, "dont_autoretry_for")
    assert ValueError in dont_autoretry_for


def test_process_job_disposes_async_engine_before_loop_closes(monkeypatch: Any) -> None:
    """Pooled asyncpg connections are closed inside the same asyncio.run loop."""
    calls: list[str] = []

    async def fake_process_job_async(job_id: str, config: dict[str, Any]) -> str:
        calls.append(f"process:{job_id}:{config['mode']}")
        return "completed"

    class FakeEngine:
        async def dispose(self) -> None:
            calls.append("dispose")

    monkeypatch.setattr(placeholder, "_process_job_async", fake_process_job_async)
    monkeypatch.setattr(placeholder, "engine", FakeEngine())

    run_job = cast(
        Callable[[str, dict[str, Any]], Coroutine[Any, Any, str]],
        getattr(placeholder, "_process_job_and_dispose_engine"),
    )

    result = asyncio.run(run_job("job-123", {"mode": "2d"}))

    assert result == "completed"
    assert calls == ["process:job-123:2d", "dispose"]


def test_process_job_disposes_async_engine_after_failure(monkeypatch: Any) -> None:
    """The engine is disposed even when processing raises an exception."""
    calls: list[str] = []

    async def fake_process_job_async(job_id: str, config: dict[str, Any]) -> str:
        calls.append("process")
        raise RuntimeError("boom")

    class FakeEngine:
        async def dispose(self) -> None:
            calls.append("dispose")

    monkeypatch.setattr(placeholder, "_process_job_async", fake_process_job_async)
    monkeypatch.setattr(placeholder, "engine", FakeEngine())

    run_job = cast(
        Callable[[str, dict[str, Any]], Coroutine[Any, Any, str]],
        getattr(placeholder, "_process_job_and_dispose_engine"),
    )

    try:
        asyncio.run(run_job("job-123", {}))
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("expected RuntimeError")

    assert calls == ["process", "dispose"]
