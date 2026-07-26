"""UP主采集器基类 + 数据模型。

策略模式 + 工厂：
- base.py: 抽象基类 + UpVideo / UpCollection 数据类
- uapi.py: 走 uapis.cn 公开接口（无需 Cookie）
- html.py: 抓 space.bilibili.com HTML 解析（反爬自主可控）
- factory.py: BilibiliUpCollectorFactory.create(strategy)
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aipulse.collectors.base import BaseCollector, RawItem


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpVideo:
    """UP主的一个视频（与 hotspot 解耦）。"""

    bvid: str
    title: str
    pubdate: datetime
    duration_sec: int = 0
    description: str = ""
    cover_url: str = ""
    play_count: int = 0
    is_backfill: bool = False
    collection_id: Optional[str] = None


@dataclass(frozen=True)
class UpCollection:
    """UP主的一个合集（系列课程 / 播放列表）。"""

    platform_collection_id: str
    title: str
    video_count: int = 0
    description: str = ""


class BaseBilibiliUpCollector(BaseCollector):
    """B站 UP主采集器基类。

    继承 BaseCollector，复用 collect() / normalize() 流程。
    """

    source_type: str = "bilibili_up"
    name: str = "Bilibili UP主"

    def __init__(self, strategy: str, **kwargs):
        self.strategy = strategy
        super().__init__(**kwargs)

    @abstractmethod
    async def fetch_videos(
        self,
        mid: str,
        count: int,
        last_cursor_id: Optional[str] = None,
    ) -> list[UpVideo]:
        """获取 UP主最新 count 个视频。last_cursor_id 实现增量（只返回新的）。

        失败约定：捕获异常 + log warning + 返回空 list（不重试）。
        """
        raise NotImplementedError

    @abstractmethod
    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """获取 UP主所有合集（系列）。失败返回空 list。"""
        raise NotImplementedError

    @abstractmethod
    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """校验 mid 是否存在。返回 (exists, display_name_or_error_msg)。"""
        raise NotImplementedError

    # ---------- BaseCollector 桥接 ----------
    async def fetch(self) -> list[RawItem]:
        """BaseCollector.fetch 默认实现 — 调用方应使用 fetch_videos(mid, count)。

        此处留空 — UP主 collector 需要 mid 参数，不能用无参 fetch() 模式。
        调用方走 fetch_videos 路径。
        """
        return []

    def normalize(self, raw: RawItem) -> None:  # type: ignore[override]
        """BaseCollector.normalize 占位 — UP主 collector 不走 hotspot 通用 normalize。

        实际写 hotspot 由 scheduler/jobs/followed_up_scan.py 控制。
        """
        return None

    def upvideo_to_raw(self, mid: str, v: UpVideo) -> RawItem:
        """把 UpVideo 转 RawItem。供 collect 流程使用。"""
        url = f"https://www.bilibili.com/video/{v.bvid}"
        return RawItem(
            title=v.title,
            url=url,
            content=v.description or v.title,
            published_at=v.pubdate,
            raw_metadata={
                "bvid": v.bvid,
                "duration_sec": v.duration_sec,
                "description": v.description,
                "cover_url": v.cover_url,
                "play_count": v.play_count,
                "is_backfill": v.is_backfill,
                "collection_id": v.collection_id,
                "strategy": self.strategy,
                "mid": mid,
            },
        )