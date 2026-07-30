"""RSS news collector."""

import time
from datetime import UTC, datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]
import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


def _parse_date(value: time.struct_time | tuple[Any, ...] | None) -> datetime | None:
    """Convert a feedparser date structure to a timezone-aware datetime.

    feedparser 解析 RFC 2822 (e.g. ``Tue, 09 Jul 2026 12:00:00 +0000``)
    返回的 ``published_parsed`` 是 **UTC** struct_time，所以这里直接
    用前 6 个字段构造 UTC aware datetime —— 不走 ``time.mktime``，
    后者会按本地时区解释，跟 macOS / Windows / Linux 服务器时区
    混在一起产生 8 小时漂移。
    """
    if value is None:
        return None
    if isinstance(value, time.struct_time) or (
        isinstance(value, tuple) and len(value) >= 6
    ):
        try:
            return datetime(  # noqa: DTZ001
                value[0], value[1], value[2], value[3], value[4], value[5],
                tzinfo=UTC,
            )
        except (TypeError, ValueError):
            return None
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
