"""Tests for the pluggable pipeline framework."""

from pathlib import Path

from app.pipeline import Pipeline, PipelineContext, PipelineStep, create_pipeline


class RecordingPublisher:
    """In-memory progress publisher used by pipeline tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish(
        self,
        *,
        job_id: str,
        status: str,
        progress: int,
        step: str,
        message: str | None = None,
    ) -> None:
        self.events.append(
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "step": step,
                "message": message,
            }
        )


class RecordingStep(PipelineStep):
    """Pipeline step that records execution order in context metadata."""

    def __init__(self, name: str, progress: int | None = None) -> None:
        self.name = name
        self.progress = progress

    def execute(self, context: PipelineContext) -> PipelineContext:
        order = context.metadata.setdefault("order", [])
        assert isinstance(order, list)
        order.append(self.name)
        return context


def test_pipeline_context_defaults_to_empty_containers() -> None:
    """PipelineContext provides safe empty defaults for future steps."""
    context = PipelineContext(job_id="job-123", input_path=Path("input.pdf"))

    assert context.page_images == []
    assert context.preprocessed == []
    assert context.masks == {}
    assert context.primitives == []
    assert context.output_path is None


def test_pipeline_run_executes_steps_in_order() -> None:
    """Pipeline.run executes each step sequentially and returns the final context."""
    context = PipelineContext(job_id="job-123", input_path=Path("input.pdf"))
    pipeline = Pipeline([RecordingStep("parse"), RecordingStep("preprocess")])

    result = pipeline.run(context)

    assert result is context
    assert result.metadata["order"] == ["parse", "preprocess"]


def test_create_pipeline_accepts_positional_steps() -> None:
    """create_pipeline is a convenience factory around Pipeline.from_steps."""
    pipeline = create_pipeline(RecordingStep("parse"), RecordingStep("preprocess"))

    assert [step.name for step in pipeline.steps] == ["parse", "preprocess"]


def test_steps_can_publish_progress_via_context() -> None:
    """Each step can publish progress through the context's attached publisher."""
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-123",
        input_path=Path("input.pdf"),
        progress_publisher=publisher,
    )
    step = RecordingStep("parse", progress=20)

    step.publish_progress(context)

    assert publisher.events == [
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 20,
            "step": "parse",
            "message": None,
        }
    ]


def test_pipeline_publishes_start_and_completion_progress_for_steps() -> None:
    """The orchestrator emits progress events around each step execution."""
    publisher = RecordingPublisher()
    context = PipelineContext(
        job_id="job-123",
        input_path=Path("input.pdf"),
        progress_publisher=publisher,
    )
    pipeline = Pipeline([RecordingStep("parse", progress=20), RecordingStep("preprocess")])

    pipeline.run(context)

    assert publisher.events == [
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 0,
            "step": "parse",
            "message": "started",
        },
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 20,
            "step": "parse",
            "message": "completed",
        },
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 50,
            "step": "preprocess",
            "message": "started",
        },
        {
            "job_id": "job-123",
            "status": "processing",
            "progress": 100,
            "step": "preprocess",
            "message": "completed",
        },
    ]
