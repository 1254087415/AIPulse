"""Direct unit tests for the hotspot web routes."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from aipulse.web.routes import (
    create_keyword_route,
    get_hotspot_route,
    hotspots_sse,
    list_hotspots_route,
)


def _make_hotspot_mock(hotspot_id: str, title: str) -> MagicMock:
    """Return a MagicMock populated with the fields required by HotspotOut."""
    return MagicMock(
        id=hotspot_id,
        title=title,
        url="https://example.com",
        summary=None,
        source_type="rss",
        heat_score=1.0,
        importance="medium",
        category=None,
        published_at=datetime.now(UTC),
    )


@pytest.mark.unit
async def test_list_hotspots_route_returns_envelope() -> None:
    session = MagicMock()
    hotspots = [_make_hotspot_mock("h1", "T1")]
    with patch("aipulse.web.routes.list_hotspots_service", return_value=(hotspots, 1)) as mock:
        result = await list_hotspots_route(session, q="ai")

    mock.assert_awaited_once_with(session, q="ai", source="", category="", page=1, limit=20)
    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0].id == "h1"
    assert result["meta"] == {"total": 1, "page": 1, "limit": 20}


@pytest.mark.unit
async def test_get_hotspot_route_returns_item() -> None:
    session = MagicMock()
    hotspot = _make_hotspot_mock("h1", "T1")
    with patch("aipulse.web.routes.get_hotspot_service", return_value=hotspot):
        result = await get_hotspot_route("h1", session)
    assert result["success"] is True
    assert result["data"].id == "h1"


@pytest.mark.unit
async def test_get_hotspot_route_raises_404_when_missing() -> None:
    session = MagicMock()
    with (
        patch("aipulse.web.routes.get_hotspot_service", return_value=None),
        pytest.raises(Exception) as exc_info,
    ):
        await get_hotspot_route("missing", session)
    assert exc_info.value.status_code == 404


@pytest.mark.unit
async def test_create_keyword_route_returns_envelope() -> None:
    session = MagicMock()
    keyword = MagicMock(id="k1", value="ai")
    payload = MagicMock(value="ai")
    with patch("aipulse.web.routes.create_keyword_service", return_value=keyword) as mock:
        result = await create_keyword_route(payload, session)
    mock.assert_awaited_once_with(session, "ai")
    assert result["success"] is True
    assert result["data"] == {"id": "k1", "value": "ai"}


@pytest.mark.unit
async def test_hotspots_sse_returns_streaming_response() -> None:
    request = MagicMock()
    response = await hotspots_sse(request)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"
