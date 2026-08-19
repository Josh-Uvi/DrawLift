"""ONNX segmentation model management for the ML pipeline.

This module owns the acquisition and validation rules for the floor-plan
semantic segmentation model consumed by
:class:`app.pipeline.steps.segmenter.OnnxSemanticSegmenter`.

The US-029 contract enforced by :func:`validate_segmentation_model`:

* the model file exists at the configured location,
* the file is no larger than ``MAX_MODEL_SIZE_BYTES`` (worker memory budget),
* the model loads with ONNX Runtime using only ``CPUExecutionProvider``,
* the model output decodes into the 5-class mask format (walls, doors,
  windows, rooms, text) understood by the segmenter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlretrieve

import numpy as np

SEGMENTATION_MODEL_FILENAME = "semantic_segmenter.onnx"
MAX_MODEL_SIZE_BYTES = 100 * 1024 * 1024
SUPPORTED_CLASS_COUNTS = frozenset({5, 6})
CPU_PROVIDER = "CPUExecutionProvider"
NUM_MASK_LABELS = 5
FLOAT_INPUT_TYPE = "tensor(float)"

OUTPUT_CHANNELS_FIRST = "channels_first"
OUTPUT_CHANNELS_LAST = "channels_last"
OUTPUT_CLASS_MAP = "class_map"
OUTPUT_UNSUPPORTED = "unsupported"


class ModelProvisioningError(RuntimeError):
    """Raised when a segmentation model cannot be downloaded, built, or validated."""


@dataclass(frozen=True)
class ModelValidationReport:
    """Outcome of validating an ONNX segmentation model against the contract."""

    path: Path
    exists: bool
    size_bytes: int | None = None
    loads_on_cpu: bool = False
    providers: tuple[str, ...] = ()
    input_name: str | None = None
    input_shape: tuple[Any, ...] | None = None
    output_shape: tuple[Any, ...] | None = None
    output_layout: str | None = None
    class_count: int | None = None
    inference_ok: bool = False
    contract_ok: bool = False
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when every US-029 acceptance check succeeded."""
        return not self.errors

    def summary(self) -> str:
        """Return a human-readable multi-line report."""
        output_shape = list(self.output_shape) if self.output_shape else "n/a"
        input_shape = list(self.input_shape) if self.input_shape else "n/a"
        lines = [
            f"model path:     {self.path}",
            f"exists:         {self.exists}",
            f"size bytes:     {self.size_bytes if self.size_bytes is not None else 'n/a'}",
            f"cpu load:       {self.loads_on_cpu}",
            f"providers:      {', '.join(self.providers) if self.providers else 'n/a'}",
            f"input:          {self.input_name} {input_shape}",
            f"output:         {output_shape} ({self.output_layout or 'unknown'})",
            f"inference:      {'ok' if self.inference_ok else 'failed'}",
            f"5-class decode: {'ok' if self.contract_ok else 'failed'}",
        ]
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {error}" for error in self.errors)
        return "\n".join(lines)


def validate_segmentation_model(
    model_path: Path | str,
    *,
    max_size_bytes: int = MAX_MODEL_SIZE_BYTES,
    probe_size: int = 64,
) -> ModelValidationReport:
    """Validate an ONNX segmentation model against the US-029 contract.

    The check loads the model with the CPU-only ONNX Runtime provider, runs a
    deterministic single-channel grayscale probe through it, and verifies that
    the output can be decoded into the five semantic mask labels.
    """
    path = Path(model_path).expanduser().resolve()
    if not path.is_file():
        return ModelValidationReport(
            path=path,
            exists=False,
            errors=(f"model file not found: {path}",),
        )

    errors: list[str] = []
    size_bytes = path.stat().st_size
    if size_bytes > max_size_bytes:
        errors.append(f"model is {size_bytes} bytes, exceeding the {max_size_bytes} byte budget")

    session = _load_cpu_session(path, errors)
    if session is None:
        return ModelValidationReport(
            path=path,
            exists=True,
            size_bytes=size_bytes,
            errors=tuple(errors),
        )

    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0]
    input_shape = tuple(input_meta.shape)
    declared_channels = _declared_input_channels(input_shape, errors)

    inference_ok = False
    output: np.ndarray | None = None
    if input_meta.type != FLOAT_INPUT_TYPE:
        errors.append(
            f"model input type is {input_meta.type}; expected {FLOAT_INPUT_TYPE} "
            "grayscale tensors"
        )
    else:
        probe_shape = _resolve_probe_shape(input_shape, declared_channels, probe_size)
        probe = np.full(probe_shape, 0.5, dtype=np.float32)
        try:
            raw_output = session.run(None, {input_meta.name: probe})
            output = np.asarray(raw_output[0])
            inference_ok = True
        except Exception as exc:  # noqa: BLE001 - report any runtime failure verbatim
            errors.append(f"CPU inference failed: {exc}")

    output_shape = tuple(output_meta.shape)
    if output is not None:
        layout, class_count = _describe_output(output, errors)
    else:
        layout, class_count = OUTPUT_UNSUPPORTED, None

    contract_ok = (
        inference_ok
        and layout in {OUTPUT_CHANNELS_FIRST, OUTPUT_CHANNELS_LAST, OUTPUT_CLASS_MAP}
        and declared_channels == 1
    )
    return ModelValidationReport(
        path=path,
        exists=True,
        size_bytes=size_bytes,
        loads_on_cpu=True,
        providers=tuple(session.get_providers()),
        input_name=input_meta.name,
        input_shape=input_shape,
        output_shape=output_shape,
        output_layout=layout,
        class_count=class_count,
        inference_ok=inference_ok,
        contract_ok=contract_ok,
        errors=tuple(errors),
    )


@dataclass(frozen=True)
class InputSizeCompatibilityReport:
    """Whether a configured input size matches a model's declared dimensions."""

    path: Path
    input_size: tuple[int, int]
    declared_shape: tuple[Any, ...] | None = None
    compatible: bool = False
    reason: str = ""


def check_model_input_size(
    model_path: Path | str, input_size: int | tuple[int, int]
) -> InputSizeCompatibilityReport:
    """Check a ``SEGMENTER_MODEL_INPUT_SIZE``-style size against a model (T-102).

    The segmenter resizes every page into a tensor of the configured size.
    Models with dynamic spatial dimensions accept any size; models with fixed
    spatial dimensions must match exactly. The check also runs one real CPU
    inference at the configured size.
    """
    size = (
        (input_size, input_size)
        if isinstance(input_size, int)
        else (int(input_size[0]), int(input_size[1]))
    )
    path = Path(model_path).expanduser().resolve()
    if not path.is_file():
        return InputSizeCompatibilityReport(
            path=path, input_size=size, reason="model file not found"
        )

    errors: list[str] = []
    session = _load_cpu_session(path, errors)
    if session is None:
        return InputSizeCompatibilityReport(path=path, input_size=size, reason="; ".join(errors))

    input_meta = session.get_inputs()[0]
    declared_shape = tuple(input_meta.shape)

    def report(reason: str, *, compatible: bool = False) -> InputSizeCompatibilityReport:
        return InputSizeCompatibilityReport(
            path=path,
            input_size=size,
            declared_shape=declared_shape,
            compatible=compatible,
            reason=reason,
        )

    if len(declared_shape) != 4:
        return report(f"model input must be a 4D NCHW tensor; got shape {list(declared_shape)}")
    channels = declared_shape[1]
    if isinstance(channels, int) and channels != 1:
        return report(
            f"model expects {channels} input channels; the segmenter feeds "
            "single-channel grayscale images"
        )
    for axis_name, declared, requested in (
        ("height", declared_shape[2], size[0]),
        ("width", declared_shape[3], size[1]),
    ):
        if isinstance(declared, int) and declared != requested:
            return report(
                f"model expects fixed {axis_name} {declared}; configured "
                f"input size is {requested}"
            )
    if input_meta.type != FLOAT_INPUT_TYPE:
        return report(f"model input type is {input_meta.type}; expected {FLOAT_INPUT_TYPE}")

    batch = declared_shape[0] if isinstance(declared_shape[0], int) and declared_shape[0] > 0 else 1
    probe_channels = channels if isinstance(channels, int) else 1
    probe = np.full((batch, probe_channels, size[0], size[1]), 0.5, dtype=np.float32)
    try:
        session.run(None, {input_meta.name: probe})
    except Exception as exc:  # noqa: BLE001 - report any runtime failure verbatim
        return report(f"inference at {size[0]}x{size[1]} failed: {exc}")

    return report(
        f"input size {size[0]}x{size[1]} is compatible with the model",
        compatible=True,
    )


def _load_cpu_session(path: Path, errors: list[str]) -> Any | None:
    """Create a CPU-only ONNX Runtime session or record the failure."""
    import onnxruntime as ort

    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        return ort.InferenceSession(
            str(path),
            sess_options=session_options,
            providers=[CPU_PROVIDER],
        )
    except Exception as exc:  # noqa: BLE001 - load errors are reported, not raised
        errors.append(f"model failed to load with ONNX Runtime CPU provider: {exc}")
        return None


def _declared_input_channels(input_shape: tuple[Any, ...], errors: list[str]) -> int:
    """Return the declared input channel count, validating the NCHW contract.

    The segmenter always feeds single-channel grayscale tensors shaped
    ``(1, 1, H, W)``, so compatible models must declare one input channel (or a
    dynamic channel dimension, which is probed with one channel).
    """
    if len(input_shape) != 4:
        errors.append(f"model input must be a 4D NCHW tensor; got shape {list(input_shape)}")
        return 0
    channels = input_shape[1]
    if not isinstance(channels, int):
        return 1
    if channels != 1:
        errors.append(
            f"model expects {channels} input channels; the segmenter feeds "
            "single-channel grayscale images"
        )
    return channels


def _resolve_probe_shape(
    input_shape: tuple[Any, ...],
    declared_channels: int,
    probe_size: int,
) -> tuple[int, int, int, int]:
    """Build a concrete probe shape from possibly dynamic declared dimensions."""

    def concrete(value: Any, fallback: int) -> int:
        return value if isinstance(value, int) and value > 0 else fallback

    batch = concrete(input_shape[0], 1) if input_shape else 1
    channels = concrete(declared_channels, 1)
    height = concrete(input_shape[2], probe_size) if len(input_shape) > 2 else probe_size
    width = concrete(input_shape[3], probe_size) if len(input_shape) > 3 else probe_size
    return batch, channels, height, width


def _describe_output(output: np.ndarray, errors: list[str]) -> tuple[str, int | None]:
    """Classify a model output array against the decodable mask layouts."""
    if output.ndim == 4:
        if output.shape[1] in SUPPORTED_CLASS_COUNTS:
            return OUTPUT_CHANNELS_FIRST, int(output.shape[1])
        if output.shape[-1] in SUPPORTED_CLASS_COUNTS:
            return OUTPUT_CHANNELS_LAST, int(output.shape[-1])
        errors.append(
            "model output class count does not match the 5-class mask format; "
            f"got shape {list(output.shape)}"
        )
        return OUTPUT_UNSUPPORTED, None
    if output.ndim == 3:
        max_class = int(np.max(output)) if output.size else 0
        min_class = int(np.min(output)) if output.size else 0
        if min_class < 0 or max_class > NUM_MASK_LABELS + 1:
            errors.append(
                "class-map output values must fall within "
                f"[0, {NUM_MASK_LABELS + 1}]; got [{min_class}, {max_class}]"
            )
            return OUTPUT_UNSUPPORTED, None
        return OUTPUT_CLASS_MAP, max_class + 1 if output.size else 0
    errors.append(
        "model output must have shape (N,C,H,W), (N,H,W,C), or (N,H,W); "
        f"got {list(output.shape)}"
    )
    return OUTPUT_UNSUPPORTED, None


def download_segmentation_model(model_url: str, destination: Path | str) -> Path:
    """Download a segmentation model from an http(s) URL to ``destination``.

    Mirrors the scheme restrictions of ``SEGMENTER_MODEL_URL`` so only http or
    https sources are accepted.
    """
    parsed_url = urlparse(model_url)
    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("model URL must use http or https")

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(model_url, destination_path)
    return destination_path


def provision_segmentation_model(
    destination: Path | str,
    *,
    model_url: str | None = None,
    force: bool = False,
    max_size_bytes: int = MAX_MODEL_SIZE_BYTES,
    probe_size: int = 64,
) -> Path:
    """Provision a contract-valid segmentation model at ``destination``.

    Downloads from ``model_url`` when provided, otherwise builds the bundled
    reference model. An existing valid model is reused unless ``force`` is set;
    an existing invalid model is replaced. The result is validated against the
    US-029 contract before being returned, and invalid artifacts are removed.
    """
    destination_path = Path(destination).expanduser().resolve()

    if destination_path.exists() and not force:
        existing = validate_segmentation_model(
            destination_path, max_size_bytes=max_size_bytes, probe_size=probe_size
        )
        if existing.passed:
            return destination_path
        _remove_quietly(destination_path)

    try:
        if model_url:
            download_segmentation_model(model_url, destination_path)
        else:
            build_reference_segmentation_model(destination_path)
    except ModelProvisioningError:
        raise
    except Exception as exc:  # noqa: BLE001 - wrap source failures for callers
        _remove_quietly(destination_path)
        raise ModelProvisioningError(f"failed to provision model: {exc}") from exc

    report = validate_segmentation_model(
        destination_path, max_size_bytes=max_size_bytes, probe_size=probe_size
    )
    if not report.passed:
        _remove_quietly(destination_path)
        raise ModelProvisioningError(
            "provisioned model failed contract validation:\n" + report.summary()
        )
    return destination_path


def _remove_quietly(path: Path) -> None:
    """Delete a file without raising when it is already absent."""
    path.unlink(missing_ok=True)


def build_reference_segmentation_model(destination: Path | str, *, opset: int = 17) -> Path:
    """Build the deterministic reference segmentation model at ``destination``.

    The reference model expresses a classical edge-energy segmenter in ONNX so
    the ML path is functional without external model hosting. It consumes a
    single-channel grayscale float tensor ``(N, 1, H, W)`` normalized to
    ``[0, 1]`` and emits ``(N, 6, H, W)`` class logits ordered
    ``[background, walls, doors, windows, rooms, text]``. Channel 0 is the
    background class, which the 6-channel decode path skips.

    This is intentionally small (a few KB) so it stays far below the 100 MB
    budget and can be committed or regenerated on demand. It is meant to be
    swapped for a trained model via ``SEGMENTER_MODEL_URL`` or
    ``make download-model MODEL_URL=...``.
    """
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    sobel_y = sobel_x.T.copy()
    laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

    def kernel(name: str, values: np.ndarray) -> Any:
        tensor = numpy_helper.from_array(values.reshape(1, 1, 3, 3), name=name)
        return helper.make_node("Constant", [], [name], value=tensor)

    def scalar(name: str, value: float) -> Any:
        tensor = numpy_helper.from_array(np.array(value, dtype=np.float32), name=name)
        return helper.make_node("Constant", [], [name], value=tensor)

    nodes = [
        kernel("sobel_x", sobel_x),
        kernel("sobel_y", sobel_y),
        kernel("laplacian", laplacian),
        scalar("edge_gain", 8.0),
        scalar("wall_offset", 3.0),
        scalar("room_base", 2.0),
        scalar("opening_gain", 4.0),
        scalar("opening_offset", 3.5),
        scalar("text_gain", 6.0),
        scalar("text_offset", 4.5),
        scalar("logit_min", -10.0),
        scalar("logit_max", 10.0),
        helper.make_node(
            "Conv", ["input", "sobel_x"], ["gx"], kernel_shape=[3, 3], pads=[1, 1, 1, 1]
        ),
        helper.make_node(
            "Conv", ["input", "sobel_y"], ["gy"], kernel_shape=[3, 3], pads=[1, 1, 1, 1]
        ),
        helper.make_node(
            "Conv", ["input", "laplacian"], ["lap"], kernel_shape=[3, 3], pads=[1, 1, 1, 1]
        ),
        helper.make_node("Abs", ["gx"], ["abs_gx"]),
        helper.make_node("Abs", ["gy"], ["abs_gy"]),
        helper.make_node("Abs", ["lap"], ["abs_lap"]),
        helper.make_node("Add", ["abs_gx", "abs_gy"], ["edge"]),
        helper.make_node("Mul", ["edge", "edge_gain"], ["edge_scaled"]),
        helper.make_node("Sub", ["edge_scaled", "wall_offset"], ["wall_logit"]),
        helper.make_node("Clip", ["wall_logit", "logit_min", "logit_max"], ["walls"]),
        helper.make_node("Sub", ["room_base", "edge_scaled"], ["room_logit"]),
        helper.make_node("Clip", ["room_logit", "logit_min", "logit_max"], ["rooms"]),
        helper.make_node("Mul", ["abs_gy", "opening_gain"], ["door_scaled"]),
        helper.make_node("Sub", ["door_scaled", "opening_offset"], ["door_logit"]),
        helper.make_node("Clip", ["door_logit", "logit_min", "logit_max"], ["doors"]),
        helper.make_node("Mul", ["abs_gx", "opening_gain"], ["window_scaled"]),
        helper.make_node("Sub", ["window_scaled", "opening_offset"], ["window_logit"]),
        helper.make_node("Clip", ["window_logit", "logit_min", "logit_max"], ["windows"]),
        helper.make_node("Mul", ["abs_lap", "text_gain"], ["text_scaled"]),
        helper.make_node("Sub", ["text_scaled", "text_offset"], ["text_logit"]),
        helper.make_node("Clip", ["text_logit", "logit_min", "logit_max"], ["text"]),
        helper.make_node("Neg", ["walls"], ["background"]),
        helper.make_node(
            "Concat",
            ["background", "walls", "doors", "windows", "rooms", "text"],
            ["output"],
            axis=1,
        ),
    ]

    graph = helper.make_graph(
        nodes=nodes,
        name="floorplan-reference-segmenter",
        inputs=[helper.make_tensor_value_info("input", TensorProto.FLOAT, ["N", 1, "H", "W"])],
        outputs=[helper.make_tensor_value_info("output", TensorProto.FLOAT, ["N", 6, "H", "W"])],
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", opset)],
        producer_name="drawlift-model-tooling",
    )
    model.ir_version = 8
    model.model_version = 1
    model.doc_string = (
        "Deterministic reference floor-plan segmenter (US-029). Edge-energy "
        "heuristics expressed as ONNX ops; replace with trained weights via "
        "SEGMENTER_MODEL_URL or `make download-model MODEL_URL=...`."
    )
    onnx.checker.check_model(model)

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination_path))
    return destination_path

    return OUTPUT_UNSUPPORTED, None
