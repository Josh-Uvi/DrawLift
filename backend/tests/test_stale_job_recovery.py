"""Tests for the stale-job recovery cleanup task."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import MonkeyPatch

from app.tasks import cleanup


def _make_job(
    *,
    job_id: uuid.UUID | None = None,
    status: str = "processing",
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    """Create a lightweight job-like object for testing."""
    return SimpleNamespace(
        id=job_id or uuid.uuid4(),
        status=status,
        step="Running",
        progress=50,
        updated_at=updated_at or datetime.now(UTC),
        error_msg=None,
    )


@pytest.mark.asyncio
async def test_cleanup_stale_marks_timed_out_processing_jobs(
    monkeypatch: MonkeyPatch,
) -> None:
    """Jobs in 'processing' older than the timeout are marked 'failed'."""
    cutoff_time = datetime(2026, 1, 1, tzinfo=UTC)
    stale_job = _make_job(updated_at=cutoff_time - timedelta(seconds=400))

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [stale_job]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        cleanup,
        "get_settings",
        lambda: SimpleNamespace(
            JOB_STALE_TIMEOUT_SECONDS=300,
            STORAGE_TTL_DAYS=7,
            STORAGE_PATH="./storage",
        ),
    )

    with patch.object(cleanup, "async_session", return_value=mock_session_cm):
        count = await cleanup._cleanup_stale_jobs_async(now=cutoff_time)

    assert count == 1
    assert stale_job.status == "failed"
    assert stale_job.step == "Failed"
    assert "timed out" in (stale_job.error_msg or "").lower()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_stale_skips_recent_processing_jobs(
    monkeypatch: MonkeyPatch,
) -> None:
    """Jobs still within the timeout window are left untouched."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    recent_job = _make_job(updated_at=now - timedelta(seconds=60))

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        cleanup,
        "get_settings",
        lambda: SimpleNamespace(
            JOB_STALE_TIMEOUT_SECONDS=300,
            STORAGE_TTL_DAYS=7,
            STORAGE_PATH="./storage",
        ),
    )

    with patch.object(cleanup, "async_session", return_value=mock_session_cm):
        count = await cleanup._cleanup_stale_jobs_async(now=now)

    assert count == 0
    assert recent_job.status == "processing"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_stale_does_not_touch_completed_jobs(
    monkeypatch: MonkeyPatch,
) -> None:
    """Completed/failed/archived jobs are never picked up by the stale sweeper."""
    now = datetime(2026, 1, 1, tzinfo=UTC)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        cleanup,
        "get_settings",
        lambda: SimpleNamespace(
            JOB_STALE_TIMEOUT_SECONDS=300,
            STORAGE_TTL_DAYS=7,
            STORAGE_PATH="./storage",
        ),
    )

    with patch.object(cleanup, "async_session", return_value=mock_session_cm):
        count = await cleanup._cleanup_stale_jobs_async(now=now)

    assert count == 0
    mock_session.commit.assert_awaited_once()
