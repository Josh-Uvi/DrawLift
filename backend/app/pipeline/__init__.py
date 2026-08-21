"""Pluggable conversion pipeline framework."""

from app.pipeline.context import PipelineContext, ProgressPublisher
from app.pipeline.orchestrator import Pipeline, create_pipeline
from app.pipeline.primitives import (
    OpeningPrimitive,
    Point,
    Point3D,
    Primitive,
    RoomPrimitive,
    SlabGenerator,
    SlabPrimitive,
    TextPrimitive,
    WallPrimitive,
    WallSolidPrimitive,
)
from app.pipeline.progress import ProgressEvent, RedisProgressPublisher, get_progress_publisher
from app.pipeline.steps.base import PipelineStep
from app.pipeline.steps.dwg_converter import DwgConverterStep
from app.pipeline.steps.dxf_writer import DxfWriterStep
from app.pipeline.steps.extruder import WallExtruderStep
from app.pipeline.steps.glb_writer import GlbWriterStep
from app.pipeline.steps.pdf_parser import PdfParserStep
from app.pipeline.steps.preprocessor import OpenCVPreprocessor
from app.pipeline.steps.segmenter import (
    AutoMlSegmenter,
    ClassicCVSegmenter,
    OnnxSemanticSegmenter,
    SegmenterStep,
    TorchYytsiSegmenter,
    preload_configured_segmentation_model,
)
from app.pipeline.steps.vectorizer import VectorizerStep

__all__ = [
    "ClassicCVSegmenter",
    "AutoMlSegmenter",
    "DxfWriterStep",
    "DwgConverterStep",
    "GlbWriterStep",
    "OpeningPrimitive",
    "OpenCVPreprocessor",
    "OnnxSemanticSegmenter",
    "Point",
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "PdfParserStep",
    "Primitive",
    "ProgressEvent",
    "ProgressPublisher",
    "RedisProgressPublisher",
    "Point3D",
    "RoomPrimitive",
    "SegmenterStep",
    "TorchYytsiSegmenter",
    "SlabGenerator",
    "SlabPrimitive",
    "TextPrimitive",
    "VectorizerStep",
    "WallExtruderStep",
    "WallPrimitive",
    "WallSolidPrimitive",
    "create_pipeline",
    "get_progress_publisher",
    "preload_configured_segmentation_model",
]
