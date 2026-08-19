"""ML five-class pipeline tests (US-031, T-101 + AC4).

T-101 validates that the ML segmenter produces non-empty masks for all five
semantic labels on representative floor-plan images. The AC-004 tests validate
that the DXF produced by the full pipeline contains door/window/text entities
when the ML segmenter is selected, whereas the classic backend leaves those
layers empty.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import cv2
import ezdxf
import fitz  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
import pytest

from app.core.config import get_settings
from app.pipeline import (
    DxfWriterStep,
    OpenCVPreprocessor,
    PdfParserStep,
    Pipeline,
    PipelineContext,
    SegmenterStep,
    VectorizerStep,
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


def create_five_class_floor_plan() -> np.ndarray:
    """Synthetic raster floor plan containing features of every semantic class."""
    image = np.ones((240, 320), dtype=np.uint8) * 255
    ink = 0
    cv2.rectangle(image, (30, 30), (290, 210), ink, thickness=6)
    cv2.line(image, (160, 30), (160, 130), ink, thickness=6)
    cv2.line(image, (30, 120), (110, 120), ink, thickness=6)
    cv2.ellipse(image, (160, 165), (28, 28), 0, 0, 90, ink, thickness=3)
    cv2.line(image, (200, 30), (250, 30), 255, thickness=4)
    cv2.line(image, (200, 27), (250, 27), ink, thickness=2)
    cv2.line(image, (200, 33), (250, 33), ink, thickness=2)
    cv2.rectangle(image, (45, 190), (70, 198), ink, thickness=-1)
    cv2.rectangle(image, (75, 190), (100, 198), ink, thickness=-1)
    cv2.rectangle(image, (105, 190), (130, 198), ink, thickness=-1)
    return image


def create_five_class_plan_pdf(path: Path) -> Path:
    """Draw walls, a door arc, window lines, and text labels into a PDF."""
    document = fitz.open()
    page = document.new_page(width=640, height=480)
    ink = (0, 0, 0)
    page.draw_rect(fitz.Rect(60, 60, 580, 420), color=ink, width=6)
    page.draw_line(fitz.Point(320, 60), fitz.Point(320, 260), color=ink, width=6)
    page.draw_line(fitz.Point(60, 240), fitz.Point(220, 240), color=ink, width=6)
    page.draw_sector(
        fitz.Point(320, 260),
        fitz.Point(320, 330),
        90,
        fullSector=False,
        color=ink,
        width=3,
    )
    page.draw_line(fitz.Point(400, 57), fitz.Point(500, 63), color=(1, 1, 1), width=8)
    page.draw_line(fitz.Point(400, 56), fitz.Point(500, 56), color=ink, width=2)
    page.draw_line(fitz.Point(400, 64), fitz.Point(500, 64), color=ink, width=2)
    page.insert_text(fitz.Point(120, 160), "LIVING", fontsize=18, color=ink)
    page.insert_text(fitz.Point(400, 320), "BED 1", fontsize=14, color=ink)
    document.save(path)
    document.close()
    return path


def run_full_pipeline(
    pdf_path: Path, *, segmenter: str, output_dir: Path, output_path: Path
) -> dict[str, object]:
    """Run PDF→preprocess→segment→vectorize→DXF and return the final context metadata."""
    context = PipelineContext(
        job_id=f"job-{segmenter}",
        input_path=pdf_path,
        config={
            "segmenter": segmenter,
            "dpi": 72,
            "output_path": str(output_path),
        },
    )
    pipeline = Pipeline.from_steps(
        PdfParserStep(),
        OpenCVPreprocessor(),
        SegmenterStep(),
        VectorizerStep(),
        DxfWriterStep(),
        publish_step_progress=False,
    )
    result = pipeline.run(context)
    assert output_path.is_file(), "DXF output was not written by the pipeline"
    assert isinstance(result.metadata, dict)
    return result.metadata


def layer_entity_counts(dxf_path: Path) -> dict[str, int]:
    """Count modelspace entities grouped by their semantic DXF layer."""
    document = ezdxf.readfile(str(dxf_path))
    counts: dict[str, int] = {}
    for entity in document.modelspace():
        layer = str(entity.dxf.layer)
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def test_ml_masks_cover_all_five_labels_on_raster_floor_plan() -> None:
    """T-101: every semantic label has a non-empty mask from the ML backend."""
    segmenter = OnnxSemanticSegmenter(model_path=BUNDLED_MODEL_PATH, input_size=(128, 128))

    masks = segmenter.segment([create_five_class_floor_plan()])

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert np.count_nonzero(masks[label][0]) > 0, f"ML returned an empty {label} mask"


def test_ml_masks_cover_all_five_labels_via_settings(
    ml_segmenter_env: pytest.MonkeyPatch,
) -> None:
    """T-101: settings-driven ML segmenter covers all five labels at default size."""
    segmenter = OnnxSemanticSegmenter()

    # Sanity check: the settings-driven size actually comes from configuration.
    expected_size = (get_settings().SEGMENTER_MODEL_INPUT_SIZE,) * 2
    assert segmenter.input_size == expected_size

    masks = segmenter.segment([create_five_class_floor_plan()])

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert masks[label][0].shape == (240, 320)
        assert np.count_nonzero(masks[label][0]) > 0, f"ML returned an empty {label} mask"


def test_ml_pipeline_dxf_includes_door_window_text_entities(
    tmp_path: Path, ml_segmenter_env: pytest.MonkeyPatch
) -> None:
    """AC4: ML-driven DXF contains entities on every semantic layer."""
    pdf_path = create_five_class_plan_pdf(tmp_path / "plan.pdf")
    dxf_path = tmp_path / "ml-output.dxf"

    metadata = run_full_pipeline(
        pdf_path, segmenter="ml", output_dir=tmp_path, output_path=dxf_path
    )

    counts = metadata["primitive_counts_by_kind"]
    assert isinstance(counts, dict)
    assert counts["door"] > 0 and counts["window"] > 0 and counts["text"] > 0

    layers = layer_entity_counts(dxf_path)
    assert layers.get("WALLS", 0) > 0
    assert layers.get("DOORS", 0) > 0
    assert layers.get("WINDOWS", 0) > 0
    assert layers.get("ROOMS", 0) > 0
    assert layers.get("TEXT", 0) > 0


def test_classic_pipeline_dxf_omits_openings_and_text(tmp_path: Path) -> None:
    """Classic DXF only has walls; doors/windows/text layers stay empty."""
    pdf = create_five_class_plan_pdf(tmp_path / "plan.pdf")
    dxf_path = tmp_path / "classic.dxf"

    metadata = run_full_pipeline(
        pdf, segmenter="classic", output_dir=tmp_path, output_path=dxf_path
    )

    counts = metadata["primitive_counts_by_kind"]
    assert isinstance(counts, dict)
    assert counts["door"] == 0 and counts["window"] == 0 and counts["text"] == 0

    layers = layer_entity_counts(dxf_path)
    assert layers.get("WALLS", 0) > 0
    assert layers.get("DOORS", 0) == 0
    assert layers.get("WINDOWS", 0) == 0
    assert layers.get("TEXT", 0) == 0
