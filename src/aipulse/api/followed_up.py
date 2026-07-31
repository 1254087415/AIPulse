"""Followed-up HTTP API routes."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.core.datetime_utils import format_iso_utc
from aipulse.hotspot.models import Hotspot
from aipulse.models.followed_up_collections import FollowedUpCollection
from aipulse.models.learning_events import LearningEvent
from aipulse.models.summary_jobs import SummaryJob
from aipulse.repositories.followed_up_repo import (
    DuplicateFollowedUpError,
    FollowedUpNotFoundError,
    SqlAlchemyFollowedUpRepository,
)
from aipulse.schemas.followed_up import (
    FollowedUpCreate,
    FollowedUpResponse,
    FollowedUpUpdate,
)
from aipulse.store.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/followed-up", tags=["followed-up"])

_BILIBILI_CARD_URL = "https://api.bilibili.com/x/web-interface/card"
_BILIBILI_VALIDATE_TIMEOUT = 15.0


async def _resolve_bilibili_display_name(uid: str) -> tuple[str, str]:
    """Look up the B站 user display name via the public card API.

    Returns ``(display_name, profile_url)``. Network failures are tolerated:
    the caller falls back to ``uid`` as the display name.
    """
    profile_url = f"https://space.bilibili.com/{uid}"
    try:
        async with httpx.AsyncClient(timeout=_BILIBILI_VALIDATE_TIMEOUT) as client:
            response = await client.get(
                _BILIBILI_CARD_URL,
                params={"mid": uid},
                headers={"User-Agent": "AIPulse/0.3"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Bilibili card lookup failed for mid=%s: %s", uid, exc)
        return uid, profile_url

    data = payload.get("data") or {}
    card = data.get("card") or {}
    name = card.get("name") or uid
    return name, profile_url


async def _resolve_bilibili_avatar(uid: str) -> str | None:
    """Return the B站 user avatar URL via the public card API.

    Best-effort lookup — any network/parse error returns ``None`` and the
    caller can fall back to a placeholder. The result is intentionally not
    cached at this layer; callers may persist it via the ``config`` JSON.
    """
    try:
        async with httpx.AsyncClient(timeout=_BILIBILI_VALIDATE_TIMEOUT) as client:
            response = await client.get(
                _BILIBILI_CARD_URL,
                params={"mid": uid},
                headers={"User-Agent": "AIPulse/0.3"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Bilibili avatar lookup failed for mid=%s: %s", uid, exc)
        return None

    data = payload.get("data") or {}
    card = data.get("card") or {}
    return card.get("face") or None


@router.post("", status_code=201)
async def create_followed_up_route(
    payload: FollowedUpCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a new FollowedUp entry.

    If the caller omits ``display_name`` for a bilibili entry, the B站
    card API is consulted to fill it in. Network failures fall back to
    ``uid``. ``profile_url`` is also defaulted when missing — bilibili
    entries use the canonical space.bilibili.com URL; non-bilibili
    entries must provide it explicitly.
    """
    repo = SqlAlchemyFollowedUpRepository(session)

    # spec 09 TC-API-FOLLOWED-UP-04: 超过 20 个 UP 主上限 → 422
    existing_count = await repo.count_active()
    MAX_FOLLOW_LIMIT = 20
    if existing_count >= MAX_FOLLOW_LIMIT:
        raise HTTPException(
            status_code=422,
            detail={
                "success": False,
                "error": "FOLLOW_LIMIT_EXCEEDED",
                "message": (
                    f"已达 UP 主上限 {MAX_FOLLOW_LIMIT} 个；"
                    "删除部分 UP 主后再添加。"
                ),
                "max_size": MAX_FOLLOW_LIMIT,
                "current_count": existing_count,
            },
        )

    display_name = payload.display_name
    profile_url = payload.profile_url

    if payload.platform == "bilibili":
        if not display_name or not profile_url:
            resolved_name, resolved_profile = await _resolve_bilibili_display_name(payload.uid)
            display_name = display_name or resolved_name
            profile_url = profile_url or resolved_profile
    elif not profile_url:
        raise HTTPException(
            status_code=422,
            detail={
                "success": False,
                "error": "profile_url required",
                "message": (
                    f"platform={payload.platform} requires an explicit profile_url; "
                    "v0.3 only supports bilibili auto-derive."
                ),
            },
        )

    try:
        record = await repo.create(
            platform=payload.platform,
            uid=payload.uid,
            display_name=display_name,
            profile_url=profile_url,
            collector_strategy=payload.collector_strategy,
            fetch_interval_minutes=payload.fetch_interval_minutes,
            config=payload.config,
        )
    except DuplicateFollowedUpError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error": "Duplicate FollowedUp",
                "message": str(exc),
            },
        ) from exc

    await session.commit()
    return {"success": True, "data": FollowedUpResponse.model_validate(record).model_dump()}


@router.get("")
async def list_followed_up_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    include_deleted: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """List FollowedUp rows, newest first."""
    repo = SqlAlchemyFollowedUpRepository(session)
    records = await repo.list_all(include_deleted=include_deleted)
    return {
        "success": True,
        "data": [
            FollowedUpResponse.model_validate(r).model_dump() for r in records
        ],
    }


@router.get("/{followed_up_key}/hotspots")
async def list_followed_up_hotspots_route(
    followed_up_key: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Return recent hotspots associated with a followed-up record."""
    record = await _find_followed_up(session, followed_up_key)
    stmt = (
        select(Hotspot)
        .where(Hotspot.followed_up_id == record.id)
        .order_by(desc(Hotspot.created_at))
        .offset(offset)
        .limit(limit)
    )
    hotspots = (await session.execute(stmt)).scalars().all()
    return {
        "success": True,
        "data": [_serialize_hotspot(hotspot) for hotspot in hotspots],
        "meta": {"offset": offset, "limit": limit},
    }


@router.get("/{followed_up_key}/sync-history")
async def list_followed_up_sync_history_route(
    followed_up_key: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Return recent summary/sync jobs associated with a followed-up record."""
    record = await _find_followed_up(session, followed_up_key)
    stmt = (
        select(SummaryJob)
        .join(Hotspot, Hotspot.content_id == SummaryJob.video_id, isouter=True)
        .where(
            (Hotspot.followed_up_id == record.id)
            | (SummaryJob.up_name == record.display_name)
        )
        .order_by(desc(SummaryJob.created_at))
        .limit(limit)
    )
    jobs = (await session.execute(stmt)).scalars().all()
    return {
        "success": True,
        "data": [_serialize_sync_history(job) for job in jobs],
        "meta": {"limit": limit},
    }


async def _find_followed_up(session: AsyncSession, key: str) -> Any:
    repo = SqlAlchemyFollowedUpRepository(session)
    record = await repo.find_by_id(key)
    if record is None:
        record = await repo.get_by_platform_uid("bilibili", key)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="FollowedUp not found")
    return record


def _record_response(record: Any) -> dict[str, Any]:
    return FollowedUpResponse.model_validate(record).model_dump()


def _serialize_hotspot(hotspot: Hotspot) -> dict[str, Any]:
    return {
        "id": hotspot.id,
        "title": hotspot.title,
        "url": hotspot.url,
        "canonical_url": hotspot.canonical_url,
        "summary": hotspot.summary,
        "source_type": hotspot.source_type,
        "published_at": format_iso_utc(hotspot.published_at),
        "created_at": format_iso_utc(hotspot.created_at),
        "heat_score": hotspot.heat_score,
    }


def _serialize_sync_history(job: SummaryJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "video_id": job.video_id,
        "title": job.title,
        "status": job.status,
        "error": job.error,
        "created_at": format_iso_utc(job.created_at),
        "started_at": format_iso_utc(job.started_at),
        "completed_at": format_iso_utc(job.completed_at),
    }


@router.get("/{followed_up_id}")
async def get_followed_up_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Return a single FollowedUp by id or platform uid."""
    record = await _find_followed_up(session, followed_up_id)
    return {
        "success": True,
        "data": FollowedUpResponse.model_validate(record).model_dump(),
    }


@router.patch("/{followed_up_id}")
async def update_followed_up_route(
    followed_up_id: str,
    payload: FollowedUpUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Partially update a FollowedUp.

    L1 #1+#2：``{id}`` 既接受 DB UUID 也接受平台 uid（bilibili mid），
    解析后再走 ``repo.update``。``enabled`` 已在 ``FollowedUpUpdate`` 的
    model_validator 中归一到 ``is_active``，此处只透传 ``is_active``。
    """
    record = await _find_followed_up(session, followed_up_id)
    repo = SqlAlchemyFollowedUpRepository(session)
    values = payload.model_dump(exclude_unset=True)
    # drop the alias — repo only knows is_active
    values.pop("enabled", None)
    try:
        updated = await repo.update(record.id, **values)
    except FollowedUpNotFoundError as exc:  # pragma: no cover - race
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return {
        "success": True,
        "data": FollowedUpResponse.model_validate(updated).model_dump(),
    }


@router.delete("/{followed_up_id}")
async def delete_followed_up_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Soft-delete a FollowedUp.

    L1 #1：``{id}`` 接受 DB UUID 或平台 uid。
    """
    record = await _find_followed_up(session, followed_up_id)
    repo = SqlAlchemyFollowedUpRepository(session)
    try:
        await repo.soft_delete(record.id)
    except FollowedUpNotFoundError as exc:  # pragma: no cover - race
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"success": True, "data": {"id": record.id}}


@router.post("/validate")
async def validate_followed_up_route(
    payload: FollowedUpCreate,
) -> dict[str, Any]:
    """Validate that a given (platform, uid) exists on the source platform.

    Phase 2 v0.3 spec §4.6 — 双轨策略：UAPI 优先 → HTML 兜底。

    Currently only B站 is implemented. Returns the live display name and
    profile URL or 409 when both strategies report non-existent.
    """
    if payload.platform != "bilibili":
        raise HTTPException(
            status_code=400,
            detail=f"validate() not implemented for platform={payload.platform}",
        )

    from aipulse.collectors.bilibili_up.factory import BilibiliUpCollectorFactory

    # 1) UAPI 优先
    try:
        uapi = BilibiliUpCollectorFactory.create("uapi")
        try:
            exists, name = await uapi.validate_up_exists(payload.uid)
        finally:
            await uapi.close()
        if exists:
            return {
                "success": True,
                "data": {
                    "platform": payload.platform,
                    "uid": payload.uid,
                    "display_name": name,
                    "profile_url": f"https://space.bilibili.com/{payload.uid}",
                    "strategy": "uapi",
                },
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("uapi validate mid=%s failed: %s", payload.uid, exc)

    # 2) HTML 兜底
    try:
        html = BilibiliUpCollectorFactory.create("html")
        try:
            exists, name = await html.validate_up_exists(payload.uid)
        finally:
            await html.close()
        if exists:
            return {
                "success": True,
                "data": {
                    "platform": payload.platform,
                    "uid": payload.uid,
                    "display_name": name,
                    "profile_url": f"https://space.bilibili.com/{payload.uid}",
                    "strategy": "html",
                },
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("html validate mid=%s failed: %s", payload.uid, exc)

    raise HTTPException(
        status_code=409,
        detail={
            "success": False,
            "error": "该 UP主不存在或账号已注销",
            "uid": payload.uid,
        },
    )


@router.post("/{followed_up_id}/sync", status_code=202)
async def sync_followed_up_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 2 v0.3 spec §4.10 — 触发单个 UP主立即同步。

    v0.3 round 6 升级：sync 现在一次性触发「数据收集 + agent 摘要 +
    三向归档」三件事 —— 新 hotspot 在 upsert 后立即由
    ``enqueue_summaries_for_hotspots`` 入 summary 队列，summary worker
    后台跑 6 个 @tool 落 DB / Obsidian / Apple Reminder。
    行为：调 ``scan_followed_up_by_id()``；15 秒超时；超时返回 202 + job id。
    失败返回 404 (UP主不存在) / 502 (上游失败)。

    L1 #1+#3：
    - ``{followed_up_id}`` 接受 DB UUID 或平台 uid（bilibili mid）。
    - 未知记录：``scan_followed_up_by_id`` 现抛 ``FollowedUpNotFoundError``，
      这里直接翻成 404，而不是返 202 + ``new_videos: 0`` 的伪成功。
    """
    from aipulse.scheduler.jobs.followed_up_scan import scan_followed_up_by_id

    record = await _find_followed_up(session, followed_up_id)
    resolved_id = record.id

    try:
        outcome = await asyncio.wait_for(
            scan_followed_up_by_id(resolved_id),
            timeout=15.0,
        )
    except FollowedUpNotFoundError as exc:
        # 解析时还存在但扫描时已被软删（race）。翻 404。
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except asyncio.TimeoutError:
        logger.info("[sync] followed_up %s sync hit 15s timeout", resolved_id)
        return {
            "success": True,
            "data": {
                "followed_up_id": resolved_id,
                "status": "timeout",
                "message": "扫描超时，已切到后台；前端可通过 /api/followed-up/{id}/health 拉进度",
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("[sync] followed_up %s sync failed: %s", resolved_id, exc)
        raise HTTPException(status_code=502, detail=f"sync failed: {exc}") from exc

    return {
        "success": True,
        "data": {
            "followed_up_id": resolved_id,
            "status": "ok",
            "new_videos": outcome.new_hotspots,
            # v0.3 round 6: sync 现在也入队 summary job；前端可据此轮询
            # /api/summary/jobs 看 agent pipeline 进度。
            "enqueued_summaries": outcome.enqueued_summaries,
            "new_bvids": list(outcome.new_bvids),
        },
    }


@router.get("/{followed_up_id}/health")
async def get_followed_up_health_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 2 v0.3 spec §4.10 — 健康状态详情（用于面板渲染状态徽章）。

    L1 #1：``{followed_up_id}`` 接受 DB UUID 或平台 uid。
    """
    record = await _find_followed_up(session, followed_up_id)

    return {
        "success": True,
        "data": {
            "id": record.id,
            "health": record.health,
            "last_checked_at": format_iso_utc(record.last_checked_at),
            "last_error": record.last_error,
            "failed_at": format_iso_utc(record.failed_at),
            "is_active": record.is_active,
        },
    }


@router.get("/{followed_up_id}/overview")
async def get_followed_up_overview_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 7 v0.3 spec §G8 — UP主详情页数据汇总（按 db id 或 uid）。

    聚合：基础信息 + health + 最近的 10 个 job + 最近的 10 个 learning event
    + 最近 10 个 collection。前端 single-page 渲染。

    L1 #1：``{followed_up_id}`` 接受 DB UUID 或平台 uid。
    """
    record = await _find_followed_up(session, followed_up_id)
    return await _build_overview_response(record, session)


@router.get("/by-uid/{platform}/{uid}/overview")
async def get_followed_up_overview_by_uid_route(
    platform: str,
    uid: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 8 R2#2 alias — same payload, addressed by (platform, uid).

    The dashboard lists FollowedUps by their platform uid (B站 mid etc.)
    rather than their database UUID. Accepting that key directly keeps the
    URL contract human-friendly without forcing the frontend to look up the
    id first.
    """
    repo = SqlAlchemyFollowedUpRepository(session)
    record = await repo.get_by_platform_uid(platform, uid)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="FollowedUp not found")
    return await _build_overview_response(record, session)


async def _build_overview_response(
    record: Any,
    session: AsyncSession,
) -> dict[str, Any]:
    """Assemble the GET /overview payload for a given FollowedUp record.

    Shared by both the db-id endpoint (`/{followed_up_id}/overview`) and the
    uid-alias endpoint (`/by-uid/{platform}/{uid}/overview`) so a row
    identifies identically regardless of how the caller addresses it.
    """
    followed_up_id = record.id

    health = {
        "health": record.health,
        "last_checked_at": format_iso_utc(record.last_checked_at),
        "last_error": record.last_error,
        "failed_at": format_iso_utc(record.failed_at),
        "is_active": record.is_active,
        "fetch_interval_minutes": record.fetch_interval_minutes,
        "status": record.status,
    }

    # Hotspots → job 关联（hotspot.followed_up_id == followed_up_id）

    stmt_jobs = (
        select(SummaryJob)
        .join(Hotspot, Hotspot.content_id == SummaryJob.video_id, isouter=True)
        .where(
            (Hotspot.followed_up_id == followed_up_id)
            | (SummaryJob.video_id.in_(
                select(Hotspot.content_id).where(Hotspot.followed_up_id == followed_up_id)
            ))
        )
        .order_by(desc(SummaryJob.created_at))
        .limit(10)
    )
    jobs = (await session.execute(stmt_jobs)).scalars().all()
    recent_jobs: list[dict[str, Any]] = [
        {
            "id": j.id,
            "video_id": j.video_id,
            "status": j.status,
            "title": j.title,
            "created_at": format_iso_utc(j.created_at),
            "completed_at": format_iso_utc(j.completed_at),
            "error": j.error,
            "note_path": j.note_path,
        }
        for j in jobs
    ]

    stmt_events = (
        select(LearningEvent)
        .where(LearningEvent.followed_up_id == followed_up_id)
        .order_by(desc(LearningEvent.scheduled_at))
        .limit(10)
    )
    events = (await session.execute(stmt_events)).scalars().all()
    recent_events: list[dict[str, Any]] = [
        {
            "id": e.id,
            "title": e.title,
            "scheduled_at": format_iso_utc(e.scheduled_at),
            "learning_status": e.learning_status,
            "summary_note_path": e.summary_note_path,
            "platform": e.platform,
        }
        for e in events
    ]

    stmt_cols = (
        select(FollowedUpCollection)
        .where(FollowedUpCollection.followed_up_id == followed_up_id)
        .order_by(desc(FollowedUpCollection.created_at))
        .limit(10)
    )
    collections = (await session.execute(stmt_cols)).scalars().all()
    recent_collections: list[dict[str, Any]] = [
        {
            "id": c.id,
            "title": c.title,
            "platform_collection_id": c.platform_collection_id,
            "description": c.description,
            "video_count": c.video_count,
            "created_at": format_iso_utc(c.created_at),
        }
        for c in collections
    ]

    await session.commit()
    return {
        "success": True,
        "data": {
            "id": record.id,
            "platform": record.platform,
            "uid": record.uid,
            "display_name": record.display_name,
            "profile_url": record.profile_url,
            "health": health,
            "config": record.config or {},
            "recent_jobs": recent_jobs,
            "recent_learning_events": recent_events,
            "recent_collections": recent_collections,
        },
    }


# ------------------------------------------------------------------
# spec §6.12 FollowDetailView — full detail + paginated videos
# ------------------------------------------------------------------


async def _build_detail_response(
    record: Any,
    session: AsyncSession,
) -> dict[str, Any]:
    """Assemble the GET /detail payload for a given FollowedUp record.

    Differs from ``_build_overview_response``:
    - ``name`` (not ``display_name``) for the spec §6.12 contract
    - ``health`` is the flat string ("healthy"/"warning"/"error")
    - ``enabled`` mirrors ``is_active`` so the UI can render 暂停/恢复
    - ``avatar`` is resolved from B站's card API (cached in ``config``)
    - ``collections[]`` carries a ``videos`` sublist so the
      ``<CollectionAccordion>`` can expand in place
    """
    config = dict(record.config or {})
    avatar = config.get("avatar_url")
    if not avatar and record.platform == "bilibili":
        avatar = await _resolve_bilibili_avatar(record.uid)
        if avatar:
            config["avatar_url"] = avatar
            # Persist lazily so the next request avoids a network call.
            try:
                from aipulse.repositories.followed_up_repo import (
                    SqlAlchemyFollowedUpRepository,
                )
                await SqlAlchemyFollowedUpRepository(session).update(
                    record.id, config=config
                )
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.debug("avatar cache write skipped: %s", exc)

    stmt_cols = (
        select(FollowedUpCollection)
        .where(FollowedUpCollection.followed_up_id == record.id)
        .order_by(desc(FollowedUpCollection.created_at))
    )
    collections = (await session.execute(stmt_cols)).scalars().all()

    stmt_videos = (
        select(Hotspot)
        .where(
            Hotspot.followed_up_id == record.id,
            Hotspot.deleted_at.is_(None) if hasattr(Hotspot, "deleted_at") else True,
        )
        .order_by(desc(Hotspot.created_at))
        .limit(500)
    )
    videos = (await session.execute(stmt_videos)).scalars().all()
    videos_by_collection: dict[str | None, list[dict[str, Any]]] = {}
    for v in videos:
        item = {
            "bvid": v.content_id,
            "title": v.title,
            "status": v.decision_status,
            "hotspot_id": v.id,
        }
        videos_by_collection.setdefault(v.followed_up_collection_id, []).append(item)

    collections_payload: list[dict[str, Any]] = []
    for c in collections:
        collections_payload.append(
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "video_count": c.video_count,
                "videos": videos_by_collection.get(c.id, []),
            }
        )
    # Surface videos that have no collection under the (None) bucket
    orphan_videos = videos_by_collection.get(None, [])

    await session.commit()
    return {
        "success": True,
        "data": {
            "id": record.id,
            "name": record.display_name,
            "mid": record.uid,
            "url": record.profile_url,
            "avatar": avatar or "",
            "health": record.health,
            "enabled": record.is_active,
            "strategy": record.collector_strategy,
            "interval_minutes": record.fetch_interval_minutes,
            "last_checked_at": format_iso_utc(record.last_checked_at),
            "last_error": record.last_error,
            "collections": collections_payload,
            "orphan_videos": orphan_videos,
        },
    }


@router.get("/{followed_up_id}/detail")
async def get_followed_up_detail_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 7 v0.3 spec §6.12 — UP主详情页 spec-shaped payload.

    Addressed by either the row's database UUID or, when the caller supplies a
    platform uid that 404s the canonical path, falls through to the uid-alias
    lookup. Either way the response shape matches the spec exactly.
    """
    repo = SqlAlchemyFollowedUpRepository(session)
    try:
        record = await _find_followed_up(session, followed_up_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        record = await repo.get_by_platform_uid("bilibili", followed_up_id)
        if record is None or record.deleted_at is not None:
            raise HTTPException(status_code=404, detail="FollowedUp not found")
    return await _build_detail_response(record, session)


@router.get("/by-uid/{platform}/{uid}/detail")
async def get_followed_up_detail_by_uid_route(
    platform: str,
    uid: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Phase 7 v0.3 spec §6.12 — UP主详情页，uid-alias 入口。"""
    repo = SqlAlchemyFollowedUpRepository(session)
    record = await repo.get_by_platform_uid(platform, uid)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="FollowedUp not found")
    return await _build_detail_response(record, session)


@router.get("/{followed_up_id}/videos")
async def list_followed_up_videos_route(
    followed_up_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    collection_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Phase 7 v0.3 spec §6.12 — UP主 视频分页 (Round 7 Q1).

    Returns ``{ items, nextOffset }``. ``nextOffset`` is ``null`` when the
    page is the last one. ``collection_id`` filters to a single collection;
    omit it to receive all videos.
    """
    record = await _find_followed_up(session, followed_up_id)

    stmt = select(Hotspot).where(
        Hotspot.followed_up_id == record.id,
    )
    if collection_id is not None:
        if collection_id == "":
            stmt = stmt.where(Hotspot.followed_up_collection_id.is_(None))
        else:
            stmt = stmt.where(Hotspot.followed_up_collection_id == collection_id)
    stmt = stmt.order_by(desc(Hotspot.created_at))

    # Fetch `limit + 1` rows so we can derive nextOffset without a count(*)
    rows = (await session.execute(stmt.offset(offset).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items: list[dict[str, Any]] = [
        {
            "bvid": v.content_id,
            "title": v.title,
            "collection_id": v.followed_up_collection_id,
            "status": v.decision_status,
            "published_at": format_iso_utc(v.published_at),
            "hotspot_id": v.id,
        }
        for v in page_rows
    ]
    next_offset: int | None = offset + limit if has_more else None

    await session.commit()
    return {
        "success": True,
        "data": {
            "items": items,
            "nextOffset": next_offset,
        },
    }


@router.get("/by-uid/{platform}/{uid}/videos")
async def list_followed_up_videos_by_uid_route(
    platform: str,
    uid: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    collection_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Phase 7 v0.3 spec §6.12 — UP主 视频分页 uid-alias 入口。"""
    repo = SqlAlchemyFollowedUpRepository(session)
    record = await repo.get_by_platform_uid(platform, uid)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="FollowedUp not found")
    stmt = select(Hotspot).where(Hotspot.followed_up_id == record.id)
    if collection_id is not None:
        if collection_id == "":
            stmt = stmt.where(Hotspot.followed_up_collection_id.is_(None))
        else:
            stmt = stmt.where(Hotspot.followed_up_collection_id == collection_id)
    stmt = stmt.order_by(desc(Hotspot.created_at))
    rows = (await session.execute(stmt.offset(offset).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [
        {
            "bvid": v.content_id,
            "title": v.title,
            "collection_id": v.followed_up_collection_id,
            "status": v.decision_status,
            "published_at": format_iso_utc(v.published_at),
            "hotspot_id": v.id,
        }
        for v in page_rows
    ]
    next_offset = offset + limit if has_more else None
    await session.commit()
    return {
        "success": True,
        "data": {
            "items": items,
            "nextOffset": next_offset,
        },
    }
