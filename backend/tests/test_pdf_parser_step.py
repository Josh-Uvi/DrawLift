"""Tests for PyMuPDF PDF page extraction."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.pipeline import PdfParserStep, PipelineContext


class RecordingPublisher:
    """In-memory progress publisher for parser step tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish(
        self,
        *,
        job_id: str,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        self.events.append(
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "step": step,
                "message": message,
            }
        )


def create_sample_pdf(path: Path, *, pages: int = 1, size: tuple[int, int] = (72, 72)) -> Path:
    """Create a small PDF fixture with the requested number of pages."""
    document = fitz.open()
    for page_number in range(1, pages + 1):
        page = document.new_page(width=size[0], height=size[1])
        page.insert_text((10, 20), f"Page {page_number}")
    document.save(path)
    document.close()
    return path


def test_pdf_parser_extracts_each_page_as_png(tmp_path: Path) -> None:
    """PdfParserStep renders every PDF page and records image paths on the context."""
    input_pdf = create_sample_pdf(tmp_path / "floorplan.pdf", pages=2)
    output_dir = tmp_path / "extracted"
    context = PipelineContext(job_id="job-123", input_path=input_pdf, config={"dpi": 72})

    result = PdfParserStep(output_dir=output_dir).execute(context)

    assert result is context
    assert result.page_images == [output_dir / "page_0001.png", output_dir / "page_0002.png"]
    assert result.metadata["page_count"] == 2
    assert result.metadata["pdf_dpi"] == 72
    assert result.metadata["page_image_dir"] == output_dir
    for image_path in result.page_images:
        assert image_path.exists()
        assert image_path.suffix == ".png"
        assert image_path.read_bytes().startswith(b"\x89PNG")


def test_pdf_parser_uses_configurable_dpi(tmp_path: Path) -> None:
    """The parser honors the configured DPI when rendering pages."""
    input_pdf = create_sample_pdf(tmp_path / "floorplan.pdf", size=(72, 72))
    context = PipelineContext(job_id="job-123", input_path=input_pdf, config={"dpi": 144})

    result = PdfParserStep(output_dir=tmp_path / "pages").execute(context)

    pixmap = fitz.Pixmap(result.page_images[0])
    assert pixmap.width == 144
    assert pixmap.height == 144


def test_pdf_parser_publishes_twenty_percent_progress(tmp_path: Path) -> None:
    """Step execution reports the US-013 20% progress milestone."""
    input_pdf = create_sample_pdf(tmp_path / "floorplan.pdf")
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-123",
        input_path=input_pdf,
        progress_publisher=publisher,
    )

    PdfParserStep(output_dir=tmp_path / "pages").execute(context)

    assert publisher.events == [
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 20,
            "step": "PDF Parsing",
            "message": "Extracted 1 page image(s)",
        }
    ]


def test_pdf_parser_rejects_invalid_dpi(tmp_path: Path) -> None:
    """Invalid DPI config fails fast with a clear validation error."""
    input_pdf = create_sample_pdf(tmp_path / "floorplan.pdf")
    context = PipelineContext(job_id="job-123", input_path=input_pdf, config={"dpi": 0})

    with pytest.raises(ValueError, match="greater than zero"):
        PdfParserStep(output_dir=tmp_path / "pages").execute(context)
