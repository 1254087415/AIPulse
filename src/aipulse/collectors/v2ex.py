"""V2EX hot topics collector."""

from datetime import UTC, datetime
from typing import Any

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class V2exHotCollector(BaseCollector):
    """Collector for V2EX hot topics."""

    source_type = "v2ex_hot"
    name = "V2EX 热门"

    def __init__(self, timeout: float = 30.0):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        }
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def fetch(self) -> list[RawItem]:
        """Fetch V2EX hot topics from public API."""
        url = "https://www.v2ex.com/api/topics/hot.json"
        response = await self._client.get(url)
        response.raise_for_status()
        items = response.json()
        raw_items: list[RawItem] = []
        for item in items:
            member = item.get("member", {})
            raw_items.append(
                RawItem(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", "") or item.get("title", ""),
                    published_at=_parse_timestamp(item.get("created")),
                    raw_metadata={
                        "interactions": {
                            "views": item.get("views", 0),
                            "comments": item.get("replies", 0),
                        },
                        "author": member.get("username"),
                        "node": item.get("node", {}).get("title"),
                    },
                )
            )
        return raw_items

    async def close(self) -> None:
        await self._client.aclose()

    def normalize(self, raw: RawItem) -> HotspotCandidate:
        return HotspotCandidate(
            title=raw.title,
            url=raw.url,
            canonical_url=raw.url,
            content=raw.content,
            published_at=raw.published_at,
            source_type=self.source_type,
            raw_metadata=raw.raw_metadata,
        )


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    return None
