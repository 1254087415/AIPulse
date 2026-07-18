"""Bilibili hot/ranking collector."""

from datetime import UTC, datetime
from typing import Any

import httpx

from aipulse.collectors.base import BaseCollector, HotspotCandidate, RawItem
from aipulse.collectors.registry import register


@register
class BilibiliHotCollector(BaseCollector):
    """Collector for Bilibili popular/ranking videos."""

    source_type = "bilibili_hot"
    name = "Bilibili 热门"

    def __init__(self, rid: str = "0", timeout: float = 30.0):
        self.rid = rid
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/ranking/all",
        }
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def fetch(self) -> list[RawItem]:
        """Fetch popular videos from Bilibili ranking API."""
        url = "https://api.bilibili.com/x/web-interface/ranking/v2"
        params = {"rid": self.rid, "type": "all"}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Bilibili API error: {data}")
        items = data.get("data", {}).get("list", [])
        raw_items: list[RawItem] = []
        for video in items:
            stat = video.get("stat", {})
            owner = video.get("owner", {})
            raw_items.append(
                RawItem(
                    title=video.get("title", ""),
                    url=f"https://www.bilibili.com/video/{video.get('bvid')}",
                    content=video.get("desc", "") or video.get("title", ""),
                    published_at=_parse_timestamp(video.get("pubdate")),
                    raw_metadata={
                        "interactions": {
                            "views": stat.get("view", 0),
                            "likes": stat.get("like", 0),
                            "comments": stat.get("reply", 0),
                            "shares": stat.get("share", 0),
                            "danmaku": stat.get("danmaku", 0),
                        },
                        "author": owner.get("name"),
                        "cover": video.get("pic"),
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
