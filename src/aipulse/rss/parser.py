"""RSS feed parser."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class RssEntryItem:
    """Normalized RSS entry item."""

    title: str | None
    url: str
    published_at: datetime | None


class RssParser:
    """Parse RSS feeds into normalized entry items."""

    async def parse_feed(self, feed_url: str) -> list[RssEntryItem]:
        """Parse an RSS feed URL and return normalized entries."""
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to parse feed %s: %s", feed_url, exc)
            return []

        return [self._normalize_entry(entry) for entry in parsed.entries]

    def _normalize_entry(self, entry: Any) -> RssEntryItem:
        """Convert a feedparser entry into a normalized item."""
        published = self._parse_published_at(entry)
        return RssEntryItem(
            title=getattr(entry, "title", None) or None,
            url=getattr(entry, "link", "") or "",
            published_at=published,
        )

    def _parse_published_at(self, entry: Any) -> datetime | None:
        """Extract the publication datetime from a feedparser entry."""
        parsed_time: struct_time | None = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if parsed_time is None:
            return None
        try:
            return datetime(*parsed_time[:6], tzinfo=UTC)
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid published date in entry: %s", exc)
            return None
