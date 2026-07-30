"""HTML 线路 —— 抓 space.bilibili.com/:mid 的 bili-video-card DOM。

自主可控（不依赖第三方），但需要处理反爬（UA + Referer）。
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpCollection,
    UpVideo,
)


logger = logging.getLogger(__name__)

SPACE_URL = "https://space.bilibili.com/{mid}"
DEFAULT_TIMEOUT = 20.0
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BilibiliUpHtmlCollector(BaseBilibiliUpCollector):
    """抓 space.bilibili.com 的 bili-video-card DOM。"""

    strategy: str = "html"

    def __init__(self, **kwargs):
        super().__init__(strategy="html", **kwargs)
        self._client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.bilibili.com",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_videos(
        self,
        mid: str,
        count: int,
        last_cursor_id: Optional[str] = None,
    ) -> list[UpVideo]:
        """抓主页首屏 + 翻页（按需）。B 站 DOM 含 pubdate 属性。"""
        url = SPACE_URL.format(mid=mid)
        videos: list[UpVideo] = []
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("bili-video-card")
            if not cards:
                logger.warning("[html] mid=%s no bili-video-card found", mid)
                return []

            for card in cards:
                v = self._parse_card(card)
                if v is None:
                    continue
                if last_cursor_id and v.bvid == last_cursor_id:
                    break
                videos.append(v)
                if len(videos) >= count:
                    break

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "[html] fetch_videos mid=%s failed: %s; returning empty list",
                mid,
                exc,
            )
            return []

        return videos

    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """抓合集列表。"""
        url = f"{SPACE_URL.format(mid=mid)}/album"
        collections: list[UpCollection] = []
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.select("li.collection-card")
            for item in items:
                sid = item.get("data-sid") or item.get("sid")
                title_el = item.select_one("p.title")
                if not sid or not title_el:
                    continue
                collections.append(
                    UpCollection(
                        platform_collection_id=sid,
                        title=title_el.get_text(strip=True) or sid,
                        video_count=int(item.get("data-count", "0") or 0),
                    )
                )

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[html] fetch_collections mid=%s failed: %s", mid, exc)
            return []

        return collections

    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """HTML 校验：主页可访问且含 h1#h-name → 视为存在。"""
        url = SPACE_URL.format(mid=mid)
        try:
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return False, "UP主不存在"
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            name_el = soup.select_one("h1#h-name")
            if name_el and name_el.get_text(strip=True):
                return True, name_el.get_text(strip=True)
            return False, "UP主账号可能已注销"
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[html] validate_up_exists mid=%s failed: %s", mid, exc)
            return False, f"校验失败：{exc}"

    @staticmethod
    def _parse_card(card) -> Optional[UpVideo]:
        """从 bili-video-card 元素提取 UpVideo。

        B 站当前结构：
          <bili-video-card data-aid data-bvid data-attribute="...">
            <a href="//www.bilibili.com/video/BVxxxx"></a>
            <p pubdate="2026-07-12 10:30">...</p>
            <h3 title="...">视频标题</h3>
          </bili-video-card>
        """
        try:
            bvid = card.get("data-bvid") or ""
            if not bvid:
                link_el = card.find("a")
                href = link_el.get("href", "") if link_el else ""
                m = re.search(r"/(BV[A-Za-z0-9]+)", href)
                if m:
                    bvid = m.group(1)
            if not bvid:
                return None

            title_el = card.find("h3")
            title = (title_el.get_text(strip=True) if title_el else "") or bvid

            pubdate_str = card.get("pubdate", "")
            pubdate = _parse_pubdate(pubdate_str)

            cover = card.find("img")
            cover_url = cover.get("src", "") if cover else ""

            return UpVideo(
                bvid=bvid,
                title=title,
                pubdate=pubdate,
                duration_sec=0,
                cover_url=cover_url,
            )
        except (AttributeError, KeyError, ValueError) as exc:
            logger.warning("[html] parse_card failed: %s", exc)
            return None


def _parse_pubdate(s: str) -> datetime:
    """解析 bili-video-card 的 pubdate 属性。"""
    if not s:
        return datetime.now(UTC)
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    if s.isdigit():
        return datetime.fromtimestamp(int(s), tz=UTC)
    return datetime.now(UTC)