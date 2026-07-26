"""Summary HTTP API + SSE streaming (spec §5.5, §6.4).

路由：
- ``POST   /api/summary/{video_id}``     异步入队，返回 202 + job_id
- ``GET    /api/summary/job/{job_id}``   单次拉取 job 状态
- ``GET    /api/summary/jobs``           列最近的 jobs
- ``GET    /api/summary/events/{job_id}``  SSE 事件流（started/completed/failed/timeout）
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.repositories.summary_job_repo import (
    SqlAlchemySummaryJobRepository,
    SummaryJobRecord,
)
from aipulse.store.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/summary", tags=["summary"])


def _serialize(record: SummaryJobRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "video_id": record.video_id,
        "hotspot_id": record.hotspot_id,
        "title": record.title,
        "up_name": record.up_name,
        "status": record.status,
        "error": record.error,
        "note_path": record.note_path,
        "event_id": record.event_id,
        "reminder_id": record.reminder_id,
        "steps_emitted": record.steps_emitted,
        "intermediate_steps": record.intermediate_steps,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }


@router.post("/{video_id}", status_code=202)
async def enqueue_summary_route(
    video_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Enqueue a summary pipeline job for a Bilibili video.

    返回 202 + job_id。前端订阅 /events/{job_id} SSE 流拿进度。
    同 video 在 running 状态时再请求会返回 409。
    """
    from sqlalchemy import select

    from aipulse.hotspot.models import Hotspot
    from aipulse.models.summary_jobs import JOB_STATUS_QUEUED, JOB_STATUS_RUNNING, SummaryJob

    video_id = video_id.strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id 不能为空")

    repo = SqlAlchemySummaryJobRepository(session)
    # 幂等性：若最近已有 running/queued 的同 video job, 直接复用
    stmt = (
        select(SummaryJob)
        .where(SummaryJob.video_id == video_id)
        .where(SummaryJob.status.in_([JOB_STATUS_QUEUED, JOB_STATUS_RUNNING]))
        .order_by(SummaryJob.created_at.desc())
        .limit(1)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        await session.commit()
        return {
            "success": True,
            "data": {
                "job_id": existing.id,
                "status": existing.status,
                "reused": True,
                "video_id": video_id,
            },
        }

    # 找 hotspot（用于 up_name/title 上下文）
    hotspot = (
        await session.execute(
            select(Hotspot).where(Hotspot.content_id == video_id).limit(1)
        )
    ).scalar_one_or_none()
    title: str | None = None
    up_name: str | None = None
    hotspot_id: str | None = None
    if hotspot is not None:
        hotspot_id = hotspot.id
        title = hotspot.title
        # UP主名走 followed_up.display_name
        from aipulse.models.followed_up import FollowedUp  # local to avoid cycle

        if hotspot.followed_up_id:
            up_row = await session.execute(
                select(FollowedUp).where(FollowedUp.id == hotspot.followed_up_id)
            )
            up = up_row.scalar_one_or_none()
            if up is not None:
                up_name = up.display_name

    from aipulse.summarizers.queue import QueueFullError, get_queue

    queue = get_queue()
    await queue.start()
    try:
        submission = await queue.enqueue(
            repo,
            video_id=video_id,
            title=title or "",
            up_name=up_name or "",
        )
    except QueueFullError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=429,
            detail={
                "error": "QUEUE_FULL",
                "message": f"总结队列已满（{exc.size}/{exc.max_size}），请稍后重试",
                "size": exc.size,
                "max_size": exc.max_size,
            },
        ) from None
    if hotspot_id is not None:
        await repo.annotate(
            submission.job_id,
            hotspot_id=hotspot_id,
            title=title,
            up_name=up_name,
        )
    await session.commit()

    return {
        "success": True,
        "data": {
            "job_id": submission.job_id,
            "status": JOB_STATUS_QUEUED,
            "reused": False,
            "video_id": video_id,
        },
    }


@router.get("/jobs")
async def list_jobs_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> dict[str, Any]:
    repo = SqlAlchemySummaryJobRepository(session)
    records = await repo.list_recent(limit=limit)
    await session.commit()
    return {
        "success": True,
        "data": [_serialize(r) for r in records],
    }


@router.post("/job/{job_id}/retry", status_code=202)
async def retry_job_route(
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Retry a failed/timeout job by enqueuing a fresh run for the same video.

    Creates a NEW SummaryJob (video_id 不变) so DB 留有 retry trail。
    若旧 job 已 completed/failed 之外的 status（如 queued/running），返回 409。
    """
    from sqlalchemy import select

    from aipulse.models.summary_jobs import (
        JOB_STATUS_COMPLETED,
        JOB_STATUS_FAILED,
        JOB_STATUS_PARTIAL,
        JOB_STATUS_QUEUED,
        JOB_STATUS_RUNNING,
        JOB_STATUS_TIMEOUT,
        SummaryJob,
    )

    repo = SqlAlchemySummaryJobRepository(session)
    old = await repo.find_by_id(job_id)
    await session.commit()
    if old is None:
        raise HTTPException(status_code=404, detail="job not found")

    reusable = {JOB_STATUS_FAILED, JOB_STATUS_TIMEOUT, JOB_STATUS_PARTIAL, JOB_STATUS_COMPLETED}
    if old.status not in reusable:
        raise HTTPException(
            status_code=409,
            detail=f"job 处于 {old.status}，不能 retry",
        )

    from aipulse.summarizers.queue import get_queue

    queue = get_queue()
    await queue.start()

    # 复用 enqueue，但先直接复用 record 已经是 queued state →
    # 我们手动写一条新 row + push 到 queue
    repo2 = SqlAlchemySummaryJobRepository(session)
    record = await repo2.create(
        video_id=old.video_id,
        title=old.title or "",
        up_name=old.up_name or "",
    )
    if old.hotspot_id:
        await repo2.annotate(record.id, hotspot_id=old.hotspot_id)
    await session.commit()

    submission = await queue.enqueue(
        repo2,
        video_id=old.video_id,
        title=old.title or "",
        up_name=old.up_name or "",
    )
    # overwrite the job_id with the freshly-created one (queue already used it)
    # Actually submission.job_id == record.id at this point
    return {
        "success": True,
        "data": {
            "new_job_id": submission.job_id,
            "old_job_id": job_id,
            "video_id": old.video_id,
            "reused": False,
        },
    }


@router.get("/job/{job_id}")
async def get_job_route(
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    repo = SqlAlchemySummaryJobRepository(session)
    record = await repo.find_by_id(job_id)
    await session.commit()
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "success": True,
        "data": _serialize(record),
    }


@router.get("/events/{job_id}")
async def summary_events_route(job_id: str, request: Request):
    """SSE stream of job progress events.

    发送事件类型：
    - started  ：worker 已开始运行
    - completed: pipeline 完整成功
    - partial  : 部分步骤成功（如 judge=False 早退）
    - failed   : 工具/异常失败
    - timeout  : 5 分钟硬超时
    - closing  : 服务端正常关闭（消费者断连前发一次）
    """
    from aipulse.summarizers.queue import get_queue

    queue = get_queue()

    async def event_gen():
        # subscribe BEFORE pulling DB status to avoid race
        sub_q = queue.subscribe(job_id)
        # Track whether we already emitted a started event so that we don't
        # double-yield it when the snapshot replay collides with the worker's
        # real ``broadcast("task.{bvid}.started")`` (race resolution).
        emitted_started = False
        try:
            # emit current snapshot first (so clients that connect late
            # still see the latest state)
            from aipulse.store.database import get_session_maker

            async with get_session_maker()() as session:
                repo = SqlAlchemySummaryJobRepository(session)
                record = await repo.find_by_id(job_id)
                if record is None:
                    yield {
                        "event": "error",
                        "data": json.dumps({"job_id": job_id, "error": "not_found"}),
                    }
                    return
                if record.status not in ("queued", "running"):
                    yield {
                        "event": record.status,
                        "data": json.dumps(_serialize(record)),
                    }
                    return
                # L1#3 (2026-07-26) — already-running job may have emitted
                # ``task.{bvid}.started`` BEFORE this SSE handler subscribed
                # (race: POST → worker fires immediately). Replay the started
                # event so consumers that connect after POST still see it.
                snapshot = _serialize(record)
                snapshot["type"] = f"task.{record.video_id}.started"
                yield {
                    "event": snapshot["type"],
                    "data": json.dumps(snapshot, default=str),
                }
                emitted_started = True

            while True:
                if await request.is_disconnected():
                    break
                # timeout loop to detect client disconnect when queue is idle
                try:
                    event = await asyncio.wait_for(sub_q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # heartbeat
                    yield {"event": "heartbeat", "data": "{}"}
                    continue
                # Dedupe: skip the worker's real started broadcast if we
                # already replayed one from the snapshot path above.
                type_str = event.get("type") or ""
                if type_str.endswith(".started") and emitted_started:
                    continue
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event, default=str),
                }
                # L1#3 (2026-07-26) — ``type`` 现在是 ``task.{bvid}.{status}``
                # 形态（不只是裸 status 字符串）。抽出尾段决定 loop 是否退出。
                terminal = type_str.rsplit(".", 1)[-1] if type_str else ""
                if terminal in {"completed", "partial", "failed", "timeout"}:
                    break
            yield {"event": "closing", "data": "{}"}
        finally:
            queue.unsubscribe(job_id, sub_q)

    return EventSourceResponse(event_gen())
