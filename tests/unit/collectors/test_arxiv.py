"""Tests for the arXiv collector."""

from datetime import UTC, datetime

import pytest
import respx
from httpx import Response

from aipulse.collectors.arxiv import ArxivCollector, _parse_iso
from aipulse.collectors.registry import clear_registry, get_collector, register


@pytest.fixture(autouse=True)
def _clean_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.mark.unit
@respx.mock
async def test_arxiv_collector_fetches_and_normalizes_entries():
    """ArxivCollector parses Atom entries into HotspotCandidates."""
    atom = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query: search_query</title>
  <entry>
    <title>Large Language Models are Great
    </title>
    <id>http://arxiv.org/abs/2607.00001</id>
    <published>2026-07-09T00:00:00Z</published>
    <summary>Abstract text here.</summary>
  </entry>
</feed>
"""
    respx.get("http://export.arxiv.org/api/query").mock(return_value=Response(200, text=atom))

    collector = ArxivCollector(categories=["cs.AI"])
    raw_items = await collector.fetch()

    assert len(raw_items) == 1
    assert raw_items[0].title == "Large Language Models are Great"
    assert raw_items[0].url == "http://arxiv.org/abs/2607.00001"
    assert raw_items[0].content == "Abstract text here."
    assert raw_items[0].published_at == datetime(2026, 7, 9, 0, 0, 0, tzinfo=UTC)

    candidate = collector.normalize(raw_items[0])
    assert candidate.title == "Large Language Models are Great"
    assert candidate.canonical_url == "http://arxiv.org/abs/2607.00001"
    assert candidate.source_type == "arxiv"


@pytest.mark.unit
def test_arxiv_collector_is_registered():
    """ArxivCollector registers itself under arxiv."""
    from aipulse.collectors.arxiv import ArxivCollector as ImportedCollector

    register(ImportedCollector)
    assert get_collector("arxiv") is ImportedCollector


@pytest.mark.unit
def test_parse_iso_returns_none_for_empty_values():
    """_parse_iso returns None for empty or missing values."""
    assert _parse_iso(None) is None
    assert _parse_iso("") is None
