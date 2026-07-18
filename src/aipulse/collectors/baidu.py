"""Baidu hot search collector."""

from datetime import UTC, datetime
from typing import Any

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class BaiduHotCollector(BaseCollector):
    """Collector for Baidu hot search."""

    source_type = "baidu_hot"
    name = "百度热搜"

    def __init__(self, timeout: float = 30.0):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://top.baidu.com/",
        }
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def fetch(self) -> list[RawItem]:
        """Fetch Baidu hot search from public API."""
        url = "https://top.baidu.com/api/board"
        params = {"platform": "wise", "tab": "realtime"}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        cards = data.get("data", {}).get("cards", [])
        items: list[dict[str, Any]] = []
        for card in cards:
            items.extend(card.get("content", []))
        raw_items: list[RawItem] = []
        for item in items:
            raw_items.append(
                RawItem(
                    title=item.get("word", ""),
                    url=item.get("url", "") or f"https://www.baidu.com/s?wd={item.get('word', '')}",
                    content=item.get("desc", "") or item.get("word", ""),
                    published_at=datetime.now(UTC),
                    raw_metadata={
                        "interactions": {
                            "views": _parse_hot_value(item.get("hotScore")),
                        },
                        "category": item.get("category"),
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


def _parse_hot_value(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.replace(",", ""))
        except ValueError:
            return 0
    return 0
