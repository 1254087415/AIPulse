"""UAPI 线路 —— 走 uapis.cn 公开接口，免 Cookie。

依赖第三方服务（uapis.cn）稳定性。失败时返回空 list，不抛异常。

接口历史（2026-07）：
- 旧 ``/api/v1/space/arc/search`` + ``/api/v1/space/card``：404 NOT_FOUND
- 新 ``/api/v1/social/bilibili/archives?mid=<mid>&page=<n>&size=<n>``：单一端点
  返回 ``{total, page, size, videos[{bvid, title, cover, duration,
  play_count, publish_time, ...}]}``。无外层 code 包裹；UP主 不存在时
  返回 ``{total: 0, videos: []}``。
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
ARCHIVES_PATH = "/social/bilibili/archives"
DEFAULT_TIMEOUT = 15.0
DEFAULT_PAGE_SIZE = 50


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
        """分页拉取 UP主 视频，直到命中 last_cursor_id 或 count 满。

        新接口响应：``{"total":N, "page":1, "size":20, "videos":[...]}``
        列表本身已按时间倒序（最新在前）。
        """
        videos: list[UpVideo] = []
        page = 1
        page_size = min(count, DEFAULT_PAGE_SIZE)
        try:
            while len(videos) < count:
                resp = await self._client.get(
                    f"{UAPI_BASE}{ARCHIVES_PATH}",
                    params={"mid": mid, "page": page, "size": page_size},
                )
                resp.raise_for_status()
                payload = resp.json() or {}
                if not isinstance(payload, dict):
                    logger.warning(
                        "[uapi] mid=%s page=%s non-dict payload: %r",
                        mid, page, payload,
                    )
                    break

                page_videos = payload.get("videos") or []
                total = int(payload.get("total") or 0)
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
                # 翻页条件：已收集 < count 且本页满 size 且 total > 已发页 × size
                if page * page_size >= total:
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
        """archives 端点不返回合集 → 返回空 list，由 HTML 线路补齐。"""
        logger.debug("[uapi] fetch_collections mid=%s (no-op for uapi)", mid)
        return []

    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """通过 /archives 总数判定：total==0 即 UP主 不存在或无投稿。

        端点不带外层 ``code``；唯一失败模式是网络/HTTP 异常（返回空 list
        时同样算不存在，避免误把接口抖动当成"账号存在"）。
        """
        try:
            resp = await self._client.get(
                f"{UAPI_BASE}{ARCHIVES_PATH}",
                params={"mid": mid, "page": 1, "size": 1},
            )
            resp.raise_for_status()
            payload = resp.json() or {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[uapi] validate_up_exists mid=%s failed: %s", mid, exc)
            return False, f"校验失败：{exc}"

        if not isinstance(payload, dict):
            return False, "校验失败：响应格式异常"

        total = int(payload.get("total") or 0)
        videos = payload.get("videos") or []
        if total == 0 and not videos:
            return False, "UP主不存在或暂无投稿"
        # 尝试拿第一条视频的标题当 display_name 的兜底（spec 不要求但方便 UI）
        name = ""
        if videos:
            first = videos[0] if isinstance(videos[0], dict) else {}
            name = (first.get("title") or "").strip()
        # display_name 由 caller（validate 路由）再走 HTML 兜底；
        # 这里返回 True + 空 name 表示"账号存在但拿不到昵称"。
        return True, name

    @staticmethod
    def _parse_video(item: dict) -> Optional[UpVideo]:
        """解析 archives 端点单条 item。"""
        try:
            bvid = item["bvid"]
            title = (item.get("title") or "").strip()
            pub_ts = int(item.get("publish_time") or 0)
            return UpVideo(
                bvid=bvid,
                title=title or bvid,
                pubdate=datetime.fromtimestamp(pub_ts) if pub_ts else datetime.now(),
                duration_sec=int(item.get("duration") or 0),
                description="",
                cover_url=item.get("cover") or "",
                play_count=int(item.get("play_count") or 0),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("[uapi] parse_video failed item=%s: %s", item, exc)
            return None