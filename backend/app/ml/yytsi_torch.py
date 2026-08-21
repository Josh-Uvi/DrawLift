"""Torch-backed floor-plan segmenter for `Yytsi/floorplan-to-3d-walls`.

This backend consumes the published Hugging Face `best.safetensors` +
`config.yaml` bundle and preserves the existing 5-label contract expected by
the rest of the pipeline:

* `walls`, `doors`, `windows` come from the 4-class structural model.
* `rooms` are derived from the predicted structural masks.
* `text` is provisioned heuristically from residual foreground in the
  preprocessed page image, so downstream DXF layers and UI previews keep the
  same stable label set.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import yaml  # type: ignore[import-untyped]

from app.ml.segmentation_model import download_segmentation_model

YYTSI_MODEL_FILENAME = "best.safetensors"
YYTSI_CONFIG_FILENAME = "config.yaml"
YYTSI_MODEL_URL = "https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/best.safetensors"
YYTSI_CONFIG_URL = "https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/config.yaml"

YYTSI_CLASS_NAMES: tuple[str, ...] = ("floor", "wall", "door", "window")
YYTSI_CLASS_TO_ID = {name: index for index, name in enumerate(YYTSI_CLASS_NAMES)}
YYTSI_NUM_CLASSES = len(YYTSI_CLASS_NAMES)
YYTSI_IMAGENET_MEAN = (0.485, 0.456, 0.406)
YYTSI_IMAGENET_STD = (0.229, 0.224, 0.225)
YYTSI_MEAN_RGB_255 = tuple(int(round(channel * 255)) for channel in YYTSI_IMAGENET_MEAN)

MIN_TEXT_COMPONENT_AREA = 8
MAX_TEXT_COMPONENT_AREA = 3_000
MAX_TEXT_DIMENSION_RATIO = 0.35
TEXT_DILATION_KERNEL = np.ones((3, 3), dtype=np.uint8)
STRUCTURE_DILATION_KERNEL = np.ones((5, 5), dtype=np.uint8)


@dataclass(frozen=True)
class YytsiModelConfig:
    """Runtime-relevant subset of the upstream `config.yaml`."""

    image_size: tuple[int, int]
    normalize: bool
    letterbox: bool
    encoder_name: str
    encoder_weights: str | None


@dataclass(frozen=True)
class YytsiBundleValidationReport:
    """Validation result for a Yytsi weights+config bundle."""

    weights_path: Path
    config_path: Path
    image_size: tuple[int, int] | None = None
    class_names: tuple[str, ...] = YYTSI_CLASS_NAMES
    loads_on_cpu: bool = False
    inference_ok: bool = False
    contract_ok: bool = False
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        size = self.image_size if self.image_size is not None else "n/a"
        lines = [
            f"weights path:   {self.weights_path}",
            f"config path:    {self.config_path}",
            f"image size:     {size}",
            f"classes:        {', '.join(self.class_names)}",
            f"cpu load:       {self.loads_on_cpu}",
            f"inference:      {'ok' if self.inference_ok else 'failed'}",
            f"5-class bridge: {'ok' if self.contract_ok else 'failed'}",
        ]
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {error}" for error in self.errors)
        return "\n".join(lines)


def infer_yytsi_config_url(model_url: str) -> str:
    """Infer the companion config URL from a published weights URL."""
    if model_url.endswith(YYTSI_MODEL_FILENAME):
        return model_url[: -len(YYTSI_MODEL_FILENAME)] + YYTSI_CONFIG_FILENAME
    return YYTSI_CONFIG_URL


def resolve_yytsi_model_assets(
    *,
    model_path: Path | str,
    config_path: Path | str | None = None,
    model_url: str | None = None,
    config_url: str | None = None,
) -> tuple[Path, Path]:
    """Resolve/download the Yytsi weights and config bundle."""
    weights_path = Path(model_path).expanduser().resolve()
    resolved_config_path = (
        Path(config_path).expanduser().resolve()
        if config_path is not None
        else weights_path.with_name(YYTSI_CONFIG_FILENAME)
    )

    if not weights_path.exists():
        download_segmentation_model(model_url or YYTSI_MODEL_URL, weights_path)
    if not resolved_config_path.exists():
        download_segmentation_model(
            config_url or infer_yytsi_config_url(model_url or YYTSI_MODEL_URL),
            resolved_config_path,
        )
    return weights_path, resolved_config_path


def load_yytsi_config(config_path: Path | str) -> YytsiModelConfig:
    """Load the upstream YAML config used by the published weights."""
    raw = yaml.safe_load(Path(config_path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("Yytsi config.yaml must deserialize to a mapping")
    data = raw.get("data", {})
    model = raw.get("model", {})
    if not isinstance(data, dict) or not isinstance(model, dict):
        raise ValueError("Yytsi config.yaml is missing the `data` or `model` section")

    image_size = data.get("image_size", [512, 512])
    if not isinstance(image_size, Sequence) or len(image_size) != 2:
        raise ValueError("Yytsi config.yaml must define data.image_size as [H, W]")

    encoder_weights = model.get("encoder_weights")
    if encoder_weights is not None and not isinstance(encoder_weights, str):
        raise ValueError("Yytsi config.yaml model.encoder_weights must be a string or null")

    return YytsiModelConfig(
        image_size=(int(image_size[0]), int(image_size[1])),
        normalize=bool(data.get("normalize", True)),
        letterbox=bool(data.get("letterbox", True)),
        encoder_name=str(model.get("encoder_name", "resnet34")),
        encoder_weights=encoder_weights,
    )


def validate_yytsi_bundle(
    *,
    weights_path: Path | str,
    config_path: Path | str,
    input_size: tuple[int, int] | int | None = None,
) -> YytsiBundleValidationReport:
    """Validate the Yytsi weights/config bundle for CPU inference use."""
    import torch

    resolved_weights = Path(weights_path).expanduser().resolve()
    resolved_config = Path(config_path).expanduser().resolve()
    errors: list[str] = []
    if not resolved_weights.is_file():
        errors.append(f"weights file not found: {resolved_weights}")
    if not resolved_config.is_file():
        errors.append(f"config file not found: {resolved_config}")
    if errors:
        return YytsiBundleValidationReport(
            weights_path=resolved_weights,
            config_path=resolved_config,
            errors=tuple(errors),
        )

    config = load_yytsi_config(resolved_config)
    requested_size = (
        config.image_size
        if input_size is None
        else ((input_size, input_size) if isinstance(input_size, int) else input_size)
    )
    if tuple(requested_size) != tuple(config.image_size):
        errors.append(
            f"configured input size {requested_size[0]}x{requested_size[1]} does not match "
            f"bundle config {config.image_size[0]}x{config.image_size[1]}"
        )

    try:
        model = get_yytsi_model(str(resolved_weights), str(resolved_config))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"failed to load Torch model bundle: {exc}")
        return YytsiBundleValidationReport(
            weights_path=resolved_weights,
            config_path=resolved_config,
            image_size=config.image_size,
            errors=tuple(errors),
        )

    inference_ok = False
    contract_ok = False
    try:
        sample = torch.zeros(
            (1, 3, config.image_size[0], config.image_size[1]),
            dtype=torch.float32,
        )
        logits = model(sample)
        expected_shape = (
            1,
            YYTSI_NUM_CLASSES,
            config.image_size[0],
            config.image_size[1],
        )
        if tuple(logits.shape) != expected_shape:
            errors.append(
                f"unexpected logits shape {tuple(logits.shape)} for image size {config.image_size}"
            )
        else:
            inference_ok = True
            contract_ok = True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Torch inference failed: {exc}")

    return YytsiBundleValidationReport(
        weights_path=resolved_weights,
        config_path=resolved_config,
        image_size=config.image_size,
        loads_on_cpu=True,
        inference_ok=inference_ok,
        contract_ok=contract_ok and not errors,
        errors=tuple(errors),
    )


@lru_cache(maxsize=1)
def get_yytsi_model(weights_path: str, config_path: str):
    """Load the published Yytsi segmentation model into process-local cache."""
    import segmentation_models_pytorch as smp
    from safetensors.torch import load_file

    config = load_yytsi_config(config_path)
    model = smp.Unet(
        encoder_name=config.encoder_name,
        encoder_weights=config.encoder_weights,
        in_channels=3,
        classes=YYTSI_NUM_CLASSES,
    )
    state_dict = load_file(str(weights_path), device="cpu")
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


def prepare_yytsi_input(
    image: np.ndarray,
    *,
    image_size: tuple[int, int],
    normalize: bool,
    letterbox: bool,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Convert a grayscale/binary page image into model-ready RGB CHW float32.

    Returns `(tensor_chw, content_rect)` where `content_rect` is
    `(left, top, inner_w, inner_h)` in the letterboxed canvas.
    """
    grayscale = _to_grayscale(image)
    binary = (grayscale > 0).astype(np.uint8)
    height, width = image_size

    if letterbox:
        scale = min(width / grayscale.shape[1], height / grayscale.shape[0])
        inner_w = max(1, int(round(grayscale.shape[1] * scale)))
        inner_h = max(1, int(round(grayscale.shape[0] * scale)))
    else:
        inner_w, inner_h = width, height

    rgb = np.full((inner_h, inner_w, 3), YYTSI_MEAN_RGB_255, dtype=np.uint8)
    resized = cv2.resize(binary, (inner_w, inner_h), interpolation=cv2.INTER_AREA)
    rgb[resized > 0] = (0, 0, 0)

    top = (height - inner_h) // 2
    left = (width - inner_w) // 2
    canvas = np.full((height, width, 3), YYTSI_MEAN_RGB_255, dtype=np.uint8)
    canvas[top : top + inner_h, left : left + inner_w] = rgb

    tensor = canvas.astype(np.float32) / np.float32(255.0)
    if normalize:
        mean = np.asarray(YYTSI_IMAGENET_MEAN, dtype=np.float32).reshape(1, 1, 3)
        std = np.asarray(YYTSI_IMAGENET_STD, dtype=np.float32).reshape(1, 1, 3)
        tensor = (tensor - mean) / std
    chw = np.moveaxis(tensor, -1, 0)
    return chw, (left, top, inner_w, inner_h)


def decode_yytsi_predictions(
    *,
    class_map: np.ndarray,
    original_image: np.ndarray,
    original_shape: tuple[int, int],
    content_rect: tuple[int, int, int, int],
    mask_labels: Sequence[str],
) -> dict[str, list[np.ndarray]]:
    """Convert the 4-class Yytsi output into the pipeline's 5-label contract."""
    left, top, inner_w, inner_h = content_rect
    crop = class_map[top : top + inner_h, left : left + inner_w]
    resized_class_map = cv2.resize(
        crop.astype(np.uint8),
        (original_shape[1], original_shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )

    masks: dict[str, list[np.ndarray]] = {label: [] for label in mask_labels}
    wall_mask = (resized_class_map == YYTSI_CLASS_TO_ID["wall"]).astype(np.uint8) * 255
    door_mask = (resized_class_map == YYTSI_CLASS_TO_ID["door"]).astype(np.uint8) * 255
    window_mask = (resized_class_map == YYTSI_CLASS_TO_ID["window"]).astype(np.uint8) * 255
    floor_mask = (resized_class_map == YYTSI_CLASS_TO_ID["floor"]).astype(np.uint8) * 255
    room_mask = derive_room_mask(floor_mask, wall_mask, door_mask, window_mask)
    text_mask = detect_text_regions(original_image, wall_mask, door_mask, window_mask)

    masks["walls"].append(wall_mask)
    masks["doors"].append(door_mask)
    masks["windows"].append(window_mask)
    masks["rooms"].append(room_mask)
    masks["text"].append(text_mask)
    return masks


def derive_room_mask(
    floor_mask: np.ndarray,
    wall_mask: np.ndarray,
    door_mask: np.ndarray,
    window_mask: np.ndarray,
) -> np.ndarray:
    """Derive room regions from structural masks while keeping interior floor."""
    structure = cv2.bitwise_or(wall_mask, cv2.bitwise_or(door_mask, window_mask))
    sealed_walls = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, STRUCTURE_DILATION_KERNEL)
    candidate_rooms = cv2.bitwise_not(sealed_walls)
    height, width = candidate_rooms.shape
    flood_filled = candidate_rooms.copy()
    flood_mask = np.zeros((height + 2, width + 2), dtype=np.uint8)
    cv2.floodFill(flood_filled, flood_mask, (0, 0), 0)
    rooms = cv2.bitwise_and(flood_filled, floor_mask)
    rooms = cv2.bitwise_and(rooms, cv2.bitwise_not(structure))
    return cv2.morphologyEx(rooms, cv2.MORPH_OPEN, TEXT_DILATION_KERNEL)


def detect_text_regions(
    image: np.ndarray,
    wall_mask: np.ndarray,
    door_mask: np.ndarray,
    window_mask: np.ndarray,
) -> np.ndarray:
    """Heuristically recover text regions from residual page foreground."""
    grayscale = _to_grayscale(image)
    foreground = ((grayscale > 0).astype(np.uint8)) * 255
    structure = cv2.bitwise_or(wall_mask, cv2.bitwise_or(door_mask, window_mask))
    structure_buffer = cv2.dilate(structure, STRUCTURE_DILATION_KERNEL)
    residual = cv2.bitwise_and(
        foreground,
        cv2.bitwise_not(structure_buffer),
    )

    component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        (residual > 0).astype(np.uint8), connectivity=8
    )
    text_mask = np.zeros_like(foreground, dtype=np.uint8)
    max_width = residual.shape[1] * MAX_TEXT_DIMENSION_RATIO
    max_height = residual.shape[0] * MAX_TEXT_DIMENSION_RATIO
    for component_index in range(1, component_count):
        area = int(stats[component_index, cv2.CC_STAT_AREA])
        width = int(stats[component_index, cv2.CC_STAT_WIDTH])
        height = int(stats[component_index, cv2.CC_STAT_HEIGHT])
        if area < MIN_TEXT_COMPONENT_AREA or area > MAX_TEXT_COMPONENT_AREA:
            continue
        if width <= 1 or height <= 1:
            continue
        if width > max_width or height > max_height:
            continue
        text_mask[labels == component_index] = 255
    return cv2.dilate(text_mask, TEXT_DILATION_KERNEL)


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
