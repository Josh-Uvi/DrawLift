"""Tests for model input-size compatibility checks (US-031, T-102)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from app.core.config import get_settings
from app.ml.segmentation_model import (
    InputSizeCompatibilityReport,
    check_model_input_size,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_MODEL_PATH = BACKEND_DIR / "models" / "semantic_segmenter.onnx"


def _make_fixed_size_model(path: Path, size: int = 16, out_channels: int = 6) -> Path:
    """Write a model with a fixed ``size x size`` input resolution."""
    weights = np.zeros((out_channels, 1, 1, 1), dtype=np.float32)
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["input", "weights"],
                ["output"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
                strides=[1, 1],
            )
        ],
        name="fixed-size-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, size, size])],
        outputs=[
            helper.make_tensor_value_info(
                "output", TensorProto.FLOAT, [1, out_channels, size, size]
            )
        ],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    return path


def test_bundled_model_accepts_default_configured_input_size() -> None:
    """T-102: the default SEGMENTER_MODEL_INPUT_SIZE works with the bundled model."""
    report = check_model_input_size(BUNDLED_MODEL_PATH, get_settings().SEGMENTER_MODEL_INPUT_SIZE)

    assert isinstance(report, InputSizeCompatibilityReport)
    assert report.compatible
    assert report.input_size == (128, 128)


def test_bundled_model_is_dynamic_and_accepts_any_square_size() -> None:
    """The reference model has dynamic spatial dims, so any size matches."""
    assert check_model_input_size(BUNDLED_MODEL_PATH, 64).compatible
    assert check_model_input_size(BUNDLED_MODEL_PATH, 256).compatible
    assert check_model_input_size(BUNDLED_MODEL_PATH, (256, 256)).compatible


def test_fixed_size_model_requires_matching_input_size(tmp_path: Path) -> None:
    """T-102: fixed-resolution models reject mismatched configured sizes."""
    model_path = _make_fixed_size_model(tmp_path / "fixed.onnx", size=16)

    compatible = check_model_input_size(model_path, 16)
    assert compatible.compatible

    mismatched = check_model_input_size(model_path, 32)
    assert not mismatched.compatible
    assert "height" in mismatched.reason
    assert "16" in mismatched.reason and "32" in mismatched.reason


def test_missing_model_file_is_incompatible(tmp_path: Path) -> None:
    report = check_model_input_size(tmp_path / "absent.onnx", 128)

    assert not report.compatible
    assert "model file not found" in report.reason


def test_corrupt_model_file_is_incompatible(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.onnx"
    corrupt.write_bytes(b"not an onnx model")

    report = check_model_input_size(corrupt, 128)

    assert not report.compatible
    assert "failed to load" in report.reason


def test_multi_channel_input_model_is_incompatible(tmp_path: Path) -> None:
    """Models expecting RGB input cannot run at any single-channel resolution."""
    weights = np.zeros((6, 3, 1, 1), dtype=np.float32)
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["input", "weights"],
                ["output"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
                strides=[1, 1],
            )
        ],
        name="rgb-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 128, 128])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 6, 128, 128])],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.save(model, str(tmp_path / "rgb.onnx"))

    report = check_model_input_size(tmp_path / "rgb.onnx", 128)

    assert not report.compatible
    assert "input channels" in report.reason


def test_configured_input_size_reasonmentions_dimensions() -> None:
    """The compatible report names the exact accepted resolution."""
    report = check_model_input_size(BUNDLED_MODEL_PATH, (128, 128))

    assert "128x128" in report.reason
