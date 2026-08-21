"""Tests for the Docker-bundled Yytsi Torch segmenter path."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ml.yytsi_torch import (
    YYTSI_CONFIG_FILENAME,
    YYTSI_MEAN_RGB_255,
    YytsiModelConfig,
    decode_yytsi_predictions,
    infer_yytsi_config_url,
    load_yytsi_config,
    prepare_yytsi_input,
    resolve_yytsi_model_assets,
)
from app.pipeline.steps.segmenter import MASK_LABELS, TorchYytsiSegmenter


def _write_config(path: Path, *, image_size: tuple[int, int] = (512, 512)) -> Path:
    path.write_text(
        "data:\n"
        f"  image_size: [{image_size[0]}, {image_size[1]}]\n"
        "  normalize: true\n"
        "  letterbox: true\n"
        "model:\n"
        "  encoder_name: resnet34\n"
        "  encoder_weights: imagenet\n",
        encoding="utf-8",
    )
    return path


def _preprocessed_floor_plan() -> np.ndarray:
    image = np.zeros((240, 320), dtype=np.uint8)
    # structural foreground (white on black, like OpenCVPreprocessor output)
    image[30:210, 30:36] = 255
    image[30:210, 284:290] = 255
    image[30:36, 30:290] = 255
    image[204:210, 30:290] = 255
    image[80:86, 160:220] = 255
    # text-like blobs away from walls/openings
    image[180:188, 90:110] = 255
    image[180:188, 116:136] = 255
    return image


def test_infer_yytsi_config_url_swaps_weights_filename() -> None:
    url = "https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/best.safetensors"

    assert infer_yytsi_config_url(url).endswith("/config.yaml")


def test_load_yytsi_config_reads_runtime_fields(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / YYTSI_CONFIG_FILENAME, image_size=(512, 512))

    config = load_yytsi_config(config_path)

    assert config == YytsiModelConfig(
        image_size=(512, 512),
        normalize=True,
        letterbox=True,
        encoder_name="resnet34",
        encoder_weights="imagenet",
    )


def test_prepare_yytsi_input_letterboxes_binary_foreground() -> None:
    image = _preprocessed_floor_plan()

    chw, rect = prepare_yytsi_input(
        image,
        image_size=(512, 512),
        normalize=False,
        letterbox=True,
    )

    assert chw.shape == (3, 512, 512)
    left, top, inner_w, inner_h = rect
    assert inner_w == 512
    assert inner_h < 512
    background_value = np.asarray(YYTSI_MEAN_RGB_255, dtype=np.float32) / 255.0
    assert np.allclose(chw[:, 0, 0], background_value, atol=1e-3)
    assert np.min(chw[:, top : top + inner_h, left : left + inner_w]) == 0.0


def test_decode_yytsi_predictions_preserves_five_label_contract() -> None:
    class_map = np.zeros((512, 512), dtype=np.uint8)  # floor background
    class_map[40:470, 40:48] = 1  # wall
    class_map[40:470, 464:472] = 1
    class_map[40:48, 40:472] = 1
    class_map[464:472, 40:472] = 1
    class_map[180:200, 248:292] = 2  # door
    class_map[56:72, 312:392] = 3  # window

    masks = decode_yytsi_predictions(
        class_map=class_map,
        original_image=_preprocessed_floor_plan(),
        original_shape=(240, 320),
        content_rect=(0, 64, 512, 384),
        mask_labels=MASK_LABELS,
    )

    assert set(masks) == set(MASK_LABELS)
    for label in MASK_LABELS:
        assert len(masks[label]) == 1
        assert masks[label][0].shape == (240, 320)
        assert np.count_nonzero(masks[label][0]) > 0, f"missing {label}"


def test_resolve_yytsi_model_assets_downloads_config_beside_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloads: list[tuple[str, Path]] = []

    def fake_download(url: str, destination: Path | str) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stub", encoding="utf-8")
        downloads.append((url, path))
        return path

    monkeypatch.setattr("app.ml.yytsi_torch.download_segmentation_model", fake_download)

    weights_path, config_path = resolve_yytsi_model_assets(
        model_path=tmp_path / "best.safetensors",
        model_url="https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/best.safetensors",
    )

    assert weights_path.is_file()
    assert config_path.is_file()
    assert config_path.name == "config.yaml"
    assert downloads[0][0].endswith("best.safetensors")
    assert downloads[1][0].endswith("config.yaml")


def test_torch_segmenter_uses_config_image_size_when_input_size_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import torch

    weights_path = tmp_path / "best.safetensors"
    weights_path.write_text("weights", encoding="utf-8")
    config_path = _write_config(tmp_path / "config.yaml", image_size=(512, 512))

    class FakeModel:
        def eval(self) -> FakeModel:
            return self

        def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
            _, _channels, height, width = tensor.shape
            output = torch.zeros((1, 4, height, width), dtype=torch.float32)
            output[:, 1, 100:420, 60:68] = 10.0  # left wall
            output[:, 1, 100:420, 444:452] = 10.0  # right wall
            output[:, 1, 100:108, 60:452] = 10.0  # top wall
            output[:, 1, 412:420, 60:452] = 10.0  # bottom wall
            output[:, 2, 220:250, 220:280] = 10.0  # door
            output[:, 3, 140:156, 300:380] = 10.0  # window
            return output

    monkeypatch.setattr(
        "app.pipeline.steps.segmenter.get_yytsi_model",
        lambda weights, config: FakeModel(),
    )

    segmenter = TorchYytsiSegmenter(model_path=weights_path, config_path=config_path)
    masks = segmenter.segment([_preprocessed_floor_plan()])

    assert set(masks) == set(MASK_LABELS)
    assert np.count_nonzero(masks["walls"][0]) > 0
    assert np.count_nonzero(masks["doors"][0]) > 0
    assert np.count_nonzero(masks["windows"][0]) > 0
    assert np.count_nonzero(masks["rooms"][0]) > 0
    assert np.count_nonzero(masks["text"][0]) > 0
