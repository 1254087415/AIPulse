"""Unit tests for aipulse/server.py — push coverage ≥80%.

覆盖：
- _seed_default_sources: 早退 + happy path
- lifespan: auto_create_tables=True + False 两条分支、scheduler/queue start & shutdown
- security_middleware: /api + 无 token → 401；/api + 有 token → 200
- health: 200 ok
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from aipulse.server import _seed_default_sources, app, lifespan


@pytest_asyncio.fixture
async def fresh_client():
    """Client with a clean DB and the app's lifespan NOT yet entered.

    Test imports `lifespan` directly to drive setup/teardown rather than going
    through the FastAPI lifespan stack twice.
    """
    from aipulse.store.database import reset_db

    await reset_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def _reregister_real_collectors() -> None:
    """清空 registry，重新触发所有真 collector module 顶层 register() 调用。

    测试间 shared module state — fake test 注册 fake 到 registry；如果只
    `import aipulse.collectors.arxiv` 已存在 sys.modules，Python 不会重跑 module body。
    必须用 `importlib.reload()` 才能让 module body 重新执行（call register()），
    然后我们的真 collector 才会重新注册。
    """
    import importlib

    from aipulse.collectors import registry

    registry.clear_registry()
    for mod_name in (
        "aipulse.collectors.news",
        "aipulse.collectors.github",
        "aipulse.collectors.arxiv",
        "aipulse.collectors.bilibili",
        "aipulse.collectors.zhihu",
        "aipulse.collectors.weibo",
        "aipulse.collectors.baidu",
        "aipulse.collectors.v2ex",
    ):
        # reload 而非 import — module body 中 @register 装饰器必须重新执行
        mod = importlib.import_module(mod_name)
        importlib.reload(mod)


class TestSeedDefaultSources:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_creates_default_sources_when_db_empty(self):
        from aipulse.hotspot.models import Source
        from aipulse.store.database import get_session_maker, reset_db
        from sqlalchemy import func, select

        # 强制 reset → DB 空 schema 一致
        await reset_db()
        # 确保 8 个真实 collectors 都注册到全局 registry（前面测试可能 clear 过）
        _reregister_real_collectors()

        # DB empty → seed should populate
        await _seed_default_sources()

        async with get_session_maker()() as s:
            count = (
                await s.execute(select(func.count()).select_from(Source))
            ).scalar_one()
            assert count > 0
            types = (
                await s.execute(select(Source.source_type))
            ).scalars().all()
            assert any(
                t in types for t in ("rss_news", "github", "arxiv")
            ), f"expected at least one known source type, got {types}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_op_when_db_already_seeded(self):
        from aipulse.hotspot.models import Source
        from aipulse.store.database import get_session_maker, reset_db
        from sqlalchemy import func, select

        await reset_db()
        _reregister_real_collectors()

        # 第一次 seed
        await _seed_default_sources()

        async with get_session_maker()() as s:
            before = (
                await s.execute(select(func.count()).select_from(Source))
            ).scalar_one()

        # 第二次应该早退，count 不变
        await _seed_default_sources()
        async with get_session_maker()() as s:
            after = (
                await s.execute(select(func.count()).select_from(Source))
            ).scalar_one()
        assert before == after


class TestLifespan:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lifespan_with_auto_create_tables_runs_seed(self):
        """auto_create_tables=True → init_db + seed 真实执行；scheduler/queue patch"""
        from aipulse.hotspot.models import Source
        from aipulse.store.database import get_session_maker, reset_db

        await reset_db()

        # patch get_settings().auto_create_tables=True is default; patch scheduler/queue
        fake_scheduler = MagicMock()
        fake_queue = AsyncMock()

        with patch("aipulse.server.get_scheduler", return_value=fake_scheduler):
            with patch("aipulse.server.get_queue", return_value=fake_queue):
                async with lifespan(app):
                    pass

        # scheduler.add_job 被调用四次：
        # hotspot_sync + digest_generate + vault_scan + register_followed_up_jobs
        assert fake_scheduler.add_job.call_count == 4
        # register_followed_up_jobs 注册的 job id 必须存在
        job_ids = {
            call.kwargs.get("id") for call in fake_scheduler.add_job.call_args_list
        }
        assert "followed_up_scan_all" in job_ids
        # scheduler.start / shutdown
        fake_scheduler.start.assert_called_once()
        fake_scheduler.shutdown.assert_called_once_with(wait=False)
        # queue.start / stop
        fake_queue.start.assert_awaited_once()
        fake_queue.stop.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lifespan_skips_init_when_auto_create_tables_false(self):
        """auto_create_tables=False → 跳过 init_db + seed；其他仍跑"""
        from aipulse.core.config import get_settings

        # 用 settings singleton 的代理 mock — patch get_settings() 返回 MagicMock
        fake_settings = MagicMock()
        fake_settings.auto_create_tables = False

        fake_scheduler = MagicMock()
        fake_queue = AsyncMock()

        with patch("aipulse.server.get_settings", return_value=fake_settings):
            with patch("aipulse.server.init_db", new=AsyncMock()) as mock_init:
                with patch(
                    "aipulse.server._seed_default_sources", new=AsyncMock()
                ) as mock_seed:
                    with patch("aipulse.server.get_scheduler", return_value=fake_scheduler):
                        with patch(
                            "aipulse.server.get_queue", return_value=fake_queue
                        ):
                            async with lifespan(app):
                                pass

        mock_init.assert_not_awaited()
        mock_seed.assert_not_awaited()
        # scheduler & queue 仍初始化 — register_followed_up_jobs 也会 add_job
        assert fake_scheduler.add_job.call_count == 4
        job_ids = {
            call.kwargs.get("id") for call in fake_scheduler.add_job.call_args_list
        }
        assert "followed_up_scan_all" in job_ids
        fake_scheduler.start.assert_called_once()
        fake_queue.start.assert_awaited_once()


class TestHealthEndpoint:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, fresh_client):
        resp = await fresh_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ok"


class TestSecurityMiddleware:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_api_without_token_returns_401(self, fresh_client):
        """没有 Authorization header 头 /api 请求 → 401 + security headers

        需要让 verify_auth_header 返回 False — 默认 aipulse_api_token 为空跳过验证，
        我们 patch verify_auth_header 为 False 模拟 token 已配置但请求未带。
        """
        # server.py 已经 from-import verify_auth_header，所以 patch `aipulse.server.verify_auth_header`
        from aipulse import server as server_mod

        with patch.object(server_mod, "verify_auth_header", return_value=False):
            resp = await fresh_client.get("/api/sources")
        assert resp.status_code == 401
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert "Referrer-Policy" in resp.headers
        assert "Content-Security-Policy" in resp.headers

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_api_with_bearer_token_proceeds(self, fresh_client):
        """有正确 Bearer → middleware 通过，路由本身可能 200/401/422/5xx，但不应是 401 (middleware)"""
        from aipulse import server as server_mod

        with patch.object(server_mod, "verify_auth_header", return_value=True):
            resp = await fresh_client.get(
                "/api/sources", headers={"Authorization": "Bearer xxxx"}
            )
        # 不该 401（middleware 通过）
        assert resp.status_code != 401

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_api_path_does_not_require_auth(self, fresh_client):
        """/health 不需要 token"""
        # patch verify_auth_header 为 False → middleware 对非 /api 路径应不调用
        from aipulse import server as server_mod

        with patch.object(server_mod, "verify_auth_header", return_value=False):
            resp = await fresh_client.get("/health")
        # 不该 401
        assert resp.status_code != 401
