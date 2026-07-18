"""Tests for the hotspot service layer."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from aipulse.collectors.base import HotspotCandidate
from aipulse.hotspot import service as hotspot_service
from aipulse.hotspot.models import Hotspot, Keyword, Source
from aipulse.hotspot.service import (
    create_keyword,
    delete_keyword,
    generate_digest,
    get_hotspot,
    get_related_hotspots,
    list_hotspots,
    list_keywords,
    list_sources,
    process_candidates,
    update_keyword,
    update_source,
)
from aipulse.hotspot.summarizer import HotspotAnalysis


@pytest_asyncio.fixture(autouse=True)
async def _reset_tables():
    """Drop and recreate tables before and after each test for isolation."""
    from aipulse.store.database import reset_db

    await reset_db()
    yield
    await reset_db()


@pytest.fixture
def source_data():
    return {
        "id": "s1",
        "name": "Test Source",
        "source_type": "rss_news",
        "collector_class": "RssNewsCollector",
    }


@pytest_asyncio.fixture
async def source(db_session, source_data):
    src = Source(**source_data)
    db_session.add(src)
    await db_session.commit()
    return src


@pytest.fixture
def real_analysis():
    return HotspotAnalysis(
        is_real=True,
        relevance=75,
        importance="high",
        summary="测试摘要",
        category="ai-products",
    )


@pytest.fixture
def fake_analysis():
    return HotspotAnalysis(
        is_real=False,
        relevance=0,
        importance="low",
        summary="",
        category="industry",
    )


def make_candidate(
    url="https://example.com/article?utm_source=x",
    title="Article",
    content="Some content",
    interactions=None,
):
    return HotspotCandidate(
        title=title,
        url=url,
        canonical_url=url,
        content=content,
        published_at=None,
        source_type="rss_news",
        raw_metadata={"interactions": interactions or {}},
    )


@pytest.mark.integration
async def test_list_hotspots_returns_empty(db_session):
    items, total = await list_hotspots(db_session)
    assert items == []
    assert total == 0


@pytest.mark.integration
async def test_list_hotspots_filters_and_paginates(db_session, source):
    for index in range(3):
        db_session.add(
            Hotspot(
                title=f"AI news {index}",
                url=f"https://example.com/{index}",
                canonical_url=f"https://example.com/{index}",
                source_id=source.id,
                source_type="rss_news" if index < 2 else "arxiv",
                category="ai-products" if index == 0 else "industry",
                heat_score=float(index * 10),
            )
        )
    await db_session.commit()

    items, total = await list_hotspots(db_session, q="AI news")
    assert total == 3

    items, total = await list_hotspots(db_session, source="rss_news")
    assert total == 2

    items, total = await list_hotspots(db_session, category="ai-products")
    assert total == 1
    assert items[0].title == "AI news 0"

    items, total = await list_hotspots(db_session, page=1, limit=2)
    assert total == 3
    assert len(items) == 2
    assert items[0].heat_score >= items[1].heat_score


@pytest.mark.integration
async def test_get_hotspot(db_session, source):
    hotspot = Hotspot(
        id="h1",
        title="Find me",
        url="https://example.com/h1",
        canonical_url="https://example.com/h1",
        source_id=source.id,
        source_type="rss_news",
    )
    db_session.add(hotspot)
    await db_session.commit()

    found = await get_hotspot(db_session, "h1")
    assert found is not None
    assert found.title == "Find me"

    missing = await get_hotspot(db_session, "missing")
    assert missing is None


@pytest.mark.integration
async def test_create_keyword(db_session):
    keyword = await create_keyword(db_session, "LLM")
    assert keyword.value == "LLM"
    assert keyword.id is not None

    persisted = await db_session.get(Keyword, keyword.id)
    assert persisted is not None
    assert persisted.value == "LLM"


@pytest.mark.integration
async def test_process_candidates_creates_hotspot(db_session, source, real_analysis, monkeypatch):
    async def fake_analyze(keyword, content, adapter=None):
        return real_analysis

    monkeypatch.setattr(hotspot_service, "analyze_hotspot", fake_analyze)
    events = []

    async def fake_broadcast(event, data):
        events.append((event, data))

    monkeypatch.setattr(hotspot_service.sse_manager, "broadcast", fake_broadcast)

    candidate = make_candidate()
    count = await process_candidates(db_session, [candidate], source)

    assert count == 1
    assert len(events) == 1
    assert events[0][0] == "hotspot.new"
    assert "id" in events[0][1]

    hotspots = (await db_session.execute(select(Hotspot))).scalars().all()
    assert len(hotspots) == 1
    assert hotspots[0].title == candidate.title
    assert hotspots[0].canonical_url == "https://example.com/article"
    assert hotspots[0].status == "new"
    assert hotspots[0].heat_score > 0


@pytest.mark.integration
async def test_process_candidates_skips_duplicate(db_session, source, real_analysis, monkeypatch):
    async def fake_analyze(keyword, content, adapter=None):
        return real_analysis

    monkeypatch.setattr(hotspot_service, "analyze_hotspot", fake_analyze)
    events = []

    async def fake_broadcast(event, data):
        events.append((event, data))

    monkeypatch.setattr(hotspot_service.sse_manager, "broadcast", fake_broadcast)

    candidate = make_candidate()
    assert await process_candidates(db_session, [candidate], source) == 1
    assert await process_candidates(db_session, [candidate], source) == 0
    assert len(events) == 1


@pytest.mark.integration
async def test_process_candidates_skips_non_real(db_session, source, fake_analysis, monkeypatch):
    async def fake_analyze(keyword, content, adapter=None):
        return fake_analysis

    monkeypatch.setattr(hotspot_service, "analyze_hotspot", fake_analyze)
    events = []

    async def fake_broadcast(event, data):
        events.append((event, data))

    monkeypatch.setattr(hotspot_service.sse_manager, "broadcast", fake_broadcast)

    candidate = make_candidate()
    count = await process_candidates(db_session, [candidate], source)

    assert count == 0
    assert events == []


@pytest.mark.integration
async def test_process_candidates_calculates_heat_score(
    db_session, source, real_analysis, monkeypatch
):
    real_analysis.relevance = 100

    async def fake_analyze(keyword, content, adapter=None):
        return real_analysis

    monkeypatch.setattr(hotspot_service, "analyze_hotspot", fake_analyze)

    source.default_weight = 2.0
    candidate = make_candidate(interactions={"likes": 10})
    count = await process_candidates(db_session, [candidate], source)

    assert count == 1
    hotspots = (await db_session.execute(select(Hotspot))).scalars().all()
    assert hotspots[0].heat_score > 200


@pytest.mark.integration
async def test_list_keywords(db_session):
    await create_keyword(db_session, "LLM")
    await create_keyword(db_session, "Agent")
    keywords = await list_keywords(db_session)
    assert len(keywords) == 2
    assert keywords[0].value == "Agent"


@pytest.mark.integration
async def test_update_keyword(db_session):
    keyword = await create_keyword(db_session, "LLM")
    updated = await update_keyword(db_session, keyword.id, {"notify_on_match": True})
    assert updated is not None
    assert updated.notify_on_match is True


@pytest.mark.integration
async def test_delete_keyword(db_session):
    keyword = await create_keyword(db_session, "LLM")
    assert await delete_keyword(db_session, keyword.id) is True
    assert await delete_keyword(db_session, keyword.id) is False


@pytest.mark.integration
async def test_list_sources(db_session, source_data):
    source = Source(**source_data)
    db_session.add(source)
    await db_session.commit()
    sources = await list_sources(db_session)
    assert len(sources) == 1
    assert sources[0].name == "Test Source"


@pytest.mark.integration
async def test_update_source(db_session, source_data):
    source = Source(**source_data)
    db_session.add(source)
    await db_session.commit()
    updated = await update_source(
        db_session, source.id, {"is_active": False, "default_weight": 2.5}
    )
    assert updated is not None
    assert updated.is_active is False
    assert updated.default_weight == 2.5


@pytest.mark.integration
async def test_generate_digest(db_session, source):
    for index in range(3):
        db_session.add(
            Hotspot(
                title=f"AI news {index}",
                url=f"https://example.com/{index}",
                canonical_url=f"https://example.com/{index}",
                source_id=source.id,
                source_type="rss_news",
                heat_score=float(index * 10),
            )
        )
    await db_session.commit()

    digest = await generate_digest(db_session)
    assert digest.title.startswith("AIPulse AI 热点日报")
    assert "AI news" in digest.content
    assert len(digest.top_hotspot_ids or []) == 3


@pytest.mark.integration
async def test_get_related_hotspots(db_session, source):
    h1 = Hotspot(
        id="h1",
        title="AI news 1",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss_news",
        category="ai-products",
        heat_score=50,
    )
    h2 = Hotspot(
        id="h2",
        title="AI news 2",
        url="https://example.com/2",
        canonical_url="https://example.com/2",
        source_id=source.id,
        source_type="rss_news",
        category="ai-products",
        heat_score=30,
    )
    db_session.add_all([h1, h2])
    await db_session.commit()

    related = await get_related_hotspots(db_session, "h1")
    assert len(related) == 1
    assert related[0].id == "h2"
