"""Processing pipeline (Template Method + Observer patterns)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from aipulse.archive.base import ArchivePaths
from aipulse.core.config import AppSettings
from aipulse.summarizers.base import SummaryResult


@dataclass
class PipelineContext:
    """Mutable-in-place context passed through pipeline stages."""

    task_id: str
    url: str
    content_type: str = "unknown"
    settings: AppSettings = field(default_factory=lambda: AppSettings())
    downloaded_path: Path | None = None
    transcript: str | None = None
    summary: SummaryResult | None = None
    archive_paths: ArchivePaths | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class PipelineEvent:
    """Progress event emitted by the pipeline."""

    task_id: str
    stage: str
    status: str
    message: str
    progress_pct: int = 0
    url: str = ""
    title: str | None = None
    error_message: str | None = None


class PipelineObserver(Protocol):
    """Observer that receives pipeline progress events."""

    async def on_stage_start(self, event: PipelineEvent) -> None:
        """Called when a pipeline stage starts."""

    async def on_stage_complete(self, event: PipelineEvent) -> None:
        """Called when a pipeline stage completes."""

    async def on_error(self, event: PipelineEvent) -> None:
        """Called when a pipeline stage fails."""

    async def on_complete(self, event: PipelineEvent) -> None:
        """Called when the pipeline completes (success or failure)."""


class BasePipeline(ABC):
    """Template method for processing content URLs."""

    def __init__(self) -> None:
        self._observers: list[PipelineObserver] = []

    def add_observer(self, observer: PipelineObserver) -> None:
        """Register a progress observer."""
        self._observers.append(observer)

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Run the processing pipeline."""
        stages = [
            ("classify", self._classify),
            ("fetch", self._fetch),
            ("extract_text", self._extract_text),
            ("summarize", self._summarize),
            ("archive", self._archive),
            ("notify", self._notify),
        ]
        total = len(stages)
        try:
            for index, (stage_name, stage_fn) in enumerate(stages, start=1):
                progress_pct = int((index - 1) / total * 100)
                await self._emit(
                    PipelineEvent(
                        task_id=ctx.task_id,
                        stage=stage_name,
                        status="running",
                        message=f"正在执行: {stage_name}",
                        progress_pct=progress_pct,
                        url=ctx.url,
                    )
                )
                ctx = await stage_fn(ctx)
                await self._emit(
                    PipelineEvent(
                        task_id=ctx.task_id,
                        stage=stage_name,
                        status="completed",
                        message=f"完成: {stage_name}",
                        progress_pct=int(index / total * 100),
                        url=ctx.url,
                    )
                )
            await self._emit(
                PipelineEvent(
                    task_id=ctx.task_id,
                    stage="done",
                    status="success",
                    message="处理完成",
                    progress_pct=100,
                    url=ctx.url,
                )
            )
        except Exception as exc:
            ctx.error_message = str(exc)
            await self._emit(
                PipelineEvent(
                    task_id=ctx.task_id,
                    stage="pipeline",
                    status="failed",
                    message=f"处理失败: {exc}",
                    progress_pct=0,
                    url=ctx.url,
                    error_message=str(exc),
                )
            )
            raise
        return ctx

    async def _emit(self, event: PipelineEvent) -> None:
        """Emit an event to all observers."""
        for observer in self._observers:
            await observer.on_stage_complete(event)

    @abstractmethod
    async def _classify(self, ctx: PipelineContext) -> PipelineContext:
        """Classify the URL into a content type."""

    @abstractmethod
    async def _fetch(self, ctx: PipelineContext) -> PipelineContext:
        """Download raw content/media."""

    @abstractmethod
    async def _extract_text(self, ctx: PipelineContext) -> PipelineContext:
        """Extract transcript or article text."""

    @abstractmethod
    async def _summarize(self, ctx: PipelineContext) -> PipelineContext:
        """Generate a summary."""

    @abstractmethod
    async def _archive(self, ctx: PipelineContext) -> PipelineContext:
        """Archive notes and update context with paths."""

    @abstractmethod
    async def _notify(self, ctx: PipelineContext) -> PipelineContext:
        """Send push notifications."""


class StdoutObserver(PipelineObserver):
    """Observer that emits JSON-RPC notifications to stdout."""

    def __init__(self, write_line: Any | None = None):
        self._write_line = write_line

    async def on_stage_start(self, event: PipelineEvent) -> None:
        """Handle stage start by emitting a task_progress notification."""
        self._emit_notification("task_progress", event)

    async def on_stage_complete(self, event: PipelineEvent) -> None:
        """Handle stage completion by emitting a task_progress notification."""
        self._emit_notification("task_progress", event)

    async def on_error(self, event: PipelineEvent) -> None:
        """Handle stage error by emitting a task_progress notification."""
        self._emit_notification("task_progress", event)

    async def on_complete(self, event: PipelineEvent) -> None:
        """Handle pipeline completion by emitting task_complete."""
        method = "task_complete" if event.status == "success" else "task_progress"
        self._emit_notification(method, event)

    def _emit_notification(self, method: str, event: PipelineEvent) -> None:
        import json
        import sys

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": {
                "task_id": event.task_id,
                "status": event.status,
                "progress_pct": event.progress_pct,
                "message": event.message,
            },
        }
        line = json.dumps(payload, ensure_ascii=False)
        if self._write_line is not None:
            self._write_line(line)
        else:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
