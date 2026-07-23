"""Base interfaces for pluggable conversion pipeline steps."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.pipeline.context import PipelineContext


class PipelineStep(ABC):
    """Abstract base class for a single conversion pipeline step."""

    name: str
    progress: int | None = None

    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute the step and return the updated pipeline context."""

    def publish_progress(
        self,
        context: PipelineContext,
        *,
        status: str = "processing",
        progress: int | None = None,
        message: str | None = None,
    ) -> None:
        """Publish this step's progress through the context publisher, if present."""
        resolved_progress = (
            self.progress if progress is None and self.progress is not None else progress
        )
        context.publish_progress(
            status=status,
            progress=resolved_progress or 0,
            step=self.name,
            message=message,
        )
