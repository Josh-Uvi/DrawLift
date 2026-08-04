"""Celery task that runs the PDF-to-DXF conversion pipeline."""

# cspell:words autoretry

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, ParamSpec, Protocol, TypeVar, cast
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session
from app.models.job import Job
from app.pipeline import (
    DwgConverterStep,
    DxfWriterStep,
    GlbWriterStep,
    OpenCVPreprocessor,
    PdfParserStep,
    Pipeline,
    PipelineContext,
    PipelineStep,
    SegmenterStep,
    VectorizerStep,
    WallExtruderStep,
)
from app.pipeline.progress import get_progress_publisher
from app.tasks.celery_app import celery_app

LOGGER = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R_co = TypeVar("_R_co", covariant=True)


class _CeleryTask(Protocol[_P, _R_co]):
    """Typed subset of a registered Celery task used by API enqueue sites."""

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R_co:
        """Run the task synchronously with the wrapped function signature."""
        ...

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        """Enqueue the task asynchronously via Celery."""
        ...


class _TypedCeleryApp(Protocol):
    """Typed subset of Celery used to register tasks in this module."""

    def task(
        self, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[_P, _R_co]], _CeleryTask[_P, _R_co]]:
        """Return a decorator that produces a typed Celery task object."""
        ...


def celery_task(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[_P, _R_co]], _CeleryTask[_P, _R_co]]:
    """Return a typed Celery task decorator for Pylance/Pyright.

    Celery's dynamic ``task`` API is typed as partially unknown, which causes
    static analysis to treat decorated functions as untyped. This wrapper keeps
    the runtime behavior unchanged while exposing both the original callable
    signature and Celery task methods such as ``delay`` to type checkers.
    """
    return cast(_TypedCeleryApp, celery_app).task(*args, **kwargs)


def publish_progress(job_id: str, status: str, progress: int, step: str) -> None:
    """Publish a progress event to Redis Pub/Sub.

    Args:
        job_id: The job UUID as a string.
        status: The current job status.
        progress: Progress percentage (0-100).
        step: The current pipeline step name.
    """
    get_progress_publisher().publish(
        job_id=job_id,
        status=status,
        progress=progress,
        step=step,
    )


def portable_storage_path(path: Path | None) -> str | None:
    """Return a storage path that is portable across host and container runtimes.

    Hybrid local development runs the API on the host and the worker in Docker.
    Persisting an absolute container path such as ``/app/storage/...`` would make
    the host API unable to serve completed outputs. When an output lives under
    ``settings.STORAGE_PATH``, persist it relative to that configured storage
    root if the root itself is relative; otherwise keep the absolute path used by
    the all-Docker workflow.
    """
    if path is None:
        return None

    storage_path = Path(get_settings().STORAGE_PATH)
    storage_base = storage_path.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(storage_base)
    except ValueError:
        return str(path)

    return str(storage_path / relative_path)


@celery_task(
    bind=True,
    name="app.tasks.placeholder.process_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=1,
    retry_kwargs={"max_retries": 1, "max_seconds": 30},
)
def process_job(_self: object, job_id: str, config: dict[str, Any]) -> str:
    """Run the real conversion pipeline and persist job progress.

    Args:
        job_id: The job UUID as a string.
        config: The job configuration dict.

    Returns:
        "completed" on success.
    """
    return asyncio.run(_process_job_async(job_id, config))


async def _process_job_async(job_id: str, config: dict[str, Any]) -> str:
    """Async implementation used by the sync Celery task entrypoint."""
    async with async_session() as session:
        result = await session.execute(select(Job).where(Job.id == UUID(job_id)))
        job = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job.status = "processing"
        job.progress = 0
        job.step = "Starting"
        job.error_msg = None
        job.error_trace = None
        await session.commit()
        publish_progress(job_id, "processing", 0, "Starting")
        LOGGER.info(
            "Job %s: starting conversion (mode=%s, output_format=%s)",
            job_id,
            config.get("mode"),
            config.get("output_format"),
        )

        if not job.input_file:
            raise ValueError(f"Job {job_id} has no input file")
        input_path = Path(job.input_file).resolve()
        job_dir = input_path.parent

        context = PipelineContext(
            job_id=job_id,
            input_path=input_path,
            config=config,
            progress_publisher=get_progress_publisher(),
        )

        steps: list[PipelineStep] = [
            PdfParserStep(output_dir=job_dir / "pages"),
            OpenCVPreprocessor(output_dir=job_dir / "preprocessed"),
            SegmenterStep(output_dir=job_dir / "masks"),
            VectorizerStep(),
        ]
        if config.get("mode") == "3d":
            steps.append(WallExtruderStep())
        steps.append(DxfWriterStep(output_path=job_dir / "output" / "output.dxf"))
        if config.get("mode") == "3d":
            steps.append(GlbWriterStep(output_path=job_dir / "output" / "output.glb"))
        if config.get("output_format") in {"dwg", "both"}:
            steps.append(DwgConverterStep(output_path=job_dir / "output" / "output.dwg"))

        pipeline = Pipeline.from_steps(*steps, publish_step_progress=False)

        LOGGER.info("Job %s: running pipeline with %d step(s)", job_id, len(steps))
        try:
            result_context = pipeline.run(context)
        except Exception as exc:
            LOGGER.error("Job %s: pipeline failed: %s", job_id, exc)
            job.status = "failed"
            job.step = "Failed"
            job.error_msg = str(exc)
            job.error_trace = traceback.format_exc()
            await session.commit()
            get_progress_publisher().publish(
                job_id=job_id,
                status="failed",
                progress=job.progress,
                step="Failed",
                message=str(exc),
            )
            raise

        job.status = "completed"
        job.progress = 100
        job.step = "Completed"
        job.output_file = portable_storage_path(result_context.output_path)
        page_count = result_context.metadata.get("page_count")
        if isinstance(page_count, int):
            job.page_count = page_count
        await session.commit()

    LOGGER.info("Job %s: pipeline completed successfully", job_id)
    publish_progress(job_id, "completed", 100, "Completed")
    return "completed"
