"""Tests for the OpenCV preprocessing pipeline step."""

from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

from app.pipeline import OpenCVPreprocessor, PdfParserStep, Pipeline, PipelineContext


class RecordingPublisher:
    """In-memory progress publisher for preprocessor tests."""

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
        """Record a progress event."""
        self.events.append(
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "step": step,
                "message": message,
            }
        )


def create_architectural_drawing(path: Path) -> Path:
    """Create a synthetic floor-plan-like page image."""
    image = np.full((240, 320, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (25, 25), (295, 215), (0, 0, 0), thickness=4)
    cv2.line(image, (160, 25), (160, 150), (0, 0, 0), thickness=4)
    cv2.line(image, (25, 120), (120, 120), (0, 0, 0), thickness=4)
    cv2.line(image, (200, 120), (295, 120), (0, 0, 0), thickness=4)
    cv2.putText(image, "ROOM", (45, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    assert cv2.imwrite(str(path), image)
    return path


def create_sample_pdf(path: Path) -> Path:
    """Create a one-page architectural PDF fixture."""
    document = fitz.open()
    page = document.new_page(width=240, height=180)
    page.draw_rect(fitz.Rect(15, 15, 225, 165), color=(0, 0, 0), width=3)
    page.draw_line(fitz.Point(120, 15), fitz.Point(120, 120), color=(0, 0, 0), width=3)
    page.insert_text((35, 70), "ROOM")
    document.save(path)
    document.close()
    return path


def estimate_dominant_angle(image: np.ndarray) -> float:
    """Return the normalized minimum-area rectangle angle for foreground pixels."""
    foreground = cv2.findNonZero(image)
    assert foreground is not None
    raw_angle = float(cv2.minAreaRect(foreground)[-1])
    return OpenCVPreprocessor._normalise_deskew_angle(raw_angle)


def test_preprocessor_converts_blurs_thresholds_and_saves_preview(tmp_path: Path) -> None:
    """The step produces a grayscale binary array and a PNG preview."""
    page_image = create_architectural_drawing(tmp_path / "page_0001.png")
    output_dir = tmp_path / "preprocessed"
    context = PipelineContext(
        job_id="job-456",
        input_path=tmp_path / "input.pdf",
        page_images=[page_image],
    )

    result = OpenCVPreprocessor(output_dir=output_dir).execute(context)

    assert result is context
    assert len(result.preprocessed) == 1
    processed = result.preprocessed[0]
    assert isinstance(processed, np.ndarray)
    assert processed.ndim == 2
    assert set(np.unique(processed).tolist()).issubset({0, 255})
    assert np.any(processed == 0)
    assert np.any(processed == 255)

    preview_path = output_dir / "preprocessed_0001.png"
    assert result.metadata["preprocessed_count"] == 1
    assert result.metadata["preprocessed_image_dir"] == output_dir
    assert result.metadata["preprocessed_image_paths"] == [preview_path]
    assert preview_path.read_bytes().startswith(b"\x89PNG")


def test_preprocessor_corrects_skew() -> None:
    """Deskew reduces a synthetic drawing's dominant angle."""
    drawing = np.zeros((300, 300), dtype=np.uint8)
    cv2.rectangle(drawing, (50, 100), (250, 200), 255, thickness=-1)
    rotation = cv2.getRotationMatrix2D((150, 150), 8.0, 1.0)
    skewed = cv2.warpAffine(drawing, rotation, (300, 300), flags=cv2.INTER_NEAREST)

    deskewed = OpenCVPreprocessor._deskew(skewed)

    assert abs(estimate_dominant_angle(skewed)) >= 7.0
    assert abs(estimate_dominant_angle(deskewed)) < 0.5


def test_preprocessor_publishes_thirty_five_percent_progress(tmp_path: Path) -> None:
    """Execution reports the US-014 35 percent progress milestone."""
    page_image = create_architectural_drawing(tmp_path / "page_0001.png")
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-456",
        input_path=tmp_path / "input.pdf",
        page_images=[page_image],
        progress_publisher=publisher,
    )

    OpenCVPreprocessor(output_dir=tmp_path / "preprocessed").execute(context)

    assert publisher.events == [
        {
            "job_id": "job-456",
            "status": "processing",
            "progress": 35,
            "step": "OpenCV Preprocessing",
            "message": "Preprocessed 1 page image(s)",
        }
    ]


def test_parser_and_preprocessor_run_as_pipeline(tmp_path: Path) -> None:
    """The step consumes page images produced by the preceding PDF parser."""
    input_pdf = create_sample_pdf(tmp_path / "floorplan.pdf")
    context = PipelineContext(job_id="job-456", input_path=input_pdf, config={"dpi": 72})
    pipeline = Pipeline.from_steps(
        PdfParserStep(output_dir=tmp_path / "pages"),
        OpenCVPreprocessor(output_dir=tmp_path / "preprocessed"),
        publish_step_progress=False,
    )

    result = pipeline.run(context)

    assert len(result.page_images) == 1
    assert len(result.preprocessed) == 1
    assert result.preprocessed[0].ndim == 2


def test_preprocessor_requires_page_images(tmp_path: Path) -> None:
    """The step fails clearly when PDF parsing has not run."""
    context = PipelineContext(job_id="job-456", input_path=tmp_path / "input.pdf")

    with pytest.raises(ValueError, match="requires page_images"):
        OpenCVPreprocessor().execute(context)


def test_preprocessor_rejects_unreadable_page_image(tmp_path: Path) -> None:
    """The step identifies the page path when OpenCV cannot read it."""
    missing_image = tmp_path / "missing.png"
    context = PipelineContext(
        job_id="job-456",
        input_path=tmp_path / "input.pdf",
        page_images=[missing_image],
    )

    with pytest.raises(FileNotFoundError, match=str(missing_image)):
        OpenCVPreprocessor().execute(context)


def test_preprocessor_uses_configured_output_directory(tmp_path: Path) -> None:
    """The context configuration can select the preview output directory."""
    page_image = create_architectural_drawing(tmp_path / "page_0001.png")
    configured_dir = tmp_path / "configured"
    context = PipelineContext(
        job_id="job-456",
        input_path=tmp_path / "input.pdf",
        page_images=[page_image],
        config={"preprocessed_image_dir": configured_dir},
    )

    result = OpenCVPreprocessor().execute(context)

    assert result.metadata["preprocessed_image_dir"] == configured_dir
    assert result.metadata["preprocessed_image_paths"] == [configured_dir / "preprocessed_0001.png"]
