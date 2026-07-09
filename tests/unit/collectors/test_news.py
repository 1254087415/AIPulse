"""Tests for the RSS news collector."""

import time
from datetime import UTC, datetime

import pytest
import respx
from httpx import Response

from aipulse.collectors.news import RssNewsCollector, _parse_date
from aipulse.collectors.registry import clear_registry, get_collector, register


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.mark.unit
def test_parse_date_handles_none():
    """_parse_date returns None for missing values."""
    assert _parse_date(None) is None


@pytest.mark.unit
def test_parse_date_handles_struct_time():
    """_parse_date converts time.struct_time to datetime."""
    published = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)
    struct = time.gmtime(published.timestamp())
    parsed = _parse_date(struct)
    assert parsed is not None
    assert parsed.utctimetuple() == struct


@pytest.mark.unit
def test_parse_date_handles_tuple():
    """_parse_date converts plain tuples to datetime."""
    published = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)
    tpl = tuple(time.gmtime(published.timestamp()))[:9]
    parsed = _parse_date(tpl)
    assert parsed is not None
    assert parsed.utctimetuple()[:6] == (2026, 7, 9, 12, 0, 0)


@pytest.mark.unit
@respx.mock
async def test_rss_collector_fetches_and_normalizes_entries():
    """RssNewsCollector parses feed entries into HotspotCandidates."""
    feed_url = "https://example.com/news.rss"
    published = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)
    published_struct = time.gmtime(published.timestamp())
    rss = f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <link>{feed_url}</link>
    <item>
      <title>AI Breakthrough</title>
      <link>https://example.com/ai-breakthrough</link>
      <summary>Summary text</summary>
      <pubDate>{published.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>
    </item>
  </channel>
</rss>
"""
    respx.get(feed_url).mock(return_value=Response(200, text=rss))

    collector = RssNewsCollector(feed_url=feed_url)
    raw_items = await collector.fetch()

    assert len(raw_items) == 1
    assert raw_items[0].title == "AI Breakthrough"
    assert raw_items[0].url == "https://example.com/ai-breakthrough"
    assert raw_items[0].content == "Summary text"
    assert raw_items[0].raw_metadata == {"feed": feed_url}

    candidate = collector.normalize(raw_items[0])
    assert candidate.title == "AI Breakthrough"
    assert candidate.canonical_url == "https://example.com/ai-breakthrough"
    assert candidate.source_type == "rss_news"
    assert candidate.published_at is not None
    assert candidate.published_at.utctimetuple() == published_struct


@pytest.mark.unit
@respx.mock
async def test_rss_collector_uses_title_when_summary_missing():
    """normalize falls back to title when content is empty."""
    feed_url = "https://example.com/news.rss"
    rss = """
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>No Summary</title>
      <link>https://example.com/no-summary</link>
    </item>
  </channel>
</rss>
"""
    respx.get(feed_url).mock(return_value=Response(200, text=rss))

    collector = RssNewsCollector(feed_url=feed_url)
    raw_items = await collector.fetch()
    candidate = collector.normalize(raw_items[0])
    assert candidate.content == "No Summary"


@pytest.mark.unit
def test_rss_collector_is_registered():
    """RssNewsCollector registers itself under rss_news."""
    from aipulse.collectors.news import RssNewsCollector as ImportedCollector

    register(ImportedCollector)
    assert get_collector("rss_news") is ImportedCollector
