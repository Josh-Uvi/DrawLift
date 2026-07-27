"""Tests for Stage 5 job management API helpers."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.v1.jobs import delete_job, retry_job
from app.models.job import Job


class StubResult:
    """Minimal SQLAlchemy result stub."""

    def __init__(self, job: Job | None) -> None:
        self.job = job

    def scalar_one_or_none(self) -> Job | None:
        return self.job


class StubSession:
    """Minimal async session stub for endpoint unit tests."""

    def __init__(self, job: Job | None) -> None:
        self.job = job
        self.deleted: Job | None = None
        self.flushed = False

    async def execute(self, _statement: object) -> StubResult:
        return StubResult(self.job)

    async def flush(self) -> None:
        self.flushed = True

    async def delete(self, job: Job) -> None:
        self.deleted = job


class RecordingTask:
    """Records Celery task enqueue calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def delay(self, job_id: str, config: dict[str, Any]) -> None:
        self.calls.append((job_id, config))


class RecordingStorage:
    """Records storage delete calls and removes the matching temp directory."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.deleted: list[str] = []

    async def delete(self, job_id: str) -> None:
        self.deleted.append(job_id)
        job_dir = self.storage_path / job_id
        if job_dir.exists():
            for child in job_dir.iterdir():
                child.unlink()
            job_dir.rmdir()


def make_job(*, status: str = "failed", storage_path: Path | None = None) -> Job:
    """Create an in-memory job model for management endpoint tests."""
    job_id = uuid.uuid4()
    base = storage_path or Path("/tmp/drawlift-tests")
    return Job(
        id=job_id,
        status=status,
        progress=42,
        step="Failed" if status == "failed" else "Processing",
        config={"mode": "2d", "output_format": "dxf"},
        input_file=str(base / str(job_id) / "input.pdf"),
        output_file=str(base / str(job_id) / "output" / "output.dxf"),
        error_msg="boom" if status == "failed" else None,
        error_trace="Traceback" if status == "failed" else None,
    )


@pytest.mark.asyncio
async def test_retry_job_requeues_failed_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry resets failure fields and enqueues the same job/config again."""
    job = make_job()
    session = StubSession(job)
    task = RecordingTask()
    monkeypatch.setattr("app.api.v1.jobs.process_job", task)

    response = await retry_job(job.id, db=session)  # type: ignore[arg-type]

    assert response.job_id == str(job.id)
    assert job.status == "pending"
    assert job.progress == 0
    assert job.step == "Retry queued"
    assert job.error_msg is None
    assert job.error_trace is None
    assert job.output_file is None
    assert session.flushed is True
    assert task.calls == [(str(job.id), {"mode": "2d", "output_format": "dxf"})]


@pytest.mark.asyncio
async def test_retry_job_rejects_non_failed_job() -> None:
    """Only failed jobs can be retried."""
    job = make_job(status="processing")

    with pytest.raises(HTTPException) as exc_info:
        await retry_job(job.id, db=StubSession(job))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_job_removes_storage_and_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a job removes its local storage directory and DB row."""
    job = make_job(status="completed", storage_path=tmp_path)
    job_dir = tmp_path / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.pdf").write_bytes(b"%PDF")
    storage = RecordingStorage(tmp_path)
    monkeypatch.setattr("app.api.v1.jobs.get_storage", lambda: storage)

    session = StubSession(job)
    response = await delete_job(job.id, db=session)  # type: ignore[arg-type]

    assert response.status_code == 204
    assert not job_dir.exists()
    assert storage.deleted == [str(job.id)]
    assert session.deleted is job
