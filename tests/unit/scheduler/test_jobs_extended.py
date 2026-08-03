"""Extended unit tests for scheduler/jobs/* — push coverage ≥80%.

覆盖：
- jobs/hotspot_sync.py (16% → ≥80%): sync_source_by_id 成功/不存在/异常；
  sync_all_sources 遍历 active sources + 异常路径 + collector.close 路径
- jobs/vault_scan.py (43% → ≥80%): vault 缺失、scan 成功
- jobs/digest_generate.py (60% → ≥80%): generate_daily_digest 调用 generate_digest
- jobs/followed_up_scan.py (67% → ≥80%):
  - _is_due: is_active=False / deleted / last_checked_at=None / 到期 / 未到期
  - upsert_hotspot_from_video: 新增 / 已存在
  - scan_followed_up_by_id: 不存在 / deleted / 成功
  - scan_all_followed_up: 全部 candidates / 不到期跳过 / 异常跳过
  - _scan_one: collector fetch 异常 / 空 videos / 成功
  - register_followed_up_jobs: 调用 add_job
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register
from aipulse.hotspot.models import Hotspot, Source
from aipulse.models.followed_up import FollowedUp


# ---------- helpers ----------


# ============================================================
# hotspot_sync.py
# ============================================================
class TestHotspotSyncById:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_source_missing(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_source_by_id

        result = await sync_source_by_id("nonexistent-id")
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_returns_processed_count(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_source_by_id

        # 注册一个 fake collector
        class _FakeCollector(BaseCollector):
            source_type = "fake_hotspot_test"
            name = "fake"

            def __init__(self, **_config):
                self._closed = False

            async def fetch(self):
                return [
                    RawItem(
                        title="hello",
                        url="https://example.com/x",
                        content="c",
                        published_at=datetime.now(UTC),
                        raw_metadata={},
                    )
                ]

            def normalize(self, raw):
                return HotspotCandidate(
                    title=raw.title,
                    url=raw.url,
                    canonical_url=raw.url,
                    content=raw.content,
                    published_at=raw.published_at,
                    source_type="fake_hotspot_test",
                    raw_metadata={},
                )

            async def close(self):
                self._closed = True

        register(_FakeCollector)

        s = Source(
            name="fake-src",
            source_type="fake_hotspot_test",
            collector_class="fake",
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        # Patch analyze_hotspot so we don't depend on LLM adapter
        with patch(
            "aipulse.hotspot.service.analyze_hotspot",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = type("A", (), {"is_real": True, "relevance": 80, "importance": "medium", "summary": "x", "category": "tech"})()
            result = await sync_source_by_id(s.id)
        assert result == 1  # 1 new hotspot

        # sync 内部 commit 了；用 db_session 验证需要重新查询
        from sqlalchemy import select, text
        from aipulse.hotspot.models import Hotspot
        from aipulse.store.database import get_session_maker

        # 用全新的 session
        async with get_session_maker()() as fresh_s:
            h_count = (
                await fresh_s.execute(select(Hotspot))
            ).scalars().all()
            assert h_count[0].source_id == s.id
            refreshed = (
                await fresh_s.execute(
                    select(Source).where(Source.id == s.id)
                )
            ).scalar_one()
            print(f"DEBUG last_fetched_at={refreshed.last_fetched_at}, last_error={refreshed.last_error}")
            # 直接 SQL
            r = await fresh_s.execute(
                text("SELECT last_fetched_at, last_error FROM sources WHERE id=:id"),
                {"id": s.id},
            )
            row = r.fetchone()
            print(f"DEBUG SQL: last_fetched_at={row[0]}, last_error={row[1]}")
            assert refreshed.last_fetched_at is not None
            assert refreshed.last_error is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collector_exception_persists_error(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_source_by_id

        class _BoomCollector(BaseCollector):
            source_type = "boom_collector_test"
            name = "boom"

            def __init__(self, **_config):
                pass

            async def fetch(self):
                raise RuntimeError("fetch exploded")

            def normalize(self, raw):
                raise NotImplementedError

            async def close(self):
                pass

        register(_BoomCollector)

        s = Source(
            name="boom-src",
            source_type="boom_collector_test",
            collector_class="boom",
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        result = await sync_source_by_id(s.id)
        assert result == 0

        # sync 内部 commit 了；用全新 session 验证避免 fixture session transaction 隔离
        from sqlalchemy import select
        from aipulse.hotspot.models import Source as SourceModel
        from aipulse.store.database import get_session_maker

        async with get_session_maker()() as fresh_s:
            refreshed = (
                await fresh_s.execute(
                    select(SourceModel).where(SourceModel.id == s.id)
                )
            ).scalar_one()
            assert refreshed.last_error is not None
            assert "exploded" in refreshed.last_error
            assert refreshed.failed_at is not None


class TestHotspotSyncAll:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_when_no_active_sources(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_all_sources

        result = await sync_all_sources()
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_iterates_active_sources_and_returns_total(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_all_sources

        class _OKCollector(BaseCollector):
            source_type = "ok_all_test"
            name = "ok"

            def __init__(self, **_config):
                self._closed = False

            async def fetch(self):
                return [
                    RawItem(
                        title="t1",
                        url="https://example.com/a",
                        content="x",
                        published_at=datetime.now(UTC),
                        raw_metadata={},
                    )
                ]

            def normalize(self, raw):
                return HotspotCandidate(
                    title=raw.title,
                    url=raw.url,
                    canonical_url=raw.url,
                    content=raw.content,
                    published_at=raw.published_at,
                    source_type="ok_all_test",
                    raw_metadata={},
                )

            async def close(self):
                self._closed = True

        register(_OKCollector)

        # 加 active + inactive 两个 source
        active = Source(
            name="ok-active",
            source_type="ok_all_test",
            collector_class="ok",
            is_active=True,
        )
        inactive = Source(
            name="ok-inactive",
            source_type="ok_all_test",
            collector_class="ok",
            is_active=False,
        )
        db_session.add_all([active, inactive])
        await db_session.commit()

        with patch(
            "aipulse.hotspot.service.analyze_hotspot",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = type("A", (), {"is_real": True, "relevance": 80, "importance": "medium", "summary": "x", "category": "tech"})()
            result = await sync_all_sources()
        assert result == 1  # 只扫 active 那个

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_continues_on_per_source_error(self, db_session):
        from aipulse.scheduler.jobs.hotspot_sync import sync_all_sources

        class _MixedCollector(BaseCollector):
            source_type = "mixed_test"
            name = "mixed"

            _raise = False  # 切换用：第二个 instance 失败

            def __init__(self, **_config):
                self._call_count = 0

            async def fetch(self):
                self._call_count += 1
                if self._call_count > 1:
                    raise RuntimeError("second call boom")
                return [
                    RawItem(
                        title="ok",
                        url="https://example.com/m",
                        content="x",
                        published_at=datetime.now(UTC),
                        raw_metadata={},
                    )
                ]

            def normalize(self, raw):
                return HotspotCandidate(
                    title=raw.title,
                    url=raw.url,
                    canonical_url=raw.url,
                    content=raw.content,
                    published_at=raw.published_at,
                    source_type="mixed_test",
                    raw_metadata={},
                )

            async def close(self):
                pass

        register(_MixedCollector)

        s = Source(
            name="mixed-src",
            source_type="mixed_test",
            collector_class="mixed",
            is_active=True,
        )
        db_session.add(s)
        await db_session.commit()

        # 第一次 sync 成功
        await sync_all_sources()
        # 第二次 sync 抛异常 — 不应冒泡
        result = await sync_all_sources()
        # 0 因为第二次全失败
        assert result == 0


# ============================================================
# vault_scan.py
# ============================================================
class TestVaultScanJob:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_vault_missing(self):
        from aipulse.scheduler.jobs.vault_scan import scan_obsidian_vault_job

        settings = MagicMock()
        settings.obsidian_vault_path = MagicMock()
        settings.obsidian_vault_path.exists.return_value = False
        settings.obsidian_vault_path.is_dir.return_value = False
        settings.obsidian_archive_folder = "AIPulse"

        with patch("aipulse.scheduler.jobs.vault_scan.get_settings", return_value=settings):
            result = await scan_obsidian_vault_job()

        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_count_when_vault_present(self, tmp_path):
        from aipulse.scheduler.jobs.vault_scan import scan_obsidian_vault_job

        settings = MagicMock()
        settings.obsidian_vault_path = tmp_path  # 真目录
        settings.obsidian_archive_folder = "AIPulse"

        fake_notes = [MagicMock(), MagicMock(), MagicMock()]
        with patch("aipulse.scheduler.jobs.vault_scan.get_settings", return_value=settings):
            with patch(
                "aipulse.scheduler.jobs.vault_scan.scan_vault",
                return_value=fake_notes,
            ):
                result = await scan_obsidian_vault_job()

        assert result == 3


# ============================================================
# digest_generate.py
# ============================================================
class TestDigestGenerate:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calls_generate_digest(self, db_session):
        from aipulse.scheduler.jobs.digest_generate import generate_daily_digest

        # generate_digest 在 import 时已被绑定到 digest_generate 模块的 namespace
        # → 必须 patch 模块里的引用
        with patch(
            "aipulse.scheduler.jobs.digest_generate.generate_digest",
            new_callable=AsyncMock,
        ) as mock_gen:
            await generate_daily_digest()
            assert mock_gen.call_count == 1


# ============================================================
# followed_up_scan.py
# ============================================================
class TestIsDue:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_inactive_returns_false(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=False,
        )
        assert await _is_due(fu, datetime.now(UTC)) is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deleted_returns_false(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
        )
        fu.deleted_at = datetime.now(UTC)
        assert await _is_due(fu, datetime.now(UTC)) is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_never_checked_returns_true(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
        )
        fu.last_checked_at = None
        assert await _is_due(fu, datetime.now(UTC)) is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_due_when_interval_elapsed(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
            fetch_interval_minutes=30,
        )
        fu.last_checked_at = datetime.now(UTC) - timedelta(minutes=31)
        assert await _is_due(fu, datetime.now(UTC)) is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_not_due_within_interval(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
            fetch_interval_minutes=30,
        )
        fu.last_checked_at = datetime.now(UTC) - timedelta(minutes=10)
        assert await _is_due(fu, datetime.now(UTC)) is False


def _make_upvideo(bvid: str = "BV1"):
    from aipulse.collectors.bilibili_up.base import UpVideo

    return UpVideo(
        bvid=bvid,
        title=f"title-{bvid}",
        pubdate=datetime.now(UTC),
        duration_sec=60,
        description="",
        cover_url="https://",
        play_count=10,
        is_backfill=False,
    )


class TestUpsertHotspotFromVideo:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_inserts_new_hotspot(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import upsert_hotspot_from_video

        fu = FollowedUp(
            platform="bilibili",
            uid="10001",
            display_name="UP1",
            profile_url="https://b/10001",
        )
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        v = _make_upvideo("BV_NEW")
        result = await upsert_hotspot_from_video(fu, v)
        # v0.3 round 6: 返回 Hotspot | None（不再返回 0/1 int）
        assert result is not None
        assert result.content_id == "BV_NEW"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_existing(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import upsert_hotspot_from_video

        fu = FollowedUp(
            platform="bilibili",
            uid="10002",
            display_name="UP2",
            profile_url="https://b/10002",
        )
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        v = _make_upvideo("BV_DUP")
        # 先插入一次
        first = await upsert_hotspot_from_video(fu, v)
        assert first is not None
        # 再插入相同 bvid → 返回 None
        second = await upsert_hotspot_from_video(fu, v)
        assert second is None


class TestScanFollowedUpById:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_when_missing(self, db_session):
        """L1 #3：未知 id 必须 raise，不能静默返空 ScanOutcome。"""
        from aipulse.repositories.followed_up_repo import FollowedUpNotFoundError
        from aipulse.scheduler.jobs.followed_up_scan import scan_followed_up_by_id

        with pytest.raises(FollowedUpNotFoundError):
            await scan_followed_up_by_id("does-not-exist")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_when_soft_deleted(self, db_session):
        """L1 #3：已软删的 id 也必须 raise，不能静默返空 ScanOutcome。"""
        from aipulse.repositories.followed_up_repo import FollowedUpNotFoundError
        from aipulse.scheduler.jobs.followed_up_scan import scan_followed_up_by_id

        fu = FollowedUp(
            platform="bilibili",
            uid="10003",
            display_name="UP3",
            profile_url="https://b/10003",
        )
        fu.deleted_at = datetime.now(UTC)
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        with pytest.raises(FollowedUpNotFoundError):
            await scan_followed_up_by_id(fu.id)


class TestScanAllFollowedUp:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_skips_inactive_or_deleted(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import scan_all_followed_up

        # 加 1 active + 1 deleted
        active = FollowedUp(
            platform="bilibili",
            uid="10010",
            display_name="UP10",
            profile_url="https://b/10010",
        )
        deleted = FollowedUp(
            platform="bilibili",
            uid="10011",
            display_name="UP11",
            profile_url="https://b/10011",
        )
        deleted.deleted_at = datetime.now(UTC)
        inactive = FollowedUp(
            platform="bilibili",
            uid="10012",
            display_name="UP12",
            profile_url="https://b/10012",
            is_active=False,
        )
        db_session.add_all([active, deleted, inactive])
        await db_session.commit()

        # collector 啥都不返回
        fake_factory = MagicMock()
        fake_collector = MagicMock()
        fake_collector.fetch_videos = AsyncMock(return_value=[])
        fake_collector.close = AsyncMock()
        fake_factory.create = MagicMock(return_value=fake_collector)

        with patch(
            "aipulse.scheduler.jobs.followed_up_scan.BilibiliUpCollectorFactory",
            fake_factory,
        ):
            result = await scan_all_followed_up()

        # 只有 active 的被扫，删的/inactive 被跳过
        assert fake_collector.fetch_videos.call_count == 1
        assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_continues_on_per_up_exception(self, db_session):
        from aipulse.scheduler.jobs.followed_up_scan import scan_all_followed_up

        fu = FollowedUp(
            platform="bilibili",
            uid="10020",
            display_name="UP20",
            profile_url="https://b/10020",
        )
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        fake_collector = MagicMock()
        fake_collector.fetch_videos = AsyncMock(side_effect=RuntimeError("network down"))
        fake_collector.close = AsyncMock()
        fake_factory = MagicMock()
        fake_factory.create = MagicMock(return_value=fake_collector)

        with patch(
            "aipulse.scheduler.jobs.followed_up_scan.BilibiliUpCollectorFactory",
            fake_factory,
        ):
            # 异常被吞，返回 0
            result = await scan_all_followed_up()
            assert result == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scan_one_success_processes_videos(self, db_session):
        """scan_followed_up_by_id 调用 _scan_one → 返回新增 hotspot 数。"""
        from aipulse.scheduler.jobs.followed_up_scan import scan_followed_up_by_id

        fu = FollowedUp(
            platform="bilibili",
            uid="10030",
            display_name="UP30",
            profile_url="https://b/10030",
            collector_strategy="uapi",
        )
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        # fake collector 返回 2 个 video
        v1 = _make_upvideo("BV_A")
        v2 = _make_upvideo("BV_B")
        fake_collector = MagicMock()
        fake_collector.fetch_videos = AsyncMock(return_value=[v1, v2])
        fake_collector.close = AsyncMock()
        fake_factory = MagicMock()
        fake_factory.create = MagicMock(return_value=fake_collector)

        with patch(
            "aipulse.scheduler.jobs.followed_up_scan.BilibiliUpCollectorFactory",
            fake_factory,
        ):
            result = await scan_followed_up_by_id(fu.id)
            # v0.3 round 6: ScanOutcome — new_hotspots 是新插入数
            assert result.new_hotspots == 2

        # last_cursor_id 应该被设置成第一个 bvid
        from aipulse.store.database import get_session_maker
        async with get_session_maker()() as fresh_s:
            from sqlalchemy import select
            refreshed = (
                await fresh_s.execute(select(FollowedUp).where(FollowedUp.id == fu.id))
            ).scalar_one()
            assert refreshed.last_cursor_id == "BV_A"
            assert refreshed.health == "healthy"


class TestRegisterFollowedUpJobs:
    @pytest.mark.unit
    def test_registers_interval_job(self):
        from aipulse.scheduler.jobs.followed_up_scan import register_followed_up_jobs

        scheduler = MagicMock()
        register_followed_up_jobs(scheduler)
        assert scheduler.add_job.call_count == 1
        kwargs = scheduler.add_job.call_args.kwargs
        assert kwargs["id"] == "followed_up_scan_all"
        assert kwargs["trigger"] == "interval"
        assert kwargs["minutes"] == 1
        assert kwargs["max_instances"] == 1


class TestHasRunningLoop:
    @pytest.mark.unit
    def test_returns_false_outside_loop(self):
        from aipulse.scheduler.jobs.followed_up_scan import _has_running_loop

        assert _has_running_loop() is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_true_inside_loop(self):
        from aipulse.scheduler.jobs.followed_up_scan import _has_running_loop

        assert _has_running_loop() is True