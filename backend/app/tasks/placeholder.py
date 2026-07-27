"""Celery task that runs the PDF-to-DXF conversion pipeline."""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

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


@celery_app.task(
    bind=True,
    name="app.tasks.placeholder.process_job",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
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

        try:
            result_context = pipeline.run(context)
        except Exception as exc:
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
        job.output_file = str(result_context.output_path) if result_context.output_path else None
        page_count = result_context.metadata.get("page_count")
        if isinstance(page_count, int):
            job.page_count = page_count
        await session.commit()

    publish_progress(job_id, "completed", 100, "Completed")
    return "completed"
