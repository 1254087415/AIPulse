"""Weibo hot search collector."""

from datetime import UTC, datetime

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class WeiboHotCollector(BaseCollector):
    """Collector for Weibo hot search."""

    source_type = "weibo_hot"
    name = "微博热搜"

    def __init__(self, timeout: float = 30.0):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://weibo.com/",
        }
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def fetch(self) -> list[RawItem]:
        """Fetch Weibo hot search from public API."""
        url = "https://weibo.com/ajax/side/hotSearch"
        response = await self._client.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("ok") != 1:
            raise RuntimeError(f"Weibo API error: {data}")
        items = data.get("data", {}).get("realtime", [])
        raw_items: list[RawItem] = []
        for item in items:
            title = item.get("note") or item.get("word") or ""
            raw_items.append(
                RawItem(
                    title=title,
                    url=f"https://s.weibo.com/weibo?q={_encode_query(title)}",
                    content=item.get("word_scheme") or title,
                    published_at=datetime.now(UTC),
                    raw_metadata={
                        "interactions": {
                            "views": item.get("num", 0),
                            "raw_hot": item.get("raw_hot", 0),
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


def _encode_query(text: str) -> str:
    import urllib.parse

    return urllib.parse.quote(f"#{text}#")
