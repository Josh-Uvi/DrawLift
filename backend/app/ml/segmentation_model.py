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
