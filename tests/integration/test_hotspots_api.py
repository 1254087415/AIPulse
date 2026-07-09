"""Integration tests for the hotspot REST API."""

import pytest
import pytest_asyncio

from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_database_before_each_test():
    """Provide a clean database for every integration test."""
    await reset_db()


@pytest.mark.integration
async def test_list_hotspots_returns_envelope(client):
    response = await client.get("/api/hotspots")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "data" in body
    assert "meta" in body


@pytest.mark.integration
async def test_list_hotspots_returns_persisted_hotspot(client, db_session):
    source = Source(name="test-source", source_type="rss", collector_class="rss")
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    hotspot = Hotspot(
        title="Test Hotspot",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss",
        heat_score=12.5,
        importance="high",
        category="tech",
    )
    db_session.add(hotspot)
    await db_session.commit()

    response = await client.get("/api/hotspots")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "Test Hotspot"
    assert body["data"][0]["source_type"] == "rss"
    assert body["meta"]["total"] == 1


@pytest.mark.integration
async def test_list_hotspots_supports_filters(client, db_session):
    source = Source(name="test-source", source_type="rss", collector_class="rss")
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    db_session.add_all(
        [
            Hotspot(
                title="Apple News",
                url="https://example.com/a",
                canonical_url="https://example.com/a",
                source_id=source.id,
                source_type="rss",
                heat_score=1.0,
                category="tech",
            ),
            Hotspot(
                title="Banana News",
                url="https://example.com/b",
                canonical_url="https://example.com/b",
                source_id=source.id,
                source_type="rss",
                heat_score=2.0,
                category="fruit",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/hotspots", params={"q": "Apple"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Apple News"

    response = await client.get("/api/hotspots", params={"category": "fruit"})
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["title"] == "Banana News"


@pytest.mark.integration
async def test_get_hotspot_returns_item(client, db_session):
    source = Source(name="test-source", source_type="rss", collector_class="rss")
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    hotspot = Hotspot(
        title="Single Hotspot",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss",
        heat_score=5.0,
    )
    db_session.add(hotspot)
    await db_session.commit()
    await db_session.refresh(hotspot)

    response = await client.get(f"/api/hotspots/{hotspot.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Single Hotspot"


@pytest.mark.integration
async def test_get_hotspot_returns_404_for_missing(client):
    response = await client.get("/api/hotspots/missing-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Hotspot not found"


@pytest.mark.integration
async def test_create_keyword_returns_envelope(client):
    response = await client.post("/api/keywords", json={"value": "ai"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["value"] == "ai"
    assert "id" in body["data"]
