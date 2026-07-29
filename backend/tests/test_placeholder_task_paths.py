"""Tests for worker-persisted storage paths."""

from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

from app.tasks import placeholder


def test_portable_storage_path_keeps_relative_storage_paths(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Hybrid local workers persist paths the host API can resolve too."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        placeholder,
        "get_settings",
        lambda: SimpleNamespace(STORAGE_PATH="storage"),
    )

    output_path = tmp_path / "storage" / "job-1" / "output" / "output.dxf"
    output_path.parent.mkdir(parents=True)
    output_path.touch()

    assert placeholder.portable_storage_path(output_path) == "storage/job-1/output/output.dxf"


def test_portable_storage_path_keeps_absolute_storage_paths(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """All-Docker/absolute storage configurations keep absolute paths."""
    storage_path = tmp_path / "storage"
    monkeypatch.setattr(
        placeholder,
        "get_settings",
        lambda: SimpleNamespace(STORAGE_PATH=str(storage_path)),
    )

    output_path = storage_path / "job-1" / "output" / "output.dxf"
    output_path.parent.mkdir(parents=True)
    output_path.touch()

    assert placeholder.portable_storage_path(output_path) == str(output_path)


def test_portable_storage_path_keeps_paths_outside_storage(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Unexpected paths outside storage are not rewritten."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        placeholder,
        "get_settings",
        lambda: SimpleNamespace(STORAGE_PATH="storage"),
    )

    outside_path = tmp_path / "elsewhere" / "output.dxf"

    assert placeholder.portable_storage_path(outside_path) == str(outside_path)
