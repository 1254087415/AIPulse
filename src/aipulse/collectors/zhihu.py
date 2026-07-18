"""Zhihu hot list collector."""

from datetime import UTC, datetime
from typing import Any

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class ZhihuHotCollector(BaseCollector):
    """Collector for Zhihu hot list."""

    source_type = "zhihu_hot"
    name = "知乎热榜"

    def __init__(self, limit: int = 50, timeout: float = 30.0):
        self.limit = limit
        self._client = httpx.AsyncClient(timeout=timeout)

    async def fetch(self) -> list[RawItem]:
        """Fetch Zhihu hot list from public API."""
        url = "https://api.zhihu.com/topstory/hot-lists/total"
        params = {"limit": self.limit}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])
        raw_items: list[RawItem] = []
        for item in items:
            target = item.get("target", {})
            question_id = target.get("url", "").split("/")[-1]
            detail_text = item.get("detail_text", "")
            hot_value = _parse_hot_value(detail_text)
            raw_items.append(
                RawItem(
                    title=target.get("title", ""),
                    url=f"https://www.zhihu.com/question/{question_id}",
                    content=target.get("excerpt", "") or target.get("title", ""),
                    published_at=_parse_timestamp(target.get("created")),
                    raw_metadata={
                        "interactions": {
                            "views": hot_value,
                        },
                        "hot_value_text": detail_text,
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


def _parse_hot_value(text: str) -> int:
    """Parse '1234 万热度' into integer views."""
    if not text:
        return 0
    try:
        number_part = text.split()[0]
        if "万" in number_part:
            return int(float(number_part.replace("万", "")) * 10000)
        return int(float(number_part))
    except (ValueError, TypeError):
        return 0


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    return None
