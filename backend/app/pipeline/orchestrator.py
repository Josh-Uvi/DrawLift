"""Pipeline orchestration for ordered conversion steps."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep


@dataclass(frozen=True)
class Pipeline:
    """Run a sequence of pluggable pipeline steps in order."""

    steps: Sequence[PipelineStep]
    publish_step_progress: bool = True

    def run(self, context: PipelineContext) -> PipelineContext:
        """Execute configured steps sequentially and return the final context."""
        current_context = context
        total_steps = len(self.steps)

        for index, step in enumerate(self.steps, start=1):
            if self.publish_step_progress:
                step.publish_progress(
                    current_context,
                    progress=self._calculate_progress(index - 1, total_steps),
                    message="started",
                )

            current_context = step.execute(current_context)

            if self.publish_step_progress:
                step.publish_progress(
                    current_context,
                    progress=self._resolve_step_progress(step, index, total_steps),
                    message="completed",
                )

        return current_context

    @classmethod
    def from_steps(cls, *steps: PipelineStep, publish_step_progress: bool = True) -> Self:
        """Build a pipeline from positional steps for concise call sites."""
        return cls(steps=steps, publish_step_progress=publish_step_progress)

    @staticmethod
    def _calculate_progress(completed_steps: int, total_steps: int) -> int:
        """Calculate percentage progress from completed and total step counts."""
        if total_steps == 0:
            return 0
        return round((completed_steps / total_steps) * 100)

    def _resolve_step_progress(self, step: PipelineStep, index: int, total_steps: int) -> int:
        """Prefer explicit step progress; otherwise derive progress from position."""
        if step.progress is not None:
            return step.progress
        return self._calculate_progress(index, total_steps)


def create_pipeline(*steps: PipelineStep, publish_step_progress: bool = True) -> Pipeline:
    """Factory helper for constructing pipelines from individual steps."""
    return Pipeline.from_steps(*steps, publish_step_progress=publish_step_progress)
