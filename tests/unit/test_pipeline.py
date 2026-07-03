"""Tests for the processing pipeline contract."""

import pytest

from aipulse.core.pipeline import (
    BasePipeline,
    PipelineContext,
    PipelineEvent,
    StdoutObserver,
)


class FakePipeline(BasePipeline):
    """A fake pipeline that returns a known context."""

    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    async def _classify(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("classify")
        ctx.content_type = "article"
        return ctx

    async def _fetch(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("fetch")
        return ctx

    async def _extract_text(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("extract_text")
        ctx.transcript = "transcript"
        return ctx

    async def _summarize(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("summarize")
        return ctx

    async def _archive(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("archive")
        return ctx

    async def _notify(self, ctx: PipelineContext) -> PipelineContext:
        self.calls.append("notify")
        return ctx


@pytest.mark.unit
async def test_pipeline_runs_all_stages() -> None:
    pipeline = FakePipeline()
    ctx = PipelineContext(task_id="task-1", url="https://example.com")
    result = await pipeline.run(ctx)
    assert pipeline.calls == [
        "classify",
        "fetch",
        "extract_text",
        "summarize",
        "archive",
        "notify",
    ]
    assert result.task_id == "task-1"
    assert result.content_type == "article"


@pytest.mark.unit
async def test_pipeline_emits_events() -> None:
    events: list[PipelineEvent] = []

    class CollectingObserver:
        async def on_stage_start(self, event: PipelineEvent) -> None:
            events.append(event)

        async def on_stage_complete(self, event: PipelineEvent) -> None:
            events.append(event)

        async def on_error(self, event: PipelineEvent) -> None:
            events.append(event)

        async def on_complete(self, event: PipelineEvent) -> None:
            events.append(event)

    pipeline = FakePipeline()
    pipeline.add_observer(CollectingObserver())
    ctx = PipelineContext(task_id="task-1", url="https://example.com")
    await pipeline.run(ctx)
    assert len(events) > 0
    assert events[-1].status == "success"


@pytest.mark.unit
async def test_pipeline_handles_stage_failure() -> None:
    class FailingPipeline(BasePipeline):
        async def _classify(self, ctx: PipelineContext) -> PipelineContext:
            raise RuntimeError("classify failed")

        async def _fetch(self, ctx: PipelineContext) -> PipelineContext:
            return ctx

        async def _extract_text(self, ctx: PipelineContext) -> PipelineContext:
            return ctx

        async def _summarize(self, ctx: PipelineContext) -> PipelineContext:
            return ctx

        async def _archive(self, ctx: PipelineContext) -> PipelineContext:
            return ctx

        async def _notify(self, ctx: PipelineContext) -> PipelineContext:
            return ctx

    pipeline = FailingPipeline()
    ctx = PipelineContext(task_id="task-1", url="https://example.com")
    with pytest.raises(RuntimeError, match="classify failed"):
        await pipeline.run(ctx)
    assert ctx.error_message == "classify failed"


@pytest.mark.unit
async def test_stdout_observer_emits_notification() -> None:
    lines: list[str] = []
    observer = StdoutObserver(write_line=lines.append)
    event = PipelineEvent(
        task_id="task-1",
        stage="classify",
        status="completed",
        message="done",
        progress_pct=20,
    )
    await observer.on_stage_complete(event)
    assert len(lines) == 1
    import json

    payload = json.loads(lines[0])
    assert payload["method"] == "task_progress"
    assert payload["params"]["task_id"] == "task-1"
    assert payload["params"]["progress_pct"] == 20
