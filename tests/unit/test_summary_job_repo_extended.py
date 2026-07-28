"""Unit tests for repositories/summary_job_repo.py — push coverage ≥80%.

覆盖：
- SummaryJobRecord: 所有字段映射（含 None 兜底）
- SqlAlchemySummaryJobRepository.create: 默认 + 自定义字段
- find_by_id: 存在 / 不存在
- list_recent: 倒序 + limit
- list_for_video: 过滤 + 倒序
- mark_started: 状态转换 + 时间戳
- append_steps: 追加 + 步骤计数
- mark_finished: 所有状态、intermediate_steps 覆盖、未知 status 报错
- annotate: 单/多字段设置
- _require: 抛 SummaryJobNotFoundError
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aipulse.models.summary_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    SummaryJob,
)
from aipulse.repositories.summary_job_repo import (
    SqlAlchemySummaryJobRepository,
    SummaryJobNotFoundError,
    SummaryJobRecord,
)


def _make_row(**kwargs) -> SummaryJob:
    """构造内存 SummaryJob 行（不写库）"""
    defaults = dict(
        id="job1",
        video_id="BV1",
        title="t",
        up_name="up",
        status=JOB_STATUS_QUEUED,
        error=None,
        note_path=None,
        event_id=None,
        reminder_id=None,
        intermediate_steps=None,
        steps_emitted=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=None,
        completed_at=None,
    )
    defaults.update(kwargs)
    return SummaryJob(**defaults)


class TestSummaryJobRecord:
    @pytest.mark.unit
    def test_maps_all_fields_with_none_defaults(self):
        row = _make_row()
        rec = SummaryJobRecord(row)
        assert rec.id == "job1"
        assert rec.video_id == "BV1"
        assert rec.hotspot_id is None
        assert rec.title == "t"
        assert rec.up_name == "up"
        assert rec.status == JOB_STATUS_QUEUED
        assert rec.error is None
        assert rec.note_path is None
        assert rec.event_id is None
        assert rec.reminder_id is None
        assert rec.intermediate_steps == []
        assert rec.steps_emitted == 0

    @pytest.mark.unit
    def test_intermediate_steps_defensive_copy(self):
        """修改外部列表不影响 record"""
        row = _make_row(intermediate_steps=[{"a": 1}])
        rec = SummaryJobRecord(row)
        rec.intermediate_steps.append({"b": 2})
        # 重新构造 record，原列表不变
        rec2 = SummaryJobRecord(row)
        assert rec2.intermediate_steps == [{"a": 1}]


class TestCreate:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_with_minimum_args(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_NEW")
        assert rec.video_id == "BV_NEW"
        assert rec.status == JOB_STATUS_QUEUED
        assert rec.title is None
        assert rec.up_name is None
        assert rec.hotspot_id is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_with_all_args(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(
            video_id="BV_X",
            title="My title",
            up_name="up master",
            hotspot_id="hs-1",
        )
        assert rec.title == "My title"
        assert rec.up_name == "up master"
        assert rec.hotspot_id == "hs-1"


class TestFindById:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        assert await repo.find_by_id("nonexistent") is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_record_when_exists(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_F")
        found = await repo.find_by_id(rec.id)
        assert found is not None
        assert found.id == rec.id
        assert found.video_id == "BV_F"


class TestListRecent:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_jobs(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        result = await repo.list_recent()
        assert list(result) == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_recent_jobs_in_desc_order(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        r1 = await repo.create(video_id="BV_1")
        r2 = await repo.create(video_id="BV_2")
        r3 = await repo.create(video_id="BV_3")
        result = await repo.list_recent(limit=10)
        ids = [r.id for r in result]
        # 倒序：r3 → r2 → r1
        assert ids[0] == r3.id
        assert ids[-1] == r1.id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_respects_limit(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        for i in range(5):
            await repo.create(video_id=f"BV_{i}")
        result = await repo.list_recent(limit=2)
        assert len(result) == 2


class TestListForVideo:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_filters_by_video_id(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        await repo.create(video_id="BV_TARGET")
        await repo.create(video_id="BV_OTHER")
        await repo.create(video_id="BV_TARGET")
        result = await repo.list_for_video("BV_TARGET", limit=10)
        assert len(result) == 2
        for r in result:
            assert r.video_id == "BV_TARGET"


class TestMarkStarted:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transitions_queued_to_running(self, db_session):
        from aipulse.models.summary_jobs import JOB_STATUS_RUNNING

        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_S")
        started = await repo.mark_started(rec.id)
        assert started.status == JOB_STATUS_RUNNING
        assert started.started_at is not None
        assert started.updated_at is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_not_found(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        with pytest.raises(SummaryJobNotFoundError):
            await repo.mark_started("does-not-exist")


class TestAppendSteps:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_appends_to_existing_steps(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_A")
        # 第一次 append
        r1 = await repo.append_steps(rec.id, [{"tool": "t1"}])
        assert len(r1.intermediate_steps) == 1
        assert r1.steps_emitted == 1
        # 第二次 append
        r2 = await repo.append_steps(rec.id, [{"tool": "t2"}, {"tool": "t3"}])
        assert len(r2.intermediate_steps) == 3
        assert r2.steps_emitted == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_starts_from_empty_when_intermediate_steps_is_none(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_B")
        # intermediate_steps 默认 None → append 应从 [] 开始
        r = await repo.append_steps(rec.id, [{"tool": "x"}])
        assert len(r.intermediate_steps) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_not_found(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        with pytest.raises(SummaryJobNotFoundError):
            await repo.append_steps("missing", [{"tool": "x"}])


class TestMarkFinished:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_marks_completed(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_F")
        finished = await repo.mark_finished(
            rec.id,
            JOB_STATUS_COMPLETED,
            note_path="/notes/x.md",
            event_id="ev-1",
            reminder_id="rm-1",
        )
        assert finished.status == JOB_STATUS_COMPLETED
        assert finished.note_path == "/notes/x.md"
        assert finished.event_id == "ev-1"
        assert finished.reminder_id == "rm-1"
        assert finished.completed_at is not None
        assert finished.error is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_marks_failed_with_error(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_F2")
        finished = await repo.mark_finished(
            rec.id, JOB_STATUS_FAILED, error="LLM timeout"
        )
        assert finished.status == JOB_STATUS_FAILED
        assert finished.error == "LLM timeout"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_overrides_intermediate_steps_when_provided(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_F3")
        await repo.append_steps(rec.id, [{"tool": "x"}])
        # mark_finished 传入 intermediate_steps → 覆盖
        finished = await repo.mark_finished(
            rec.id,
            JOB_STATUS_COMPLETED,
            intermediate_steps=[{"tool": "final"}],
        )
        assert finished.intermediate_steps == [{"tool": "final"}]
        assert finished.steps_emitted == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_on_unknown_status(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_F4")
        with pytest.raises(ValueError, match="unknown finish status"):
            await repo.mark_finished(rec.id, "BOGUS_STATUS")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_not_found(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        with pytest.raises(SummaryJobNotFoundError):
            await repo.mark_finished("missing", JOB_STATUS_COMPLETED)


class TestAnnotate:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_annotate_all_three_fields(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_ANN")
        annotated = await repo.annotate(
            rec.id,
            hotspot_id="hs-1",
            title="annotated title",
            up_name="annotated up",
        )
        assert annotated.hotspot_id == "hs-1"
        assert annotated.title == "annotated title"
        assert annotated.up_name == "annotated up"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_annotate_partial(self, db_session):
        """只传 hotspot_id → 其他字段不动"""
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_P", title="orig", up_name="orig_up")
        annotated = await repo.annotate(rec.id, hotspot_id="hs-new")
        assert annotated.hotspot_id == "hs-new"
        assert annotated.title == "orig"
        assert annotated.up_name == "orig_up"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_annotate_no_args_does_nothing(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        rec = await repo.create(video_id="BV_N")
        annotated = await repo.annotate(rec.id)
        assert annotated.hotspot_id is None
        assert annotated.title is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_annotate_raises_not_found(self, db_session):
        repo = SqlAlchemySummaryJobRepository(db_session)
        with pytest.raises(SummaryJobNotFoundError):
            await repo.annotate("missing", hotspot_id="x")