#!/usr/bin/env python3
"""AIPulse Python sidecar: JSON-RPC entry point for the Tauri desktop app."""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

# ruff: noqa: E402
# Ensure project source is on PYTHONPATH during development.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pydantic import ValidationError

from aipulse.core.article_pipeline import ArticlePipeline
from aipulse.core.config import AppSettings, get_settings, reset_settings
from aipulse.core.content_router import ContentType
from aipulse.core.pipeline import PipelineContext, PipelineEvent, PipelineObserver
from aipulse.core.rpc import JsonRpcRequest, JsonRpcResponse
from aipulse.core.video_pipeline import VideoPipeline
from aipulse.store.database import close_db, get_session_maker, init_db
from aipulse.store.repository import TaskRepository

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class _TaskProgressObserver(PipelineObserver):
    """Forward pipeline events to the sidecar notification sink."""

    def __init__(self, sidecar: "Sidecar"):
        self._sidecar = sidecar

    async def on_stage_start(self, event: PipelineEvent) -> None:
        await self._sidecar.emit_progress(
            event.task_id,
            event.status,
            event.progress_pct,
            event.message,
        )

    async def on_stage_complete(self, event: PipelineEvent) -> None:
        await self._sidecar.emit_progress(
            event.task_id,
            event.status,
            event.progress_pct,
            event.message,
        )

    async def on_error(self, event: PipelineEvent) -> None:
        await self._sidecar.emit_progress(
            event.task_id,
            event.status,
            event.progress_pct,
            event.message,
        )

    async def on_complete(self, event: PipelineEvent) -> None:
        await self._sidecar.emit_complete(
            event.task_id,
            event.status,
            result={"url": event.url, "title": event.title},
            error_message=event.error_message,
        )


class Sidecar:
    """JSON-RPC sidecar dispatcher."""

    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or get_settings()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._write_line: Any | None = None
        self._running_tasks: set[asyncio.Task[None]] = set()

    async def handle_request(
        self, request: JsonRpcRequest | dict[str, Any]
    ) -> JsonRpcResponse | None:
        """Dispatch incoming JSON-RPC requests."""
        raw_request = request
        if isinstance(raw_request, dict):
            try:
                validated = JsonRpcRequest.model_validate(raw_request)
            except ValidationError:
                return JsonRpcResponse.failure(
                    raw_request.get("id"), -32600, "invalid request"
                )
        else:
            validated = raw_request
        handlers = {
            "submit_url": self._submit_url,
            "get_task_status": self._get_task_status,
            "retry_task": self._retry_task,
            "get_settings": self._get_settings,
            "update_settings": self._update_settings,
        }
        handler = handlers.get(validated.method)
        if handler is None:
            return JsonRpcResponse.failure(
                validated.id, -32601, f"method not found: {validated.method}"
            )
        try:
            result = await handler(validated.params)
            return JsonRpcResponse.success(validated.id, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Handler %s failed", validated.method)
            return JsonRpcResponse.failure(
                validated.id, -32603, f"internal error: {exc}"
            )

    async def _submit_url(self, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url")
        if not url:
            raise ValueError("url is required")
        content_type_hint = params.get("content_type_hint")
        source = params.get("source", "menubar")
        mode = params.get("mode", "archive")
        session_maker = get_session_maker()
        async with session_maker() as session:
            repo = TaskRepository(session)
            task = await repo.create(
                url=str(url),
                content_type=str(content_type_hint or "unknown"),
                source=str(source),
            )
            await session.commit()
            task_id = task.id
        self._tasks[task_id] = {
            "task_id": task_id,
            "url": str(url),
            "status": "pending",
            "progress_pct": 0,
            "message": "任务已提交",
            "source": str(source),
            "mode": str(mode),
        }
        self._spawn_pipeline(task_id, str(url))
        return {"task_id": task_id, "url": str(url)}

    async def _get_task_status(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("task_id")
        if not task_id:
            raise ValueError("task_id is required")
        session_maker = get_session_maker()
        async with session_maker() as session:
            repo = TaskRepository(session)
            task = await repo.get_by_id(str(task_id))
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        cached = self._tasks.get(task.id, {})
        return {
            "task_id": task.id,
            "status": task.status,
            "progress_pct": cached.get("progress_pct", 0),
            "message": cached.get("message", ""),
            "error_message": task.error_message,
        }

    async def _retry_task(self, params: dict[str, Any]) -> dict[str, Any]:
        task_id = params.get("task_id")
        if not task_id:
            raise ValueError("task_id is required")
        session_maker = get_session_maker()
        async with session_maker() as session:
            repo = TaskRepository(session)
            task = await repo.get_by_id(str(task_id))
            if task is None:
                raise ValueError(f"task not found: {task_id}")
            await repo.update_status(task.id, "pending", error_message=None)
            await session.commit()
            url = task.url
        cached = self._tasks.get(task.id, {})
        self._tasks[task.id] = {
            **cached,
            "status": "pending",
            "progress_pct": 0,
            "message": "任务已重新提交",
        }
        self._spawn_pipeline(task.id, url)
        return {"task_id": task.id, "status": "pending"}

    async def _get_settings(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self.settings.to_public_dict()

    async def _update_settings(self, params: dict[str, Any]) -> dict[str, Any]:
        self.settings = self.settings.update(**params)
        self.settings.save()
        reset_settings()
        return self.settings.to_public_dict()

    def _spawn_pipeline(self, task_id: str, url: str) -> None:
        """Start an asyncio task to run the appropriate pipeline."""
        loop = asyncio.get_event_loop()
        task = loop.create_task(self._run_pipeline(task_id, url))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

    async def _run_pipeline(self, task_id: str, url: str) -> None:
        """Run the pipeline for a task and update DB status along the way."""
        # Give the submit request's transaction time to commit before we
        # open our own DB connection, avoiding SQLite lock contention in
        # fast-running tests.
        await asyncio.sleep(0.1)
        content_type = await self._classify_url(url)
        ctx = PipelineContext(
            task_id=task_id,
            url=url,
            content_type=content_type.value,
            settings=self.settings,
        )

        pipeline: VideoPipeline | ArticlePipeline
        if content_type in {
            ContentType.YOUTUBE,
            ContentType.BILIBILI,
            ContentType.DOUYIN,
            ContentType.XIAOHONGSHU,
            ContentType.GENERIC_VIDEO,
        }:
            pipeline = VideoPipeline(self.settings)
        elif content_type == ContentType.RSS_FEED:
            pipeline = ArticlePipeline(self.settings)
        else:
            pipeline = ArticlePipeline(self.settings)

        pipeline.add_observer(_TaskProgressObserver(self))

        try:
            await self._update_task_status(task_id, "running")
            await pipeline.run(ctx)
            await self._update_task_status(task_id, "completed")
            await self._persist_task_result(task_id, ctx)
            await self.emit_complete(
                task_id, "success", {"url": url, "title": ctx.metadata.get("title")}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline failed for task %s", task_id)
            error_message = str(exc)
            await self._update_task_status(task_id, "failed", error_message)
            await self.emit_complete(task_id, "failed", error_message=error_message)

    async def _classify_url(self, url: str) -> ContentType:
        from aipulse.core.content_router import classify_url

        return await classify_url(url)

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        session_maker = get_session_maker()
        async with session_maker() as session:
            repo = TaskRepository(session)
            await repo.update_status(task_id, status, error_message)
            await session.commit()

    async def _persist_task_result(self, task_id: str, ctx: PipelineContext) -> None:
        session_maker = get_session_maker()
        async with session_maker() as session:
            repo = TaskRepository(session)
            fields: dict[str, Any] = {
                "title": ctx.metadata.get("title"),
                "raw_content_path": (
                    str(ctx.downloaded_path) if ctx.downloaded_path else None
                ),
                "transcript": ctx.transcript,
                "summary": ctx.summary.raw_markdown if ctx.summary else None,
                "key_moments": ctx.summary.key_points if ctx.summary else None,
            }
            if ctx.archive_paths:
                fields["source_note_path"] = str(ctx.archive_paths.source_note_path)
                fields["summary_note_path"] = str(ctx.archive_paths.summary_note_path)
            await repo.update_fields(task_id, **fields)
            await session.commit()

    def _emit_notification(self, method: str, params: dict[str, Any]) -> None:
        import json
        import sys

        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        if self._write_line is not None:
            self._write_line(line)
        else:
            sys.stdout.write(line)
            sys.stdout.flush()

    async def emit_progress(
        self,
        task_id: str,
        status: str,
        progress_pct: int,
        message: str,
    ) -> None:
        """Emit a task_progress notification."""
        self._tasks[task_id] = {
            **self._tasks.get(task_id, {}),
            "task_id": task_id,
            "status": status,
            "progress_pct": progress_pct,
            "message": message,
        }
        self._emit_notification(
            "task_progress",
            {
                "task_id": task_id,
                "status": status,
                "progress_pct": progress_pct,
                "message": message,
            },
        )

    async def emit_complete(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Emit a task_complete notification."""
        cached = self._tasks.get(task_id, {})
        self._tasks[task_id] = {
            **cached,
            "status": status,
            "progress_pct": (
                100 if status == "success" else cached.get("progress_pct", 0)
            ),
        }
        self._emit_notification(
            "task_complete",
            {
                "task_id": task_id,
                "status": status,
                "result": result or {},
                "error_message": error_message,
            },
        )

    async def shutdown(self) -> None:
        """Wait for running pipeline tasks to finish."""
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)


async def _read_stdin_lines() -> AsyncGenerator[bytes, None]:
    """Read lines from stdin, yielding one at a time."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    while True:
        line = await reader.readline()
        if not line:
            break
        yield line


async def main() -> None:
    """Read JSON-RPC requests from stdin and write responses to stdout."""
    await init_db()
    sidecar = Sidecar()

    try:
        async for line in _read_stdin_lines():
            response: JsonRpcResponse | None
            try:
                data = json.loads(line.decode("utf-8"))
                request = JsonRpcRequest.model_validate(data)
            except json.JSONDecodeError as exc:
                response = JsonRpcResponse.failure(None, -32700, f"parse error: {exc}")
            except Exception as exc:  # noqa: BLE001
                response = JsonRpcResponse.failure(
                    None, -32600, f"invalid request: {exc}"
                )
            else:
                response = await sidecar.handle_request(request)
                if response is None:
                    continue

            if response is not None:
                sys.stdout.write(response.model_dump_json(exclude_none=True) + "\n")
                sys.stdout.flush()
    finally:
        await sidecar.shutdown()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
