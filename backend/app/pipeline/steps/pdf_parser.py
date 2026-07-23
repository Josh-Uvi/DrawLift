"""PyMuPDF-powered PDF page extraction step."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep

DEFAULT_DPI = 300
PDF_POINTS_PER_INCH = 72


class PdfParserStep(PipelineStep):
    """Render every PDF page to a PNG image and attach paths to the context."""

    name = "PDF Parsing"
    progress = 20

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Create a parser step with an optional output directory override."""
        self.output_dir = Path(output_dir) if output_dir is not None else None

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract all pages from ``context.input_path`` as PNGs."""
        dpi = self._resolve_dpi(context.config.get("dpi", DEFAULT_DPI))
        page_output_dir = self._resolve_output_dir(context)
        page_output_dir.mkdir(parents=True, exist_ok=True)

        page_images: list[Path] = []
        zoom = dpi / PDF_POINTS_PER_INCH
        matrix = fitz.Matrix(zoom, zoom)

        with fitz.open(context.input_path) as document:
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                image_path = page_output_dir / f"page_{page_index + 1:04d}.png"
                pixmap.save(image_path)
                page_images.append(image_path)

        context.page_images = page_images
        context.metadata["page_count"] = len(page_images)
        context.metadata["pdf_dpi"] = dpi
        context.metadata["page_image_dir"] = page_output_dir

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Extracted {len(page_images)} page image(s)",
        )
        return context

    def _resolve_output_dir(self, context: PipelineContext) -> Path:
        """Resolve where extracted page images should be written."""
        configured_dir = context.config.get("page_image_dir") or context.config.get(
            "page_images_dir"
        )
        if self.output_dir is not None:
            return self.output_dir
        if configured_dir is not None:
            return Path(str(configured_dir))
        return context.input_path.parent / context.job_id / "pages"

    @staticmethod
    def _resolve_dpi(value: Any) -> int:
        """Return a positive integer DPI, falling back to the default when absent."""
        try:
            dpi = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("PDF parser DPI must be an integer") from exc

        if dpi <= 0:
            raise ValueError("PDF parser DPI must be greater than zero")
        return dpi
