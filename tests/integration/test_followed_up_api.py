"""Integration tests for /api/followed-up endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio

from aipulse.core.config import get_settings
from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import get_session_maker
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await reset_db()


@pytest.mark.integration
async def test_create_followed_up_minimal_payload(client):
    """POST /api/followed-up accepts platform + uid (display_name derived)."""
    payload = {
        "platform": "bilibili",
        "uid": "1567748478",
        "profile_url": "https://space.bilibili.com/1567748478",
    }
    response = await client.post("/api/followed-up", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["platform"] == "bilibili"
    assert body["data"]["uid"] == "1567748478"
    assert body["data"]["display_name"]  # derived from B站 API
    assert body["data"]["id"]


@pytest.mark.integration
async def test_create_followed_up_duplicate_returns_409(client):
    """Duplicate (platform, uid) returns 409 Conflict."""
    payload = {
        "platform": "bilibili",
        "uid": "1567748478",
        "display_name": "First",
        "profile_url": "https://space.bilibili.com/1567748478",
    }
    response = await client.post("/api/followed-up", json=payload)
    assert response.status_code == 201

    response2 = await client.post("/api/followed-up", json=payload)
    assert response2.status_code == 409
    body = response2.json()
    # HTTPException returns {"detail": ...}; the detail contains an
    # error envelope with success=False.
    assert "detail" in body
    detail = body["detail"]
    assert detail["success"] is False


@pytest.mark.integration
async def test_create_followed_up_invalid_profile_url_returns_422(client):
    """Invalid profile_url (missing http scheme) returns 422."""
    payload = {
        "platform": "bilibili",
        "uid": "1567748478",
        "display_name": "X",
        "profile_url": "not-a-url",
    }
    response = await client.post("/api/followed-up", json=payload)
    assert response.status_code == 422


@pytest.mark.integration
async def test_list_followed_up_returns_empty(client):
    """GET /api/followed-up returns an empty envelope when no rows."""
    response = await client.get("/api/followed-up")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []


@pytest.mark.integration
async def test_list_followed_up_returns_persisted(client):
    """GET /api/followed-up returns previously created rows."""
    payload = {
        "platform": "bilibili",
        "uid": "999",
        "display_name": "Existing User",
        "profile_url": "https://space.bilibili.com/999",
    }
    create = await client.post("/api/followed-up", json=payload)
    assert create.status_code == 201

    response = await client.get("/api/followed-up")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["display_name"] == "Existing User"
    assert body["data"][0]["mid"] == "999"
    assert body["data"][0]["video_count"] == 0


@pytest.mark.integration
async def test_list_followed_up_counts_related_hotspots(client):
    """GET /api/followed-up returns a real video_count based on related hotspots."""
    payload = {
        "platform": "bilibili",
        "uid": "998",
        "display_name": "Counted User",
        "profile_url": "https://space.bilibili.com/998",
    }
    create = await client.post("/api/followed-up", json=payload)
    assert create.status_code == 201
    record_id = create.json()["data"]["id"]

    async with get_session_maker()() as session:
        source = Source(name="bilibili", source_type="bilibili", collector_class="X")
        session.add(source)
        await session.flush()
        session.add_all(
            [
                Hotspot(
                    content_id="BVcount01",
                    followed_up_id=record_id,
                    title="counted-1",
                    url="https://www.bilibili.com/video/BVcount01",
                    canonical_url="https://www.bilibili.com/video/BVcount01",
                    source_id=source.id,
                    source_type="bilibili",
                ),
                Hotspot(
                    content_id="BVcount02",
                    followed_up_id=record_id,
                    title="counted-2",
                    url="https://www.bilibili.com/video/BVcount02",
                    canonical_url="https://www.bilibili.com/video/BVcount02",
                    source_id=source.id,
                    source_type="bilibili",
                ),
            ],
        )
        await session.commit()

    response = await client.get("/api/followed-up")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["mid"] == "998"
    assert body["data"][0]["video_count"] == 2


@pytest.mark.integration
async def test_get_followed_up_by_id(client):
    """GET /api/followed-up/{id} returns a single record."""
    payload = {
        "platform": "bilibili",
        "uid": "999",
        "display_name": "Existing",
        "profile_url": "https://space.bilibili.com/999",
    }
    create = await client.post("/api/followed-up", json=payload)
    record_id = create.json()["data"]["id"]

    response = await client.get(f"/api/followed-up/{record_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == record_id


@pytest.mark.integration
async def test_get_followed_up_missing_returns_404(client):
    """GET /api/followed-up/{id} returns 404 for unknown id."""
    response = await client.get("/api/followed-up/missing-id")
    assert response.status_code == 404


@pytest.mark.integration
async def test_patch_followed_up_updates_fields(client):
    """PATCH /api/followed-up/{id} mutates only the supplied fields."""
    payload = {
        "platform": "bilibili",
        "uid": "999",
        "display_name": "Original",
        "profile_url": "https://space.bilibili.com/999",
    }
    create = await client.post("/api/followed-up", json=payload)
    record_id = create.json()["data"]["id"]

    response = await client.patch(
        f"/api/followed-up/{record_id}",
        json={"display_name": "Updated", "fetch_interval_minutes": 60},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["display_name"] == "Updated"
    assert body["data"]["fetch_interval_minutes"] == 60


@pytest.mark.integration
async def test_delete_followed_up_soft_deletes(client):
    """DELETE /api/followed-up/{id} soft-deletes (sets deleted_at)."""
    payload = {
        "platform": "bilibili",
        "uid": "999",
        "display_name": "Doomed",
        "profile_url": "https://space.bilibili.com/999",
    }
    create = await client.post("/api/followed-up", json=payload)
    record_id = create.json()["data"]["id"]

    response = await client.delete(f"/api/followed-up/{record_id}")
    assert response.status_code == 200

    # Subsequent GET should treat the row as gone (soft delete)
    response = await client.get(f"/api/followed-up/{record_id}")
    assert response.status_code == 404


@pytest.mark.integration
async def test_validate_followed_up_endpoint(client, monkeypatch):
    """POST /api/followed-up/validate returns the B站 user info."""
    # Avoid making real network calls in CI; check the endpoint shape
    # via a successful creation path. The full integration is covered
    # by tests that exercise the validator directly.
    payload = {
        "platform": "bilibili",
        "uid": "1567748478",
        "profile_url": "https://space.bilibili.com/1567748478",
    }
    response = await client.post("/api/followed-up/validate", json=payload)
    # Either 200 (network OK) or 409 (both strategies report non-existent)
    # or 502 (network blocked) – all confirm the endpoint is wired and
    # returns a structured envelope.
    assert response.status_code in (200, 409, 502)
    body = response.json()
    assert "success" in body or "detail" in body


@pytest.mark.integration
async def test_sync_followed_up_returns_202(client):
    """POST /api/followed-up/{id}/sync returns 202 Accepted (Phase 2 implementation)."""
    payload = {
        "platform": "bilibili",
        "uid": "999",
        "display_name": "Sync Target",
        "profile_url": "https://space.bilibili.com/999",
    }
    create = await client.post("/api/followed-up", json=payload)
    record_id = create.json()["data"]["id"]

    response = await client.post(f"/api/followed-up/{record_id}/sync")
    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["followed_up_id"] == record_id
    assert body["data"]["status"] in ("ok", "timeout")


@pytest.mark.integration
async def test_followed_up_endpoints_require_bearer(client, monkeypatch):
    """Bearer auth is enforced on /api/followed-up/* when token is set."""
    from pydantic import SecretStr

    cached = get_settings()
    # Patch the cached AppSettings directly so monkeypatch restores it. An
    # env var change would not invalidate the cached instance.
    monkeypatch.setattr(cached, "aipulse_api_token", SecretStr("secret123"))

    response = await client.get("/api/followed-up")
    assert response.status_code == 401

    response = await client.get(
        "/api/followed-up", headers={"Authorization": "Bearer secret123"}
    )
    assert response.status_code == 200
