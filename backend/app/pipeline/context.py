"""Shared state passed between conversion pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


def _empty_config() -> dict[str, Any]:
    """Return an empty conversion config mapping."""
    return {}


def _empty_path_list() -> list[Path]:
    """Return an empty list of filesystem paths."""
    return []


def _empty_any_list() -> list[Any]:
    """Return an empty list for future pipeline artifacts."""
    return []


def _empty_any_mapping() -> dict[str, Any]:
    """Return an empty mapping for future pipeline artifacts."""
    return {}


class ProgressPublisher(Protocol):
    """Protocol for publishing pipeline progress events."""

    def publish(
        self,
        *,
        job_id: str,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        """Publish a progress update for a pipeline step."""


@dataclass
class PipelineContext:
    """Mutable pipeline state that each conversion step receives and returns.

    The fields intentionally use flexible container types so Phase 2+ steps can
    attach PDF page images, OpenCV arrays, ML masks, CAD primitives, and output
    paths without coupling this foundational package to heavy optional
    dependencies such as NumPy, OpenCV, PyMuPDF, or ezdxf.
    """

    job_id: str
    input_path: Path
    config: dict[str, Any] = field(default_factory=_empty_config)
    page_images: list[Path] = field(default_factory=_empty_path_list)
    preprocessed: list[Any] = field(default_factory=_empty_any_list)
    masks: dict[str, Any] = field(default_factory=_empty_any_mapping)
    primitives: list[Any] = field(default_factory=_empty_any_list)
    output_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=_empty_any_mapping)
    progress_publisher: ProgressPublisher | None = None

    def publish_progress(
        self,
        *,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        """Publish a progress event when a publisher is attached to the context."""
        if self.progress_publisher is None:
            return

        self.progress_publisher.publish(
            job_id=self.job_id,
            status=status,
            progress=progress,
            step=step,
            message=message,
        )
