"""Integration tests for the /api/summary routes + SSE."""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import patch

import pytest

from aipulse.models.summary_jobs import JOB_STATUS_COMPLETED  # noqa: F401  used by tests
from aipulse.summarizers.queue import drop_queue_sync

import aipulse.summarizers.queue as queue_mod  # noqa: E402


def _bearer():
    return {"Authorization": "Bearer test-token"}


def _fake_run_factory(payload: dict, sleep_s: float = 0.0):
    """Build a fake ``run_summary_pipeline`` returning ``payload``."""
    async def fake_run(video_id, title, up_name, extra_context=""):
        if sleep_s:
            await asyncio.sleep(sleep_s)
        return payload
    return fake_run


@pytest.fixture(autouse=True)
def _isolate_queue_and_pipeline():
    """Drop global queue + 默认 patch pipeline（测试可改写）。"""
    drop_queue_sync()
    default_payload = {
        "status": "completed",
        "note_path": None,
        "event_id": None,
        "reminder_id": None,
        "error": None,
        "intermediate_steps": [],
    }
    default_fake = _fake_run_factory(default_payload)
    patcher = patch.object(queue_mod, "run_summary_pipeline", new=default_fake)
    patcher.start()
    try:
        yield {"payload": default_payload, "fake": default_fake}
    finally:
        patcher.stop()
        drop_queue_sync()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_returns_202_with_job_id(client, db_session, _isolate_queue_and_pipeline) -> None:
    payload = _isolate_queue_and_pipeline["payload"]
    payload["note_path"] = "/tmp/note.md"
    payload["event_id"] = "evt1"
    payload["reminder_id"] = "rem1"
    payload["intermediate_steps"] = [{"tool": "fetch_transcript", "output": "ok"}]

    resp = await client.post("/api/summary/BV1test", headers=_bearer())
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    job_id = body["data"]["job_id"]
    assert body["data"]["video_id"] == "BV1test"
    assert body["data"]["reused"] is False
    assert len(job_id) == 12

    await asyncio.sleep(0.5)
    resp2 = await client.get(f"/api/summary/job/{job_id}", headers=_bearer())
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()["data"]
    assert data["status"] == JOB_STATUS_COMPLETED
    assert data["note_path"] == "/tmp/note.md"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_returns_400_on_empty_video_id(client) -> None:
    # %20 → " " → strip 后空 → 400
    resp = await client.post("/api/summary/%20%20", headers=_bearer())
    # fastapi 路由级 "%20%20" 解析为 "  "，strip 后空 — 业务逻辑内 400
    assert resp.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_reused_when_existing_running(client, db_session, _isolate_queue_and_pipeline) -> None:
    payload = _isolate_queue_and_pipeline["payload"]
    # 让第一次请求 hang 1.5s，第二次立即复用
    sleep_fake = _fake_run_factory(payload, sleep_s=1.5)
    with patch.object(queue_mod, "run_summary_pipeline", new=sleep_fake):
        resp1 = await client.post("/api/summary/BVdup", headers=_bearer())
        assert resp1.status_code == 202
        job_id_1 = resp1.json()["data"]["job_id"]
        resp2 = await client.post("/api/summary/BVdup", headers=_bearer())
        assert resp2.status_code == 202
        data2 = resp2.json()["data"]
        assert data2["reused"] is True
        assert data2["job_id"] == job_id_1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown_id(client) -> None:
    resp = await client.get(
        "/api/summary/job/" + uuid.uuid4().hex[:12], headers=_bearer()
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_jobs_returns_recent(client, db_session, _isolate_queue_and_pipeline) -> None:
    for vid in ("BVa", "BVb", "BVc"):
        r = await client.post(f"/api/summary/{vid}", headers=_bearer())
        assert r.status_code == 202
    await asyncio.sleep(0.5)

    resp = await client.get("/api/summary/jobs", headers=_bearer())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    assert {d["video_id"] for d in data} == {"BVa", "BVb", "BVc"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sse_streams_started_then_completed(client, db_session, _isolate_queue_and_pipeline) -> None:
    payload = _isolate_queue_and_pipeline["payload"]
    payload["note_path"] = "/tmp/sse-note.md"
    payload["event_id"] = "evtSSE"
    payload["reminder_id"] = "remSSE"
    # 给 fake_run 0.3s hang 才有 SSE started/completed 两个事件
    sleep_fake = _fake_run_factory(payload, sleep_s=0.3)
    with patch.object(queue_mod, "run_summary_pipeline", new=sleep_fake):
        resp = await client.post("/api/summary/BVsse", headers=_bearer())
        assert resp.status_code == 202
        job_id = resp.json()["data"]["job_id"]

        events: list[dict] = []
        ev_type = ""
        complete = asyncio.Event()

        async def consume():
            nonlocal ev_type
            async with client.stream(
                "GET", f"/api/summary/events/{job_id}", headers=_bearer()
            ) as r:
                assert r.status_code == 200
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        ev_type = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:"):
                        try:
                            pl = json.loads(line.split(":", 1)[1].strip())
                        except json.JSONDecodeError:
                            continue
                        events.append({"event": ev_type, "data": pl})
                        if pl.get("type") == "completed":
                            complete.set()
                            return

        consume_task = asyncio.create_task(consume())
        await asyncio.wait_for(complete.wait(), timeout=5.0)
        await consume_task

        assert any(e["data"].get("type") == "started" for e in events)
        completed_event = next(
            e for e in events if e["data"].get("type") == "completed"
        )
        assert completed_event["data"]["note_path"] == "/tmp/sse-note.md"
