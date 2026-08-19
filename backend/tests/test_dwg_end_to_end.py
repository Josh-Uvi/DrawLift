"""End-to-end DWG conversion tests for the GNU LibreDWG sidecar (US-032)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.pipeline import DwgConverterStep, DxfWriterStep, PipelineContext
from app.pipeline.primitives import (
    OpeningPrimitive,
    Point,
    RoomPrimitive,
    TextPrimitive,
    WallPrimitive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
LIBREDWG_IMAGE_TAG = "drawlift-libredwg:test"


def dxf_primitives() -> list[object]:
    """Return primitives spanning all semantic DXF layers."""
    return [
        WallPrimitive(start=Point(0, 0), end=Point(100, 0), thickness=5),
        OpeningPrimitive(kind="door", insertion=Point(20, 0), width=12, height=4),
        OpeningPrimitive(kind="window", insertion=Point(70, 0), width=20, height=3),
        RoomPrimitive(polygon=(Point(0, 10), Point(100, 10), Point(100, 80), Point(0, 80))),
        TextPrimitive(insertion=Point(10, 20), width=20, height=5, value="Room"),
    ]


def _write_stub_converter(path: Path) -> Path:
    """Write a tiny converter that copies the DXF into a DWG-like file."""
    path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'infile="$1"\n'
        'outfile="$2"\n'
        "printf 'AC1027\\0DWG' > \"$outfile\"\n"
        'cat "$infile" >> "$outfile"\n',
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _build_pipeline_context(tmp_path: Path) -> tuple[PipelineContext, Path, Path]:
    """Create a DXF via the real writer step and return DWG conversion inputs."""
    dxf_path = tmp_path / "output.dxf"
    dwg_path = tmp_path / "output.dwg"
    context = PipelineContext(
        job_id="job-dwg-e2e",
        input_path=tmp_path / "input.pdf",
        primitives=dxf_primitives(),
    )
    DxfWriterStep(output_path=dxf_path).execute(context)
    return context, dxf_path, dwg_path


def test_pipeline_dxf_to_dwg_end_to_end_with_converter_command(tmp_path: Path) -> None:
    """T-107: the full DXF->DWG step succeeds with a real external command.

    This test covers the application-level end-to-end behavior in CI without
    depending on Docker by using a tiny local converter script as the external
    CAD tool.
    """
    context, dxf_path, dwg_path = _build_pipeline_context(tmp_path)
    converter = _write_stub_converter(tmp_path / "fake-dwgwrite.sh")

    result = DwgConverterStep(
        output_path=dwg_path,
        command=f"{converter} {{input}} {{output}}",
    ).execute(context)

    assert result.metadata["dwg_path"] == dwg_path
    assert result.metadata["dwg_converter"] == f"{converter} {{input}} {{output}}"
    assert dwg_path.is_file()
    assert dwg_path.read_bytes().startswith(b"AC1027\x00DWG")
    assert dxf_path.is_file(), "DXF is preserved alongside DWG for download helpers"


def _ensure_docker_available() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI is not installed")
    try:
        subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"docker is unavailable: {exc}")


def test_libredwg_image_builds_and_converts_dxf_to_dwg(tmp_path: Path) -> None:
    """T-107: real GNU LibreDWG sidecar converts a generated DXF into DWG.

    The test is opt-in because it performs a source build inside Docker.
    Set RUN_DOCKER_TESTS=1 to execute it. The DXF is staged in a repo-local
    `.tmp-docker-tests/` mount path so the container can reliably access it.
    """
    if os.getenv("RUN_DOCKER_TESTS") != "1":
        pytest.skip("set RUN_DOCKER_TESTS=1 to run Docker/libredwg integration tests")

    _ensure_docker_available()

    build = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(BACKEND_DIR / "Dockerfile.libredwg"),
            "-t",
            LIBREDWG_IMAGE_TAG,
            str(BACKEND_DIR),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert build.returncode == 0, build.stderr or build.stdout

    context, dxf_path, dwg_path = _build_pipeline_context(tmp_path)
    shared_root = REPO_ROOT / ".tmp-docker-tests"
    shared_root.mkdir(exist_ok=True)
    docker_mount = Path(tempfile.mkdtemp(prefix="us032-dwg-", dir=shared_root))
    mounted_dxf = docker_mount / dxf_path.name
    mounted_dwg = docker_mount / dwg_path.name
    shutil.copy2(dxf_path, mounted_dxf)

    command = (
        "docker run --rm "
        f"-v {docker_mount}:/work "
        f"{LIBREDWG_IMAGE_TAG} "
        f"/opt/libredwg/bin/dxf2dwg -y -o /work/{mounted_dwg.name} /work/{mounted_dxf.name}"
    )
    try:
        result = DwgConverterStep(output_path=mounted_dwg, command=command).execute(context)

        assert result.metadata["dwg_path"] == mounted_dwg
        assert mounted_dwg.is_file()
        shutil.copy2(mounted_dwg, dwg_path)
        assert dwg_path.is_file()
        assert dwg_path.stat().st_size > 0
        header = dwg_path.read_bytes()[:6]
        assert header.startswith(b"AC10")
    finally:
        shutil.rmtree(docker_mount, ignore_errors=True)
