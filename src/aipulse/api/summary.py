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

    from aipulse.summarizers.queue import get_queue

    queue = get_queue()
    await queue.start()
    submission = await queue.enqueue(
        repo,
        video_id=video_id,
        title=title or "",
        up_name=up_name or "",
    )
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
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event, default=str),
                }
                if event.get("type") in {"completed", "partial", "failed", "timeout"}:
                    break
            yield {"event": "closing", "data": "{}"}
        finally:
            queue.unsubscribe(job_id, sub_q)

    return EventSourceResponse(event_gen())
