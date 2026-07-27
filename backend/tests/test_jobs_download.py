"""Tests for generated DXF download helpers."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.v1.jobs import _resolve_download_path, download_job_output
from app.models.job import Job


def create_job(
    storage_path: Path,
    *,
    status: str = "completed",
    with_glb: bool = False,
) -> Job:
    """Create an in-memory job model with a valid output file."""
    job_id = uuid.uuid4()
    output_path = storage_path / str(job_id) / "output" / "output.dxf"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("0\nSECTION\n2\nEOF\n", encoding="utf-8")
    if with_glb:
        (output_path.parent / "output.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    return Job(
        id=job_id,
        status=status,
        progress=100,
        config={},
        input_file=str(storage_path / str(job_id) / "input.pdf"),
        output_file=str(output_path),
    )


def test_resolve_download_path_allows_completed_job_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Download resolution serves only a trusted DXF under the job storage directory."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    job = create_job(tmp_path)

    assert _resolve_download_path(job) == Path(job.output_file).resolve()


def test_resolve_download_path_rejects_path_outside_job_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path traversal / externally persisted output paths are rejected."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    outside = tmp_path.parent / "outside.dxf"
    outside.write_text("DXF", encoding="utf-8")
    job = create_job(tmp_path)
    job.output_file = str(outside)

    with pytest.raises(HTTPException) as exc_info:
        _resolve_download_path(job)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_download_endpoint_returns_dxf_content_disposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The download endpoint returns a FileResponse with a DXF attachment filename."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    job = create_job(tmp_path)

    class StubResult:
        def scalar_one_or_none(self) -> Job:
            return job

    class StubSession:
        async def execute(self, _statement: object) -> StubResult:
            return StubResult()

    response = await download_job_output(job.id, db=StubSession())  # type: ignore[arg-type]

    assert response.media_type == "application/dxf"
    assert response.filename == f"drawlift-{job.id}.dxf"
    assert "attachment" in response.headers["content-disposition"]
    assert f"drawlift-{job.id}.dxf" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_endpoint_rejects_incomplete_jobs(tmp_path: Path) -> None:
    """A job must be completed before its output can be downloaded."""
    job = create_job(tmp_path, status="processing")

    class StubResult:
        def scalar_one_or_none(self) -> Job:
            return job

    class StubSession:
        async def execute(self, _statement: object) -> StubResult:
            return StubResult()

    with pytest.raises(HTTPException) as exc_info:
        await download_job_output(job.id, db=StubSession())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409


def test_resolve_download_path_serves_glb_alongside_dxf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The GLB output is served from the same trusted job output directory."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    job = create_job(tmp_path, with_glb=True)

    resolved = _resolve_download_path(job, download_format="glb")

    assert resolved.suffix == ".glb"
    assert resolved.is_file()


def test_resolve_download_path_missing_glb_returns_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requesting GLB for a 2D job without a GLB output returns 404."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    job = create_job(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        _resolve_download_path(job, download_format="glb")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_download_endpoint_returns_glb_content_disposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The download endpoint serves GLB with a model/gltf-binary media type."""
    monkeypatch.setattr("app.api.v1.jobs.settings.STORAGE_PATH", str(tmp_path))
    job = create_job(tmp_path, with_glb=True)

    class StubResult:
        def scalar_one_or_none(self) -> Job:
            return job

    class StubSession:
        async def execute(self, _statement: object) -> StubResult:
            return StubResult()

    response = await download_job_output(
        job.id,
        format="glb",
        db=StubSession(),  # type: ignore[arg-type]
    )

    assert response.media_type == "model/gltf-binary"
    assert response.filename == f"drawlift-{job.id}.glb"
    assert f"drawlift-{job.id}.glb" in response.headers["content-disposition"]
