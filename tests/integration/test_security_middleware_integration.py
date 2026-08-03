"""Integration tests for the Bearer auth middleware at the FastAPI app boundary."""

from __future__ import annotations

import pytest
import pytest_asyncio
from pydantic import SecretStr

from aipulse.core.config import get_settings
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    await reset_db()


def _patch_token(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Replace the cached AppSettings.aipulse_api_token so monkeypatch restores it."""
    cached = get_settings()
    monkeypatch.setattr(cached, "aipulse_api_token", SecretStr(value or ""))


@pytest.mark.integration
async def test_unauthenticated_when_token_unset(client):
    """No token configured means /api/hotspots is open."""
    # Already unset by default; just verify
    response = await client.get("/api/hotspots")
    assert response.status_code == 200


@pytest.mark.integration
async def test_sources_reject_missing_bearer_when_token_configured(client, monkeypatch):
    """The sources page reproduces the current 401 when the UI sends no token."""
    _patch_token(monkeypatch, "secret123")
    response = await client.get("/api/sources")
    assert response.status_code == 401
    assert response.json() == {"success": False, "error": "Unauthorized"}


@pytest.mark.integration
async def test_bearer_token_required_when_configured(client, monkeypatch):
    """With a token configured, missing Authorization header returns 401."""
    _patch_token(monkeypatch, "secret123")
    response = await client.get("/api/hotspots")
    assert response.status_code == 401
    assert response.json() == {"success": False, "error": "Unauthorized"}


@pytest.mark.integration
async def test_bearer_token_accepted_when_configured(client, monkeypatch):
    """Correct Bearer token lets the request through."""
    _patch_token(monkeypatch, "secret123")
    response = await client.get(
        "/api/hotspots", headers={"Authorization": "Bearer secret123"}
    )
    assert response.status_code == 200


@pytest.mark.integration
async def test_x_token_header_no_longer_accepted(client, monkeypatch):
    """Legacy X-AIPulse-Token header is rejected."""
    _patch_token(monkeypatch, "secret123")
    response = await client.get(
        "/api/hotspots", headers={"X-AIPulse-Token": "secret123"}
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_health_endpoint_is_exempt(client, monkeypatch):
    """/health is on the root path, not /api, so it's not gated."""
    _patch_token(monkeypatch, "secret123")
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["success"] is True
