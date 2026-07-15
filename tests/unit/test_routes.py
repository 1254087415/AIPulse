"""Direct unit tests for the hotspot web routes."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest

from aipulse.web.routes import (
    archive_hotspot_route,
    create_keyword_route,
    generate_digest_route,
    get_hotspot_route,
    get_related_hotspots_route,
    hotspots_sse,
    list_digests_route,
    list_hotspots_route,
    list_keywords_route,
    list_sources_route,
    update_keyword_route,
    update_source_route,
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


def _make_keyword_mock(keyword_id: str, value: str) -> MagicMock:
    return MagicMock(
        id=keyword_id,
        value=value,
        is_active=True,
        notify_on_match=False,
        created_at=datetime.now(UTC),
    )


def _make_source_mock(source_id: str, name: str) -> MagicMock:
    source = MagicMock(
        id=source_id,
        source_type="rss_news",
        collector_class="RssNewsCollector",
        config=None,
        default_weight=1.0,
        fetch_interval_minutes=30,
        is_active=True,
        last_fetched_at=None,
        last_error=None,
        failed_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    source.name = name
    return source


def _make_digest_mock(digest_id: str) -> MagicMock:
    return MagicMock(
        id=digest_id,
        date=date.today(),
        title="Daily Digest",
        content="Summary",
        top_hotspot_ids=["h1"],
        generated_at=datetime.now(UTC),
        pushed_at=None,
    )


@pytest.mark.unit
async def test_list_hotspots_route_returns_envelope() -> None:
    session = MagicMock()
    hotspots = [_make_hotspot_mock("h1", "T1")]
    with patch("aipulse.web.routes.list_hotspots_service", return_value=(hotspots, 1)) as mock:
        result = await list_hotspots_route(session, q="ai")

    mock.assert_awaited_once_with(session, q="ai", source="", importance="", category="", sort="", order="", page=1, limit=20)
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
async def test_get_related_hotspots_route_returns_items() -> None:
    session = MagicMock()
    hotspots = [_make_hotspot_mock("h2", "Related")]
    with patch("aipulse.web.routes.get_related_hotspots_service", return_value=hotspots) as mock:
        result = await get_related_hotspots_route("h1", session)
    mock.assert_awaited_once_with(session, "h1", limit=10)
    assert result["success"] is True
    assert result["data"][0].id == "h2"


@pytest.mark.unit
async def test_archive_hotspot_route_returns_paths() -> None:
    session = MagicMock()
    paths = {"source_note_path": "/a/b.md", "summary_note_path": "/a/c.md"}
    with patch("aipulse.web.routes.archive_hotspot_service", return_value=paths) as mock:
        result = await archive_hotspot_route("h1", session)
    mock.assert_awaited_once_with(session, "h1")
    assert result["success"] is True
    assert result["data"] == paths


@pytest.mark.unit
async def test_archive_hotspot_route_raises_400_when_not_configured() -> None:
    session = MagicMock()
    with (
        patch("aipulse.web.routes.archive_hotspot_service", side_effect=FileNotFoundError("no vault")),
        pytest.raises(Exception) as exc_info,
    ):
        await archive_hotspot_route("h1", session)
    assert exc_info.value.status_code == 400


@pytest.mark.unit
async def test_list_keywords_route_returns_envelope() -> None:
    session = MagicMock()
    keywords = [_make_keyword_mock("k1", "ai")]
    with patch("aipulse.web.routes.list_keywords_service", return_value=keywords) as mock:
        result = await list_keywords_route(session)
    mock.assert_awaited_once_with(session)
    assert result["success"] is True
    assert result["data"][0].id == "k1"


@pytest.mark.unit
async def test_create_keyword_route_returns_envelope() -> None:
    session = MagicMock()
    keyword = _make_keyword_mock("k1", "ai")
    payload = MagicMock(value="ai")
    with patch("aipulse.web.routes.create_keyword_service", return_value=keyword) as mock:
        result = await create_keyword_route(payload, session)
    mock.assert_awaited_once_with(session, "ai")
    assert result["success"] is True
    assert result["data"].id == "k1"
    assert result["data"].value == "ai"


@pytest.mark.unit
async def test_update_keyword_route_returns_envelope() -> None:
    session = MagicMock()
    keyword = _make_keyword_mock("k1", "ai")
    keyword.notify_on_match = True
    payload = MagicMock(model_dump=lambda exclude_unset: {"notify_on_match": True})
    with patch("aipulse.web.routes.update_keyword_service", return_value=keyword) as mock:
        result = await update_keyword_route("k1", payload, session)
    mock.assert_awaited_once_with(session, "k1", {"notify_on_match": True})
    assert result["success"] is True
    assert result["data"].notify_on_match is True


@pytest.mark.unit
async def test_list_sources_route_returns_envelope() -> None:
    session = MagicMock()
    sources = [_make_source_mock("s1", "Test")]
    with patch("aipulse.web.routes.list_sources_service", return_value=sources) as mock:
        result = await list_sources_route(session)
    mock.assert_awaited_once_with(session)
    assert result["success"] is True
    assert result["data"][0].id == "s1"


@pytest.mark.unit
async def test_update_source_route_returns_envelope() -> None:
    session = MagicMock()
    source = _make_source_mock("s1", "Test")
    source.is_active = False
    payload = MagicMock(model_dump=lambda exclude_unset: {"is_active": False})
    with patch("aipulse.web.routes.update_source_service", return_value=source) as mock:
        result = await update_source_route("s1", payload, session)
    mock.assert_awaited_once_with(session, "s1", {"is_active": False})
    assert result["success"] is True
    assert result["data"].is_active is False


@pytest.mark.unit
async def test_list_digests_route_returns_envelope() -> None:
    session = MagicMock()
    digests = [_make_digest_mock("d1")]
    with patch("aipulse.web.routes.list_digests_service", return_value=digests) as mock:
        result = await list_digests_route(session)
    mock.assert_awaited_once_with(session, limit=30)
    assert result["success"] is True
    assert result["data"][0].id == "d1"


@pytest.mark.unit
async def test_generate_digest_route_returns_envelope() -> None:
    session = MagicMock()
    digest = _make_digest_mock("d1")
    with patch("aipulse.web.routes.generate_digest_service", return_value=digest) as mock:
        result = await generate_digest_route(session)
    mock.assert_awaited_once_with(session)
    assert result["success"] is True
    assert result["data"].id == "d1"


@pytest.mark.unit
async def test_hotspots_sse_returns_streaming_response() -> None:
    request = MagicMock()
    response = await hotspots_sse(request)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"
