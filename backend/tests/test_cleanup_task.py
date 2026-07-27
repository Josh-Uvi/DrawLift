"""Tests for file lifecycle cleanup helpers."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.models.job import Job
from app.tasks.cleanup import _delete_job_files


def test_delete_job_files_removes_only_contained_job_directory(tmp_path: Path) -> None:
    """Cleanup deletes the trusted job directory under the configured storage root."""
    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    (job_dir / "input.pdf").write_bytes(b"%PDF")
    job = Job(id=job_id, status="completed", progress=100, config={}, input_file=str(job_dir))

    _delete_job_files(storage_base=tmp_path.resolve(), job=job)

    assert not job_dir.exists()
