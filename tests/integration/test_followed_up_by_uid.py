"""Integration tests for GET /api/followed-up/by-uid/{uid}/overview.

Phase 8 R2#2 fix: Frontend users landed on /followed-up/{mid} but the
overview endpoint only accepted the database UUID. Adding a uid-based alias
preserves the dashboard's clickable UX without forcing a db-id migration in
the URL.
"""

from __future__ import annotations

import pytest


def _bearer():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_by_uid_overview_returns_record(client) -> None:
    """POST creates a bilibili follower; /by-uid/{uid}/overview resolves it."""
    payload = {
        "platform": "bilibili",
        "uid": "222222",
        "display_name": "ByUidUP",
        "profile_url": "https://space.bilibili.com/222222",
        "collector_strategy": "uapi",
    }
    create = await client.post("/api/followed-up", json=payload, headers=_bearer())
    assert create.status_code == 201, create.text
    fu_id = create.json()["data"]["id"]

    resp = await client.get(
        "/api/followed-up/by-uid/bilibili/222222/overview", headers=_bearer()
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == fu_id
    assert data["uid"] == "222222"
    assert data["platform"] == "bilibili"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_by_uid_overview_returns_404_when_unknown(client) -> None:
    resp = await client.get(
        "/api/followed-up/by-uid/bilibili/9999999/overview", headers=_bearer()
    )
    assert resp.status_code == 404, resp.text
