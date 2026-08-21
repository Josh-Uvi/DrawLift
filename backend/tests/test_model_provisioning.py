"""Tests for ONNX segmentation model provisioning (US-029)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml import download_model as download_model_cli
from app.ml import segmentation_model
from app.ml.segmentation_model import (
    MAX_MODEL_SIZE_BYTES,
    ModelProvisioningError,
    build_reference_segmentation_model,
    download_segmentation_model,
    provision_segmentation_model,
    validate_segmentation_model,
)
from app.ml.yytsi_torch import YYTSI_CONFIG_FILENAME, YYTSI_MODEL_FILENAME
from app.pipeline import PipelineContext, SegmenterStep
from app.pipeline.steps.segmenter import MASK_LABELS, OnnxSemanticSegmenter

BACKEND_DIR = Path(__file__).resolve().parents[1]


def create_floor_plan() -> np.ndarray:
    """Create a synthetic binary floor plan with wall strokes."""
    image = np.zeros((160, 220), dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (200, 140), 255, thickness=5)
    cv2.line(image, (110, 20), (110, 100), 255, thickness=5)
    cv2.line(image, (20, 80), (85, 80), 255, thickness=5)
    return image


def test_build_reference_model_creates_contract_valid_model(tmp_path: Path) -> None:
    """The reference model satisfies every US-029 validation check."""
    destination = tmp_path / "reference.onnx"

    result = build_reference_segmentation_model(destination)

    assert result == destination
    assert destination.is_file()
    report = validate_segmentation_model(destination)
    assert report.passed
    assert report.loads_on_cpu
    assert report.inference_ok
    assert report.contract_ok
    assert report.class_count == 6
    assert report.size_bytes is not None
    assert report.size_bytes < MAX_MODEL_SIZE_BYTES


def test_build_reference_model_is_deterministic(tmp_path: Path) -> None:
    """Repeated builds produce byte-identical artifacts."""
    first = build_reference_segmentation_model(tmp_path / "first.onnx")
    second = build_reference_segmentation_model(tmp_path / "second.onnx")

    assert first.read_bytes() == second.read_bytes()


def test_reference_model_segments_synthetic_floor_plan(tmp_path: Path) -> None:
    """OnnxSemanticSegmenter decodes reference output into all five labels."""
    model_path = build_reference_segmentation_model(tmp_path / "reference.onnx")
    segmenter = OnnxSemanticSegmenter(model_path=model_path, input_size=(64, 64))

    masks = segmenter.segment([create_floor_plan()])

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert len(masks[label]) == 1
        assert masks[label][0].shape == (160, 220)
        assert masks[label][0].dtype == np.uint8
    assert np.count_nonzero(masks["walls"][0]) > 0
    assert np.count_nonzero(masks["rooms"][0]) > 0


def test_provision_without_url_builds_reference_model(tmp_path: Path) -> None:
    """Provisioning with no URL creates a valid model, including parent dirs."""
    destination = tmp_path / "models" / "semantic_segmenter.onnx"

    result = provision_segmentation_model(destination)

    assert result == destination
    assert destination.is_file()


def test_provision_keeps_existing_valid_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid model is reused without rebuilding when force is not set."""
    destination = tmp_path / "semantic_segmenter.onnx"
    provision_segmentation_model(destination)
    original_bytes = destination.read_bytes()

    build_calls: list[Path] = []

    def spy(_: Path) -> Path:
        build_calls.append(_)
        raise AssertionError("builder should not run for a valid existing model")

    monkeypatch.setattr(segmentation_model, "build_reference_segmentation_model", spy)

    result = provision_segmentation_model(destination)

    assert result == destination
    assert build_calls == []
    assert destination.read_bytes() == original_bytes


def test_provision_force_rebuilds_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """force=True rebuilds even when the existing model is valid."""
    destination = tmp_path / "semantic_segmenter.onnx"
    provision_segmentation_model(destination)

    build_calls: list[Path] = []
    real_builder = segmentation_model.build_reference_segmentation_model

    def spy(path: Path) -> Path:
        build_calls.append(path)
        return real_builder(path)

    monkeypatch.setattr(segmentation_model, "build_reference_segmentation_model", spy)

    provision_segmentation_model(destination, force=True)

    assert build_calls == [destination]
    assert validate_segmentation_model(destination).passed


def test_provision_replaces_existing_invalid_file(tmp_path: Path) -> None:
    """A corrupt file at the destination is replaced by a valid model."""
    destination = tmp_path / "semantic_segmenter.onnx"
    destination.write_bytes(b"corrupted model bytes")

    result = provision_segmentation_model(destination)

    assert result == destination
    assert validate_segmentation_model(destination).passed


def test_provision_downloads_from_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A contract-valid download is accepted and placed at the destination."""
    source = build_reference_segmentation_model(tmp_path / "source.onnx")
    destination = tmp_path / "models" / "semantic_segmenter.onnx"

    def fake_urlretrieve(url: str, dest: object) -> None:
        assert url == "https://models.example.com/semantic_segmenter.onnx"
        shutil.copyfile(source, Path(str(dest)))

    monkeypatch.setattr(segmentation_model, "urlretrieve", fake_urlretrieve)

    result = provision_segmentation_model(
        destination, model_url="https://models.example.com/semantic_segmenter.onnx"
    )

    assert result == destination
    assert destination.is_file()
    assert validate_segmentation_model(destination).passed


def test_provision_download_failure_raises_and_cleans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Network failures surface as ModelProvisioningError with no partial file."""
    destination = tmp_path / "semantic_segmenter.onnx"

    def failing_urlretrieve(url: str, dest: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(segmentation_model, "urlretrieve", failing_urlretrieve)

    with pytest.raises(ModelProvisioningError, match="connection refused"):
        provision_segmentation_model(destination, model_url="https://example.com/m.onnx")

    assert not destination.exists()


def test_provision_invalid_download_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Downloaded artifacts failing contract validation are deleted."""
    destination = tmp_path / "semantic_segmenter.onnx"

    def fake_urlretrieve(url: str, dest: object) -> None:
        Path(str(dest)).write_bytes(b"not an onnx model")

    monkeypatch.setattr(segmentation_model, "urlretrieve", fake_urlretrieve)

    with pytest.raises(ModelProvisioningError, match="contract validation"):
        provision_segmentation_model(destination, model_url="https://example.com/m.onnx")

    assert not destination.exists()


def test_download_rejects_non_http_scheme(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="http or https"):
        download_segmentation_model("ftp://example.com/model.onnx", tmp_path / "m.onnx")


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the download_model CLI from the backend package root."""
    return subprocess.run(
        [sys.executable, "-m", "app.ml.download_model", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        env=os.environ.copy(),
        check=False,
    )


def _write_yytsi_config(path: Path, *, image_size: tuple[int, int] = (128, 128)) -> Path:
    path.write_text(
        "data:\n"
        f"  image_size: [{image_size[0]}, {image_size[1]}]\n"
        "  normalize: true\n"
        "  letterbox: true\n"
        "model:\n"
        "  encoder_name: resnet34\n"
        "  encoder_weights: null\n",
        encoding="utf-8",
    )
    return path


def test_cli_provisions_reference_model(tmp_path: Path) -> None:
    """`python -m app.ml.download_model` provisions a valid model and reports it."""
    result = _run_cli("--models-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "result: PASS" in result.stdout
    assert (tmp_path / "semantic_segmenter.onnx").is_file()


def test_cli_check_validates_existing_model(tmp_path: Path) -> None:
    provision_segmentation_model(tmp_path / "semantic_segmenter.onnx")

    result = _run_cli("--check", "--models-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "result: PASS" in result.stdout


def test_cli_check_reports_configured_input_size_compatibility(tmp_path: Path) -> None:
    """T-102: `--check` surfaces the configured input size and its compatibility."""
    provision_segmentation_model(tmp_path / "semantic_segmenter.onnx")

    result = _run_cli("--check", "--models-dir", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "input size:" in result.stdout
    assert "is compatible with the model" in result.stdout


def test_cli_check_fails_for_missing_model(tmp_path: Path) -> None:
    result = _run_cli("--check", "--models-dir", str(tmp_path))

    assert result.returncode == 1
    assert "result: FAIL" in result.stdout
    assert "not found" in result.stdout


def test_cli_force_replaces_corrupt_model(tmp_path: Path) -> None:
    destination = tmp_path / "semantic_segmenter.onnx"
    destination.write_bytes(b"corrupted")

    result = _run_cli("--models-dir", str(tmp_path), "--force")

    assert result.returncode == 0, result.stderr
    assert validate_segmentation_model(destination).passed


def test_cli_check_validates_existing_yytsi_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--check` validates a `.safetensors + config.yaml` Torch bundle."""
    weights_path = tmp_path / YYTSI_MODEL_FILENAME
    weights_path.write_text("weights", encoding="utf-8")
    _write_yytsi_config(tmp_path / YYTSI_CONFIG_FILENAME)

    def fake_validate(*, weights_path: Path | str, config_path: Path | str, input_size: int):
        class Report:
            passed = True

            @staticmethod
            def summary() -> str:
                return (
                    f"weights path:   {weights_path}\n"
                    f"config path:    {config_path}\n"
                    f"input size:     {input_size}"
                )

        return Report()

    monkeypatch.setattr("app.ml.download_model.validate_yytsi_bundle", fake_validate)

    exit_code = download_model_cli.main(
        ["--check", "--models-dir", str(tmp_path), "--filename", YYTSI_MODEL_FILENAME]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "weights path:" in captured.out
    assert "config path:" in captured.out
    assert "result: PASS" in captured.out


def test_cli_provisions_yytsi_bundle_with_config_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Provisioning a `.safetensors` bundle resolves both weights and config."""

    def fake_resolve(**kwargs: object) -> tuple[Path, Path]:
        model_path = Path(str(kwargs["model_path"]))
        config_path = Path(str(kwargs["config_path"]))
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text("weights", encoding="utf-8")
        _write_yytsi_config(config_path)
        return model_path, config_path

    def fake_validate(*, weights_path: Path | str, config_path: Path | str, input_size: int):
        class Report:
            passed = True

            @staticmethod
            def summary() -> str:
                return (
                    f"weights path:   {weights_path}\n"
                    f"config path:    {config_path}\n"
                    f"configured input size: {input_size}"
                )

        return Report()

    monkeypatch.setattr("app.ml.download_model.resolve_yytsi_model_assets", fake_resolve)
    monkeypatch.setattr("app.ml.download_model.validate_yytsi_bundle", fake_validate)

    exit_code = download_model_cli.main(
        [
            "--models-dir",
            str(tmp_path),
            "--filename",
            YYTSI_MODEL_FILENAME,
            "--url",
            "https://example.com/best.safetensors",
            "--config-url",
            "https://example.com/config.yaml",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (tmp_path / YYTSI_MODEL_FILENAME).is_file()
    assert (tmp_path / YYTSI_CONFIG_FILENAME).is_file()
    assert "result: PASS" in captured.out


def test_segmenter_step_runs_ml_path_with_provisioned_model(tmp_path: Path) -> None:
    """End-to-end: SegmenterStep with the ml backend consumes the model."""
    model_path = provision_segmentation_model(tmp_path / "models" / "semantic_segmenter.onnx")
    ml_segmenter = OnnxSemanticSegmenter(model_path=model_path, input_size=(64, 64))
    context = PipelineContext(
        job_id="job-us029",
        input_path=tmp_path / "input.pdf",
        config={"segmenter": "ml"},
        preprocessed=[create_floor_plan()],
    )

    result = SegmenterStep(output_dir=tmp_path / "masks", ml_segmenter=ml_segmenter).execute(
        context
    )

    assert result.metadata["segmenter"] == "ml"
    assert set(result.masks) == set(MASK_LABELS)
    assert np.count_nonzero(result.masks["walls"][0]) > 0
    walls_png = tmp_path / "masks" / "walls" / "page_0001_walls.png"
    assert walls_png.is_file()
