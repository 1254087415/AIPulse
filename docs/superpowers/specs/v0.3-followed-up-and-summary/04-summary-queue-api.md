# 04 — 总结队列 + SSE 进度 + Summary API

> **来源**：原文档 §5.9-§5.10（队列 + API）
> **上游依赖**：03 Agent 工具调用契约
> **下游交付物**：
> - `src/aipulse/summarizers/agent/queue.py` — `asyncio.Queue` + 单 worker + 队列上限 20
> - `src/aipulse/api/summaries.py` — Summary API 端点
> - SSE 推送三态进度（排队/进行/完成）
> - `obsidian://open?path=...` 跳转协议
> - 完整测试用例清单（Q142 + Q147）
>
> **subagent 边界**：本模块产出队列 + API + SSE 推送，不产出归档与三方向存储（在 06）。
> **执行模式**：单独 subagent-D 串行执行。

---



位置：`src/aipulse/summarizers/agent/queue.py`

```python
# src/aipulse/summarizers/agent/queue.py
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from aipulse.summarizers.agent.runner import run_summary_pipeline
from aipulse.db.repositories.summaries import SummaryRepository

logger = logging.getLogger(__name__)

QUEUE_MAX_SIZE = 20  # Q124 锁定：上限 20


@dataclass
class SummaryJob:
    """队列中的一个总结任务。"""
    video_id: str
    title: str
    up_name: str
    requester_token: str  # 用于 SSE 权限校验
    extra_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "up_name": self.up_name,
            "extra_context": self.extra_context,
        }


class SummaryQueue:
    """全局单例：asyncio.Queue + 单 worker 协程（Q124 锁定：并发 1）。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[SummaryJob] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._worker_task: asyncio.Task | None = None
        self._progress_subscribers: dict[str, set[asyncio.Queue]] = {}  # video_id -> set of subscriber queues

    def start_worker(self) -> None:
        """在 FastAPI lifespan 启动时调用一次。"""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop(), name="summary-worker")
            logger.info("Summary worker started")

    async def stop_worker(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, job: SummaryJob) -> int:
        """入队。队列满时**阻塞等待 5 秒**，超时抛 QueueFull 异常（前端捕获返回 429）。"""
        try:
            self._queue.put_nowait(job)
            return self._queue.qsize()
        except asyncio.QueueFull:
            # 短阻塞 5s，给 worker 消费的机会
            try:
                await asyncio.wait_for(self._queue.put(job), timeout=5.0)
                return self._queue.qsize()
            except asyncio.TimeoutError:
                raise QueueFullError(f"队列已满（{QUEUE_MAX_SIZE}），请稍后重试")

    def queue_size(self) -> int:
        return self._queue.qsize()

    def subscribe_progress(self, video_id: str) -> asyncio.Queue:
        """前端 SSE 订阅进度（Q126：黄色排队/蓝色进行/绿色完成三态）。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._progress_subscribers.setdefault(video_id, set()).add(q)
        return q

    def unsubscribe_progress(self, video_id: str, q: asyncio.Queue) -> None:
        subs = self._progress_subscribers.get(video_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._progress_subscribers.pop(video_id, None)

    def _broadcast(self, video_id: str, event: dict[str, Any]) -> None:
        for q in list(self._progress_subscribers.get(video_id, set())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # 慢消费者丢弃，不阻塞 worker

    async def _worker_loop(self) -> None:
        """单 worker 串行消费（Q124：并发 1）。"""
        while True:
            job = await self._queue.get()
            try:
                self._broadcast(job.video_id, {"phase": "started", "queue_size": self._queue.qsize()})
                # 标记 DB 为 running
                await SummaryRepository().update_status(job.video_id, "running")
                # 跑 pipeline
                result = await run_summary_pipeline(
                    video_id=job.video_id,
                    title=job.title,
                    up_name=job.up_name,
                    extra_context=job.extra_context,
                )
                # 落库结果
                await SummaryRepository().save_result(job.video_id, result)
                # 广播完成
                self._broadcast(job.video_id, {
                    "phase": "completed" if result["status"] == "completed" else "failed",
                    "result": result,
                })
            except Exception as exc:
                logger.exception("Worker failed for %s", job.video_id)
                self._broadcast(job.video_id, {"phase": "failed", "error": str(exc)})
            finally:
                self._queue.task_done()


class QueueFullError(Exception):
    """队列满 5 秒仍无法入队 → 前端返回 429。"""
    pass


# 全局单例
summary_queue = SummaryQueue()
```



位置：`src-python/src/aipulse/api/summaries.py`

```python
# src-python/src/aipulse/api/summaries.py
from __future__ import annotations
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from aipulse.auth import require_bearer_token  # Q130 锁定
from aipulse.summarizers.agent.queue import summary_queue, SummaryJob, QueueFullError
from aipulse.db.repositories.summaries import SummaryRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/summaries", tags=["summaries"])


class SummaryRequest(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    up_name: str = Field(..., min_length=1, max_length=100)
    extra_context: str = Field(default="", max_length=500)


class SummaryResponse(BaseModel):
    video_id: str
    status: Literal["queued", "running", "completed", "failed", "partial"]
    queue_position: int | None = None
    note_path: str | None = None
    event_id: str | None = None
    error: str | None = None


@router.post("", response_model=SummaryResponse, status_code=202)
async def enqueue_summary(
    req: SummaryRequest,
    request: Request,
    _: None = Depends(require_bearer_token),
) -> SummaryResponse:
    """手动触发一次总结 pipeline。返回 202 + queue 位置。"""
    job = SummaryJob(
        video_id=req.video_id,
        title=req.title,
        up_name=req.up_name,
        requester_token=request.headers.get("Authorization", ""),
        extra_context=req.extra_context,
    )
    try:
        position = await summary_queue.enqueue(job)
    except QueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return SummaryResponse(
        video_id=req.video_id,
        status="queued",
        queue_position=position,
    )


@router.get("/{video_id}/status", response_model=SummaryResponse)
async def get_summary_status(
    video_id: str,
    _: None = Depends(require_bearer_token),
) -> SummaryResponse:
    repo = SummaryRepository()
    record = await repo.find_by_video_id(video_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到总结记录")
    return SummaryResponse(**record.to_dict())


@router.get("/{video_id}/progress")
async def stream_progress(
    video_id: str,
    request: Request,
    _: None = Depends(require_bearer_token),
) -> StreamingResponse:
    """SSE 流式进度推送（Q126）。"""
    sub_q = summary_queue.subscribe_progress(video_id)

    async def event_gen():
        try:
            # 立刻发送当前 DB 状态作为首帧
            repo = SummaryRepository()
            record = await repo.find_by_video_id(video_id)
            if record:
                yield f"data: {json.dumps({'phase': record.status, 'snapshot': True})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(sub_q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("phase") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    # 15s 心跳
                    yield ": keepalive\n\n"
        finally:
            summary_queue.unsubscribe_progress(video_id, sub_q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/{video_id}/retry", response_model=SummaryResponse)
async def retry_summary(
    video_id: str,
    request: Request,
    _: None = Depends(require_bearer_token),
) -> SummaryResponse:
    """手动重试（Q128：不自动重试）。"""
    repo = SummaryRepository()
    record = await repo.find_by_video_id(video_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到记录")
    job = SummaryJob(
        video_id=video_id,
        title=record.title,
        up_name=record.up_name,
        requester_token=request.headers.get("Authorization", ""),
        extra_context=record.extra_context,
    )
    try:
        position = await summary_queue.enqueue(job)
    except QueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    await repo.update_status(video_id, "queued")
    return SummaryResponse(video_id=video_id, status="queued", queue_position=position)
```

### 5.11 测试用例清单（Q142 + Q147）

位置：`src-python/tests/summarizers/test_agent_pipeline.py`

| # | 测试名 | 验证内容 | Mock 边界 |
|---|--------|----------|-----------|
| 1 | `test_fetch_transcript_success` | 返回字幕文本 | mock `bilibili.subtitles.fetch_subtitle_text` |
| 2 | `test_fetch_transcript_timeout` | 30s 超时返回 [ERROR] | mock 让其 sleep 31s |
| 3 | `test_fetch_transcript_api_error` | B 站 404 返回 [ERROR] | mock 抛 HTTPException |
| 4 | `test_summarize_success` | 调用 Kimi 返回 markdown | mock `llm.get_llm_client` |
| 5 | `test_summarize_kimi_timeout` | 180s 超时 | mock 让其 sleep 181s |
| 6 | `test_summarize_kimi_rate_limit` | 429 → 返回 ok=False | mock 抛 openai.error.RateLimitError |
| 7 | `test_judge_tech_relevance_high_score` | score=0.8 → should_archive=True | mock LLM 返回 JSON |
| 8 | `test_judge_tech_relevance_low_score` | score=0.3 → should_archive=False | 同上 |
| 9 | `test_judge_tech_relevance_default_archive` | LLM 失败时保守归档 | mock 让 LLM 抛异常 |
| 10 | `test_create_obsidian_note_writes_file` | 真实 tmp_path 写入 frontmatter + body | **不 mock**：tmp_path/vault 是真目录 |
| 11 | `test_create_obsidian_note_no_vault` | 未配置 vault → ok=False error | settings.obsidian_vault_path=None |
| 12 | `test_create_learning_event_inserts_db` | 真 SQLite (aiosqlite 内存) 插入 | **不 mock**：用 `:memory:` |
| 13 | `test_send_notification_appends_task` | 真实文件追加 - [ ] ⏰ | **不 mock**：tmp_path |
| 14 | `test_send_notification_reminder_failure_keeps_ok` | Reminder 失败 → ok=True 但带 reminder_error | mock `apple_assistant_eventkit.create_reminder` 抛异常 |
| 15 | `test_agent_pipeline_end_to_end` | 6 个 tool 完整链路（happy path） | **不 mock**：tmp_path + 内存 SQLite + mock Kimi |
| 16 | `test_agent_pipeline_judge_rejects_skips_write` | judge 拒绝时**不**调用 create_obsidian_note | mock 所有 tool 的 invoke |
| 17 | `test_agent_pipeline_5min_timeout` | 整体超时 → status=partial | mock 让 tool sleep 301s |
| 18 | `test_summary_queue_serial_execution` | 并发 1（任务 1 完成前 任务 2 不开始） | enqueue 2 个 job，断言 timestamps |
| 19 | `test_summary_queue_max_size_429` | 队列满 → enqueue 抛 QueueFullError | enqueue 21 个 job |
| 20 | `test_summary_queue_sse_progress_three_phases` | SSE 推送 started → completed | 订阅 queue 后 enqueue + run worker |
| 21 | `test_summary_api_requires_bearer_token` | 无 Authorization 头 → 401 | — |
| 22 | `test_summary_api_enqueue_returns_202` | 正常入队返回 queue_position | mock queue.enqueue |
| 23 | `test_summary_api_retry_resets_status` | 重试时 DB status 改回 queued | mock repo |

**测试原则**（符合项目 §3 测试约定）：
- **不 mock 真实 sidecar / 数据库 / 文件系统**（Q142 验证原则）
- 只 mock LLM 调用（避免烧 token 和不确定性）
- 真实 `aiosqlite` + 真实 `tmp_path` 验证 I/O 边界
- E2E 测试在 `extensions/chromium/tests/e2e/summarize-pipeline.spec.ts` 跨前后端

---

