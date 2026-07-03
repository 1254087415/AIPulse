"""Tests for RSS feed parser."""

from datetime import UTC, datetime
from time import struct_time
from unittest.mock import MagicMock, patch

import pytest

from aipulse.rss.parser import RssEntryItem, RssParser


@pytest.fixture
def parser() -> RssParser:
    return RssParser()


@pytest.mark.unit
async def test_parse_feed_returns_normalized_entries(parser: RssParser) -> None:
    mock_entry = MagicMock()
    mock_entry.title = "Test Title"
    mock_entry.link = "https://example.com/article"
    mock_entry.published_parsed = struct_time((2024, 1, 15, 10, 30, 0, 0, 15, 0))

    with patch("feedparser.parse", return_value=MagicMock(entries=[mock_entry])):
        result = await parser.parse_feed("https://example.com/feed.xml")

    assert len(result) == 1
    assert result[0].title == "Test Title"
    assert result[0].url == "https://example.com/article"
    assert result[0].published_at == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_parse_feed_uses_updated_parsed_fallback(parser: RssParser) -> None:
    mock_entry = MagicMock()
    mock_entry.title = "Updated Title"
    mock_entry.link = "https://example.com/updated"
    mock_entry.published_parsed = None
    mock_entry.updated_parsed = struct_time((2024, 2, 1, 8, 0, 0, 0, 32, 0))

    with patch("feedparser.parse", return_value=MagicMock(entries=[mock_entry])):
        result = await parser.parse_feed("https://example.com/feed.xml")

    assert len(result) == 1
    assert result[0].published_at == datetime(2024, 2, 1, 8, 0, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_parse_feed_returns_empty_on_exception(parser: RssParser) -> None:
    with patch("feedparser.parse", side_effect=RuntimeError("parse failed")):
        result = await parser.parse_feed("https://example.com/feed.xml")

    assert result == []


@pytest.mark.unit
async def test_parse_feed_skips_invalid_dates(parser: RssParser) -> None:
    mock_entry = MagicMock()
    mock_entry.title = "Bad Date"
    mock_entry.link = "https://example.com/bad"
    mock_entry.published_parsed = "not-a-struct-time"

    with patch("feedparser.parse", return_value=MagicMock(entries=[mock_entry])):
        result = await parser.parse_feed("https://example.com/feed.xml")

    assert len(result) == 1
    assert result[0].published_at is None


@pytest.mark.unit
def test_normalize_entry_defaults() -> None:
    parser = RssParser()
    entry = MagicMock()
    entry.title = None
    entry.link = None
    entry.published_parsed = None
    entry.updated_parsed = None

    result = parser._normalize_entry(entry)

    assert result == RssEntryItem(title=None, url="", published_at=None)
