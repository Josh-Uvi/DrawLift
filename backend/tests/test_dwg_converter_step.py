"""Tests for the DWG converter pipeline step."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.pipeline.context import PipelineContext
from app.pipeline.steps.dwg_converter import (
    DwgConverterStep,
    _default_converter_commands,
    _format_command,
)


def test_dwg_converter_runs_configured_command_and_records_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured converter command creates a DWG alongside the DXF."""
    dxf_path = tmp_path / "output.dxf"
    dxf_path.write_text("0\nSECTION\n2\nEOF\n", encoding="utf-8")
    dwg_path = tmp_path / "output.dwg"
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        dwg_path.write_bytes(b"AC1027\x00DWG")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.pipeline.steps.dwg_converter.subprocess.run", fake_run)
    context = PipelineContext(job_id="job-123", input_path=tmp_path / "input.pdf")
    context.output_path = dxf_path

    result = DwgConverterStep(
        output_path=dwg_path,
        command="dwgwrite {input} {output}",
    ).execute(context)

    assert result is context
    assert commands == [["dwgwrite", str(dxf_path.resolve()), str(dwg_path)]]
    assert context.metadata["dwg_path"] == dwg_path
    assert dwg_path.read_bytes().startswith(b"AC1027")


def test_dwg_converter_surfaces_command_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing converter returns an actionable RuntimeError."""
    dxf_path = tmp_path / "output.dxf"
    dxf_path.write_text("DXF", encoding="utf-8")

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, "", "invalid input")

    monkeypatch.setattr("app.pipeline.steps.dwg_converter.subprocess.run", fake_run)
    context = PipelineContext(job_id="job-123", input_path=tmp_path / "input.pdf")
    context.output_path = dxf_path

    with pytest.raises(RuntimeError, match="DWG conversion failed"):
        DwgConverterStep(command="dwgwrite {input} {output}").execute(context)


def test_format_command_expands_documented_placeholders(tmp_path: Path) -> None:
    """Operators can use stable placeholders in DWG converter commands."""
    dxf_path = tmp_path / "output.dxf"
    dwg_path = tmp_path / "output.dwg"

    command = _format_command(
        "converter --in {input} --out {output} --stem {stem}",
        dxf_path=dxf_path,
        dwg_path=dwg_path,
    )

    assert command == [
        "converter",
        "--in",
        str(dxf_path),
        "--out",
        str(dwg_path),
        "--stem",
        "output",
    ]


def test_default_converter_commands_prefer_libredwg_dxftodwg(tmp_path: Path) -> None:
    """LibreDWG's official DXF -> DWG tools are preferred before ODA fallback."""
    dxf_path = tmp_path / "output.dxf"
    dwg_path = tmp_path / "output.dwg"

    commands = _default_converter_commands(dxf_path=dxf_path, dwg_path=dwg_path)

    assert commands[0] == ["dxf2dwg", "-y", "-o", str(dwg_path), str(dxf_path)]
    assert commands[1] == ["dwgwrite", "-y", "-o", str(dwg_path), str(dxf_path)]


def test_dwg_converter_auto_detects_libredwg_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no command is configured, the step tries LibreDWG CLI tools first."""
    dxf_path = tmp_path / "output.dxf"
    dxf_path.write_text("0\nSECTION\n2\nEOF\n", encoding="utf-8")
    dwg_path = tmp_path / "output.dwg"
    seen: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[0] == "dxf2dwg":
            dwg_path.write_bytes(b"AC1015\x00DWG")
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected fallback command: {command}")

    monkeypatch.setattr("app.pipeline.steps.dwg_converter.subprocess.run", fake_run)
    context = PipelineContext(job_id="job-123", input_path=tmp_path / "input.pdf")
    context.output_path = dxf_path

    result = DwgConverterStep(output_path=dwg_path).execute(context)

    assert result.metadata["dwg_converter"] == "auto-detect"
    assert seen == [["dxf2dwg", "-y", "-o", str(dwg_path), str(dxf_path.resolve())]]
