"""Integration tests for hotspot decision actions.

Covers the new patch/retry control surface used by FollowRecordsPanel.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_database_before_each_test():
    await reset_db()


async def _seed_hotspot(db_session, *, decision_status: str = "pending") -> str:
    src = Source(
        id="src-decision-1",
        name="B 站处理测试",
        source_type="bilibili",
        collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
        is_active=True,
    )
    hs = Hotspot(
        id="hs-decision-1",
        title="Decision test",
        url="https://www.bilibili.com/video/BV1decision",
        canonical_url="https://www.bilibili.com/video/BV1decision",
        source_id="src-decision-1",
        source_type="bilibili",
        content_id="BV1decision",
        decision_status=decision_status,
    )
    db_session.add_all([src, hs])
    await db_session.commit()
    return hs.id


@pytest.mark.integration
async def test_patch_hotspot_updates_decision_status(client, db_session) -> None:
    hotspot_id = await _seed_hotspot(db_session)

    response = await client.patch(
        f"/api/hotspots/{hotspot_id}",
        json={"decision_status": "skipped"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["decision_status"] == "skipped"

    row = (
        await db_session.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
    ).scalar_one()
    assert row.decision_status == "skipped"


@pytest.mark.integration
async def test_retry_hotspot_resets_status_and_enqueues_summary(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    hotspot_id = await _seed_hotspot(db_session, decision_status="failed")

    from aipulse.api import summary as summary_api

    fake_enqueue = AsyncMock(
        return_value={
            "success": True,
            "data": {
                "job_id": "job-retry-1",
                "status": "queued",
                "reused": False,
                "video_id": "BV1decision",
            },
        }
    )
    monkeypatch.setattr(summary_api, "enqueue_summary_route", fake_enqueue)

    response = await client.post(f"/api/agent/retry/{hotspot_id}")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["hotspot_id"] == hotspot_id
    assert body["data"]["video_id"] == "BV1decision"
    assert body["data"]["job_id"] == "job-retry-1"

    row = (
        await db_session.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
    ).scalar_one()
    assert row.decision_status == "pending"
    fake_enqueue.assert_awaited_once()
