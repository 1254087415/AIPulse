"""Integration tests for followed_up scan scheduler job.

Mock httpx (respx) to simulate UAPI / HTML responses.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
import respx

from aipulse.core.config import get_settings
from aipulse.scheduler.jobs.followed_up_scan import (
    scan_all_followed_up,
    scan_followed_up_by_id,
)
from aipulse.store.database import reset_db


UAPI_BASE = "https://uapis.cn/api/v1"
ARCHIVES_PATH = "/social/bilibili/archives"
SPACE_URL = "https://space.bilibili.com/1567748478"


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await reset_db()
    yield


@pytest.fixture
def sample_uapi_payload():
    # 新端点（2026-07 切到 /social/bilibili/archives）响应形态：
    # 无外层 code 包裹；total/page/size/videos
    return {
        "total": 2,
        "page": 1,
        "size": 50,
        "videos": [
            {
                "bvid": "BV1new",
                "title": "新视频",
                "publish_time": 1721000000,
                "duration": 600,
                "play_count": 100,
            },
            {
                "bvid": "BV2old",
                "title": "旧视频",
                "publish_time": 1720900000,
                "duration": 300,
                "play_count": 50,
            },
        ],
    }


class TestScanById:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_followed_up_by_id_inserts_hotspots(
        self,
        client,
        sample_uapi_payload: dict[str, Any],
    ):
        """scan_followed_up_by_id → 新增 hotspots，UP主 健康状态更新。"""
        # 先建 UP主
        payload = {
            "platform": "bilibili",
            "uid": "1567748478",
            "display_name": "测试 UP主",
            "profile_url": SPACE_URL,
        }
        resp = await client.post("/api/followed-up", json=payload)
        assert resp.status_code == 201
        followed_up_id = resp.json()["data"]["id"]

        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(200, json=sample_uapi_payload)
            )

            outcome = await scan_followed_up_by_id(followed_up_id)

        # v0.3 round 6: 返回 ScanOutcome
        assert outcome.new_hotspots == 2  # 两条新视频

        # 检查 hotspots 已写
        health = await client.get(f"/api/followed-up/{followed_up_id}/health")
        assert health.status_code == 200
        body = health.json()["data"]
        assert body["health"] == "healthy"
        assert body["last_checked_at"] is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_followed_up_by_id_not_found_raises(self):
        """L1 #3：未知 id 必须 raise，不能静默返空 ScanOutcome。"""
        from aipulse.repositories.followed_up_repo import FollowedUpNotFoundError

        with pytest.raises(FollowedUpNotFoundError):
            await scan_followed_up_by_id("nonexistent-id")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_all_skips_inactive(self, client):
        """is_active=false 的 UP主 被 scan_all_followed_up 跳过。"""
        payload = {
            "platform": "bilibili",
            "uid": "1567748478",
            "display_name": "X",
            "profile_url": SPACE_URL,
        }
        resp = await client.post("/api/followed-up", json=payload)
        followed_up_id = resp.json()["data"]["id"]

        # 软停（设 is_active=false）
        patch_resp = await client.patch(
            f"/api/followed-up/{followed_up_id}",
            json={"is_active": False},
        )
        assert patch_resp.status_code == 200

        with respx.mock(assert_all_called=False, base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 0, "page": 1, "size": 50, "videos": []},
                )
            )

            new_count = await scan_all_followed_up()

        # 没活跃 UP主 → 0 新增
        assert new_count == 0

        # 确认没被扫过
        health = await client.get(f"/api/followed-up/{followed_up_id}/health")
        # is_active=false 仍然在 DB；但 last_checked_at 应该没更新
        assert health.json()["data"]["last_checked_at"] is None


class TestSyncApi:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_endpoint_returns_202_with_new_count(
        self,
        client,
        sample_uapi_payload: dict[str, Any],
    ):
        payload = {
            "platform": "bilibili",
            "uid": "1567748478",
            "display_name": "X",
            "profile_url": SPACE_URL,
        }
        resp = await client.post("/api/followed-up", json=payload)
        followed_up_id = resp.json()["data"]["id"]

        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(200, json=sample_uapi_payload)
            )

            sync_resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")

        assert sync_resp.status_code == 202
        body = sync_resp.json()["data"]
        assert body["status"] == "ok"
        assert body["new_videos"] == 2
        # v0.3 round 6: sync 同时返回 enqueued_summaries（新 hotspot 入队数）
        assert "enqueued_summaries" in body
        assert isinstance(body["enqueued_summaries"], int)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_endpoint_404_for_missing_followed_up(self, client):
        """L1 #3：sync 对未知 id 必须 404，不能返伪 202 + new_videos=0。"""
        sync_resp = await client.post("/api/followed-up/nonexistent/sync")
        assert sync_resp.status_code == 404


class TestValidateEndpoint:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validate_returns_uapi_strategy_when_valid(self, client):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "total": 188,
                        "page": 1,
                        "size": 1,
                        "videos": [
                            {
                                "bvid": "BV1",
                                "title": "跟李沐学AI 的第一条视频",
                                "publish_time": 1721000000,
                            }
                        ],
                    },
                )
            )

            resp = await client.post(
                "/api/followed-up/validate",
                json={
                    "platform": "bilibili",
                    "uid": "1567748478",
                    "profile_url": SPACE_URL,
                },
            )

        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["strategy"] == "uapi"
        # 新端点 /archives 不直接给 UP主 名，uapi.validate_up_exists 兜底取
        # 第一条视频 title 作为 display_name；spec 没要求 user.name
        assert body["display_name"] == "跟李沐学AI 的第一条视频"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validate_falls_back_to_html(self, client):
        # UAPI 失败（模拟旧 404 响应） → HTML 兜底
        with respx.mock() as mock:
            mock.get("https://uapis.cn/api/v1/social/bilibili/archives").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": "NOT_FOUND", "message": "endpoint retired"},
                )
            )
            mock.get(SPACE_URL).mock(
                return_value=httpx.Response(
                    200,
                    text='<html><body><h1 id="h-name">HTML兜底UP主</h1></body></html>',
                )
            )

            resp = await client.post(
                "/api/followed-up/validate",
                json={
                    "platform": "bilibili",
                    "uid": "1567748478",
                    "profile_url": SPACE_URL,
                },
            )

        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["strategy"] == "html"
        assert body["display_name"] == "HTML兜底UP主"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validate_returns_409_when_both_fail(self, client):
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://uapis.cn/api/v1/social/bilibili/archives").mock(
                return_value=httpx.Response(
                    200,
                    json={"total": 0, "page": 1, "size": 1, "videos": []},
                )
            )
            mock.get("https://space.bilibili.com/99999999").mock(
                return_value=httpx.Response(404)
            )

            resp = await client.post(
                "/api/followed-up/validate",
                json={
                    "platform": "bilibili",
                    "uid": "99999999",
                    "profile_url": "https://space.bilibili.com/99999999",
                },
            )

        assert resp.status_code == 409


class TestSchedulerRegistration:
    @pytest.mark.integration
    def test_register_followed_up_jobs_adds_interval_job(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from aipulse.scheduler.jobs.followed_up_scan import register_followed_up_jobs

        scheduler = AsyncIOScheduler()
        try:
            register_followed_up_jobs(scheduler)
            job = scheduler.get_job("followed_up_scan_all")
            assert job is not None
            assert job.name == "Scan all enabled followed UP主"
            # trigger is IntervalTrigger with minutes=1
            assert job.trigger.interval.total_seconds() == 60
        finally:
            # 不调 shutdown — 测试结束 scheduler 自然 GC
            pass


# =====================================================================
# Real-network integration (RED-NOT-BLOCK)
# =====================================================================
#
# 真实链路 uapis.cn / space.bilibili.com 测试需要：
# 1) 用户登录态 cookie（不然 412 风控 + WBI 校验），否则会被 B 站拒绝；
# 2) 真实网络出口不能被 mock 拦截；
# 3) 不能在 CI 默认 runner 跑（会被判定为不稳定 + 触发风控封 IP）。
#
# 默认跳过；显式 opt-in：``AIPULSE_REAL_BILIBILI=1 pytest -m real_bilibili``。
# 任何 RED-NOT-BLOCK 真实链路必须先在本地用真实 mid 跑一次，验证断言再入库。
# 红线：永不让 mock 冒充真链路；永不让默认测试访问 B 站真实域。
class TestRealBilibiliUpCollector:
    """Real-network tests — opt-in only, default SKIP.

    跳过条件：
      - AIPULSE_REAL_BILIBILI != "1"
      - 或 pytest 不带 ``-m real_bilibili``
    """

    @pytest.mark.integration
    @pytest.mark.real_bilibili
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        "os.environ.get('AIPULSE_REAL_BILIBILI') != '1'",
        reason="默认跳过；AIPULSE_REAL_BILIBILI=1 启用（防风控 + CI 不稳定）",
    )
    async def test_uapi_collect_real_mid_1567748478(self):
        """RED-NOT-BLOCK：真实 uapis.cn /archives 链路。

        本地运行（需 SESSDATA cookie 可选）：
            AIPULSE_REAL_BILIBILI=1 pytest -m real_bilibili tests/integration/test_followed_up_scan.py

        CI 默认不会跑；如果跑也只会是用户主动 opt-in。
        """
        from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory

        collector = BilibiliUpCollectorFactory.create("uapi")
        try:
            videos = await collector.fetch_videos(mid="1567748478", count=3)
        finally:
            await collector.close()
        # 真实接口对未登录 IP 可能返回空（兜底）；不强制断言数量。
        assert isinstance(videos, list)

    @pytest.mark.integration
    @pytest.mark.real_bilibili
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        "os.environ.get('AIPULSE_REAL_BILIBILI') != '1'",
        reason="默认跳过；AIPULSE_REAL_BILIBILI=1 启用",
    )
    async def test_uapi_validate_real_mid(self):
        """RED-NOT-BLOCK：真实 /archives total 校验 UP主 存在性。"""
        from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory

        collector = BilibiliUpCollectorFactory.create("uapi")
        try:
            exists, name = await collector.validate_up_exists("1567748478")
        finally:
            await collector.close()
        assert isinstance(exists, bool)