"""Integration tests for the UP detail API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_up_detail_endpoints_return_record_hotspots_and_sync_history(client):
    payload = {
        "platform": "bilibili",
        "uid": "round5-up",
        "display_name": "Round 5 UP",
        "profile_url": "https://space.bilibili.com/round5-up",
        "collector_strategy": "uapi",
        "fetch_interval_minutes": 30,
    }
    created = await client.post("/api/followed-up", json=payload, headers={"Authorization": "Bearer test-token"})
    assert created.status_code == 201
    followed_up_id = created.json()["data"]["id"]

    detail = await client.get("/api/followed-up/round5-up", headers={"Authorization": "Bearer test-token"})
    assert detail.status_code == 200
    assert detail.json()["data"]["uid"] == "round5-up"

    hotspots = await client.get("/api/followed-up/round5-up/hotspots", headers={"Authorization": "Bearer test-token"})
    assert hotspots.status_code == 200
    assert hotspots.json()["data"] == []

    history = await client.get("/api/followed-up/round5-up/sync-history", headers={"Authorization": "Bearer test-token"})
    assert history.status_code == 200
    assert history.json()["data"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_up_detail_endpoints_return_404_for_unknown(client):
    headers = {"Authorization": "Bearer test-token"}
    for suffix in ("", "/hotspots", "/sync-history"):
        response = await client.get(f"/api/followed-up/unknown{suffix}", headers=headers)
        assert response.status_code == 404
