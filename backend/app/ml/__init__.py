"""ML model management for the conversion pipeline."""

from app.ml.segmentation_model import (
    MAX_MODEL_SIZE_BYTES,
    SEGMENTATION_MODEL_FILENAME,
    SUPPORTED_CLASS_COUNTS,
    InputSizeCompatibilityReport,
    ModelProvisioningError,
    ModelValidationReport,
    build_reference_segmentation_model,
    check_model_input_size,
    download_segmentation_model,
    provision_segmentation_model,
    validate_segmentation_model,
)
from app.ml.yytsi_torch import (
    YYTSI_CONFIG_FILENAME,
    YYTSI_CONFIG_URL,
    YYTSI_MODEL_FILENAME,
    YYTSI_MODEL_URL,
    YytsiBundleValidationReport,
    infer_yytsi_config_url,
    load_yytsi_config,
    resolve_yytsi_model_assets,
    validate_yytsi_bundle,
)

__all__ = [
    "MAX_MODEL_SIZE_BYTES",
    "SEGMENTATION_MODEL_FILENAME",
    "SUPPORTED_CLASS_COUNTS",
    "InputSizeCompatibilityReport",
    "ModelProvisioningError",
    "ModelValidationReport",
    "build_reference_segmentation_model",
    "check_model_input_size",
    "download_segmentation_model",
    "provision_segmentation_model",
    "validate_segmentation_model",
    "YYTSI_CONFIG_FILENAME",
    "YYTSI_CONFIG_URL",
    "YYTSI_MODEL_FILENAME",
    "YYTSI_MODEL_URL",
    "YytsiBundleValidationReport",
    "infer_yytsi_config_url",
    "load_yytsi_config",
    "resolve_yytsi_model_assets",
    "validate_yytsi_bundle",
]
