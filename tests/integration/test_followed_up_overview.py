"""Integration tests for /api/followed-up/{id}/overview + retry endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from aipulse.repositories.summary_job_repo import SqlAlchemySummaryJobRepository
from aipulse.summarizers.queue import drop_queue_sync

import aipulse.summarizers.queue as queue_mod  # noqa: E402


def _bearer():
    return {"Authorization": "Bearer test-token"}


def _fake_run_factory(payload: dict):
    async def fake_run(video_id, title, up_name, extra_context=""):
        return payload
    return fake_run


@pytest.fixture(autouse=True)
def _isolate():
    drop_queue_sync()
    default_payload = {
        "status": "completed",
        "note_path": "/tmp/note.md",
        "event_id": "evt1",
        "reminder_id": "rem1",
        "error": None,
        "intermediate_steps": [],
    }
    patcher = patch.object(
        queue_mod, "run_summary_pipeline", new=_fake_run_factory(default_payload)
    )
    patcher.start()
    try:
        yield default_payload
    finally:
        patcher.stop()
        drop_queue_sync()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overview_returns_aggregate(client, db_session, _isolate) -> None:
    """Create a followed_up, then overview."""
    payload = {
        "platform": "bilibili",
        "uid": "111111",
        "display_name": "TestUP",
        "profile_url": "https://space.bilibili.com/111111",
        "collector_strategy": "uapi",
        "fetch_interval_minutes": 30,
    }
    r = await client.post("/api/followed-up", json=payload, headers=_bearer())
    assert r.status_code == 201
    fu_id = r.json()["data"]["id"]

    resp = await client.get(f"/api/followed-up/{fu_id}/overview", headers=_bearer())
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == fu_id
    assert data["display_name"] == "TestUP"
    assert data["health"]["is_active"] is True
    assert data["recent_jobs"] == []
    assert data["recent_learning_events"] == []
    assert data["recent_collections"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overview_returns_404_for_unknown(client) -> None:
    r = await client.get(
        "/api/followed-up/nonexistent/overview", headers=_bearer()
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_overview_includes_recent_job(client, db_session, _isolate) -> None:
    """Create a summary job, ensure it shows in overview of related UP."""
    payload = {
        "platform": "bilibili",
        "uid": "222222",
        "display_name": "AnotherUP",
        "profile_url": "https://space.bilibili.com/222222",
        "collector_strategy": "uapi",
        "fetch_interval_minutes": 30,
    }
    r = await client.post("/api/followed-up", json=payload, headers=_bearer())
    fu_id = r.json()["data"]["id"]

    # 直接在 DB 写入 hotspot 来做关联（content_id=BVoverview）
    from aipulse.hotspot.models import Hotspot, Source

    from aipulse.store.database import get_session_maker

    async with get_session_maker()() as session:
        src = Source(name="bilibili", source_type="bilibili", collector_class="X")
        session.add(src)
        await session.commit()
        source_id = src.id

    async with get_session_maker()() as session:
        h = Hotspot(
            content_id="BVoverview",
            followed_up_id=fu_id,
            title="t",
            url="https://www.bilibili.com/video/BVoverview",
            canonical_url="https://www.bilibili.com/video/BVoverview",
            source_id=source_id,
            source_type="bilibili",
        )
        session.add(h)
        await session.commit()

    # 2) summary job for that video
    r2 = await client.post("/api/summary/BVoverview", headers=_bearer())
    assert r2.status_code == 202
    job_id = r2.json()["data"]["job_id"]
    # wait for worker
    await asyncio.sleep(0.5)

    resp = await client.get(f"/api/followed-up/{fu_id}/overview", headers=_bearer())
    assert resp.status_code == 200
    data = resp.json()["data"]
    # jobs list 应包含该 job（通过 video_id hotspot 关联）
    matching = [j for j in data["recent_jobs"] if j["id"] == job_id]
    assert matching
    assert matching[0]["video_id"] == "BVoverview"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_failed_job_returns_new_job_id(client, db_session, _isolate) -> None:
    """Return 202 + new_job_id, with video_id 不变."""
    # 1) 创建一个失败的 job
    async def fake_failed(video_id, title, up_name, extra_context=""):
        return {
            "status": "failed",
            "note_path": None,
            "event_id": None,
            "reminder_id": None,
            "error": "agent exploded",
            "intermediate_steps": [],
        }

    with patch.object(queue_mod, "run_summary_pipeline", new=fake_failed):
        r = await client.post("/api/summary/BVretry", headers=_bearer())
        assert r.status_code == 202
        old_job_id = r.json()["data"]["job_id"]

        # wait for worker to mark failed
        await asyncio.sleep(0.5)

        # 2) 重试
        with patch.object(
            queue_mod,
            "run_summary_pipeline",
            new=_fake_run_factory(
                {
                    "status": "completed",
                    "note_path": "/v2.md",
                    "event_id": "evt2",
                    "reminder_id": "rem2",
                    "error": None,
                    "intermediate_steps": [],
                }
            ),
        ):
            r2 = await client.post(
                f"/api/summary/job/{old_job_id}/retry", headers=_bearer()
            )
            assert r2.status_code == 202
            new_job_id = r2.json()["data"]["new_job_id"]
            assert new_job_id != old_job_id
            assert r2.json()["data"]["video_id"] == "BVretry"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_unknown_job_returns_404(client) -> None:
    import uuid

    r = await client.post(
        f"/api/summary/job/{uuid.uuid4().hex[:12]}/retry", headers=_bearer()
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_running_job_returns_409(client, db_session, _isolate) -> None:
    async def fake_slow(video_id, title, up_name, extra_context=""):
        await asyncio.sleep(2.0)
        return _isolate  # payload reference; doesn't matter

    with patch.object(queue_mod, "run_summary_pipeline", new=fake_slow):
        r = await client.post("/api/summary/BV409", headers=_bearer())
        assert r.status_code == 202
        job_id = r.json()["data"]["job_id"]

        # 立即 retry — 旧 job 仍 running
        r2 = await client.post(
            f"/api/summary/job/{job_id}/retry", headers=_bearer()
        )
        assert r2.status_code == 409
