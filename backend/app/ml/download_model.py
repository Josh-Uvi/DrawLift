"""Command-line tool to download or provision the ONNX segmentation model.

Examples:
    # Provision the bundled reference model into MODELS_PATH
    python -m app.ml.download_model

    # Download a trained model from a URL into a specific directory
    python -m app.ml.download_model --url https://example.com/model.onnx \
        --models-dir ./models

    # Validate an existing model without provisioning
    python -m app.ml.download_model --check
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from app.core.config import get_settings
from app.ml.segmentation_model import (
    SEGMENTATION_MODEL_FILENAME,
    ModelProvisioningError,
    check_model_input_size,
    provision_segmentation_model,
    validate_segmentation_model,
)
from app.ml.yytsi_torch import (
    YYTSI_CONFIG_FILENAME,
    resolve_yytsi_model_assets,
    validate_yytsi_bundle,
)


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.download_model",
        description="Download or provision the floor-plan segmentation ONNX model.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Model download URL (falls back to SEGMENTER_MODEL_URL when omitted)",
    )
    parser.add_argument(
        "--models-dir",
        default=None,
        help="Destination directory (defaults to MODELS_PATH)",
    )
    parser.add_argument(
        "--filename",
        default=SEGMENTATION_MODEL_FILENAME,
        help=f"Model file name (default: {SEGMENTATION_MODEL_FILENAME})",
    )
    parser.add_argument(
        "--config-filename",
        default=YYTSI_CONFIG_FILENAME,
        help=f"Companion config filename for multi-file bundles (default: {YYTSI_CONFIG_FILENAME})",
    )
    parser.add_argument(
        "--config-url",
        default=None,
        help="Optional config download URL for multi-file model bundles",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-provision even when a valid model already exists",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only validate an existing model file; do not provision",
    )
    parser.add_argument(
        "--probe-size",
        type=int,
        default=64,
        help="Spatial size of the validation inference probe (default: 64)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the model provisioning CLI and return a process exit code."""
    args = build_arg_parser().parse_args(argv)
    settings = get_settings()
    models_dir = Path(args.models_dir) if args.models_dir else Path(settings.MODELS_PATH)
    destination = models_dir / args.filename
    config_destination = models_dir / args.config_filename

    is_yytsi_bundle = destination.suffix.lower() == ".safetensors"

    if args.check:
        if is_yytsi_bundle:
            yytsi_report = validate_yytsi_bundle(
                weights_path=destination,
                config_path=config_destination,
                input_size=settings.SEGMENTER_MODEL_INPUT_SIZE,
            )
            print(yytsi_report.summary())
            print("result: PASS" if yytsi_report.passed else "result: FAIL")
            return 0 if yytsi_report.passed else 1
        onnx_report = validate_segmentation_model(destination, probe_size=args.probe_size)
        print(onnx_report.summary())
        input_size_report = check_model_input_size(destination, settings.SEGMENTER_MODEL_INPUT_SIZE)
        configured_size = settings.SEGMENTER_MODEL_INPUT_SIZE
        print(
            f"input size: ({configured_size}, {configured_size}) — " f"{input_size_report.reason}"
        )
        passed = onnx_report.passed and input_size_report.compatible
        print("result: PASS" if passed else "result: FAIL")
        return 0 if passed else 1

    model_url = args.url or settings.SEGMENTER_MODEL_URL
    try:
        if is_yytsi_bundle:
            if args.force:
                destination.unlink(missing_ok=True)
                config_destination.unlink(missing_ok=True)
            path, config_path = resolve_yytsi_model_assets(
                model_path=destination,
                config_path=config_destination,
                model_url=model_url,
                config_url=args.config_url or settings.SEGMENTER_MODEL_CONFIG_URL,
            )
            yytsi_report = validate_yytsi_bundle(
                weights_path=path,
                config_path=config_path,
                input_size=settings.SEGMENTER_MODEL_INPUT_SIZE,
            )
            if not yytsi_report.passed:
                raise ModelProvisioningError(yytsi_report.summary())
            print(yytsi_report.summary())
            print(f"result: PASS — model provisioned at {path}")
            return 0
        path = provision_segmentation_model(
            destination,
            model_url=model_url,
            force=args.force,
            probe_size=args.probe_size,
        )
    except ModelProvisioningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    onnx_report = validate_segmentation_model(path, probe_size=args.probe_size)
    print(onnx_report.summary())
    print(f"result: PASS — model provisioned at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
