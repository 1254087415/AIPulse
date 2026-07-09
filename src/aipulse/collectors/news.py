"""RSS news collector."""

import time
from datetime import datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]
import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


def _parse_date(value: time.struct_time | tuple[Any, ...] | None) -> datetime | None:
    """Convert a feedparser date structure to a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, time.struct_time):
        return datetime.fromtimestamp(time.mktime(value))
    if isinstance(value, tuple):
        return datetime.fromtimestamp(time.mktime(value))
    return None


@register
class RssNewsCollector(BaseCollector):
    """Collector for RSS/Atom news feeds."""

    source_type = "rss_news"
    name = "RSS News"

    def __init__(self, feed_url: str, name: str = "RSS News", timeout: float = 30.0):
        self.feed_url = feed_url
        self.name = name
        self._client = httpx.AsyncClient(timeout=timeout)

    async def fetch(self) -> list[RawItem]:
        """Fetch and parse the RSS feed."""
        response = await self._client.get(self.feed_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        return [
            RawItem(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                content=entry.get("summary", ""),
                published_at=_parse_date(entry.get("published_parsed")),
                raw_metadata={"feed": self.feed_url},
            )
            for entry in parsed.entries
        ]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def normalize(self, raw: RawItem) -> HotspotCandidate:
        """Normalize a raw RSS entry into a hotspot candidate."""
        return HotspotCandidate(
            title=raw.title,
            url=raw.url,
            canonical_url=raw.url,
            content=raw.content or raw.title,
            published_at=raw.published_at,
            source_type=self.source_type,
            raw_metadata=raw.raw_metadata,
        )
