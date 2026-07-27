"""Async in-process summary job queue + worker (spec §5.5).

- ``SummaryJobQueue``: singleton-style manager holding a per-server asyncio.Queue。
- Worker pulls jobs, runs ``run_summary_pipeline``, 把每步 intermediate step
  推给订阅者（SSE 通道），把最终结果回写到 summary_jobs 表。

约定：进程重启后内存中队列里的 job 重新查 DB（status=queued）即可恢复，
因为 DB 已经是持久化真相。

队列上限（spec §5.5）：maxsize=20。超出时 ``enqueue`` 抛
:class:`QueueFullError`，由 HTTP 路由捕获转 429 + "queue full"。

注意：maxsize 是 backpressure 闸门，并不能保证客户端"窗口"始终为 20。
worker 在跑时 qsize 会短暂 < 20，但只要生产者 > 1 且新进 21..N 请求在 worker
没消费前涌入，仍会被 ``asyncio.Queue.put_nowait`` 拒绝。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from aipulse.core.config import get_settings
from aipulse.models.summary_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_TIMEOUT,
    SummaryJob,
)
from aipulse.repositories.summary_job_repo import (
    SqlAlchemySummaryJobRepository,
    SummaryJobNotFoundError,
    SummaryJobRepository,
)
from aipulse.summarizers.agent.runner import run_summary_pipeline
from aipulse.summarizers.finalize import finalize_summary_job
from aipulse.store.database import get_session_maker

logger = logging.getLogger(__name__)

QUEUE_MAX_SIZE = 20


class QueueFullError(Exception):
    """enqueue 时队列已满（>= QUEUE_MAX_SIZE） → 上层转 HTTP 429。"""

    def __init__(self, size: int, max_size: int = QUEUE_MAX_SIZE) -> None:
        super().__init__(f"summary queue full ({size}/{max_size})")
        self.size = size
        self.max_size = max_size


@dataclass
class JobSubmission:
    """A unit of work submitted to the queue."""

    job_id: str
    video_id: str
    title: str = ""
    up_name: str = ""
    extra_context: str = ""
    event: asyncio.Event = field(default_factory=asyncio.Event)


class SummaryJobQueue:
    """Singleton-like manager for in-process summary queue + SSE fanout."""

    def __init__(self) -> None:
        # 不要在 __init__ 中创建 asyncio.Queue / asyncio.Lock：他们会绑到
        # 第一次实例化的 event loop；测试每次 loop 都不一样会抛
        # "<Queue ...> is bound to a different event loop"。
        self._queue: Optional[asyncio.Queue[JobSubmission]] = None
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._lock: Optional[asyncio.Lock] = None
        self._stop: Optional[asyncio.Event] = None

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        """Start the worker (idempotent)."""
        await self._ensure_loop_state()
        async with self._lock:  # type: ignore[union-attr]
            if self._worker_task is None or self._worker_task.done():
                self._stop.clear()  # type: ignore[union-attr]
                self._worker_task = asyncio.create_task(
                    self._worker_loop(), name="aipulse-summary-worker"
                )
                logger.info("SummaryJobQueue worker started")

    async def stop(self) -> None:
        """Stop the worker; safe to call multiple times."""
        if self._lock is None:
            return
        async with self._lock:
            self._stop.set()  # type: ignore[union-attr]
            task = self._worker_task
            if task is None:
                return
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                task.cancel()
            self._worker_task = None

    async def _ensure_loop_state(self) -> None:
        """Lazily create asyncio primitives on first start."""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        if self._lock is None:
            self._lock = asyncio.Lock()
        if self._stop is None:
            self._stop = asyncio.Event()

    # ------------------------------------------------------------ producer API

    async def enqueue(
        self,
        repo: SummaryJobRepository,
        *,
        video_id: str,
        title: str = "",
        up_name: str = "",
        extra_context: str = "",
    ) -> JobSubmission:
        """Create a SummaryJob row, then enqueue a worker submission.

        队列已满（>= QUEUE_MAX_SIZE）→ 抛 :class:`QueueFullError`，
        上层应捕获转 HTTP 429。不阻塞等待（避免长时间挂住 HTTP 请求）。

        Returns the :class:`JobSubmission` so the caller can broadcast
        intermediate SSE events back to the HTTP layer.
        """
        await self._ensure_loop_state()
        record = await repo.create(
            video_id=video_id, title=title, up_name=up_name
        )
        submission = JobSubmission(
            job_id=record.id,
            video_id=video_id,
            title=title or "",
            up_name=up_name or "",
            extra_context=extra_context,
        )
        try:
            self._queue.put_nowait(submission)  # type: ignore[union-attr]
        except asyncio.QueueFull:
            size = self._queue.qsize()  # type: ignore[union-attr]
            # 不回滚 DB row：worker 空闲时会自然 drain queued records；
            # 回滚代价（额外的 repo.delete 方法 + commit 协调）不值
            raise QueueFullError(size=size, max_size=QUEUE_MAX_SIZE) from None
        return submission

    # ------------------------------------------------------------ consumer / SSE

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Return a new per-subscriber asyncio.Queue; consumer must drain it."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._subscribers.get(job_id)
        if not subs:
            return
        try:
            subs.remove(q)
        except ValueError:
            pass
        if not subs:
            self._subscribers.pop(job_id, None)

    async def broadcast(self, job_id: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # drop on slow subscriber; client dropped = reconnect
                logger.warning("SSE subscriber full for job=%s; dropping", job_id)

    # ------------------------------------------------------------ internal

    async def _worker_loop(self) -> None:
        while not self._stop.is_set() if self._stop else False:
            try:
                submission = await asyncio.wait_for(self._queue.get(), timeout=0.05)  # type: ignore[union-attr]
            except asyncio.TimeoutError:
                continue
            try:
                await self._run_submission(submission)
            except Exception:  # noqa: BLE001
                logger.exception("Worker loop swallowed unexpected error")

    async def _run_submission(self, sub: JobSubmission) -> None:
        """Run a single pipeline submission; emit SSE + update DB.

        L6 业务侧终态分支（2026-07-26）：所有 3 个终态路径（success / timeout /
        exception）都必须经过 :func:`finalize_summary_job` —— 业务结果完整性判定
        优先于异常捕获（feedback_status-must-not-mask-failure 硬契约）。不允许
        except 后 early return 跳过 finalize。
        """
        async with get_session_maker()() as session:
            repo = SqlAlchemySummaryJobRepository(session)
            await repo.mark_started(sub.job_id)
            await self.broadcast(
                sub.job_id,
                {
                    "type": f"task.{sub.video_id}.started",
                    "job_id": sub.job_id,
                    "video_id": sub.video_id,
                    "title": sub.title,
                    "up_name": sub.up_name,
                },
            )
            await session.commit()

        # Build a tight callback that flushes each tool step to DB + SSE
        settings = get_settings()
        timeout = float(getattr(settings, "summary_pipeline_timeout", 300.0))

        # The result fields consumed by finalize. Each branch (success /
        # timeout / exception) populates whatever it has, then funnels through
        # finalize_summary_job so the terminal status / SSE event name follow
        # the L6 contract uniformly.
        result: dict[str, Any] = {
            "note_path": None,
            "event_id": None,
            "reminder_id": None,
            "hotspot_id": None,
            "intermediate_steps": [],
            "error": None,
        }

        try:
            pipeline_result = await asyncio.wait_for(
                run_summary_pipeline(
                    video_id=sub.video_id,
                    title=sub.title,
                    up_name=sub.up_name,
                    extra_context=sub.extra_context,
                ),
                timeout=timeout + 30.0,  # outer guard
            )
            result.update(
                {
                    "note_path": pipeline_result.get("note_path"),
                    "event_id": pipeline_result.get("event_id"),
                    "reminder_id": pipeline_result.get("reminder_id"),
                    "hotspot_id": pipeline_result.get("hotspot_id"),
                    "intermediate_steps": pipeline_result.get(
                        "intermediate_steps", []
                    ),
                    "error": pipeline_result.get("error"),
                }
            )
        except asyncio.TimeoutError:
            result["error"] = f"Pipeline outer timeout after {timeout + 30.0}s"
            logger.error(
                "summary pipeline timed out for job=%s video_id=%s after %.0fs",
                sub.job_id,
                sub.video_id,
                timeout + 30.0,
            )
        except Exception as exc:  # noqa: BLE001
            # Always log the full stack trace so post-mortem debugging does
            # not depend on the UI / SSE consumer having surfaced the
            # exception chain (workers may run unattended for hours).
            logger.exception(
                "summary pipeline raised for job=%s video_id=%s",
                sub.job_id,
                sub.video_id,
            )
            result["error"] = f"{type(exc).__name__}: {exc}"

        # Finalize: ONE funnel for all three terminal branches. Even the
        # timeout / exception paths must go through this so we never
        # accidentally mark a job "completed" when the business-side fields
        # are missing.
        finalized = finalize_summary_job(
            video_id=sub.video_id,
            hotspot_id=result.get("hotspot_id"),
            note_path=result.get("note_path"),
            error=result.get("error"),
        )

        async with get_session_maker()() as session:
            repo = SqlAlchemySummaryJobRepository(session)
            await repo.mark_finished(
                sub.job_id,
                finalized.status,
                error=finalized.error,
                note_path=result.get("note_path"),
                event_id=result.get("event_id"),
                reminder_id=result.get("reminder_id"),
                intermediate_steps=result.get("intermediate_steps"),
            )
            await session.commit()

        # SSE payload — event name comes from finalize, payload carries the
        # full job state so the frontend can render completion / failure
        # states uniformly. L1#3 (2026-07-26): the ``type`` field on the
        # broadcast payload is the canonical ``task.{bvid}.{status}`` event
        # name so the SSE route's ``event.get("type")`` forwards it directly
        # to the wire ``event:`` line.
        sse_payload = finalized.sse_payload(
            sub.job_id,
            video_id=sub.video_id,
            note_path=result.get("note_path"),
            event_id=result.get("event_id"),
            reminder_id=result.get("reminder_id"),
            hotspot_id=result.get("hotspot_id"),
            intermediate_steps=result.get("intermediate_steps", []),
        )
        # Override the type with the canonical task.{bvid}.{status} event
        # name so the SSE ``event:`` line in summary_events_route matches the
        # spec contract. Frontend can subscribe on either ``task.*`` or the
        # legacy ``completed|partial|failed|timeout`` names.
        sse_payload["type"] = finalized.event_name
        await self.broadcast(sub.job_id, sse_payload)
        sub.event.set()


# Module-level singleton accessor (re-import safe)
_queue: Optional[SummaryJobQueue] = None


def get_queue() -> SummaryJobQueue:
    """Return (lazily create) the global SummaryJobQueue instance."""
    global _queue
    if _queue is None:
        _queue = SummaryJobQueue()
    return _queue


async def reset_queue_for_tests() -> None:
    """Drop the global queue (used by test fixtures to enforce isolation)."""
    global _queue
    if _queue is not None:
        # 防御：旧实例可能绑在另一个 event loop 上 — 直接放弃所有内部状态
        _queue._queue = None  # type: ignore[attr-defined]
        _queue._lock = None  # type: ignore[attr-defined]
        _queue._stop = None  # type: ignore[attr-defined]
        _queue._worker_task = None  # type: ignore[attr-defined]
        _queue._subscribers.clear()  # type: ignore[attr-defined]
    _queue = None


def drop_queue_sync() -> None:
    """Sync version: just forget the singleton (caller should NOT use it again)."""
    global _queue
    _queue = None
