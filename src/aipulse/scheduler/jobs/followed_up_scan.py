"""UP主扫描任务 —— 单个 + 批量入口。

Phase 2 v0.3 spec §4.4 + §4.8：
- scan_followed_up_by_id(followed_up_id) → int  # 给 /api/followed-up/{id}/sync 用
- scan_all_followed_up() → int  # 给 APScheduler 高频定时用
- register_followed_up_jobs(scheduler) → None

并发：Q5 锁定串行扫描（concurrency=1），避免 B 站风控。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import select, update

from aipulse.collectors.bilibili_up.base import UpVideo
from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory
from aipulse.core.datetime_utils import to_utc
from aipulse.hotspot.models import Hotspot
from aipulse.models.followed_up import FollowedUp
from aipulse.store.database import get_session_maker


logger = logging.getLogger(__name__)


# ---------- 内部辅助 ----------
async def _is_due(fu: FollowedUp, now: datetime) -> bool:
    """判断 UP主是否到扫描时机。

    v0.3 时区修复：SQLite 存 DATETIME 时丢 tzinfo，DB 读出的
    last_checked_at 可能是 naive（存量）也可能是 aware（修复后）。
    调用方传的 now 统一是 aware UTC。直接比较 naive vs aware 会抛
    ``TypeError``，所以 ``to_utc`` 在比较前做归一：naive 视为 UTC。
    """
    if not fu.is_active or fu.deleted_at is not None:
        return False
    if fu.last_checked_at is None:
        return True
    last_checked_utc = to_utc(fu.last_checked_at)
    now_utc = to_utc(now)
    if last_checked_utc is None or now_utc is None:
        return False
    next_due = last_checked_utc + timedelta(minutes=fu.fetch_interval_minutes)
    return now_utc >= next_due


def _has_running_loop() -> bool:
    """Detect whether we're inside an event loop (sync vs async caller)."""
    try:
        import asyncio

        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


async def upsert_hotspot_from_video(fu: FollowedUp, v: UpVideo) -> Hotspot | None:
    """根据 UP主 + 视频 upsert 一个 Hotspot，返回新插入的 Hotspot 或 None（已存在）。

    按 (followed_up_id, content_id) 去重；新行 decision_status='pending'。
    异步 — caller 在 event loop 内 await 即可。

    v0.3 round 6 变更：返回类型从 ``int`` 改为 ``Hotspot | None``，让 caller
    能拿到新 hotspot 的 id（用于后续 enqueue summary job）。
    """
    canonical_url = f"https://www.bilibili.com/video/{v.bvid}"

    async with get_session_maker()() as s:
        stmt = select(Hotspot).where(
            Hotspot.followed_up_id == fu.id,
            Hotspot.content_id == v.bvid,
        )
        existing = (await s.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return None
        hotspot = Hotspot(
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
        s.add(hotspot)
        await s.commit()
        await s.refresh(hotspot)
        return hotspot


async def enqueue_summaries_for_hotspots(
    fu: FollowedUp,
    new_hotspots: list[Hotspot],
) -> list[str]:
    """为新插入的 hotspot enqueue summary job，返回 enqueue 成功得到的 job_id 列表。

    v0.3 round 6 集成 (spec 03 + spec 06 三向接通)：
    - POST /api/followed-up/<id>/sync 现在也会触发 agent 摘要 + 三向归档
    - 复用现有 ``SummaryJobQueue.enqueue``（自带 running/queued 幂等性）
    - 任何 enqueue 异常都 log + 跳过单条，不让整次 sync fail

    约束 (feedback_status-must-not-mask-failure)：enqueue 阶段不跑 pipeline
    只排队；真正 status 判定由 worker + finalize 完成，这里只关心 job_id
    是否被持久化到 summary_jobs 表（lifecycle=queued）。
    """
    if not new_hotspots:
        return []

    from aipulse.repositories.summary_job_repo import (
        SqlAlchemySummaryJobRepository,
    )
    from aipulse.summarizers.queue import JobSubmission, QueueFullError, get_queue

    enqueued_ids: list[str] = []
    queue = get_queue()
    try:
        await queue.start()
    except Exception:  # noqa: BLE001
        # worker 已在跑（lifespan / 其他测试启动过），start 是幂等的
        logger.debug("[scan] summary queue already started", exc_info=True)

    for hotspot in new_hotspots:
        try:
            async with get_session_maker()() as session:
                repo = SqlAlchemySummaryJobRepository(session)
                # 关键时序: 先 create + commit, 再 enqueue_submission 纯投递。
                # 旧版 queue.enqueue 内部还会 repo.create(), 紧接着 put_nowait
                # 触发 worker 调度, 但 session.commit() 还在后面 —— worker
                # 立即 mark_started 时该 row 还在 session 里未 commit, 跨
                # connection 不可见。与 summary.py enqueue_summary_route 同款
                # 修复模式 (verifier R3 已批准)。
                record = await repo.create(
                    video_id=hotspot.content_id,
                    title=hotspot.title or hotspot.content_id,
                    up_name=fu.display_name,
                )
                await session.commit()
                submission = JobSubmission(
                    job_id=record.id,
                    video_id=hotspot.content_id,
                    title=hotspot.title or hotspot.content_id,
                    up_name=fu.display_name,
                )
                await queue.enqueue_submission(submission)
                if hotspot.id is not None:
                    await repo.annotate(
                        submission.job_id,
                        hotspot_id=hotspot.id,
                        title=hotspot.title,
                        up_name=fu.display_name,
                    )
                    await session.commit()
                enqueued_ids.append(submission.job_id)
        except QueueFullError as exc:  # noqa: PERF203
            logger.warning(
                "[scan] summary queue full, skipping bvid=%s (%d/%d)",
                hotspot.content_id,
                exc.size,
                exc.max_size,
            )
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[scan] enqueue summary failed bvid=%s: %s",
                hotspot.content_id,
                exc,
            )
            continue

    if enqueued_ids:
        logger.info(
            "[scan] mid=%s enqueued %d summary job(s) for new hotspots",
            fu.uid,
            len(enqueued_ids),
        )
    return enqueued_ids


# ---------- 公开入口 ----------
@dataclass(frozen=True)
class ScanOutcome:
    """v0.3 round 6: sync 一次扫描的聚合结果。

    - ``new_hotspots`` — 新插入的 hotspot 数
    - ``enqueued_summaries`` — 为新 hotspot 入队的 summary job 数
    - ``new_bvids`` — 新插入的 bvid 列表（便于 caller 给前端展示）
    """

    new_hotspots: int = 0
    enqueued_summaries: int = 0
    new_bvids: tuple[str, ...] = ()


async def scan_followed_up_by_id(followed_up_id: str) -> ScanOutcome:
    """扫单个 UP主。供 POST /api/followed-up/{id}/sync 调用。

    v0.3 round 6 升级：返回 :class:`ScanOutcome`（同时含新 hotspot 数 +
    enqueue 的 summary job 数 + 新 bvid 列表）—— 让 sync 一次返回把
    「数据收集 + agent 摘要触发 + 三向归档」三件事都报告给前端。
    失败返回空 ``ScanOutcome()`` 且记日志（不抛）。
    """
    async with get_session_maker()() as s:
        fu = (
            await s.execute(select(FollowedUp).where(FollowedUp.id == followed_up_id))
        ).scalar_one_or_none()
    if fu is None or fu.deleted_at is not None:
        logger.warning("[scan] followed_up %s not found or deleted", followed_up_id)
        return ScanOutcome()
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
async def _scan_one(fu: FollowedUp) -> ScanOutcome:
    """扫单个 UP主，返回 :class:`ScanOutcome`。失败返回空 outcome 且记日志（不抛）。

    v0.3 round 6 升级：除新 hotspot 数外，额外回报 enqueue 的 summary job 数
    与新 bvid 列表，让 sync 调用方能告诉前端「数据收集 + agent 触发」都
    跑了多少。
    """
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
        return ScanOutcome()

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
        return ScanOutcome()

    new_count = 0
    new_hotspots: list[Hotspot] = []
    new_bvids: list[str] = []
    latest_bvid: Optional[str] = None
    for v in videos:
        try:
            new_hs = await upsert_hotspot_from_video(fu, v)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[scan] upsert failed bvid=%s: %s", v.bvid, exc)
            continue
        if new_hs is not None:
            new_count += 1
            new_hotspots.append(new_hs)
            new_bvids.append(v.bvid)
        if latest_bvid is None:
            latest_bvid = v.bvid

    # v0.3 round 6: 触发 agent 摘要 + 三向归档（spec 03 + spec 06）
    enqueued_ids: list[str] = []
    if new_hotspots:
        try:
            enqueued_ids = await enqueue_summaries_for_hotspots(fu, new_hotspots)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[scan] enqueue_summaries_for_hotspots failed mid=%s: %s",
                fu.uid,
                exc,
            )

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

    logger.info(
        "[scan] mid=%s videos=%d new=%d enqueued_summaries=%d",
        fu.uid,
        len(videos),
        new_count,
        len(enqueued_ids),
    )
    return ScanOutcome(
        new_hotspots=new_count,
        enqueued_summaries=len(enqueued_ids),
        new_bvids=tuple(new_bvids),
    )


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