"""Direct unit tests for the hotspot web routes."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from aipulse.hotspot.schemas import GenerateDigestRequest
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
    update_hotspot_route,
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
        content_id="BV1mock",
        up_name="Mock UP",
        followed_up_id=None,
        heat_score=1.0,
        importance="medium",
        category=None,
        status="pending",
        decision_status="pending",
        notified=False,
        obsidian_source_path=None,
        obsidian_summary_path=None,
        learning_event_id=None,
        created_at=datetime.now(UTC),
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

    mock.assert_awaited_once_with(
        session,
        q="ai",
        source="",
        importance="",
        category="",
        decision_status="",
        sort="",
        order="",
        page=1,
        limit=20,
    )
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
async def test_update_hotspot_route_updates_decision_status() -> None:
    session = AsyncMock()
    hotspot = _make_hotspot_mock("h1", "T1")
    hotspot.decision_status = "skipped"
    payload = MagicMock(model_dump=lambda exclude_unset: {"decision_status": "skipped"})
    session.get.return_value = hotspot

    with patch("aipulse.web.routes.update_hotspot_service", return_value=hotspot) as mock:
        result = await update_hotspot_route("h1", payload, session)

    mock.assert_awaited_once_with(session, "h1", {"decision_status": "skipped"})
    assert result["success"] is True
    assert result["data"].decision_status == "skipped"


@pytest.mark.unit
async def test_archive_hotspot_route_returns_paths() -> None:
    from aipulse.archive.service import ArchiveOutcome

    session = AsyncMock()
    hotspot = MagicMock()
    hotspot.id = "h1"
    hotspot.content_id = "v1"
    hotspot.title = "video"
    hotspot.summary = "summary"
    hotspot.followed_up_id = None
    session.get.return_value = hotspot

    outcome = ArchiveOutcome(
        note_path="/a/b.md",
        learning_event_id=42,
        reminder_id="rem-1",
        obsidian_task_written=True,
        errors=[],
    )
    with patch("aipulse.web.routes.archive_three_way", return_value=outcome) as mock:
        result = await archive_hotspot_route("h1", session)
    mock.assert_awaited_once()
    assert result["success"] is True
    assert result["data"]["note_path"] == "/a/b.md"
    assert result["data"]["learning_event_id"] == 42
    assert result["data"]["obsidian_task_written"] is True


@pytest.mark.unit
async def test_archive_hotspot_route_returns_failure_envelope_when_obsidian_missing() -> None:
    from aipulse.archive.service import ArchiveOutcome

    session = AsyncMock()
    hotspot = MagicMock()
    hotspot.id = "h1"
    hotspot.content_id = "v1"
    hotspot.title = "video"
    hotspot.summary = "summary"
    hotspot.followed_up_id = None
    session.get.return_value = hotspot

    # 模拟 obsidian_note 写失败：archive_three_way 返回 note_path=None + errors
    outcome = ArchiveOutcome(
        note_path=None,
        learning_event_id=None,
        reminder_id=None,
        obsidian_task_written=False,
        errors=["obsidian_note: vault not configured"],
    )
    with patch("aipulse.web.routes.archive_three_way", return_value=outcome) as mock:
        result = await archive_hotspot_route("h1", session)
    mock.assert_awaited_once()
    # spec 06 §7.2 三方向容错：obsidian 失败 → data.note_path=None + errors 非空
    # success=True 是 routes.py 设计选择（整体 fail 不抛异常，前端读 errors 处理）
    assert result["success"] is True
    assert result["data"]["note_path"] is None
    assert "obsidian_note" in result["data"]["errors"][0]


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
    """Generate today's digest (no body) — service called with session + target_date."""
    from datetime import date as _date

    session = MagicMock()
    # Existence check (async): returns no duplicate
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    digest = _make_digest_mock("d1")
    with patch("aipulse.web.routes.generate_digest_service", AsyncMock(return_value=digest)) as mock:
        result = await generate_digest_route(session)
    mock.assert_awaited_once()
    _, kwargs = mock.call_args
    assert kwargs["target_date"] == _date.today()
    assert result["success"] is True
    assert result["data"].id == "d1"


@pytest.mark.unit
async def test_generate_digest_route_returns_409_when_duplicate() -> None:
    """If a digest already exists for the target date, return 409 with existing record."""
    from datetime import date as _date

    session = MagicMock()
    existing = _make_digest_mock("existing-1")
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))

    with pytest.raises(HTTPException) as exc_info:
        await generate_digest_route(
            session, payload=GenerateDigestRequest(target_date=_date(2026, 7, 25))
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "digest_exists"
    assert exc_info.value.detail["date"] == "2026-07-25"


@pytest.mark.unit
async def test_generate_digest_route_accepts_custom_date() -> None:
    """Body with target_date should be passed through to service."""
    from datetime import date as _date

    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    digest = _make_digest_mock("d2")
    with patch("aipulse.web.routes.generate_digest_service", AsyncMock(return_value=digest)) as mock:
        result = await generate_digest_route(
            session, payload=GenerateDigestRequest(target_date=_date(2026, 7, 20))
        )
    _, kwargs = mock.call_args
    assert kwargs["target_date"] == _date(2026, 7, 20)
    assert result["data"].id == "d2"


@pytest.mark.unit
async def test_hotspots_sse_returns_streaming_response() -> None:
    request = MagicMock()
    response = await hotspots_sse(request)
    assert response.media_type == "text/event-stream"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"
