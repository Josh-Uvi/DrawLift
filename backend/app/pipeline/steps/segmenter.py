"""Semantic segmentation pipeline steps for floor-plan raster images."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse
from urllib.request import urlretrieve

import cv2
import numpy as np

from app.core.config import get_settings
from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep

MASK_LABELS: tuple[str, ...] = ("walls", "doors", "windows", "rooms", "text")
ML_SEGMENTER = "ml"
CLASSIC_SEGMENTER = "classic"
DEFAULT_SEGMENTER = CLASSIC_SEGMENTER
DEFAULT_MODEL_FILENAME = "semantic_segmenter.onnx"
DEFAULT_MODEL_INPUT_SIZE: tuple[int, int] = (512, 512)

SegmentationMasks = dict[str, list[np.ndarray]]
MaskPathMap = dict[str, list[Path]]


class SemanticSegmenter(Protocol):
    """Protocol implemented by concrete semantic segmentation backends."""

    def segment(self, images: Sequence[np.ndarray]) -> SegmentationMasks:
        """Return per-label masks for every input image."""
        ...


class ClassicCVSegmenter:
    """Fast non-ML segmentation fallback for simple line drawings.

    The classic path assumes preprocessed binary images where foreground drawing
    pixels are non-zero. It uses thresholding, Canny edges, and probabilistic
    Hough line detection to identify wall-like structures, then derives room
    regions from the closed wall mask. Other semantic classes are emitted as
    empty masks so downstream vectorization can depend on a stable label set.
    """

    def __init__(self, *, wall_thickness: int = 3) -> None:
        """Create the classic OpenCV segmenter."""
        if wall_thickness <= 0:
            raise ValueError("wall_thickness must be greater than zero")
        self.wall_thickness = wall_thickness

    def segment(self, images: Sequence[np.ndarray]) -> SegmentationMasks:
        """Segment binary floor-plan images with thresholding and Hough lines."""
        masks = _empty_mask_collection()
        for image in images:
            binary = _as_binary_mask(image)
            wall_mask = self._detect_walls(binary)
            rooms_mask = self._detect_room_regions(wall_mask)

            masks["walls"].append(wall_mask)
            masks["rooms"].append(rooms_mask)
            masks["doors"].append(np.zeros_like(binary, dtype=np.uint8))
            masks["windows"].append(np.zeros_like(binary, dtype=np.uint8))
            masks["text"].append(np.zeros_like(binary, dtype=np.uint8))

        return masks

    def _detect_walls(self, image: np.ndarray) -> np.ndarray:
        """Detect dominant straight-line structures as wall pixels."""
        edges = cv2.Canny(image, 50, 150)
        min_dimension = max(1, min(image.shape[:2]))
        min_line_length = max(12, min_dimension // 8)
        threshold = max(12, min_dimension // 10)
        lines = cast(np.ndarray | None, cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=threshold,
            minLineLength=min_line_length,
            maxLineGap=8,
        ))

        wall_mask = np.zeros_like(image, dtype=np.uint8)
        if lines is None:
            kernel = np.ones((3, 3), dtype=np.uint8)
            return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)

        for line in lines.reshape(-1, 4):
            x1, y1, x2, y2 = (int(value) for value in line)
            cv2.line(wall_mask, (x1, y1), (x2, y2), 255, thickness=self.wall_thickness)

        kernel = np.ones((3, 3), dtype=np.uint8)
        return cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, kernel)

    @staticmethod
    def _detect_room_regions(wall_mask: np.ndarray) -> np.ndarray:
        """Infer enclosed room regions from a wall mask."""
        kernel = np.ones((5, 5), dtype=np.uint8)
        closed_walls = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        candidate_rooms = cv2.bitwise_not(closed_walls)

        height, width = candidate_rooms.shape[:2]
        flood_filled = candidate_rooms.copy()
        flood_mask = np.zeros((height + 2, width + 2), dtype=np.uint8)
        cv2.floodFill(flood_filled, flood_mask, (0, 0), 0)

        return _as_binary_mask(flood_filled)


class OnnxSemanticSegmenter:
    """CPU ONNX Runtime segmenter for ML-based semantic masks."""

    def __init__(
        self,
        *,
        model_path: Path | str | None = None,
        model_url: str | None = None,
        models_dir: Path | str | None = None,
        input_size: tuple[int, int] = DEFAULT_MODEL_INPUT_SIZE,
    ) -> None:
        """Create an ONNX segmenter with an optional model override."""
        self.model_path = Path(model_path) if model_path is not None else None
        self.model_url = model_url
        self.models_dir = Path(models_dir) if models_dir is not None else None
        self.input_size = input_size

    def preload(self) -> None:
        """Load the ONNX Runtime session into the process-level cache."""
        _get_onnx_session(str(self._resolve_model_path()))

    def segment(self, images: Sequence[np.ndarray]) -> SegmentationMasks:
        """Run CPU ONNX inference and decode semantic masks for every page.

        Pages are processed one at a time rather than batched together. This
        keeps peak memory proportional to a single page's tensors instead of
        ``N_pages × page_tensor_size``, which is critical for avoiding OOM
        kills on memory-constrained worker containers.
        """
        if not images:
            return _empty_mask_collection()

        session = _get_onnx_session(str(self._resolve_model_path()))
        input_name = session.get_inputs()[0].name

        masks = _empty_mask_collection()
        for image in images:
            original_shape = image.shape[:2]
            single_input = self._prepare_input(image)[np.newaxis, :, :]
            raw_output = cast(Any, session.run(None, {input_name: single_input})[0])
            page_masks = self.decode_output(np.asarray(raw_output), [original_shape])
            for label in MASK_LABELS:
                masks[label].extend(page_masks[label])

        return masks

    def _resolve_model_path(self) -> Path:
        """Return a cached ONNX model path, downloading from a configured URL if needed."""
        settings = get_settings()
        configured_path = self.model_path or _optional_path(settings.SEGMENTER_MODEL_PATH)
        if configured_path is not None:
            model_path = configured_path.expanduser().resolve()
        else:
            model_dir = (self.models_dir or Path(settings.MODELS_PATH)).expanduser().resolve()
            model_path = model_dir / DEFAULT_MODEL_FILENAME

        if model_path.exists():
            return model_path

        model_url = self.model_url or settings.SEGMENTER_MODEL_URL
        if model_url:
            _download_model(model_url, model_path)
            return model_path

        raise FileNotFoundError(
            "ONNX segmentation model not found. Configure SEGMENTER_MODEL_PATH "
            "or SEGMENTER_MODEL_URL, or select segmenter='classic'."
        )

    def _prepare_input(self, image: np.ndarray) -> np.ndarray:
        """Convert an image to an NCHW float tensor expected by ONNX models."""
        grayscale = _to_grayscale(image)
        resized = cv2.resize(grayscale, self.input_size, interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        return normalized[np.newaxis, :, :]

    def decode_output(
        self,
        output: np.ndarray,
        original_shapes: Sequence[tuple[int, int]],
    ) -> SegmentationMasks:
        """Decode common ONNX semantic segmentation output shapes."""
        if output.ndim == 4:
            return self._decode_channel_masks(output, original_shapes)
        if output.ndim == 3:
            return self._decode_class_maps(output, original_shapes)
        raise ValueError("ONNX segmenter output must have shape (N,C,H,W), (N,H,W,C), or (N,H,W)")

    @staticmethod
    def _decode_channel_masks(
        output: np.ndarray,
        original_shapes: Sequence[tuple[int, int]],
    ) -> SegmentationMasks:
        """Decode per-class channels into binary masks."""
        if output.shape[1] in {len(MASK_LABELS), len(MASK_LABELS) + 1}:
            channels_first = output
        elif output.shape[-1] in {len(MASK_LABELS), len(MASK_LABELS) + 1}:
            channels_first = np.moveaxis(output, -1, 1)
        else:
            raise ValueError("ONNX segmenter output class count does not match semantic labels")

        channel_offset = 1 if channels_first.shape[1] == len(MASK_LABELS) + 1 else 0
        masks = _empty_mask_collection()
        for page_index, shape in enumerate(original_shapes):
            for label_index, label in enumerate(MASK_LABELS):
                channel = channels_first[page_index, label_index + channel_offset]
                probabilities = _sigmoid_if_logits(channel)
                mask = (probabilities >= 0.5).astype(np.uint8) * 255
                masks[label].append(_resize_mask(mask, shape))
        return masks

    @staticmethod
    def _decode_class_maps(
        output: np.ndarray,
        original_shapes: Sequence[tuple[int, int]],
    ) -> SegmentationMasks:
        """Decode class-index maps into binary masks."""
        masks = _empty_mask_collection()
        output_max = int(np.max(output)) if output.size else 0
        first_label_index = 0 if output_max <= len(MASK_LABELS) - 1 else 1

        for page_index, shape in enumerate(original_shapes):
            class_map = output[page_index]
            for label_index, label in enumerate(MASK_LABELS, start=first_label_index):
                mask = (class_map == label_index).astype(np.uint8) * 255
                masks[label].append(_resize_mask(mask, shape))
        return masks


class SegmenterStep(PipelineStep):
    """Pipeline step that produces semantic masks from preprocessed pages."""

    name = "Semantic Segmentation"
    progress = 60

    def __init__(
        self,
        output_dir: Path | str | None = None,
        *,
        ml_segmenter: SemanticSegmenter | None = None,
        classic_segmenter: SemanticSegmenter | None = None,
    ) -> None:
        """Create the segmentation step with optional backend overrides."""
        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.ml_segmenter = ml_segmenter or OnnxSemanticSegmenter()
        self.classic_segmenter = classic_segmenter or ClassicCVSegmenter()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Run the configured semantic segmentation backend."""
        if not context.preprocessed:
            raise ValueError(
                "SegmenterStep requires preprocessed images on the context. "
                "Ensure OpenCVPreprocessor runs before this step."
            )

        selected_segmenter = _resolve_segmenter_name(context.config.get("segmenter"))
        segmenter = (
            self.ml_segmenter if selected_segmenter == ML_SEGMENTER else self.classic_segmenter
        )
        images = [_require_image_array(image) for image in context.preprocessed]
        masks = segmenter.segment(images)
        _validate_masks(masks, expected_pages=len(images))

        output_dir = self._resolve_output_dir(context)
        mask_paths = self._save_masks(masks, output_dir)

        context.masks = masks
        context.metadata["segmenter"] = selected_segmenter
        context.metadata["segmentation_labels"] = list(MASK_LABELS)
        context.metadata["segmentation_count"] = len(images)
        context.metadata["segmentation_mask_dir"] = output_dir
        context.metadata["segmentation_mask_paths"] = mask_paths

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Segmented {len(images)} page image(s) using {selected_segmenter}",
        )
        return context

    def _resolve_output_dir(self, context: PipelineContext) -> Path:
        """Resolve where segmentation mask previews should be written."""
        if self.output_dir is not None:
            return self.output_dir

        preprocessed_dir = context.metadata.get("preprocessed_image_dir")
        if preprocessed_dir is not None:
            return Path(str(preprocessed_dir)) / "masks"

        return context.input_path.parent / context.job_id / "masks"

    @staticmethod
    def _save_masks(masks: SegmentationMasks, output_dir: Path) -> MaskPathMap:
        """Persist mask PNGs for diagnostics and downstream inspection."""
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_paths: MaskPathMap = {label: [] for label in MASK_LABELS}
        for label in MASK_LABELS:
            label_dir = output_dir / label
            label_dir.mkdir(parents=True, exist_ok=True)
            for page_index, mask in enumerate(masks[label], start=1):
                output_path = label_dir / f"page_{page_index:04d}_{label}.png"
                if not cv2.imwrite(str(output_path), _as_binary_mask(mask)):
                    raise OSError(f"Unable to write segmentation mask: {output_path}")
                mask_paths[label].append(output_path)
        return mask_paths


def preload_configured_segmentation_model() -> None:
    """Preload the configured ONNX model once when a worker process starts."""
    settings = get_settings()
    if settings.SEGMENTER_MODEL_PATH is None and settings.SEGMENTER_MODEL_URL is None:
        return
    OnnxSemanticSegmenter().preload()


def _empty_mask_collection() -> SegmentationMasks:
    """Return an empty semantic mask collection keyed by label."""
    return {label: [] for label in MASK_LABELS}


def _optional_path(value: str | None) -> Path | None:
    """Convert a non-empty string into a Path."""
    if value is None or value.strip() == "":
        return None
    return Path(value)


def _download_model(model_url: str, destination: Path) -> None:
    """Download a configured model URL into the local model cache."""
    parsed_url = urlparse(model_url)
    if parsed_url.scheme not in {"https", "http"}:
        raise ValueError("SEGMENTER_MODEL_URL must use http or https")

    destination.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(model_url, destination)


@lru_cache(maxsize=4)
def _get_onnx_session(model_path: str):
    """Return a cached CPU ONNX Runtime session for the given model path."""
    import onnxruntime as ort

    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a supported OpenCV image array to grayscale."""
    if image.ndim == 2:
        return image
    if image.ndim != 3:
        raise ValueError("Segmenter expects a 2D or 3D image array")
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    if image.shape[2] == 1:
        return image[:, :, 0]
    raise ValueError("Segmenter expects 1, 3, or 4 image channels")


def _as_binary_mask(image: np.ndarray) -> np.ndarray:
    """Return a uint8 binary mask with values in {0, 255}."""
    grayscale = _to_grayscale(image)
    normalized = grayscale.astype(np.uint8, copy=False)
    _, binary = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return binary


def _resize_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Resize a mask to its original image shape with nearest-neighbour sampling."""
    height, width = shape
    return cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)


def _sigmoid_if_logits(channel: np.ndarray) -> np.ndarray:
    """Normalize logits or probabilities into a probability map."""
    channel_float = channel.astype(np.float32, copy=False)
    if float(channel_float.min()) < 0.0 or float(channel_float.max()) > 1.0:
        return 1.0 / (1.0 + np.exp(-channel_float))
    return channel_float


def _resolve_segmenter_name(value: object) -> str:
    """Validate the configured segmenter backend name."""
    if value is None:
        return DEFAULT_SEGMENTER
    segmenter = str(value).strip().lower()
    if segmenter not in {ML_SEGMENTER, CLASSIC_SEGMENTER}:
        raise ValueError("segmenter must be either 'ml' or 'classic'")
    return segmenter


def _require_image_array(value: object) -> np.ndarray:
    """Ensure preprocessed context entries are NumPy arrays."""
    if not isinstance(value, np.ndarray):
        raise TypeError("SegmenterStep expects preprocessed images to be NumPy arrays")
    return cast(np.ndarray, value)


def _validate_masks(masks: SegmentationMasks, *, expected_pages: int) -> None:
    """Validate that every semantic label has one mask per page."""
    missing_labels = set(MASK_LABELS).difference(masks)
    if missing_labels:
        raise ValueError(f"Segmenter did not return masks for: {sorted(missing_labels)}")

    for label in MASK_LABELS:
        if len(masks[label]) != expected_pages:
            raise ValueError(f"Segmenter returned an unexpected mask count for {label}")
