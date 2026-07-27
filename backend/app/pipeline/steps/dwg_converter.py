"""DWG conversion post-processor for generated DXF outputs."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep


class DwgConverterStep(PipelineStep):
    """Convert the generated DXF into a true DWG using an external CAD converter.

    The production path is intentionally external because DWG is a proprietary
    binary format. The step supports either a custom command template via
    ``DWG_CONVERTER_COMMAND`` or common converter binaries made available by a
    Docker sidecar / shared volume setup.
    """

    name = "DWG Converter"
    progress = 98

    def __init__(self, output_path: Path | str | None = None, command: str | None = None) -> None:
        self.output_path = Path(output_path) if output_path is not None else None
        self.command = command

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Convert ``context.output_path`` from DXF to DWG and store metadata."""
        dxf_path = self._resolve_dxf_path(context)
        dwg_path = self.output_path or dxf_path.with_suffix(".dwg")
        dwg_path.parent.mkdir(parents=True, exist_ok=True)

        self._run_converter(dxf_path=dxf_path, dwg_path=dwg_path)

        if not dwg_path.is_file() or dwg_path.stat().st_size == 0:
            raise RuntimeError(f"DWG converter did not produce a valid file at {dwg_path}")

        context.metadata["dwg_path"] = dwg_path
        context.metadata["dwg_converter"] = self._configured_command_display()
        context.publish_progress(
            status="processing",
            progress=98,
            step=self.name,
            message=f"Wrote DWG output to {dwg_path.name}",
        )
        return context

    def _resolve_dxf_path(self, context: PipelineContext) -> Path:
        output_path = context.output_path or context.metadata.get("output_path")
        if output_path is None:
            raise ValueError("DwgConverterStep requires a DXF output path on the context")
        dxf_path = Path(str(output_path)).resolve()
        if dxf_path.suffix.lower() != ".dxf" or not dxf_path.is_file():
            raise ValueError(f"DwgConverterStep expected an existing DXF file, got {dxf_path}")
        return dxf_path

    def _run_converter(self, *, dxf_path: Path, dwg_path: Path) -> None:
        command = self.command or os.getenv("DWG_CONVERTER_COMMAND")
        if command:
            self._run_command(_format_command(command, dxf_path=dxf_path, dwg_path=dwg_path))
            return

        attempted: list[str] = []
        for candidate in _default_converter_commands(dxf_path=dxf_path, dwg_path=dwg_path):
            attempted.append(" ".join(candidate))
            try:
                self._run_command(candidate)
                return
            except FileNotFoundError:
                continue

        raise RuntimeError(
            "No DWG converter is available. Install libredwg's `dwgwrite`, ODA FileConverter, "
            "or set DWG_CONVERTER_COMMAND. Attempted: " + "; ".join(attempted)
        )

    def _run_command(self, command: list[str]) -> None:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            stdout = completed.stdout.strip()
            details = stderr or stdout or f"exit code {completed.returncode}"
            raise RuntimeError(f"DWG conversion failed: {details}")

    def _configured_command_display(self) -> str:
        return self.command or os.getenv("DWG_CONVERTER_COMMAND") or "auto-detect"


def _format_command(command: str, *, dxf_path: Path, dwg_path: Path) -> list[str]:
    """Expand a converter command template into argv tokens."""
    values: dict[str, Any] = {
        "input": str(dxf_path),
        "output": str(dwg_path),
        "input_dir": str(dxf_path.parent),
        "output_dir": str(dwg_path.parent),
        "stem": dxf_path.stem,
    }
    return [part.format(**values) for part in shlex.split(command)]


def _default_converter_commands(*, dxf_path: Path, dwg_path: Path) -> list[list[str]]:
    """Return supported converter command candidates in preference order."""
    return [
        ["dwgwrite", str(dxf_path), str(dwg_path)],
        [
            "ODAFileConverter",
            str(dxf_path.parent),
            str(dwg_path.parent),
            "ACAD2018",
            "DWG",
            "0",
            "1",
            dxf_path.name,
        ],
    ]
