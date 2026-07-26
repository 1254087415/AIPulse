# 02 — B站 UP主采集（双轨 + 字幕 + 调度）

> **来源**：原文档 §4（B站采集方案 Q1 + Q18 + Q19）
> **上游依赖**：01 数据模型（`followed_up` 表 + `hotspots` 表）
> **下游交付物**：
> - `collectors/bilibili_up/` 完整双轨实现（base + uapi + html + factory）
> - `@register_strategy` 装饰器接入 `collectors/registry.py`
> - 字幕获取完整代码（AI 字幕 + ASR 兜底 + SESSDATA 读取）
> - APScheduler 定时任务（30 分钟）
> - `POST /api/followed-up/{id}/sync` 端点
> - UP主存在性校验端点
> - 完整测试用例清单
>
> **subagent 边界**：本模块产出 collector 实现 + sync 调度 + 字幕工具，不产出 Agent 逻辑（Agent 在 03）。
> **执行模式**：Phase 2 内 subagent-B1（Collector）和 subagent-B2（API 端点）可并行。

---



### 4.1 双线路策略模式 + 工厂

```python
# collectors/bilibili_up/base.py
class BaseBilibiliUpCollector(BaseCollector):
    source_type: str  # "bilibili_up"
    strategy: str     # "uapi" or "html"

    @abstractmethod
    async def fetch_videos(self, mid: str, count: int) -> list[UpVideo]: ...

    @abstractmethod
    async def fetch_collections(self, mid: str) -> list[UpCollection]: ...

    @abstractmethod
    async def validate_up_exists(self, mid: str) -> bool: ...


# collectors/bilibili_up/uapi.py
@register_strategy("uapi")
class BilibiliUpUapiCollector(BaseBilibiliUpCollector):
    """走 uapis.cn 公开接口，无需 Cookie"""
    ...


# collectors/bilibili_up/html.py
@register_strategy("html")
class BilibiliUpHtmlCollector(BaseBilibiliUpCollector):
    """走 space.bilibili.com HTML 抓取，自主可控"""
    ...


# collectors/bilibili_up/factory.py
class BilibiliUpCollectorFactory:
    @staticmethod
    def create(strategy: str, **kwargs) -> BaseBilibiliUpCollector: ...
```

### 4.2 存在性校验（Q18）

后端调 `https://api.bilibili.com/x/web-interface/card?mid={mid}`，返回 `code != 0` 或 `data.user.name` 为空 → 视为不存在。

### 4.3 字幕获取（Q10）

复用 `obsidian-clip-summary/scripts/bilibili_extract.py` 思路：

1. 优先官方字幕：调 `https://api.bilibili.com/x/player/v2?bvid=...&cid=...`
2. Cookie 来源：从 Obsidian Media Extended SQLite 读 SESSDATA（用户已登录时可用）
3. 校验：复用 `validate_subtitle_by_duration()` + `verify_subtitle_relevance()`
4. 无 Cookie fallback：直接调用（部分公共视频可访问）
5. ASR 兜底：下载音频走本地 whisper（`whisper_model` 已配置）
6. 完全失败：标 `decision_status = "failed"`，UI 显示需手动

### 4.4 扫描调度（Q15）

```python
# scheduler/jobs/followed_up_scan.py
async def scan_followed_up_by_id(followed_up_id: str) -> int: ...
async def scan_all_followed_up() -> int: ...
```

定时任务注册（复用 `scheduler/client.py`）：
```python
scheduler.add_job(
    scan_all_followed_up,
    trigger="interval",
    minutes=1,  # 高频触发，内部按 fetch_interval_minutes 判断
    id="followed_up_scan_all",
    replace_existing=True,
    coalesce=True,
)
```

**注**：扫描定时（Q15 锁定），**Agent pipeline 不定时**（Q14 锁定手动）。

### 4.5 双线路完整代码示例（Q1）

`BilibiliUpCollector` 家族由三部分组成：`base.py`（抽象基类 + 数据结构）+ `uapi.py` / `html.py`（两种实现）+ `factory.py`（工厂 + 注册表）。所有 collector **共享 `BaseCollector`** 的 raw item 转 hotspot 流程，只在「如何拿 UP主视频列表」这一段有差异。

#### 4.5.1 `collectors/bilibili_up/__init__.py`

```python
"""B站 UP主采集器族（双线路：uapi + html）"""
from src.aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpVideo,
    UpCollection,
)
from src.aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory

__all__ = [
    "BaseBilibiliUpCollector",
    "UpVideo",
    "UpCollection",
    "BilibiliUpCollectorFactory",
]
```

#### 4.5.2 `collectors/bilibili_up/base.py`

```python
"""UP主采集器基类 + 数据模型"""
from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.aipulse.collectors.base import BaseCollector, RawItem


logger = logging.getLogger(__name__)


@dataclass
class UpVideo:
    """UP主的一个视频（与 hotspot 解耦）"""
    bvid: str
    title: str
    pubdate: datetime           # 发布时间
    duration_sec: int
    description: str = ""
    cover_url: str = ""
    play_count: int = 0
    is_backfill: bool = False   # true = 历史 backfill（Q19 锁定）
    collection_id: Optional[str] = None  # 属于哪个合集（None = 主列表）


@dataclass
class UpCollection:
    """UP主的一个合集（系列课程 / 播放列表）"""
    platform_collection_id: str  # B站合集 sid
    title: str
    video_count: int = 0
    description: str = ""


class BaseBilibiliUpCollector(BaseCollector):
    """B站 UP主采集器基类。继承 BaseCollector，复用 collect() / from_source() 流程。"""

    source_type: str = "bilibili_up"

    def __init__(self, strategy: str, **kwargs):
        self.strategy = strategy
        super().__init__(source_type=self.source_type, **kwargs)

    @abstractmethod
    async def fetch_videos(
        self,
        mid: str,
        count: int,
        last_cursor_id: Optional[str] = None,
    ) -> list[UpVideo]:
        """获取 UP主最新 count 个视频。last_cursor_id 实现增量（只返回新的）。"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """获取 UP主所有合集（系列）。"""
        raise NotImplementedError

    @abstractmethod
    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """校验 mid 是否存在。返回 (exists, display_name_or_error_msg)。"""
        raise NotImplementedError

    # ---------- BaseCollector 桥接 ----------
    async def collect(self, source) -> list[RawItem]:
        """实现 BaseCollector.collect：扫一次 UP主，转 RawItem 列表。"""
        mid = source.uid  # 平台用户 ID
        cursor = getattr(source, "last_cursor_id", None)
        raw_videos = await self.fetch_videos(mid, count=50, last_cursor_id=cursor)
        return [self._upvideo_to_raw(mid, v) for v in raw_videos]

    def _upvideo_to_raw(self, mid: str, v: UpVideo) -> RawItem:
        """把 UpVideo 转 RawItem（继承自 BaseCollector 的统一数据结构）"""
        url = f"https://www.bilibili.com/video/{v.bvid}"
        return RawItem(
            source_type=self.source_type,
            platform="bilibili",
            content_id=v.bvid,
            title=v.title,
            url=url,
            author_uid=mid,
            published_at=v.pubdate,
            raw_data={
                "duration_sec": v.duration_sec,
                "description": v.description,
                "cover_url": v.cover_url,
                "play_count": v.play_count,
                "is_backfill": v.is_backfill,
                "collection_id": v.collection_id,
                "strategy": self.strategy,
            },
        )
```

#### 4.5.3 `collectors/bilibili_up/uapi.py`

```python
"""UAPI 线路 —— 走 uapis.cn 公开接口，免 Cookie"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from src.aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpVideo,
    UpCollection,
)
from src.aipulse.collectors.registry import register_strategy


logger = logging.getLogger(__name__)

UAPI_BASE = "https://uapis.cn/api/v1/space"
DEFAULT_TIMEOUT = 15.0


@register_strategy("uapi")
class BilibiliUpUapiCollector(BaseBilibiliUpCollector):
    """走 uapis.cn 公开接口，无需 Cookie；依赖第三方服务稳定性。"""

    strategy: str = "uapi"

    def __init__(self, **kwargs):
        super().__init__(strategy="uapi", **kwargs)
        # 复用 BaseCollector 的 httpx 客户端
        self._client = self.client  # type: httpx.AsyncClient

    async def fetch_videos(
        self,
        mid: str,
        count: int,
        last_cursor_id: Optional[str] = None,
    ) -> list[UpVideo]:
        """分页拉取 UP主视频，until last_cursor_id 已读"""
        videos: list[UpVideo] = []
        page = 1
        # UAPI 单页最大 page_size=50，这里循环翻页
        page_size = min(count, 50)
        try:
            while len(videos) < count:
                url = (
                    f"{UAPI_BASE}/arc/search"
                    f"?mid={mid}&type=video&page={page}&page_size={page_size}"
                )
                resp = await self._client.get(url, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                payload = resp.json()

                # UAPI 返回格式：{"code":0,"data":{"list":[...],"total":N}}
                if payload.get("code") != 0:
                    logger.warning(
                        "[uapi] mid=%s page=%s returned non-zero code: %s",
                        mid, page, payload,
                    )
                    break  # 不抛异常，直接停止翻页（让其他 UP 主继续扫描）

                data = payload.get("data") or {}
                page_videos = data.get("list") or []
                if not page_videos:
                    break

                stop = False
                for item in page_videos:
                    v = self._parse_video(item, mid)
                    if v is None:
                        continue
                    # 增量锚点：已读过的 bvid 不再返回
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
            # 失败处理：捕获异常 → log → 返回空 list（不重试）
            logger.warning(
                "[uapi] fetch_videos mid=%s failed: %s; returning empty list",
                mid, exc,
            )
            return []

        return videos

    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """UAPI 当前不返回合集接口 —— 返回空 list，由 HTML 线路或定时任务补齐。"""
        logger.debug("[uapi] fetch_collections mid=%s (no-op for uapi)", mid)
        return []

    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """通过 UAPI card 接口校验 UP主 存在性"""
        url = f"{UAPI_BASE}/card?mid={mid}"
        try:
            resp = await self._client.get(url, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                return False, "UP主不存在"
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 0:
                return False, payload.get("message", "UP主不存在")
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
    def _parse_video(item: dict, mid: str) -> Optional[UpVideo]:
        """解析 UAPI 返回的单条视频 item"""
        try:
            bvid = item["bvid"]
            title = item.get("title", "").strip()
            # UAPI 返回时间戳（秒）
            pub_ts = int(item.get("pubdate", 0))
            return UpVideo(
                bvid=bvid,
                title=title,
                pubdate=datetime.fromtimestamp(pub_ts),
                duration_sec=int(item.get("duration", 0)),
                description=item.get("description", ""),
                cover_url=item.get("pic", ""),
                play_count=int(item.get("play", 0)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("[uapi] parse failed mid=%s item=%s: %s", mid, item, exc)
            return None
```

#### 4.5.4 `collectors/bilibili_up/html.py`

```python
"""HTML 线路 —— 抓 space.bilibili.com/:mid 的 bili-video-card DOM"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from src.aipulse.collectors.bilibili_up.base import (
    BaseBilibiliUpCollector,
    UpVideo,
    UpCollection,
)
from src.aipulse.collectors.registry import register_strategy


logger = logging.getLogger(__name__)

SPACE_URL = "https://space.bilibili.com/{mid}"
DEFAULT_TIMEOUT = 20.0
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@register_strategy("html")
class BilibiliUpHtmlCollector(BaseBilibiliUpCollector):
    """抓 space.bilibili.com 的 bili-video-card DOM。自主可控，但需处理反爬。"""

    strategy: str = "html"

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
            # 使用独立 client 以塞自定义 UA（绕过基础反爬）
            async with httpx.AsyncClient(
                headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text

            tree = HTMLParser(html)
            cards = tree.css("bili-video-card")
            if not cards:
                logger.warning("[html] mid=%s no bili-video-card found", mid)
                return []

            for card in cards:
                v = self._parse_card(card, mid)
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
                mid, exc,
            )
            return []

        return videos

    async def fetch_collections(self, mid: str) -> list[UpCollection]:
        """抓合集列表（合集卡片 li.collection-card → sid + title）"""
        url = f"{SPACE_URL.format(mid=mid)}/album"
        collections: list[UpCollection] = []
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": UA}, timeout=DEFAULT_TIMEOUT
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                tree = HTMLParser(resp.text)

            items = tree.css("li.collection-card")
            for item in items:
                sid = item.attributes.get("data-sid") or item.attributes.get("sid")
                title_el = item.css_first("p.title")
                if not sid or not title_el:
                    continue
                collections.append(
                    UpCollection(
                        platform_collection_id=sid,
                        title=title_el.text(strip=True),
                        video_count=int(
                            item.attributes.get("data-count", "0") or 0
                        ),
                    )
                )

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "[html] fetch_collections mid=%s failed: %s", mid, exc
            )
            return []

        return collections

    async def validate_up_exists(self, mid: str) -> tuple[bool, str]:
        """HTML 校验：主页可访问且含 h1#h-name → 视为存在"""
        url = SPACE_URL.format(mid=mid)
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": UA}, timeout=10.0
            ) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code == 404:
                    return False, "UP主不存在"
                resp.raise_for_status()
                tree = HTMLParser(resp.text)
                name_el = tree.css_first("h1#h-name")
                if name_el and name_el.text(strip=True):
                    return True, name_el.text(strip=True)
                return False, "UP主账号可能已注销"
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[html] validate_up_exists mid=%s failed: %s", mid, exc)
            return False, f"校验失败：{exc}"

    @staticmethod
    def _parse_card(card, mid: str) -> Optional[UpVideo]:
        """从 bili-video-card 元素提取 UpVideo。
        bili-video-card 的 B 站当前结构：
          <bili-video-card data-aid data-bvid data-attribute="...">
            <a href="//www.bilibili.com/video/BVxxxx"></a>
            <p pubdate="2026-07-12 10:30">...</p>
            <h3 title="...">视频标题</h3>
          </bili-video-card>
        """
        try:
            bvid = card.attributes.get("data-bvid") or ""
            if not bvid:
                link_el = card.css_first("a")
                href = link_el.attributes.get("href", "") if link_el else ""
                m = re.search(r"/(BV[A-Za-z0-9]+)", href)
                if m:
                    bvid = m.group(1)
            if not bvid:
                return None

            title_el = card.css_first("h3")
            title = (title_el.text(strip=True) if title_el else "") or bvid

            pubdate_str = card.attributes.get("pubdate", "")
            pubdate = _parse_pubdate(pubdate_str)

            cover = card.css_first("img")
            cover_url = cover.attributes.get("src", "") if cover else ""

            return UpVideo(
                bvid=bvid,
                title=title,
                pubdate=pubdate,
                duration_sec=0,        # HTML DOM 通常不含 duration，留 0
                cover_url=cover_url,
            )
        except (AttributeError, KeyError, ValueError) as exc:
            logger.warning("[html] parse_card mid=%s failed: %s", mid, exc)
            return None


def _parse_pubdate(s: str) -> datetime:
    """解析 bili-video-card 的 pubdate 属性（'2026-07-12 10:30' 或时间戳）"""
    if not s:
        return datetime.now()
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # 尝试时间戳
    if s.isdigit():
        return datetime.fromtimestamp(int(s))
    return datetime.now()
```

#### 4.5.5 `collectors/bilibili_up/factory.py`

```python
"""UP主采集器工厂 + 策略注册"""
from __future__ import annotations

import logging

from src.aipulse.collectors.bilibili_up.base import BaseBilibiliUpCollector
from src.aipulse.collectors.bilibili_up.uapi import BilibiliUpUapiCollector
from src.aipulse.collectors.bilibili_up.html import BilibiliUpHtmlCollector
from src.aipulse.collectors.registry import (
    STRATEGY_REGISTRY,
    register_strategy,
)


logger = logging.getLogger(__name__)

# 触发装饰器副作用 —— 确保两个实现都注册到全局表
register_strategy("uapi")(BilibiliUpUapiCollector)  # 幂等
register_strategy("html")(BilibiliUpHtmlCollector)  # 幂等


class BilibiliUpCollectorFactory:
    """UP主采集器工厂。调用 BilibiliUpCollectorFactory.create(strategy) 拿实例。"""

    @staticmethod
    def create(strategy: str, **kwargs) -> BaseBilibiliUpCollector:
        """strategy: 'uapi' | 'html'。默认 uapi。"""
        key = strategy or "uapi"
        cls = STRATEGY_REGISTRY.get("bilibili_up", {}).get(key)
        if cls is None:
            raise ValueError(
                f"Unknown bilibili_up strategy: {strategy!r}; "
                f"available: {list(STRATEGY_REGISTRY.get('bilibili_up', {}).keys())}"
            )
        logger.debug("[factory] creating bilibili_up collector strategy=%s", key)
        return cls(**kwargs)

    @staticmethod
    def available_strategies() -> list[str]:
        return sorted(STRATEGY_REGISTRY.get("bilibili_up", {}).keys())
```

#### 4.5.6 `collectors/registry.py` 中 @register_strategy 装饰器（位置参考）

```python
# src/aipulse/collectors/registry.py
"""collector 策略注册表（platform × strategy → class）。"""
from __future__ import annotations

from typing import Any, Callable, Type

STRATEGY_REGISTRY: dict[str, dict[str, Type[Any]]] = {}


def register_strategy(
    strategy: str,
    platform: str = "bilibili_up",
) -> Callable[[Type[Any]], Type[Any]]:
    """把 collector class 注册到 STRATEGY_REGISTRY[platform][strategy]。

    用法：
        @register_strategy("uapi")
        class BilibiliUpUapiCollector(BaseBilibiliUpCollector): ...
    """

    def deco(cls: Type[Any]) -> Type[Any]:
        bucket = STRATEGY_REGISTRY.setdefault(platform, {})
        # 幂等：同 platform+strategy 重复注册视为 no-op（保留首次）
        bucket.setdefault(strategy, cls)
        cls.strategy = strategy  # 给类挂个 .strategy 便于调试
        return cls

    return deco
```

**失败处理约定**：所有 `fetch_*` 方法在遇到 httpx / 解析失败时，**捕获异常 + log warning + 返回空 list**，**不重试**。让 scheduler 跳过这个 UP 主，继续扫下一个。`validate_up_exists` 失败时返回 `(False, error_msg)`，由 API 层转 409 Conflict。

### 4.6 UP主存在性校验端点（Q18）

#### 4.6.1 API 端点

```
POST /api/followed-up/validate
Authorization: Bearer <token>
Body: { "mid": "1567748478" }
Response 200: { "exists": true,  "name": "跟李沐学AI", "uid": "1567748478" }
Response 409: { "exists": false, "error": "该 UP主不存在或账号已注销" }
Response 400: { "detail": "mid 必填" }
```

#### 4.6.2 实现 `web/api/followed_up.py`

```python
"""followed_up 相关 FastAPI 路由"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
from src.aipulse.core.auth import require_bearer  # 假设封装过 Bearer 校验
from src.aipulse.db.repositories.followed_up_repo import FollowedUpRepository


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/followed-up", tags=["followed-up"])


class ValidateRequest(BaseModel):
    mid: str = Field(..., min_length=1, max_length=64, description="B站 UP主 mid")


class ValidateResponse(BaseModel):
    exists: bool
    name: Optional[str] = None
    uid: str
    error: Optional[str] = None


@router.post(
    "/validate",
    response_model=ValidateResponse,
    summary="校验 UP主 存在性",
)
async def validate_up(
    body: ValidateRequest,
    _: None = Depends(require_bearer),
) -> ValidateResponse:
    """默认走 UAPI 策略（无 Cookie、可快速失败）。
    用户已登录时由上层先用 Obsidian SESSDATA 优调 HTML 策略，失败回退到 UAPI。"""
    # 默认 UAPI（User 加 UP主 前先在这里 warm-up 校验）
    collector = BilibiliUpCollectorFactory.create("uapi")
    exists, name = await collector.validate_up_exists(body.mid)
    if exists:
        return ValidateResponse(exists=True, name=name, uid=body.mid)

    # UPAPI 失败 → 退到 HTML 再试一次
    try:
        html_collector = BilibiliUpCollectorFactory.create("html")
        exists, name = await html_collector.validate_up_exists(body.mid)
        if exists:
            return ValidateResponse(exists=True, name=name, uid=body.mid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("html fallback validate mid=%s failed: %s", body.mid, exc)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"exists": False, "error": "该 UP主不存在或账号已注销"},
    )
```

#### 4.6.3 添加 UP主 时链路（Q18 + Q19）

```python
# web/api/followed_up.py （追加 —— POST /api/followed-up）
class CreateFollowedUpRequest(BaseModel):
    url: str = Field(..., description="主页 URL，必填")
    backfill_count: int = Field(default=50, ge=0, le=200)


@router.post("", response_model=FollowedUpOut, status_code=201)
async def create_followed_up(
    body: CreateFollowedUpRequest,
    repo: FollowedUpRepository = Depends(),
    _: None = Depends(require_bearer),
) -> FollowedUpOut:
    """1. 解析 mid → 2. 校验存在 → 3. 写 DB → 4. backfill 历史 → 5. 同步合集"""
    mid = _extract_mid_from_space_url(body.url)
    if not mid:
        raise HTTPException(
            status_code=400,
            detail={"error": "URL 解析失败，期望 https://space.bilibili.com/<mid>"},
        )

    # 2. 存在性校验（UAPI 优先 → HTML 兜底）
    collector = BilibiliUpCollectorFactory.create("uapi")
    exists, name = await collector.validate_up_exists(mid)
    if not exists:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"error": "该 UP主不存在或账号已注销", "mid": mid},
        )

    # 3. 写 DB（UNIQUE 约束防止重复）
    entity = await repo.create(
        platform="bilibili",
        uid=mid,
        display_name=name,
        profile_url=f"https://space.bilibili.com/{mid}",
        collector_strategy="uapi",
        fetch_interval_minutes=30,
        is_active=True,
        config={"space_url": body.url, "auto_backfill_count": 50},
    )

    # 4. backfill 历史视频（异步队列写 hotspots，decision_status=pending, is_backfill=true）
    if body.backfill_count > 0:
        from src.aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
        from src.aipulse.summarizers.up_backfill import backfill_followed_up

        asyncio.create_task(
            backfill_followed_up(
                followed_up_id=entity.id,
                collector=BilibiliUpCollectorFactory.create(entity.collector_strategy),
                count=body.backfill_count,
            )
        )

    # 5. 同步合集（异步）
    asyncio.create_task(_sync_collections(entity.id, mid))

    return FollowedUpOut.from_entity(entity)


def _extract_mid_from_space_url(url: str) -> Optional[str]:
    """从 https://space.bilibili.com/<mid>?... 提取 mid。"""
    m = re.search(r"space\.bilibili\.com/(\d+)", url)
    return m.group(1) if m else None


async def _sync_collections(followed_up_id: str, mid: str) -> None:
    collector = BilibiliUpCollectorFactory.create("html")  # 合集只有 HTML 拿得到
    cols = await collector.fetch_collections(mid)
    # 写 followed_up_collections 表（实现省略）
```

### 4.7 字幕获取完整代码（Q10）

文件位置：`src/aipulse/summarizers/agent/tools/transcript.py`。复用 `~/.claude/skills/obsidian-clip-summary/scripts/bilibili_extract.py` 思路：**三步走 + ASR 兜底**。

```python
"""字幕获取工具 —— AI 字幕 → 校验 → ASR 兜底。供 Agent `fetch_transcript_tool` 调用。"""
from __future__ import annotations

import logging
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from langchain.tools import tool

from src.aipulse.core.config import get_settings
from src.aipulse.core.exceptions import TranscriptUnavailableError


logger = logging.getLogger(__name__)

PLAYER_API = "https://api.bilibili.com/x/player/v2"
MEDIA_EXT_DB_CANDIDATES = [
    Path.home() / "Library/Application Support/obsidian/media-extended.sqlite",
    Path.home() / ".config/obsidian/media-extended.sqlite",
    Path.home() / ".local/share/obsidian/media-extended.sqlite",
]


# ---------- 数据模型 ----------
@dataclass
class SubtitleSegment:
    from_sec: float
    to_sec: float
    text: str


@dataclass
class TranscriptResult:
    text: str
    source: str   # "official" | "cookie-official" | "asr"
    duration_sec: float
    confidence: float = 1.0  # ASR 时 < 1.0


# ---------- 异常 ----------
class SubtitleValidationError(Exception):
    """字幕时长或相关性校验失败"""


# ---------- 主流程 ----------
async def fetch_transcript(
    bvid: str,
    cid: Optional[int] = None,
    title: str = "",
) -> TranscriptResult:
    """三步走：官方字幕（Cookie 优先） → ASR → 失败抛异常。

    Args:
        bvid: B站视频 id（必传）
        cid: 分 P id（必传，否则内部会先拿一次）
        title: 用于相关性校验
    Returns:
        TranscriptResult
    Raises:
        TranscriptUnavailableError: 字幕 + ASR 都不可用
    """
    settings = get_settings()

    # ① 优先：带 Cookie 调官方字幕
    cookies = _load_sessdata_from_obsidian()
    if cookies:
        try:
            result = await _fetch_official_subtitle(bvid, cid, cookies)
            if _validate_subtitle(result, title):
                return result
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[transcript] cookie-official failed bvid=%s: %s", bvid, exc)

    # ② 退而求其次：无 Cookie 官方字幕
    try:
        result = await _fetch_official_subtitle(bvid, cid, cookies=None)
        if _validate_subtitle(result, title):
            return result
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("[transcript] official failed bvid=%s: %s", bvid, exc)

    # ③ ASR 兜底：调本地 whisper
    try:
        asr_result = await _transcribe_with_whisper(bvid, settings.whisper_model)
        return asr_result
    except Exception as exc:  # noqa: BLE001
        logger.error("[transcript] asr failed bvid=%s: %s", bvid, exc)
        raise TranscriptUnavailableError(
            f"bvid={bvid} 字幕不可用且 ASR 失败：{exc}"
        ) from exc


# ---------- Step 1：官方字幕 ----------
async def _fetch_official_subtitle(
    bvid: str,
    cid: Optional[int],
    cookies: Optional[dict[str, str]],
) -> TranscriptResult:
    """调 https://api.bilibili.com/x/player/v2?bvid=...&cid=...
    返回字幕列表中第一条中文轨；bvid 与 cid 必传其一。"""
    if cid is None:
        cid = await _resolve_cid(bvid)

    params = {"bvid": bvid, "cid": str(cid)}
    headers = {"User-Agent": "Mozilla/5.0"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(PLAYER_API, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    if payload.get("code") != 0:
        raise ValueError(f"player v2 code={payload.get('code')} msg={payload.get('message')}")

    subtitles = (payload.get("data") or {}).get("subtitle") or {}
    sub_list = subtitles.get("subtitles") or []
    if not sub_list:
        raise ValueError("no subtitles in response")

    # 选中文轨；否则取第一条
    chosen = next(
        (s for s in sub_list if "zh" in (s.get("lan") or "").lower()),
        sub_list[0],
    )
    sub_url = chosen.get("sub_url")
    if not sub_url:
        raise ValueError("no sub_url on chosen subtitle")

    # sub_url 是 B 站相对路径 => 拼协议头
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(sub_url)
        resp.raise_for_status()
        body = resp.json()

    segments = _parse_bilibili_subtitle_json(body)
    full_text = "\n".join(seg.text for seg in segments)
    duration = sum(seg.to_sec - seg.from_sec for seg in segments)

    source = "cookie-official" if cookies else "official"
    return TranscriptResult(
        text=full_text,
        source=source,
        duration_sec=duration,
        confidence=1.0,
    )


async def _resolve_cid(bvid: str) -> int:
    """从 https://api.bilibili.com/x/web-interface/view?bvid=... 拿 cid。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
        )
        resp.raise_for_status()
        payload = resp.json()
    cid = (payload.get("data") or {}).get("cid")
    if not cid:
        raise ValueError(f"cannot resolve cid for bvid={bvid}")
    return int(cid)


def _parse_bilibili_subtitle_json(body: list[dict]) -> list[SubtitleSegment]:
    """B 站字幕 JSON: [{"from":12.3,"to":15.0,"content":"..."}, ...]"""
    segments: list[SubtitleSegment] = []
    for item in body:
        try:
            segments.append(
                SubtitleSegment(
                    from_sec=float(item["from"]),
                    to_sec=float(item["to"]),
                    text=str(item.get("content", "")).strip(),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return segments


# ---------- Step 2：从 Obsidian Media Extended 读 SESSDATA ----------
def _load_sessdata_from_obsidian() -> Optional[dict[str, str]]:
    """读 Obsidian Media Extended SQLite 拿 SESSDATA cookie。

    user 已登录时返回 {"SESSDATA": "xxxx"}；未登录返回 None。
    不要硬编码 cookie，必须经此函数读取。
    """
    for db_path in MEDIA_EXT_DB_CANDIDATES:
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            # Media Extended 把 bilibili 域的 cookies 存在 cookie 表，domain='.bilibili.com'
            cur.execute(
                "SELECT name, value FROM cookies WHERE domain LIKE '%bilibili.com%'"
            )
            rows = cur.fetchall()
            conn.close()
            return {name: value for name, value in rows if name}
        except (sqlite3.Error, OSError) as exc:
            logger.warning("[transcript] read media-extended db failed: %s", exc)
            continue
    return None


# ---------- Step 3：字幕校验（复用 obsidian-clip-summary 思路） ----------
def _validate_subtitle(result: TranscriptResult, video_title: str) -> bool:
    """两道校验：
      1. 字数校验：字幕总字符数 ≥ 50（残缺字幕过滤）
      2. 相关性校验：字幕前 N 字符与视频标题关键词有交集（字幕错挂过滤）
    失败抛 SubtitleValidationError；调用方可决定 fallback 到 ASR。
    """
    # 1. 字数校验
    if len(result.text) < 50:
        raise SubtitleValidationError(
            f"字幕过短（{len(result.text)} 字符），疑似残缺"
        )

    # 2. 相关性校验：取字幕前 200 字符，看是否与标题关键词重叠
    title_keywords = set(_extract_keywords(video_title))
    text_keywords = set(_extract_keywords(result.text[:200]))
    if not (title_keywords & text_keywords):
        raise SubtitleValidationError(
            "字幕与标题相关性低，疑似字幕错挂"
        )

    return True


def _extract_keywords(text: str, top_k: int = 30) -> list[str]:
    """极简关键词：去停用词 + 2+ 字符的中文 / 3+ 英文词。"""
    import re
    if not text:
        return []
    words = re.findall(r"[一-龥]{2,}", text)
    words += re.findall(r"[A-Za-z]{3,}", text)
    return [w.lower() for w in words[:top_k]]


# ---------- ASR 兜底 ----------
async def _transcribe_with_whisper(
    bvid: str,
    whisper_model: str,
) -> TranscriptResult:
    """下载音频 → 调本地 whisper CLI（whisper.cpp / openai-whisper）转写。

    实际项目里音频下载走 yt-dlp；这里给出骨架：
      1. yt-dlp 拿 m4a
      2. whisper 转 srt
      3. 解析 srt → TranscriptResult
    """
    import tempfile

    audio_path = Path(tempfile.gettempdir()) / f"{bvid}.m4a"
    try:
        # 1. 下载音频（yt-dlp CLI，10 分钟超时）
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "m4a",
             "-o", str(audio_path), f"https://www.bilibili.com/video/{bvid}"],
            check=True, timeout=600, capture_output=True,
        )
        # 2. 转写
        out_dir = audio_path.parent
        subprocess.run(
            ["whisper", str(audio_path),
             "--model", whisper_model,
             "--language", "zh",
             "--output_format", "srt",
             "--output_dir", str(out_dir)],
            check=True, timeout=1800, capture_output=True,
        )
        # 3. 解析 srt
        srt_path = out_dir / f"{audio_path.stem}.srt"
        text, duration = _parse_srt(srt_path)
        return TranscriptResult(
            text=text, source="asr", duration_sec=duration, confidence=0.85
        )
    finally:
        if audio_path.exists():
            audio_path.unlink(missing_ok=True)


def _parse_srt(srt_path: Path) -> tuple[str, float]:
    """极简 srt 解析：拼接 text 字段，总时长 = 最后一段 end"""
    import re
    if not srt_path.exists():
        return "", 0.0
    content = srt_path.read_text(encoding="utf-8")
    text_lines = []
    max_end = 0.0
    for block in content.split("\n\n"):
        match = re.search(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            block,
        )
        if not match:
            continue
        end_ts = match.group(2)
        h, m, s = end_ts.split(":")
        s, ms = s.split(",")
        max_end = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        lines = [
            ln.strip()
            for ln in block.splitlines()[2:]
            if ln.strip() and "-->" not in ln
        ]
        text_lines.extend(lines)
    return "\n".join(text_lines), max_end


# ---------- Agent Tool 包装 ----------
@tool
def fetch_transcript_tool(bvid: str) -> str:
    """拉取 B 站视频字幕 + ASR 兜底，返回纯文本字幕。

    Args:
        bvid: B 站视频 BV 号，例如 BV1xx411c7mD
    Returns:
        字幕文本
    """
    import asyncio
    # 假定此函数被 LangChain Agent 在异步上下文中调用
    result = asyncio.run(fetch_transcript(bvid=bvid))
    return result.text
```

### 4.8 Scheduler 任务代码（Q15）

文件位置：`src/aipulse/scheduler/jobs/followed_up_scan.py`。

```python
"""UP主扫描任务 —— 单个 + 批量入口。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update

from src.aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
from src.aipulse.db.models import FollowedUp, Hotspot
from src.aipulse.db.session import get_session
from src.aipulse.summarizers.up_backfill import upsert_hotspot_from_video


logger = logging.getLogger(__name__)


# ---------- 内部辅助 ----------
async def _is_due(fu: FollowedUp, now: datetime) -> bool:
    """判断 UP主是否到扫描时机"""
    if not fu.is_active or fu.deleted_at is not None:
        return False
    if fu.last_checked_at is None:
        return True
    next_due = fu.last_checked_at + timedelta(minutes=fu.fetch_interval_minutes)
    return now >= next_due


def _update_after_scan(fu_id: str, *, ok: bool, error: Optional[str] = None) -> None:
    """更新 last_checked_at / last_error / health"""
    now = datetime.now(tz=timezone.utc)
    with get_session() as s:
        stmt = (
            update(FollowedUp)
            .where(FollowedUp.id == fu_id)
            .values(
                last_checked_at=now,
                last_error=error,
                failed_at=now if error else None,
                health="healthy" if ok and not error else "warning" if ok else "error",
                updated_at=now,
            )
        )
        s.execute(stmt)
        s.commit()


async def _scan_one(fu: FollowedUp) -> int:
    """扫单个 UP主，返回新增视频数。失败返回 0 且记日志（不抛）。"""
    try:
        collector = BilibiliUpCollectorFactory.create(
            fu.collector_strategy or "uapi"
        )
        videos = await collector.fetch_videos(
            mid=fu.uid,
            count=50,
            last_cursor_id=fu.last_cursor_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[scan] mid=%s fetch failed: %s", fu.uid, exc)
        _update_after_scan(fu.id, ok=False, error=str(exc)[:500])
        return 0

    if not videos:
        _update_after_scan(fu.id, ok=True)
        return 0

    # 写 hotspots + 更新 last_cursor_id
    new_count = 0
    latest_bvid: Optional[str] = None
    for v in videos:
        new_count += await upsert_hotspot_from_video(fu, v)
        if latest_bvid is None:
            latest_bvid = v.bvid

    with get_session() as s:
        s.execute(
            update(FollowedUp)
            .where(FollowedUp.id == fu.id)
            .values(last_cursor_id=latest_bvid, updated_at=datetime.now(tz=timezone.utc))
        )
        s.commit()

    _update_after_scan(fu.id, ok=True)
    logger.info("[scan] mid=%s videos=%d new=%d", fu.uid, len(videos), new_count)
    return new_count


# ---------- 公开入口 ----------
async def scan_followed_up_by_id(followed_up_id: str) -> int:
    """扫单个 UP主。供 `POST /api/followed-up/{id}/sync` 调用。"""
    with get_session() as s:
        fu = s.execute(
            select(FollowedUp).where(FollowedUp.id == followed_up_id)
        ).scalar_one_or_none()
    if fu is None or fu.deleted_at is not None:
        logger.warning("[scan] followed_up %s not found or deleted", followed_up_id)
        return 0
    return await _scan_one(fu)


async def scan_all_followed_up() -> int:
    """扫所有 enabled 且到期的 UP主。供 APScheduler 高频触发。"""
    now = datetime.now(tz=timezone.utc)
    total_new = 0
    with get_session() as s:
        stmt = select(FollowedUp).where(
            FollowedUp.is_active.is_(True),
            FollowedUp.deleted_at.is_(None),
        )
        candidates = s.execute(stmt).scalars().all()

    # 串行扫（Q5 锁定：concurrency=1），避免触发 B 站风控
    for fu in candidates:
        if not await _is_due(fu, now):
            continue
        try:
            new_count = await _scan_one(fu)
            total_new += new_count
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scan-all] mid=%s failed: %s", fu.uid, exc)
            continue

    if total_new > 0:
        logger.info("[scan-all] new videos=%d across all ups", total_new)
    return total_new


# ---------- APScheduler 注册 ----------
def register_followed_up_jobs(scheduler) -> None:
    """在 scheduler/client.py 的 lifespan 里调用，注册 1 分钟高频扫描任务。"""
    scheduler.add_job(
        scan_all_followed_up,
        trigger="interval",
        minutes=1,                # 高频触发，内部按 fetch_interval_minutes 判断
        id="followed_up_scan_all",
        name="Scan all enabled followed UP主",
        replace_existing=True,
        coalesce=True,            # 把堆积的 miss 折叠为一次
        max_instances=1,          # 与 Q5 锁定一致：concurrency=1
        misfire_grace_time=300,
    )
    logger.info("[scheduler] registered followed_up_scan_all (interval=1m)")
```

### 4.9 测试用例清单

`tests/` 下覆盖 §4 各组件，至少 **22 条**：

| # | 测试名 | 覆盖范围 | 类型 |
|---|---|---|---|
| 1 | `test_bilibili_up_html_collector_parses_video_cards` | `BilibiliUpHtmlCollector._parse_card` 正确解析 `bili-video-card` DOM（含 `pubdate` 属性、`data-bvid`、`<h3>` 标题） | unit |
| 2 | `test_bilibili_up_uapi_collector_handles_rate_limit` | UAPI 线路遇到 `code != 0` / 429 时**不抛异常**，返回空 list 且 log warning | unit（mock httpx） |
| 3 | `test_bilibili_up_uapi_collector_incremental_cursor` | 传入 `last_cursor_id=xxx` 时 UAPI 在命中 bvid 处停止翻页 | unit |
| 4 | `test_bilibili_up_factory_creates_correct_strategy` | `BilibiliUpCollectorFactory.create("uapi"/"html")` 返回正确 class；`available_strategies()` 返回 `["html", "uapi"]` | unit |
| 5 | `test_bilibili_up_factory_rejects_unknown_strategy` | `create("xxx")` 抛 `ValueError` | unit |
| 6 | `test_register_strategy_decorator_idempotent` | 重复 `@register_strategy("uapi")` 装饰同一 class 不报错，注册表保持首次 | unit |
| 7 | `test_up_exists_validation_returns_404_for_invalid_mid` | `POST /api/followed-up/validate mid="99999999"` → UAPI 校验失败 → HTML 兜底 → **409 Conflict** `"该 UP主不存在或账号已注销"` | integration（FastAPI TestClient + mock httpx） |
| 8 | `test_up_exists_validation_returns_name_for_valid_mid` | 已知 mid → 200 + `{exists:true, name:"...", uid:"..."}` | integration |
| 9 | `test_create_followed_up_backfills_50_videos` | `POST /api/followed-up backfill_count=50` → 50 条 `is_backfill=true, decision_status=pending` 写入 hotspots | integration |
| 10 | `test_create_followed_up_rejects_duplicate_uid` | 同 `(platform, uid)` 二次添加 → 409 Conflict（UNIQUE 约束） | integration |
| 11 | `test_transcript_extraction_falls_back_to_asr` | 官方字幕不可用 + 无 Cookie → 走 `_transcribe_with_whisper` → 返回 `source="asr", confidence=0.85` | unit（mock subprocess） |
| 12 | `test_transcript_extraction_uses_obsidian_cookie` | 已登录状态（mock SQLite 有 SESSDATA）→ 字幕 `source="cookie-official"` | unit（临时 SQLite） |
| 13 | `test_subtitle_validation_by_duration` | 字幕长度 < 50 字符 → `SubtitleValidationError("字幕过短...")` | unit |
| 14 | `test_subtitle_relevance_verification` | 字幕前 200 字与标题无关键词重叠 → `SubtitleValidationError("字幕与标题相关性低")` | unit |
| 15 | `test_subtitle_official_api_parses_segments` | mock B 站 JSON → `_parse_bilibili_subtitle_json` 正确产出 `SubtitleSegment` 列表 | unit |
| 16 | `test_scheduler_skips_disabled_followed_up` | `is_active=false` 的 UP主 被 `scan_all_followed_up()` 跳过 | unit（DB fixture） |
| 17 | `test_scheduler_skips_not_yet_due` | `fetch_interval_minutes=30` 且 `last_checked_at=now-10min` → 跳过；`last_checked_at=now-31min` → 扫描 | unit |
| 18 | `test_scheduler_respects_fetch_interval_minutes` | 混合 `interval=5/30/120` 的 UP主 仅各自到期时触发 | unit |
| 19 | `test_scheduler_updates_health_status_on_failure` | 单个 UP主 fetch 抛异常 → `health="error", last_error=<msg>, failed_at=<ts>` | unit |
| 20 | `test_scheduler_registers_with_1min_interval` | `register_followed_up_jobs` 后 `scheduler.get_job("followed_up_scan_all")` 存在且 trigger interval=60s | unit |
| 21 | `test_collect_videos_returns_empty_on_html_failure` | HTML 线路 fetch 失败 → 返回 `[]` 不抛异常 | unit |
| 22 | `test_backfill_threshold_caps_at_50` | `backfill_count=200` → 实际写入 50 条 + UI 显示「剩余 N 条可在详情页加载更多」 | integration |

> 实现约定：所有 `fetch_*` / `collect` 测试用 `respx` / `pytest-httpx` mock 外部 HTTP；DB 测试用 SQLite in-memory；Scheduler 测试用 `AsyncMock` + 时钟 fake。

### 4.10 API Endpoint 清单（B站采集相关）

所有 endpoint 走全局 `Authorization: Bearer <token>`；未配置 `aipulse_api_token` 时跳过校验（本地开发友好）。

| Method | Path | 用途 | 鉴权 | 关键参数 / 返回 |
|---|---|---|---|---|
| `GET` | `/api/followed-up` | 列出所有 UP主（分页 + status/health/platform 过滤） | Bearer | Query: `page, page_size, platform, is_active, health`；返回 `{items:[...], total, page, page_size}` |
| `POST` | `/api/followed-up` | 添加 UP主（URL 解析 + 存在性校验 + backfill + 同步合集） | Bearer | Body: `{url, backfill_count=50}` → 201 + UP主详情；409 mid 不存在；409 重复 |
| `GET` | `/api/followed-up/{id}` | UP主 详情（含 `config` + 状态徽章所需字段） | Bearer | Path: `id`；404 不存在 |
| `PATCH` | `/api/followed-up/{id}` | 更新 UP主（启停 / 排序 / 备注 / 策略切换 / 间隔） | Bearer | Body 部分字段；200/404 |
| `DELETE` | `/api/followed-up/{id}` | 软删除 UP主（`deleted_at` 置位） | Bearer | 204；二次删除幂等返回 204 |
| `POST` | `/api/followed-up/{id}/sync` | 立即同步（单 UP主扫描） | Bearer | 15s 超时，**超时返回 202 Accepted** + job id，前端 SSE 拉进度 |
| `GET` | `/api/followed-up/{id}/videos` | UP主 视频列表（分页 + `collection_id` 过滤 + hotspot 状态关联） | Bearer | Query: `page, page_size, collection_id` |
| `GET` | `/api/followed-up/{id}/collections` | UP主 合集列表（accordion 折叠用） | Bearer | 返回 `followed_up_collections[]` |
| `POST` | `/api/followed-up/validate` | 校验 UP主 存在性（UAPI 优先 → HTML 兜底） | Bearer | Body: `{mid}`；200 或 409 |
| `POST` | `/api/followed-up/{id}/load-more-history` | 详情页「加载更多历史」每次 +50（Q19） | Bearer | Body: `{offset: 50}`；分页写入 hotspots（backfill 标记） |
| `GET` | `/api/followed-up/{id}/health` | 健康状态详情（`last_checked_at` / `last_error` / `failed_at`） | Bearer | 用于面板渲染状态徽章 |

**关键约定**：
- 所有 POST/PATCH 的鉴权失败 → 401（Bearer 缺失或错误）
- 软删除的 UP主 视为「不存在」返回 404
- `POST /sync` 的 15s 超时来源于 B 站 HTML 抓取最长等待时间；超过时限改 202 + 后台继续，前端轮询或 SSE
- list 接口支持 `?platform=bilibili&health=error` 多维过滤，便于"失败 UP主" 面板
- `validate` 端点同时被添加表单和 PATCH 表单复用（避免重复实现）

**前端路由（vue-router）**：
- `/dashboard?tab=follow-list` → 关注列表 Panel
- `/dashboard?tab=follow-records` → 处理记录 Panel（hotspots `decision_status` 视图）
- `/dashboard?tab=follow-upcoming` → 即将学习 Panel（learning_events）
- `/dashboard?tab=follow-failed` → 失败 Panel
- `/dashboard/followed-up/:id` → UP主 详情页（合集 accordion + 视频 list）

---

