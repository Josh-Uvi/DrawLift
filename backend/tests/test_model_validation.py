"""Tests for ONNX segmentation model contract validation (US-029)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from app.ml.segmentation_model import (
    CPU_PROVIDER,
    MAX_MODEL_SIZE_BYTES,
    OUTPUT_CHANNELS_FIRST,
    OUTPUT_CHANNELS_LAST,
    OUTPUT_CLASS_MAP,
    validate_segmentation_model,
)

OPSET = 17


def _make_channel_model(out_channels: int) -> onnx.ModelProto:
    """Build a 1x1-conv model mapping (1,1,H,W) input to (1,out_channels,H,W)."""
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
        name="channel-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, None, None])],
        outputs=[
            helper.make_tensor_value_info(
                "output", TensorProto.FLOAT, [1, out_channels, None, None]
            )
        ],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _make_channels_last_model() -> onnx.ModelProto:
    """Build a model emitting channels-last (1,H,W,5) output."""
    weights = np.zeros((5, 1, 1, 1), dtype=np.float32)
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["input", "weights"],
                ["conv_out"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
            ),
            helper.make_node("Transpose", ["conv_out"], ["output"], perm=[0, 2, 3, 1]),
        ],
        name="channels-last-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, None, None])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, None, None, 5])],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _make_class_map_model() -> onnx.ModelProto:
    """Build a model emitting an integer class map (1,H,W)."""
    graph = helper.make_graph(
        nodes=[helper.make_node("ArgMax", ["input"], ["output"], axis=1, keepdims=0)],
        name="class-map-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, None, None])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.INT64, [1, None, None])],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _make_rgb_input_model() -> onnx.ModelProto:
    """Build a 3-channel-input model incompatible with the grayscale segmenter."""
    weights = np.zeros((5, 3, 1, 1), dtype=np.float32)
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["input", "weights"],
                ["output"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
            )
        ],
        name="rgb-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, None, None])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 5, None, None])],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _make_vector_output_model() -> onnx.ModelProto:
    """Build a model collapsing spatial dims into an undecodable vector."""
    graph = helper.make_graph(
        nodes=[helper.make_node("ReduceMean", ["input"], ["output"], axes=[2, 3], keepdims=0)],
        name="vector-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, None, None])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 1])],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _make_fixed_size_model() -> onnx.ModelProto:
    """Build a model with a fixed 16x16 input resolution."""
    weights = np.zeros((5, 1, 1, 1), dtype=np.float32)
    graph = helper.make_graph(
        nodes=[
            helper.make_node(
                "Conv",
                ["input", "weights"],
                ["output"],
                kernel_shape=[1, 1],
                pads=[0, 0, 0, 0],
            )
        ],
        name="fixed-probe",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, 16, 16])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 5, 16, 16])],
        initializer=[numpy_helper.from_array(weights, name="weights")],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", OPSET)])


def _save(model: onnx.ModelProto, tmp_path: Path, name: str = "model.onnx") -> Path:
    path = tmp_path / name
    onnx.save(model, str(path))
    return path


def test_validation_accepts_five_channel_contract_model(tmp_path: Path) -> None:
    """A (1,5,H,W) channel model satisfies the US-029 5-class contract."""
    report = validate_segmentation_model(_save(_make_channel_model(5), tmp_path))

    assert report.passed
    assert report.exists
    assert report.loads_on_cpu
    assert report.inference_ok
    assert report.contract_ok
    assert report.output_layout == OUTPUT_CHANNELS_FIRST
    assert report.class_count == 5


def test_validation_accepts_six_channel_model_with_background(tmp_path: Path) -> None:
    """A 6-channel model (background + 5 labels) is also decodable."""
    report = validate_segmentation_model(_save(_make_channel_model(6), tmp_path))

    assert report.passed
    assert report.contract_ok
    assert report.class_count == 6


def test_validation_accepts_channels_last_output(tmp_path: Path) -> None:
    """Channels-last (1,H,W,5) output is normalized and accepted."""
    report = validate_segmentation_model(_save(_make_channels_last_model(), tmp_path))

    assert report.passed
    assert report.contract_ok
    assert report.output_layout == OUTPUT_CHANNELS_LAST
    assert report.class_count == 5


def test_validation_accepts_class_map_output(tmp_path: Path) -> None:
    """Integer class-map (1,H,W) output is a supported decode layout."""
    report = validate_segmentation_model(_save(_make_class_map_model(), tmp_path))

    assert report.passed
    assert report.contract_ok
    assert report.output_layout == OUTPUT_CLASS_MAP


def test_validation_accepts_fixed_input_size_model(tmp_path: Path) -> None:
    """The probe respects declared fixed spatial dimensions."""
    report = validate_segmentation_model(_save(_make_fixed_size_model(), tmp_path))

    assert report.passed
    assert report.inference_ok
    assert report.contract_ok


def test_validation_reports_missing_file(tmp_path: Path) -> None:
    report = validate_segmentation_model(tmp_path / "absent.onnx")

    assert not report.passed
    assert not report.exists
    assert "not found" in report.errors[0]


def test_validation_reports_oversized_model(tmp_path: Path) -> None:
    """Files exceeding the size budget fail validation."""
    model_path = _save(_make_channel_model(5), tmp_path)

    report = validate_segmentation_model(model_path, max_size_bytes=16)

    assert not report.passed
    assert report.size_bytes is not None and report.size_bytes > 16
    assert any("exceeding" in error for error in report.errors)
    # The other checks still run and are reported for diagnostics.
    assert report.loads_on_cpu


def test_validation_reports_corrupt_file(tmp_path: Path) -> None:
    corrupt_path = tmp_path / "corrupt.onnx"
    corrupt_path.write_bytes(b"this is not an onnx model")

    report = validate_segmentation_model(corrupt_path)

    assert not report.passed
    assert not report.loads_on_cpu
    assert any("failed to load" in error for error in report.errors)


def test_validation_reports_wrong_class_count(tmp_path: Path) -> None:
    report = validate_segmentation_model(_save(_make_channel_model(3), tmp_path))

    assert not report.passed
    assert not report.contract_ok
    assert any("class count" in error for error in report.errors)


def test_validation_reports_undecodable_output(tmp_path: Path) -> None:
    report = validate_segmentation_model(_save(_make_vector_output_model(), tmp_path))

    assert not report.passed
    assert not report.contract_ok
    assert any("must have shape" in error for error in report.errors)


def test_validation_reports_multi_channel_input_mismatch(tmp_path: Path) -> None:
    """Models expecting RGB input cannot consume grayscale segmenter tensors."""
    report = validate_segmentation_model(_save(_make_rgb_input_model(), tmp_path))

    assert not report.passed
    assert not report.contract_ok
    assert any("input channels" in error for error in report.errors)


def test_validation_uses_cpu_provider_only(tmp_path: Path) -> None:
    report = validate_segmentation_model(_save(_make_channel_model(5), tmp_path))

    assert report.providers == (CPU_PROVIDER,)


def test_validation_report_summary_lists_errors(tmp_path: Path) -> None:
    report = validate_segmentation_model(tmp_path / "absent.onnx")

    summary = report.summary()

    assert "errors:" in summary
    assert "not found" in summary


def test_size_budget_matches_worker_memory_limit() -> None:
    """US-029 requires the model file size budget to be 100 MB."""
    assert MAX_MODEL_SIZE_BYTES == 100 * 1024 * 1024
