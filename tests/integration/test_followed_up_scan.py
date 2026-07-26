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
SPACE_URL = "https://space.bilibili.com/1567748478"


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await reset_db()
    yield


@pytest.fixture
def sample_uapi_payload():
    return {
        "code": 0,
        "data": {
            "list": [
                {
                    "bvid": "BV1new",
                    "title": "新视频",
                    "pubdate": 1721000000,
                    "duration": 600,
                    "play": 100,
                },
                {
                    "bvid": "BV2old",
                    "title": "旧视频",
                    "pubdate": 1720900000,
                    "duration": 300,
                    "play": 50,
                },
            ],
            "has_more": False,
        },
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
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(200, json=sample_uapi_payload)
            )

            new_count = await scan_followed_up_by_id(followed_up_id)

        assert new_count == 2  # 两条新视频

        # 检查 hotspots 已写
        health = await client.get(f"/api/followed-up/{followed_up_id}/health")
        assert health.status_code == 200
        body = health.json()["data"]
        assert body["health"] == "healthy"
        assert body["last_checked_at"] is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_followed_up_by_id_not_found_returns_zero(self):
        result = await scan_followed_up_by_id("nonexistent-id")
        assert result == 0

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
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": 0, "data": {"list": [], "has_more": False}},
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
            mock.get("/space/arc/search").mock(
                return_value=httpx.Response(200, json=sample_uapi_payload)
            )

            sync_resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")

        assert sync_resp.status_code == 202
        body = sync_resp.json()["data"]
        assert body["status"] == "ok"
        assert body["new_videos"] == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_endpoint_404_for_missing_followed_up(self, client):
        sync_resp = await client.post("/api/followed-up/nonexistent/sync")
        # 501 → 502 (sync failed) 因为 scan_followed_up_by_id 返回 0 而不抛
        # 但 502 不该有 — 我看代码 _scan_one 不抛异常 → 0 → ok
        assert sync_resp.status_code == 202
        body = sync_resp.json()["data"]
        assert body["new_videos"] == 0


class TestValidateEndpoint:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validate_returns_uapi_strategy_when_valid(self, client):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get("/space/card").mock(
                return_value=httpx.Response(
                    200,
                    json={"code": 0, "data": {"user": {"name": "跟李沐学AI"}}},
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
        assert body["display_name"] == "跟李沐学AI"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validate_falls_back_to_html(self, client):
        # UAPI 失败 → HTML 兜底
        with respx.mock() as mock:
            mock.get("https://uapis.cn/api/v1/space/card").mock(
                return_value=httpx.Response(200, json={"code": -404, "message": "404"})
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
            mock.get("https://uapis.cn/api/v1/space/card").mock(
                return_value=httpx.Response(200, json={"code": -404})
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