"""Tests for ML segmentation model preloading on Celery worker startup (US-030)."""

from __future__ import annotations

import weakref
from collections.abc import Iterator
from pathlib import Path

import pytest
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.pipeline.steps.segmenter import _get_onnx_session
from app.tasks import celery_app as celery_app_module

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_MODEL_PATH = BACKEND_DIR / "models" / "semantic_segmenter.onnx"


@pytest.fixture
def worker_startup_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Isolate settings and ONNX session caches around each startup test."""
    get_settings.cache_clear()
    _get_onnx_session.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()
    _get_onnx_session.cache_clear()


def _send_worker_process_init() -> None:
    """Simulate Celery initializing a worker child process."""
    worker_process_init.send(sender=None)


def _resolve_receivers() -> list[object]:
    """Dereference Celery's weakref-held signal receivers."""
    resolved: list[object] = []
    for _, receiver in worker_process_init.receivers:
        target = receiver() if isinstance(receiver, weakref.ref) else receiver
        if target is not None:
            resolved.append(target)
    return resolved


def test_worker_preload_handler_is_registered_on_worker_process_init() -> None:
    """AC: the model preload is wired into Celery worker startup."""
    assert celery_app_module._preload_segmentation_model in _resolve_receivers()


def test_worker_startup_loads_configured_model_without_errors(
    worker_startup_state: pytest.MonkeyPatch,
) -> None:
    """AC: worker preloads the configured ONNX backend on startup."""
    worker_startup_state.setenv("SEGMENTER_MODEL_PATH", str(BUNDLED_MODEL_PATH))
    worker_startup_state.delenv("SEGMENTER_MODEL_URL", raising=False)

    _send_worker_process_init()

    assert _get_onnx_session.cache_info().currsize == 1


def test_worker_startup_preload_is_cached_per_process(
    worker_startup_state: pytest.MonkeyPatch,
) -> None:
    """Repeated startup signals reuse the process-level ONNX session cache."""
    worker_startup_state.setenv("SEGMENTER_MODEL_PATH", str(BUNDLED_MODEL_PATH))
    worker_startup_state.delenv("SEGMENTER_MODEL_URL", raising=False)

    _send_worker_process_init()
    misses_after_first_load = _get_onnx_session.cache_info().misses

    _send_worker_process_init()

    assert _get_onnx_session.cache_info().currsize == 1
    assert _get_onnx_session.cache_info().misses == misses_after_first_load


def test_worker_startup_is_noop_without_model_config(
    worker_startup_state: pytest.MonkeyPatch,
) -> None:
    """Workers without model configuration start without touching model caches."""
    worker_startup_state.delenv("SEGMENTER_MODEL_PATH", raising=False)
    worker_startup_state.delenv("SEGMENTER_MODEL_URL", raising=False)

    _send_worker_process_init()

    assert _get_onnx_session.cache_info().currsize == 0


def test_worker_startup_with_missing_model_path_does_not_load_session(
    worker_startup_state: pytest.MonkeyPatch,
) -> None:
    """Misconfigured paths are logged by Celery without loading a session.

    Celery signal dispatch swallows handler exceptions (logging them at
    startup), so the worker still boots; the missing model then surfaces as a
    clear FileNotFoundError on any job that selects the ml segmenter.
    """
    missing = BACKEND_DIR / "models" / "does_not_exist.onnx"
    worker_startup_state.setenv("SEGMENTER_MODEL_PATH", str(missing))
    worker_startup_state.delenv("SEGMENTER_MODEL_URL", raising=False)

    _send_worker_process_init()

    assert _get_onnx_session.cache_info().currsize == 0


def test_worker_startup_preloads_torch_bundle_without_touching_onnx_cache(
    worker_startup_state: pytest.MonkeyPatch,
) -> None:
    """Workers preload the Torch Yytsi backend when configured with `.safetensors`."""
    worker_startup_state.setenv("SEGMENTER_MODEL_PATH", "/tmp/models/best.safetensors")
    worker_startup_state.setenv("SEGMENTER_MODEL_CONFIG_PATH", "/tmp/models/config.yaml")
    worker_startup_state.delenv("SEGMENTER_MODEL_URL", raising=False)
    worker_startup_state.delenv("SEGMENTER_MODEL_CONFIG_URL", raising=False)

    calls: list[tuple[str, str]] = []

    def fake_get_yytsi_model(weights_path: str, config_path: str) -> object:
        calls.append((weights_path, config_path))
        return object()

    worker_startup_state.setattr(
        "app.pipeline.steps.segmenter.resolve_yytsi_model_assets",
        lambda **_: (Path("/tmp/models/best.safetensors"), Path("/tmp/models/config.yaml")),
    )
    worker_startup_state.setattr(
        "app.pipeline.steps.segmenter.get_yytsi_model",
        fake_get_yytsi_model,
    )

    _send_worker_process_init()

    assert calls == [("/tmp/models/best.safetensors", "/tmp/models/config.yaml")]
    assert _get_onnx_session.cache_info().currsize == 0
