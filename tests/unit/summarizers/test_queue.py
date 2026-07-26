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


class TestWorkerExceptionLogging:
    """L6: pipeline 抛异常时必须 log stack trace（不只是 error message）。

    背景：之前 ``_run_submission`` 在 except 里只把 ``str(exc)`` 写入
    ``error`` 字段，没调 ``logger.exception``。结果：worker 静默吃异常，
    日志只看到一行 ``summary pipeline failed`` 但没有任何 stack trace，
    调试时只能靠 SSE 客户端收到的 error 字符串反推。修复后必须在 except
    分支里 ``logger.exception(...)`` 一次，让 ops 能直接拿到完整 traceback。
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_submission_logs_stack_trace_on_pipeline_exception(
        self, fresh_queue: SummaryJobQueue, db_session, caplog: pytest.LogCaptureFixture
    ) -> None:
        """_run_submission 在 pipeline 抛异常时必须 logger.exception 调用。"""
        from unittest.mock import patch

        # 让 worker drain 一个提交（pipeline 抛 RuntimeError）
        repo = SqlAlchemySummaryJobRepository(db_session)
        sub = await fresh_queue.enqueue(repo, video_id="BVbreak")

        async def boom(video_id, title, up_name, extra_context=""):
            raise RuntimeError(f"upstream tool blew up for {video_id}")

        with patch("aipulse.summarizers.queue.run_summary_pipeline", new=boom):
            with caplog.at_level("ERROR", logger="aipulse.summarizers.queue"):
                await fresh_queue._run_submission(sub)

        # 至少有一条 ERROR + 含 "summary pipeline raised" + 真正的 stack trace
        records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert any(
            "summary pipeline raised" in r.getMessage() for r in records
        ), f"expected 'summary pipeline raised' log, got {[r.getMessage() for r in records]}"
        # caplog 默认会抓取 exc_info，校验 traceback 内容包含 RuntimeError + boom message
        boom_records = [r for r in records if r.exc_info is not None]
        assert boom_records, "expected at least one record with exc_info (stack trace)"
        # 取任一条的 formatted traceback 验证含关键字符串
        rendered = boom_records[0].exc_info[1]  # the actual RuntimeError instance
        assert isinstance(rendered, RuntimeError)
        assert "upstream tool blew up" in str(rendered)

        # DB row 应被标记为 failed，error 含类型前缀
        row = (
            await db_session.execute(
                select(SummaryJob).where(SummaryJob.id == sub.job_id)
            )
        ).scalar_one()
        assert row.status == JOB_STATUS_FAILED
        assert "RuntimeError" in (row.error or "")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_worker_loop_continues_after_exception(
        self, fresh_queue: SummaryJobQueue, db_session, caplog: pytest.LogCaptureFixture
    ) -> None:
        """一个 job 失败后 worker 不退出，后续 job 仍能被消费。"""
        from unittest.mock import patch

        repo = SqlAlchemySummaryJobRepository(db_session)
        bad = await fresh_queue.enqueue(repo, video_id="BVbad")
        good = await fresh_queue.enqueue(repo, video_id="BVgood")

        async def maybe_ok(video_id, title, up_name, extra_context=""):
            if video_id == "BVbad":
                raise RuntimeError("bad upstream")
            return {
                "status": "completed",
                "note_path": "/vault/BVgood.md",
                "event_id": "evt-good",
                "reminder_id": "rem-good",
                "hotspot_id": "hs-good",
                "error": None,
                "intermediate_steps": [],
            }

        await fresh_queue.start()
        try:
            with patch("aipulse.summarizers.queue.run_summary_pipeline", new=maybe_ok):
                # 等两个 job 都被消费
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    bad_row = (
                        await db_session.execute(
                            select(SummaryJob).where(SummaryJob.id == bad.job_id)
                        )
                    ).scalar_one()
                    good_row = (
                        await db_session.execute(
                            select(SummaryJob).where(SummaryJob.id == good.job_id)
                        )
                    ).scalar_one()
                    if (
                        bad_row.status in (JOB_STATUS_FAILED, JOB_STATUS_COMPLETED)
                        and good_row.status in (JOB_STATUS_FAILED, JOB_STATUS_COMPLETED)
                    ):
                        break
        finally:
            await fresh_queue.stop()

        bad_row = (
            await db_session.execute(
                select(SummaryJob).where(SummaryJob.id == bad.job_id)
            )
        ).scalar_one()
        good_row = (
            await db_session.execute(
                select(SummaryJob).where(SummaryJob.id == good.job_id)
            )
        ).scalar_one()
        assert bad_row.status == JOB_STATUS_FAILED
        # L6 (2026-07-26) 业务侧终态契约：good job 三件齐（hotspot_id +
        # note_path + 无 error）→ completed；缺一项必然降级为 failed/partial。
        assert good_row.status == JOB_STATUS_COMPLETED


class TestL1L6FinalizeContract:
    """L1#3 SSE 广播 + L6 业务侧终态分支（2026-07-26）。

    之前：worker 写 status=completed 时 SSE 只推 ``type: "completed"``，
    前端只能按 status 字符串 grep；异常分支也直接推 ``type: "failed"``，
    pipeline 异常被吞后 status 错位、event 名字也不一致。

    修复后：所有 3 个终态路径都过 finalize；SSE event name 恒为
    ``task.{bvid}.{status}``（L1#3 硬契约）；pipeline 异常必然 → status=failed
    （即便 hotspot_id/note_path 都没填，L6 也不会让 status 错位成 completed）。
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sse_event_name_is_task_dot_bvid_dot_failed_on_exception(
        self, fresh_queue: SummaryJobQueue, db_session
    ) -> None:
        """pipeline 抛 RuntimeError → 订阅者必须收到 ``task.{bvid}.failed`` 事件。"""
        from unittest.mock import patch

        repo = SqlAlchemySummaryJobRepository(db_session)
        sub = await fresh_queue.enqueue(repo, video_id="BVpipeboom")

        async def boom(video_id, title, up_name, extra_context=""):
            raise RuntimeError("upstream tool blew up")

        # subscribe BEFORE running so we capture the broadcast
        sub_q = fresh_queue.subscribe(sub.job_id)

        with patch("aipulse.summarizers.queue.run_summary_pipeline", new=boom):
            await fresh_queue._run_submission(sub)

        # Drain the subscriber queue — should have at least the terminal event
        events = []
        for _ in range(10):
            try:
                events.append(await asyncio.wait_for(sub_q.get(), timeout=0.5))
            except asyncio.TimeoutError:
                break

        # The terminal event must be ``task.{bvid}.failed``
        terminal = [e for e in events if e.get("type", "").endswith(".failed")]
        assert terminal, (
            f"expected terminal event ending with .failed, "
            f"got types: {[e.get('type') for e in events]}"
        )
        assert terminal[-1]["type"] == "task.BVpipeboom.failed"
        assert "RuntimeError" in (terminal[-1].get("error") or "")

        # DB row should be failed (L6 hard contract: error set → failed when
        # hotspot_id/note_path absent)
        row = (
            await db_session.execute(
                select(SummaryJob).where(SummaryJob.id == sub.job_id)
            )
        ).scalar_one()
        assert row.status == JOB_STATUS_FAILED
        assert "RuntimeError" in (row.error or "")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sse_event_name_is_task_dot_bvid_dot_completed_on_success(
        self, fresh_queue: SummaryJobQueue, db_session
    ) -> None:
        """pipeline 完整三件齐（hotspot_id + note_path + 无 error）→ ``task.{bvid}.completed``。"""
        from unittest.mock import patch

        repo = SqlAlchemySummaryJobRepository(db_session)
        sub = await fresh_queue.enqueue(repo, video_id="BVfullwin")

        async def full_success(video_id, title, up_name, extra_context=""):
            return {
                "status": "completed",
                "note_path": f"/vault/{video_id}.md",
                "event_id": "evt-1",
                "reminder_id": "rem-1",
                "hotspot_id": "hs-1",
                "error": None,
                "intermediate_steps": [],
            }

        sub_q = fresh_queue.subscribe(sub.job_id)

        with patch("aipulse.summarizers.queue.run_summary_pipeline", new=full_success):
            await fresh_queue._run_submission(sub)

        events = []
        for _ in range(10):
            try:
                events.append(await asyncio.wait_for(sub_q.get(), timeout=0.5))
            except asyncio.TimeoutError:
                break

        terminal = [e for e in events if e.get("type", "").endswith(".completed")]
        assert terminal
        assert terminal[-1]["type"] == "task.BVfullwin.completed"
        assert terminal[-1]["note_path"] == "/vault/BVfullwin.md"
        assert terminal[-1]["hotspot_id"] == "hs-1"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pipeline_exception_does_not_early_return_skipping_finalize(
        self, fresh_queue: SummaryJobQueue, db_session
    ) -> None:
        """pipeline 异常分支必须在 except 后经过 finalize，不允许 early return。

        L6 硬契约：worker 写 status 前必须 funnel through finalize。验证手段：
        异常路径下的 DB status 必须由 finalize 决定（error + 缺字段 → failed），
        而不是被直接 hardcode 成"failed but with completed-shaped payload"。
        """
        from unittest.mock import patch

        repo = SqlAlchemySummaryJobRepository(db_session)
        sub = await fresh_queue.enqueue(repo, video_id="BVverify")

        async def partial_run(video_id, title, up_name, extra_context=""):
            # pipeline 自身成功返回 status=completed，但缺 hotspot_id
            return {
                "status": "completed",
                "note_path": "/vault/x.md",
                "event_id": "evt",
                "reminder_id": "rem",
                "hotspot_id": None,  # 缺
                "error": None,
                "intermediate_steps": [],
            }

        sub_q = fresh_queue.subscribe(sub.job_id)

        with patch("aipulse.summarizers.queue.run_summary_pipeline", new=partial_run):
            await fresh_queue._run_submission(sub)

        # 缺 hotspot_id → finalize 强制 partial（即使 pipeline 自报 completed）
        row = (
            await db_session.execute(
                select(SummaryJob).where(SummaryJob.id == sub.job_id)
            )
        ).scalar_one()
        assert row.status == JOB_STATUS_PARTIAL
        assert "hotspot_id" in (row.error or "")

        events = []
        for _ in range(10):
            try:
                events.append(await asyncio.wait_for(sub_q.get(), timeout=0.5))
            except asyncio.TimeoutError:
                break
        terminal = [e for e in events if e.get("type", "").endswith(".partial")]
        assert terminal
        assert terminal[-1]["type"] == "task.BVverify.partial"
