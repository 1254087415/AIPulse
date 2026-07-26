"""UP主扫描任务 —— 单个 + 批量入口。

Phase 2 v0.3 spec §4.4 + §4.8：
- scan_followed_up_by_id(followed_up_id) → int  # 给 /api/followed-up/{id}/sync 用
- scan_all_followed_up() → int  # 给 APScheduler 高频定时用
- register_followed_up_jobs(scheduler) → None

并发：Q5 锁定串行扫描（concurrency=1），避免 B 站风控。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import select, update

from aipulse.collectors.bilibili_up.base import UpVideo
from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
from aipulse.hotspot.models import Hotspot
from aipulse.models.followed_up import FollowedUp
from aipulse.store.database import get_session_maker


logger = logging.getLogger(__name__)


# ---------- 内部辅助 ----------
async def _is_due(fu: FollowedUp, now: datetime) -> bool:
    """判断 UP主是否到扫描时机。"""
    if not fu.is_active or fu.deleted_at is not None:
        return False
    if fu.last_checked_at is None:
        return True
    next_due = fu.last_checked_at + timedelta(minutes=fu.fetch_interval_minutes)
    return now >= next_due


def _has_running_loop() -> bool:
    """Detect whether we're inside an event loop (sync vs async caller)."""
    try:
        import asyncio

        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


async def upsert_hotspot_from_video(fu: FollowedUp, v: UpVideo) -> int:
    """根据 UP主 + 视频 upsert 一个 Hotspot，返回 1 (新增) 或 0 (已存在)。

    按 (followed_up_id, content_id) 去重；新行 decision_status='pending'。
    异步 — caller 在 event loop 内 await 即可。
    """
    canonical_url = f"https://www.bilibili.com/video/{v.bvid}"

    async with get_session_maker()() as s:
        stmt = select(Hotspot).where(
            Hotspot.followed_up_id == fu.id,
            Hotspot.content_id == v.bvid,
        )
        existing = (await s.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return 0
        s.add(
            Hotspot(
                title=v.title or v.bvid,
                url=canonical_url,
                canonical_url=canonical_url,
                summary=None,
                source_id="000000000000",  # 占位：UP主路径不走 Source 表
                source_type="bilibili_up",
                published_at=v.pubdate,
                fetched_at=datetime.now(UTC),
                raw_metadata={
                    "bvid": v.bvid,
                    "duration_sec": v.duration_sec,
                    "description": v.description,
                    "cover_url": v.cover_url,
                    "play_count": v.play_count,
                    "strategy": fu.collector_strategy,
                    "mid": fu.uid,
                },
                followed_up_id=fu.id,
                followed_up_collection_id=None,
                content_id=v.bvid,
                platform_user_id=fu.uid,
                decision_status="pending",
                is_backfill=v.is_backfill,
                importance="medium",
            )
        )
        await s.commit()
        return 1


# ---------- 公开入口 ----------
async def scan_followed_up_by_id(followed_up_id: str) -> int:
    """扫单个 UP主。供 POST /api/followed-up/{id}/sync 调用。

    返回新增 hotspot 数；失败返回 0 且记日志（不抛）。
    """
    async with get_session_maker()() as s:
        fu = (
            await s.execute(select(FollowedUp).where(FollowedUp.id == followed_up_id))
        ).scalar_one_or_none()
    if fu is None or fu.deleted_at is not None:
        logger.warning("[scan] followed_up %s not found or deleted", followed_up_id)
        return 0
    return await _scan_one(fu)


async def scan_all_followed_up() -> int:
    """扫所有 enabled 且到期的 UP主。供 APScheduler 高频触发。"""
    now = datetime.now(UTC)
    total_new = 0
    async with get_session_maker()() as s:
        stmt = select(FollowedUp).where(
            FollowedUp.is_active.is_(True),
            FollowedUp.deleted_at.is_(None),
        )
        candidates = (await s.execute(stmt)).scalars().all()

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


# ---------- 单 UP主扫描 ----------
async def _scan_one(fu: FollowedUp) -> int:
    """扫单个 UP主，返回新增 hotspot 数。失败返回 0 且记日志（不抛）。"""
    try:
        collector = BilibiliUpCollectorFactory.create(fu.collector_strategy or "uapi")
        try:
            videos = await collector.fetch_videos(
                mid=fu.uid,
                count=50,
                last_cursor_id=fu.last_cursor_id,
            )
        finally:
            await collector.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[scan] mid=%s fetch failed: %s", fu.uid, exc)
        async with get_session_maker()() as s:
            await s.execute(
                update(FollowedUp)
                .where(FollowedUp.id == fu.id)
                .values(
                    last_checked_at=datetime.now(UTC),
                    last_error=str(exc)[:500],
                    failed_at=datetime.now(UTC),
                    health="error",
                    updated_at=datetime.now(UTC),
                )
            )
            await s.commit()
        return 0

    if not videos:
        async with get_session_maker()() as s:
            await s.execute(
                update(FollowedUp)
                .where(FollowedUp.id == fu.id)
                .values(
                    last_checked_at=datetime.now(UTC),
                    last_error=None,
                    failed_at=None,
                    health="healthy",
                    updated_at=datetime.now(UTC),
                )
            )
            await s.commit()
        return 0

    new_count = 0
    latest_bvid: Optional[str] = None
    for v in videos:
        try:
            new_count += await upsert_hotspot_from_video(fu, v)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scan] upsert failed bvid=%s: %s", v.bvid, exc)
            continue
        if latest_bvid is None:
            latest_bvid = v.bvid

    now = datetime.now(UTC)
    async with get_session_maker()() as s:
        await s.execute(
            update(FollowedUp)
            .where(FollowedUp.id == fu.id)
            .values(
                last_cursor_id=latest_bvid or fu.last_cursor_id,
                last_checked_at=now,
                last_error=None,
                failed_at=None,
                health="healthy",
                updated_at=now,
            )
        )
        await s.commit()

    logger.info("[scan] mid=%s videos=%d new=%d", fu.uid, len(videos), new_count)
    return new_count


# ---------- APScheduler 注册 ----------
def register_followed_up_jobs(scheduler) -> None:
    """在 scheduler/client.py 的 lifespan 里调用，注册 1 分钟高频扫描任务。"""
    scheduler.add_job(
        scan_all_followed_up,
        trigger="interval",
        minutes=1,  # 高频触发，内部按 fetch_interval_minutes 判断
        id="followed_up_scan_all",
        name="Scan all enabled followed UP主",
        replace_existing=True,
        coalesce=True,  # 把堆积的 miss 折叠为一次
        max_instances=1,  # 与 Q5 锁定一致：concurrency=1
        misfire_grace_time=300,
    )
    logger.info("[scheduler] registered followed_up_scan_all (interval=1m)")