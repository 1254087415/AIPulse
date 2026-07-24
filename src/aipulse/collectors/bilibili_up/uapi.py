"""UAPI 线路 —— 走 uapis.cn 公开接口，免 Cookie。

依赖第三方服务（uapis.cn）稳定性。失败时返回空 list，不抛异常。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpCollection,
    UpVideo,
)


logger = logging.getLogger(__name__)

UAPI_BASE = "https://uapis.cn/api/v1"
DEFAULT_TIMEOUT = 15.0


class BilibiliUpUapiCollector(BaseBilibiliUpCollector):
    """走 uapis.cn 公开接口，无需 Cookie。"""

    strategy: str = "uapi"

    def __init__(self, **kwargs):
        super().__init__(strategy="uapi", **kwargs)
        self._client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": "AIPulse/0.3"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_videos(
        self,
        mid: str,
        count: int,
        last_cursor_id: Optional[str] = None,
    ) -> list[UpVideo]:
        """分页拉取 UP主视频，until last_cursor_id 已读。

        UAPI 返回格式：{"code":0,"data":{"list":[...],"has_more":N}}
        """
        videos: list[UpVideo] = []
        page = 1
        page_size = min(count, 50)
        try:
            while len(videos) < count:
                url = (
                    f"{UAPI_BASE}/space/arc/search"
                    f"?mid={mid}&type=video&page={page}&page_size={page_size}"
                )
                resp = await self._client.get(url)
                resp.raise_for_status()
                payload = resp.json()

                if payload.get("code") != 0:
                    logger.warning(
                        "[uapi] mid=%s page=%s returned non-zero code: %s",
                        mid,
                        page,
                        payload.get("message") or payload,
                    )
                    break

                data = payload.get("data") or {}
                page_videos = data.get("list") or []
                if not page_videos:
                    break

                stop = False
                for item in page_videos:
                    v = self._parse_video(item)
                    if v is None:
                        continue
                    if last_cursor_id and v.bvid == last_cursor_id:
                        stop = True
                        break
                    videos.append(v)
                    if len(videos) >= count:
                        stop = True
                        break

                if stop:
                    break
                if not data.get("has_more", True):
                    break
                page += 1

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "[uapi] fetch_videos mid=%s failed: %s; returning empty list",
                mid,
                exc,
            )
            return []

        return videos

    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """UAPI 当前不返回合集接口 —— 返回空 list，由 HTML 线路补齐。"""
        logger.debug("[uapi] fetch_collections mid=%s (no-op for uapi)", mid)
        return []

    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """通过 UAPI card 接口校验 UP主 存在性。"""
        url = f"{UAPI_BASE}/space/card?mid={mid}"
        try:
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return False, "UP主不存在"
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 0:
                return False, payload.get("message") or "UP主不存在"
            data = payload.get("data") or {}
            user = data.get("user") or {}
            name = user.get("name") or ""
            if not name:
                return False, "UP主账号已注销"
            return True, name
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[uapi] validate_up_exists mid=%s failed: %s", mid, exc)
            return False, f"校验失败：{exc}"

    @staticmethod
    def _parse_video(item: dict) -> Optional[UpVideo]:
        """解析 UAPI 返回的单条视频 item。"""
        try:
            bvid = item["bvid"]
            title = (item.get("title") or "").strip()
            pub_ts = int(item.get("pubdate", 0))
            return UpVideo(
                bvid=bvid,
                title=title or bvid,
                pubdate=datetime.fromtimestamp(pub_ts) if pub_ts else datetime.now(),
                duration_sec=int(item.get("duration", 0) or 0),
                description=item.get("description", "") or "",
                cover_url=item.get("pic", "") or "",
                play_count=int(item.get("play", 0) or 0),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("[uapi] parse_video failed item=%s: %s", item, exc)
            return None