"""Unit tests for in-process SummaryJobQueue.

测试维度：
- enqueue 创建 DB row + 推入队列
- subscribe/unsubscribe 给订阅者通道
- broadcast 把事件送到每个订阅者
- 单 worker 消费，状态流转
- start/stop 幂等
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
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
from aipulse.repositories.summary_job_repo import SqlAlchemySummaryJobRepository
from aipulse.summarizers.queue import JobSubmission, SummaryJobQueue
from aipulse.store.database import get_session_maker


@pytest_asyncio.fixture
async def fresh_queue():
    q = SummaryJobQueue()
    yield q
    await q.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_and_stop_are_idempotent(fresh_queue: SummaryJobQueue) -> None:
    await fresh_queue.start()
    await fresh_queue.start()  # 双启动不应重复 create task
    assert fresh_queue._worker_task is not None  # type: ignore[attr-defined]
    assert not fresh_queue._worker_task.done()  # type: ignore[attr-defined]
    await fresh_queue.stop()
    assert fresh_queue._worker_task is None  # type: ignore[attr-defined]
    await fresh_queue.stop()  # 双停止不应报错


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_creates_db_row_and_submission(
    fresh_queue: SummaryJobQueue, db_session
) -> None:
    from aipulse.repositories.summary_job_repo import SqlAlchemySummaryJobRepository

    repo = SqlAlchemySummaryJobRepository(db_session)
    sub = await fresh_queue.enqueue(repo, video_id="BV1abc")
    assert sub.job_id and len(sub.job_id) == 12
    assert sub.video_id == "BV1abc"
    assert sub.event.is_set() is False

    row = (
        await db_session.execute(
            select(SummaryJob).where(SummaryJob.id == sub.job_id)
        )
    ).scalar_one()
    assert row.video_id == "BV1abc"
    assert row.status == JOB_STATUS_QUEUED


@pytest.mark.unit
@pytest.mark.asyncio
async def test_subscribe_and_broadcast_push_to_subscribers(
    fresh_queue: SummaryJobQueue,
) -> None:
    q = fresh_queue.subscribe("test-job")
    try:
        await fresh_queue.broadcast(
            "test-job",
            {"type": "started", "job_id": "test-job", "video_id": "BV1"},
        )
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "started"
    finally:
        fresh_queue.unsubscribe("test-job", q)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_broadcast_does_not_drop_for_unknown_job(
    fresh_queue: SummaryJobQueue,
) -> None:
    # 对不存在的 job_id 调用 broadcast 不应抛异常
    await fresh_queue.broadcast("nope", {"type": "noop"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_job_id_yields_no_subscribers(
    fresh_queue: SummaryJobQueue,
) -> None:
    sub_q = fresh_queue.subscribe("ghost")
    try:
        # empty subscriber list — broadcast should not put to subs
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_q.get(), timeout=0.3)
    finally:
        fresh_queue.unsubscribe("ghost", sub_q)
