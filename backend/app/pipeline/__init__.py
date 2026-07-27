"""Pluggable conversion pipeline framework."""

from app.pipeline.context import PipelineContext, ProgressPublisher
from app.pipeline.orchestrator import Pipeline, create_pipeline
from app.pipeline.progress import ProgressEvent, RedisProgressPublisher, get_progress_publisher
from app.pipeline.steps.base import PipelineStep
from app.pipeline.steps.pdf_parser import PdfParserStep
from app.pipeline.steps.preprocessor import OpenCVPreprocessor
from app.pipeline.steps.segmenter import (
    ClassicCVSegmenter,
    OnnxSemanticSegmenter,
    SegmenterStep,
    preload_configured_segmentation_model,
)

__all__ = [
    "ClassicCVSegmenter",
    "OpenCVPreprocessor",
    "OnnxSemanticSegmenter",
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "PdfParserStep",
    "ProgressEvent",
    "ProgressPublisher",
    "RedisProgressPublisher",
    "SegmenterStep",
    "create_pipeline",
    "get_progress_publisher",
    "preload_configured_segmentation_model",
]
