"""Tests for ML segmentation model environment wiring (US-030, T-098).

``yaml`` is available because ``pre-commit==4.*`` (pinned in requirements.txt)
depends on PyYAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

CONTAINER_MODEL_PATH_DEFAULT = "/app/models/semantic_segmenter.onnx"


def _active_env_example_values() -> dict[str, str]:
    """Parse uncommented key=value pairs from .env.example."""
    values: dict[str, str] = {}
    for raw_line in ENV_EXAMPLE_PATH.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _compose_environment(service_name: str) -> dict[str, str]:
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    environment = compose["services"][service_name]["environment"]
    assert isinstance(environment, dict)
    return environment


def test_env_example_sets_segmenter_model_path() -> None:
    """AC: SEGMENTER_MODEL_PATH is set in .env.example for the bundled model."""
    values = _active_env_example_values()

    assert values.get("SEGMENTER_MODEL_PATH") == "./models/semantic_segmenter.onnx"


def test_env_example_sets_segmenter_model_url_fallback() -> None:
    """AC: SEGMENTER_MODEL_URL is set as an https auto-download fallback."""
    values = _active_env_example_values()

    model_url = values.get("SEGMENTER_MODEL_URL", "")
    assert model_url.startswith("https://")
    assert model_url.endswith("semantic_segmenter.onnx")


@pytest.mark.parametrize("service_name", ["backend", "worker", "beat"])
def test_compose_services_configure_segmenter_model_env(service_name: str) -> None:
    """AC: Docker services receive model path and download-fallback config."""
    environment = _compose_environment(service_name)

    path_value = environment.get("SEGMENTER_MODEL_PATH", "")
    url_value = environment.get("SEGMENTER_MODEL_URL", "")

    assert CONTAINER_MODEL_PATH_DEFAULT in path_value
    assert path_value.startswith("${SEGMENTER_MODEL_PATH:-")
    assert url_value.startswith("${SEGMENTER_MODEL_URL:-https://")
    assert url_value.endswith("semantic_segmenter.onnx}")


def test_compose_worker_mounts_models_volume() -> None:
    """The worker model path lives on the shared models volume."""
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    worker_volumes = compose["services"]["worker"]["volumes"]

    assert any(str(volume).endswith(":/app/models") for volume in worker_volumes)


def test_settings_expose_segmenter_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings surface SEGMENTER_MODEL_PATH/URL from the environment."""
    monkeypatch.setenv("SEGMENTER_MODEL_PATH", "./models/semantic_segmenter.onnx")
    monkeypatch.setenv("SEGMENTER_MODEL_URL", "https://example.com/semantic_segmenter.onnx")
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.SEGMENTER_MODEL_PATH == "./models/semantic_segmenter.onnx"
        assert settings.SEGMENTER_MODEL_URL == "https://example.com/semantic_segmenter.onnx"
    finally:
        get_settings.cache_clear()
