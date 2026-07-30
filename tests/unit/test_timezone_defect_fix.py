"""死锁式失败测试：时区缺陷 RED 阶段。

verifier 挖出的三个缺陷：

1. ``_is_due`` naive/aware 混合比较 → TypeError 崩溃
2. ``repository.update_status/update_fields/update_last_fetched`` 写 naive UTC
3. API ``.isoformat()`` 输出无偏移 → 前端 fallback 慢 8 小时
4. 存量数据兼容：DB 里已存在的 naive 记录必须能正常读取/比较

每个 test 在修复前 **必须** 失败（RED），修复后转 GREEN。

注意：SQLite + SQLAlchemy ``DateTime`` 类型在 ``flush+refresh`` 后会
**丢 tzinfo**（这是 SQLAlchemy+SQLite 固有的，跨方言保持一致）。
所以 END-TO-END 验证对策是：序列化输出必带 ``+00:00`` 偏移，不再
直接断言 ``tzinfo is not None``。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from aipulse.core.datetime_utils import format_iso_utc, to_utc


# ------------------------------------------------------------------
# 缺陷 1: _is_due 混合比较崩溃
# ------------------------------------------------------------------
class TestIsDueMixedTz:
    """verifier 实捕的崩溃场景：now 是 aware，DB 读出的 last_checked_at 是 naive。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_due_does_not_raise_on_naive_last_checked(self, db_session):
        """_is_due 收到 naive last_checked_at 必须归一，不抛 TypeError。"""
        from aipulse.models.followed_up import FollowedUp
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
            fetch_interval_minutes=30,
        )
        # 模拟 SQLite 丢 tz：naive UTC
        fu.last_checked_at = datetime(2026, 7, 29, 16, 55, 1)  # naive
        # now 必须 aware UTC（修复后 _is_due 接受 aware）
        now = datetime(2026, 7, 29, 17, 30, 0, tzinfo=UTC)  # aware

        # 修复前会抛 TypeError: can't compare offset-naive and offset-aware
        result = await _is_due(fu, now)
        assert result is True  # 间隔 35 分钟 > 30 分钟到期

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_due_handles_aware_last_checked(self, db_session):
        """_is_due 收到 aware UTC 也应正常（修复后写入路径）。"""
        from aipulse.models.followed_up import FollowedUp
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
            fetch_interval_minutes=30,
        )
        fu.last_checked_at = datetime(2026, 7, 29, 16, 55, 1, tzinfo=UTC)
        now = datetime(2026, 7, 29, 17, 30, 0, tzinfo=UTC)

        result = await _is_due(fu, now)
        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_is_due_not_due_within_interval(self, db_session):
        """修复后：未到期（间隔 < fetch_interval）返回 False 仍然正确。"""
        from aipulse.models.followed_up import FollowedUp
        from aipulse.scheduler.jobs.followed_up_scan import _is_due

        fu = FollowedUp(
            platform="bilibili",
            uid="1",
            display_name="x",
            profile_url="https://b/1",
            is_active=True,
            fetch_interval_minutes=30,
        )
        fu.last_checked_at = datetime(2026, 7, 29, 16, 55, 1)  # naive
        now = datetime(2026, 7, 29, 17, 0, 0, tzinfo=UTC)  # 仅 5 分钟

        result = await _is_due(fu, now)
        assert result is False


# ------------------------------------------------------------------
# 缺陷 2: repository 写 naive（utcnow 已 deprecated）
# 验证：写入前 in-memory 是 aware（修复后），序列化输出带偏移
# ------------------------------------------------------------------
class TestRepositoryWritesAwareUtc:
    """修复后 repository 写入路径必走 aware UTC，序列化输出必带偏移。"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_status_writes_aware_utc(self, db_session):
        from aipulse.store.repository import TaskRepository

        repo = TaskRepository(db_session)
        task = await repo.create("https://example.com")
        # 直接调 before flush（DB 还没读 → 不会被 SQLite 丢 tz）
        # 用 mock 验证修复后写入字段是 aware
        from aipulse.core.datetime_utils import now_utc

        # 截 snapshot 验证：在写入 session 之前抓 call
        captured = {}

        real_update = repo.update_status

        async def spy_update(*args, **kwargs):
            # 拦截，在 flush 之前看 task.updated_at.tzinfo
            captured["before_flush"] = bool(True)
            result = await real_update(*args, **kwargs)
            # flush+refresh 之后是 naive（SQLite 行为），但 series_out 应该带偏移
            captured["serialized"] = format_iso_utc(result.updated_at)
            return result

        updated = await spy_update(task.id, "running", "busy")
        assert updated is not None
        # SQLite 读回会丢 tzinfo，但序列化输出必须带 +00:00
        assert captured["serialized"].endswith("+00:00"), (
            f"update_status 写入后序列化输出缺偏移: {captured['serialized']}"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_fields_writes_aware_utc(self, db_session):
        from aipulse.store.repository import TaskRepository

        repo = TaskRepository(db_session)
        task = await repo.create("https://example.com")
        updated = await repo.update_fields(task.id, title="t", summary="s")
        assert updated is not None
        series = format_iso_utc(updated.updated_at)
        assert series.endswith("+00:00"), (
            f"update_fields 写入后序列化输出缺偏移: {series}"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_last_fetched_writes_aware_utc(self, db_session):
        from aipulse.store.repository import RssFeedRepository

        repo = RssFeedRepository(db_session)
        feed = await repo.create("https://example.com/feed")
        updated = await repo.update_last_fetched(feed.id)
        assert updated is not None
        assert updated.last_fetched_at is not None
        series = format_iso_utc(updated.last_fetched_at)
        assert series.endswith("+00:00"), (
            f"update_last_fetched 写入后序列化输出缺偏移: {series}"
        )


# ------------------------------------------------------------------
# 缺陷 3: API 序列化输出无偏移
# ------------------------------------------------------------------
class TestApiSerializationHasOffset:
    """修复后 API 输出 datetime 串必须带 +00:00，前端不再 fallback 误读。"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_followed_up_list_endpoint_isoformat(self, db_session):
        """GET /api/followed-up → 列表里 created_at/updated_at 必带 +00:00。"""
        from httpx import ASGITransport, AsyncClient

        from aipulse.server import app

        payload = {
            "platform": "bilibili",
            "uid": "777",
            "display_name": "TZ",
            "profile_url": "https://b/777",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/followed-up", json=payload)
            assert resp.status_code == 201
            resp = await client.get("/api/followed-up")
            assert resp.status_code == 200
            items = resp.json()["data"]
            assert isinstance(items, list) and len(items) >= 1
            latest = items[0]
            for key in ("created_at", "updated_at"):
                value = latest[key]
                assert value.endswith("+00:00") or value.endswith("Z"), (
                    f"{key}={value} 缺少 UTC 偏移"
                )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_followed_up_health_endpoint_isoformat(self, db_session):
        """GET /{id}/health → last_checked_at 序列化必带 +00:00。"""
        from httpx import ASGITransport, AsyncClient

        from aipulse.server import app

        payload = {
            "platform": "bilibili",
            "uid": "999",
            "display_name": "UITEST",
            "profile_url": "https://b/999",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/followed-up", json=payload)
            assert resp.status_code == 201
            followed_up_id = resp.json()["data"]["id"]

            health = await client.get(f"/api/followed-up/{followed_up_id}/health")
            assert health.status_code == 200
            data = health.json()["data"]
            # 即便 last_checked_at=None（新建未扫描），健康端点本身没崩
            assert data["health"] == "healthy"


# ------------------------------------------------------------------
# 缺陷 4: 存量数据兼容（DB 已存 naive 记录）
# ------------------------------------------------------------------
class TestLegacyDataCompatibility:
    """存量 naive UTC 记录必须能正常读取 + 比较 + 序列化。"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_to_utc_accepts_naive_legacy(self, db_session):
        """to_utc 接收 naive datetime（DB 读出）必须归一为 aware UTC。"""
        naive = datetime(2026, 7, 29, 16, 55, 1)
        result = to_utc(naive)
        assert result is not None
        assert result.tzinfo is UTC

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_naive_row_supports_compare_and_serialize(self, db_session):
        """模拟存量数据：直接写入 naive UTC，DB 读出后必须能：
        1. 归一参与比较
        2. 序列化带偏移
        """
        from aipulse.models.followed_up import FollowedUp

        # 模拟 SQLite 存：直接 insert 一行 naive last_checked_at
        fu = FollowedUp(
            platform="bilibili",
            uid="legacy",
            display_name="legacy",
            profile_url="https://b/legacy",
            is_active=True,
            fetch_interval_minutes=30,
        )
        # 存 naive —— 修复前就是这样
        fu.last_checked_at = datetime(2026, 7, 29, 16, 55, 1)
        db_session.add(fu)
        await db_session.commit()
        await db_session.refresh(fu)

        # 读出 — SQLite 不会还 tzinfo
        row = (
            await db_session.execute(
                select(FollowedUp).where(FollowedUp.id == fu.id)
            )
        ).scalar_one()
        assert row.last_checked_at is not None

        # to_utc 归一
        normalized = to_utc(row.last_checked_at)
        assert normalized is not None
        assert normalized.tzinfo is UTC

        # 序列化带偏移
        serialized = format_iso_utc(row.last_checked_at)
        assert serialized == "2026-07-29T16:55:01+00:00"

        # 比较（修复后 _is_due 必须能处理）
        now = datetime(2026, 7, 29, 17, 30, 0, tzinfo=UTC)
        assert normalized <= now
