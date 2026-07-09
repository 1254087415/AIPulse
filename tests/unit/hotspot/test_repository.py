"""Tests for hotspot repository."""

import pytest

from aipulse.hotspot.repository import HotspotRepository


@pytest.mark.integration
async def test_create_and_list_recent_hotspot(db_session):
    """Repository can persist a hotspot and return it in recent listing."""
    repo = HotspotRepository(db_session)
    await repo.create(
        title="Test",
        url="https://example.com",
        canonical_url="https://example.com",
        source_id="s1",
        source_type="news",
    )
    recent = await repo.list_recent(limit=10)
    assert len(recent) == 1
    assert recent[0].title == "Test"
