"""Integration tests for the ML segmenter wiring with the real model (US-030).

Covers T-099 (ONNX tensor shapes match ``OnnxSemanticSegmenter``) and T-100
(end-to-end ML segmentation of a sample floor-plan PDF through the actual
pipeline steps and the bundled ``backend/models/semantic_segmenter.onnx``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import fitz  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
import pytest

from app.core.config import get_settings
from app.pipeline import (
    OpenCVPreprocessor,
    PdfParserStep,
    Pipeline,
    PipelineContext,
    SegmenterStep,
)
from app.pipeline.steps.segmenter import MASK_LABELS, OnnxSemanticSegmenter

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_MODEL_PATH = BACKEND_DIR / "models" / "semantic_segmenter.onnx"


@pytest.fixture
def ml_segmenter_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Point the settings-driven segmenter at the bundled model."""
    get_settings.cache_clear()
    monkeypatch.setenv("SEGMENTER_MODEL_PATH", str(BUNDLED_MODEL_PATH))
    monkeypatch.delenv("SEGMENTER_MODEL_URL", raising=False)
    yield monkeypatch
    get_settings.cache_clear()


def create_floor_plan_pdf(path: Path) -> Path:
    """Draw a simple architectural floor plan (walls + partitions) into a PDF."""
    document = fitz.open()
    page = document.new_page(width=320, height=240)
    ink = (0, 0, 0)
    # Exterior walls.
    page.draw_rect(fitz.Rect(40, 30, 280, 210), color=ink, width=4)
    # Interior partitions.
    page.draw_line(fitz.Point(160, 30), fitz.Point(160, 130), color=ink, width=4)
    page.draw_line(fitz.Point(40, 120), fitz.Point(120, 120), color=ink, width=4)
    page.draw_line(fitz.Point(200, 120), fitz.Point(280, 120), color=ink, width=4)
    document.save(path)
    document.close()
    return path


def test_bundled_model_tensor_shapes_match_segmenter_contract() -> None:
    """T-099: declared tensors align with the single-channel NCHW segmenter."""
    import onnxruntime as ort

    session = ort.InferenceSession(str(BUNDLED_MODEL_PATH), providers=["CPUExecutionProvider"])

    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0]

    assert input_meta.type == "tensor(float)"
    assert len(input_meta.shape) == 4, "segmenter feeds NCHW tensors"
    assert input_meta.shape[1] == 1, "segmenter feeds single-channel grayscale"
    assert len(output_meta.shape) == 4
    assert output_meta.shape[1] == len(MASK_LABELS) + 1, "background + five labels"


def test_segmenter_resolves_model_and_input_size_from_settings(
    ml_segmenter_env: pytest.MonkeyPatch,
) -> None:
    """T-099: a default-configured segmenter consumes env-driven settings."""
    ml_segmenter_env.setenv("SEGMENTER_MODEL_INPUT_SIZE", "160")
    get_settings.cache_clear()

    segmenter = OnnxSemanticSegmenter()

    assert segmenter.input_size == (160, 160)
    image = np.zeros((120, 160), dtype=np.uint8)
    image[20:100, 20:140] = 255

    masks = segmenter.segment([image])

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert masks[label][0].shape == (120, 160)


def test_ml_segmenter_produces_valid_output_for_sample_floor_plan_pdf(
    tmp_path: Path, ml_segmenter_env: pytest.MonkeyPatch
) -> None:
    """T-100/AC: PDF → parse → preprocess → ML segmentation emits 5-class masks."""
    pdf_path = create_floor_plan_pdf(tmp_path / "floorplan.pdf")
    context = PipelineContext(
        job_id="job-us030",
        input_path=pdf_path,
        config={"segmenter": "ml", "dpi": 72},
    )
    pipeline = Pipeline.from_steps(
        PdfParserStep(),
        OpenCVPreprocessor(),
        SegmenterStep(),
        publish_step_progress=False,
    )

    result = pipeline.run(context)

    assert result.metadata["segmenter"] == "ml"
    assert result.metadata["segmentation_labels"] == list(MASK_LABELS)
    assert result.metadata["segmentation_count"] == 1
    assert set(result.masks) == set(MASK_LABELS)

    page_shape = (240, 320)
    for label in MASK_LABELS:
        assert len(result.masks[label]) == 1
        assert result.masks[label][0].shape == page_shape
        assert result.masks[label][0].dtype == np.uint8

    # Wall strokes in the fixture must be detected by the ML path.
    assert np.count_nonzero(result.masks["walls"][0]) > 0
    assert np.count_nonzero(result.masks["rooms"][0]) > 0

    mask_dir = Path(str(result.metadata["segmentation_mask_dir"]))
    for label in MASK_LABELS:
        assert (mask_dir / label / f"page_0001_{label}.png").is_file()


def test_ml_segmenter_processes_multi_page_floor_plan_pdf(
    tmp_path: Path, ml_segmenter_env: pytest.MonkeyPatch
) -> None:
    """The env-configured ML path handles every page of a multi-page PDF."""
    pdf_path = tmp_path / "floorplan_multi.pdf"
    document = fitz.open()
    for _ in range(2):
        page = document.new_page(width=320, height=240)
        page.draw_rect(fitz.Rect(40, 30, 280, 210), color=(0, 0, 0), width=4)
        page.draw_line(fitz.Point(160, 30), fitz.Point(160, 210), color=(0, 0, 0), width=4)
    document.save(pdf_path)
    document.close()

    context = PipelineContext(
        job_id="job-us030-multi",
        input_path=pdf_path,
        config={"segmenter": "ml", "dpi": 72},
    )
    pipeline = Pipeline.from_steps(
        PdfParserStep(),
        OpenCVPreprocessor(),
        SegmenterStep(),
        publish_step_progress=False,
    )

    result = pipeline.run(context)

    assert result.metadata["segmentation_count"] == 2
    for label in MASK_LABELS:
        assert len(result.masks[label]) == 2
    assert np.count_nonzero(result.masks["walls"][0]) > 0
    assert np.count_nonzero(result.masks["walls"][1]) > 0
