"""Web API routes for hotspots and keywords."""

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.hotspot.schemas import (
    DailyDigestOut,
    GenerateDigestRequest,
    HotspotOut,
    HotspotUpdate,
    KeywordCreate,
    KeywordOut,
    KeywordUpdate,
    SourceOut,
    SourceUpdate,
)
from aipulse.archive.service import archive_three_way
from aipulse.hotspot.service import (
    create_keyword as create_keyword_service,
)
from aipulse.hotspot.service import (
    delete_keyword as delete_keyword_service,
)
from aipulse.hotspot.service import (
    generate_digest as generate_digest_service,
)
from aipulse.hotspot.service import (
    get_hotspot as get_hotspot_service,
)
from aipulse.hotspot.service import (
    get_latest_digest as get_latest_digest_service,
)
from aipulse.hotspot.service import (
    get_related_hotspots as get_related_hotspots_service,
)
from aipulse.hotspot.service import (
    list_digests as list_digests_service,
)
from aipulse.hotspot.service import (
    list_hotspots as list_hotspots_service,
)
from aipulse.hotspot.service import (
    list_keywords as list_keywords_service,
)
from aipulse.hotspot.service import (
    list_sources as list_sources_service,
)
from aipulse.hotspot.service import (
    update_hotspot as update_hotspot_service,
)
from aipulse.hotspot.service import (
    update_keyword as update_keyword_service,
)
from aipulse.hotspot.service import (
    update_source as update_source_service,
)
from aipulse.core.config import get_settings as get_global_settings
from aipulse.core.config import reset_settings as reset_global_settings
from aipulse.store.database import get_session
from aipulse.store.models import now_utc
from aipulse.web.schemas import SettingsResponse, SettingsUpdate
from aipulse.web.sse import sse_manager

router = APIRouter()

logger = logging.getLogger(__name__)


# Spec E3: well-known macOS / iCloud / Nutstore vault locations. The UI
# shows these as suggestions before the user falls back to a manual picker.
DEFAULT_VAULT_CANDIDATES: tuple[str, ...] = (
    "~/Documents",
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents",
    "~/Nutstore Files",
    "~/坚果云",
)


@router.get("/hotspots")
async def list_hotspots_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(max_length=128)] = "",
    source: Annotated[str, Query(max_length=64)] = "",
    importance: Annotated[str, Query(max_length=64)] = "",
    category: Annotated[str, Query(max_length=64)] = "",
    decision_status: Annotated[str, Query(max_length=128)] = "",
    sort: Annotated[str, Query(max_length=64)] = "",
    order: Annotated[str, Query(max_length=64)] = "",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """List hotspots with optional filters and pagination."""
    items, total = await list_hotspots_service(
        session,
        q=q,
        source=source,
        importance=importance,
        category=category,
        decision_status=decision_status,
        sort=sort,
        order=order,
        page=page,
        limit=limit,
    )
    await _attach_hotspot_context(session, items)
    return {
        "success": True,
        "data": [HotspotOut.model_validate(item) for item in items],
        "meta": {"total": total, "page": page, "limit": limit},
    }


@router.get("/hotspots/{hotspot_id}")
async def get_hotspot_route(
    hotspot_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Fetch a single hotspot by ID."""
    hotspot = await get_hotspot_service(session, hotspot_id)
    if hotspot is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    await _attach_hotspot_context(session, [hotspot])
    return {"success": True, "data": HotspotOut.model_validate(hotspot)}


@router.get("/hotspots/{hotspot_id}/related")
async def get_related_hotspots_route(
    hotspot_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Fetch hotspots related to the given hotspot."""
    items = await get_related_hotspots_service(session, hotspot_id, limit=limit)
    return {"success": True, "data": [HotspotOut.model_validate(item) for item in items]}


@router.post("/hotspots/{hotspot_id}/archive")
async def archive_hotspot_route(
    hotspot_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Archive a hotspot via the v0.3 three-way pipeline (DB + Obsidian Tasks + Apple Reminders).

    spec 06 §7.2：触发 DB learning_events + Obsidian note + Obsidian Task checkbox +
    Apple Reminder 三方向独立 try/except。Bearer 鉴权由 server 中间件统一处理
    （aipulse_api_token 未配置时跳过）。

    Returns:
        ``{note_path, learning_event_id, reminder_id, obsidian_task_written, errors}``。
    """
    from aipulse.hotspot.models import Hotspot
    from aipulse.models.followed_up import FollowedUp
    from aipulse.summarizers.agent import tools as agent_tools

    hotspot = await session.get(Hotspot, hotspot_id)
    if hotspot is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")

    # 解析三方向存储所需字段（spec 06 §7.2 + plan §Task 3）
    video_id = hotspot.content_id or hotspot.id
    title = hotspot.title or ""
    up_name = ""
    if hotspot.followed_up_id:
        fu = await session.get(FollowedUp, hotspot.followed_up_id)
        if fu is not None:
            up_name = fu.display_name
    markdown = hotspot.summary or ""
    scheduled_at = agent_tools.default_scheduled_at()
    # topic 优先用 hotspot.title；空则用 title 兜底
    topic = hotspot.title or title or video_id

    outcome = await archive_three_way(
        video_id=video_id,
        title=title,
        up_name=up_name,
        markdown=markdown,
        scheduled_at=scheduled_at,
        topic=topic,
    )
    if outcome.note_path:
        await update_hotspot_service(
            session,
            hotspot_id,
            {
                "status": "archived",
                "decision_status": "archived",
                "obsidian_summary_path": outcome.note_path,
                "learning_event_id": str(outcome.learning_event_id)
                if outcome.learning_event_id is not None
                else None,
            },
        )
    return {
        "success": True,
        "data": {
            "note_path": outcome.note_path,
            "learning_event_id": outcome.learning_event_id,
            "reminder_id": outcome.reminder_id,
            "obsidian_task_written": outcome.obsidian_task_written,
            "errors": outcome.errors,
        },
    }


@router.patch("/hotspots/{hotspot_id}")
async def update_hotspot_route(
    hotspot_id: str,
    payload: HotspotUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Update hotspot decision metadata."""
    updated = await update_hotspot_service(
        session,
        hotspot_id,
        payload.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    await _attach_hotspot_context(session, [updated])
    return {"success": True, "data": HotspotOut.model_validate(updated)}


@router.post("/hotspots/{hotspot_id}/notify")
async def notify_hotspot_route(
    hotspot_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Notify on a hotspot via the configured push strategies (spec 06 plan §Task 4).

    三重 gate：
      1. ``settings.learning_notification_enabled`` 必须为 true。
      2. hotspot 还没 ``notified``（防止重复推送）。
      3. hotspot.decision_status == "worth_learning"（judge 通过才推送）。

    触发后置 ``hotspot.notified = true`` 持久化到 DB。
    Bearer 鉴权由 server 中间件统一处理。
    """
    from aipulse.hotspot.models import Hotspot
    from aipulse.pushers.base import PushMessage
    from aipulse.pushers.registry import get_push_registry

    settings = get_global_settings()
    if not settings.learning_notification_enabled:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "learning_notification_disabled",
                "message": "settings.learning_notification_enabled is false",
            },
        )

    hotspot = await session.get(Hotspot, hotspot_id)
    if hotspot is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")

    if hotspot.notified:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "already_notified",
                "message": "hotspot already notified",
                "hotspot_id": hotspot_id,
            },
        )

    if hotspot.decision_status != "worth_learning":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "not_worth_learning",
                "message": "hotspot.decision_status != worth_learning",
                "decision_status": hotspot.decision_status,
            },
        )

    registry = get_push_registry(settings)
    message = PushMessage(
        title=hotspot.title,
        summary=hotspot.summary or "",
        url=hotspot.url,
        platform=hotspot.source_type,
    )
    sent_to: list[str] = []
    for strategy in registry.list_configured():
        try:
            ok = await strategy.send(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Push strategy failed: %s", exc)
            continue
        if ok:
            sent_to.append(type(strategy).__name__)

    hotspot.notified = True
    hotspot.decision_status = "worth_notified"
    await session.commit()

    return {
        "success": True,
        "data": {
            "hotspot_id": hotspot_id,
            "notified": True,
            "sent_to": sent_to,
            "title": hotspot.title,
        },
    }


@router.post("/agent/retry/{hotspot_id}", status_code=202)
async def retry_hotspot_route(
    hotspot_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Retry a failed hotspot by resetting it to pending and enqueueing summary."""
    from aipulse.api.summary import enqueue_summary_route
    from aipulse.hotspot.models import Hotspot

    hotspot = await session.get(Hotspot, hotspot_id)
    if hotspot is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    if not hotspot.content_id:
        raise HTTPException(status_code=409, detail="Hotspot has no content_id")

    await update_hotspot_service(
        session,
        hotspot_id,
        {
            "decision_status": "pending",
        },
    )
    result = await enqueue_summary_route(hotspot.content_id, session)
    return {
        "success": True,
        "data": {
            "hotspot_id": hotspot_id,
            "video_id": hotspot.content_id,
            **result["data"],
        },
    }


@router.get("/keywords")
async def list_keywords_route(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """List all keywords."""
    items = await list_keywords_service(session)
    return {"success": True, "data": [KeywordOut.model_validate(item) for item in items]}


@router.post("/keywords")
async def create_keyword_route(
    payload: KeywordCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a new keyword."""
    keyword = await create_keyword_service(session, payload.value)
    return {"success": True, "data": KeywordOut.model_validate(keyword)}


@router.put("/keywords/{keyword_id}")
async def update_keyword_route(
    keyword_id: str,
    payload: KeywordUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Update a keyword."""
    updated = await update_keyword_service(session, keyword_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"success": True, "data": KeywordOut.model_validate(updated)}


@router.delete("/keywords/{keyword_id}")
async def delete_keyword_route(
    keyword_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Delete a keyword."""
    deleted = await delete_keyword_service(session, keyword_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"success": True, "data": {"id": keyword_id}}


@router.get("/sources")
async def list_sources_route(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """List all configured sources."""
    items = await list_sources_service(session)
    return {"success": True, "data": [SourceOut.model_validate(item) for item in items]}


@router.put("/sources/{source_id}")
async def update_source_route(
    source_id: str,
    payload: SourceUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Update a source configuration."""
    updated = await update_source_service(session, source_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"success": True, "data": SourceOut.model_validate(updated)}


@router.post("/sources/{source_id}/sync")
async def sync_source_route(
    source_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Trigger immediate sync for a single source via the scheduler."""
    from aipulse.scheduler.client import get_scheduler
    from aipulse.scheduler.jobs.hotspot_sync import sync_source_by_id

    scheduler = get_scheduler()
    job_id = f"source_sync_{source_id}"
    scheduler.add_job(
        sync_source_by_id,
        args=[source_id],
        id=job_id,
        replace_existing=True,
        trigger="date",
        run_date=now_utc(),
    )
    return {"success": True, "data": {"job_id": job_id, "source_id": source_id}}


@router.get("/digests")
async def list_digests_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    """List recent daily digests."""
    items = await list_digests_service(session, limit=limit)
    return {"success": True, "data": [DailyDigestOut.model_validate(item) for item in items]}


@router.get("/digests/latest")
async def get_latest_digest_route(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Return the most recent daily digest."""
    digest = await get_latest_digest_service(session)
    if digest is None:
        raise HTTPException(status_code=404, detail="No digest available")
    return {"success": True, "data": DailyDigestOut.model_validate(digest)}


@router.post("/digests/generate")
async def generate_digest_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: GenerateDigestRequest | None = None,
) -> dict[str, Any]:
    """Generate today's digest from current hotspots.

    Body (optional):
        {"date": "2026-07-25"} — defaults to today. If a digest already exists
        for that date, return 409 with the existing record (idempotent UX).
    """
    from datetime import date as _date
    from sqlalchemy import select

    from aipulse.hotspot.models import DailyDigest

    target_date = payload.target_date if payload and payload.target_date else _date.today()
    stmt = select(DailyDigest).where(DailyDigest.date == target_date)
    result = await session.execute(stmt)
    dup = result.scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "digest_exists",
                "date": target_date.isoformat(),
                "existing": DailyDigestOut.model_validate(dup).model_dump(mode="json"),
            },
        )
    digest = await generate_digest_service(session, target_date=target_date)
    return {"success": True, "data": DailyDigestOut.model_validate(digest)}


@router.get("/sse/hotspots")
async def hotspots_sse(request: Request) -> StreamingResponse:
    """Stream hotspot events to connected clients."""
    return StreamingResponse(
        sse_manager.subscribe(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/settings")
async def get_settings_route() -> dict[str, Any]:
    """Return current AppSettings, grouped by section, with secrets masked."""
    from aipulse.web.settings_map import build_settings_response

    settings = get_global_settings()
    return {"success": True, "data": build_settings_response(settings)}


@router.post("/settings/obsidian-vault/scan")
async def scan_obsidian_vault_route() -> dict[str, Any]:
    """Return candidate Obsidian vault directories (spec E3).

    The list merges:
      * ``DEFAULT_VAULT_CANDIDATES`` — well-known macOS / iCloud / Nutstore
        paths expanded against the current ``$HOME``.
      * CWD ancestors up to 5 levels — useful when the project ships a
        sample vault inside a few parent dirs.

    Each entry reports whether the path currently exists so the UI can dim
    out non-existent candidates. The endpoint is read-only and never
    touches settings; it does NOT require the API token.
    """
    candidates: list[dict[str, Any]] = []

    # 1) Default well-known locations. We keep the raw ``~`` form in the
    # ``path`` field so the UI can show it verbatim; the UI expands it
    # before sending PATCH /api/settings. ``exists`` is checked against the
    # expanded path on disk.
    for raw in DEFAULT_VAULT_CANDIDATES:
        expanded = Path(raw).expanduser()
        candidates.append(
            {
                "path": raw,
                "exists": expanded.exists(),
                "note": _candidate_note(raw),
            }
        )

    # 2) CWD ancestors up to 5 levels
    seen: set[str] = {c["path"] for c in candidates}
    cwd = Path.cwd().resolve()
    for level, ancestor in enumerate(_iter_ancestors(cwd, max_levels=5)):
        key = str(ancestor)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "path": key,
                "exists": ancestor.exists(),
                "note": f"向上 {level + 1} 层",
            }
        )

    return {"success": True, "data": {"candidates": candidates}}


@router.patch("/settings")
async def patch_settings_route(payload: SettingsUpdate) -> dict[str, Any]:
    """Apply a partial update to AppSettings.

    Semantics:
      * Empty / masked secrets are preserved (UI can safely round-trip
        masked placeholders without clearing the underlying value).
      * New secret values overwrite the existing secret.
      * Non-secret fields overwrite.
      * Updated value is validated (e.g. obsidian_vault_path must exist) and
        persisted to data/settings.json via AppSettings.save().
      * After a successful update, the cached settings singleton is reset
        so the next request reads the new values.
    """
    from pathlib import Path

    from aipulse.web.settings_map import build_settings_response, update_settings

    current = get_global_settings()
    changes = payload.model_dump(exclude_unset=True)
    updated = update_settings(current, changes)

    # obsidian_vault_path existence is enforced by SettingsUpdate's
    # field_validator (spec E4), so FastAPI returns 422 before we get here.
    # No runtime check needed.

    try:
        updated.save()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist settings: {exc}") from exc

    # Do NOT reset_global_settings() here: AppSettings.update() mutates in
    # place and the cached singleton already reflects the new values.
    # Resetting would discard the in-memory update (e.g. secrets that are
    # not persisted to disk) and force the next GET to reconstruct an empty
    # instance from settings.json alone.
    return {"success": True, "data": build_settings_response(updated)}


def _iter_ancestors(path: Path, *, max_levels: int) -> list[Path]:
    """Walk from ``path`` upward, returning up to ``max_levels`` ancestors.

    The starting directory itself is excluded — the spec asks for "CWD
    ancestors up to 5 levels", not the CWD itself. ``/`` is the natural
    terminus; we stop when ``parent == path``.
    """
    out: list[Path] = []
    current = path.parent
    while current != current.parent and len(out) < max_levels:
        out.append(current)
        current = current.parent
    return out


def _candidate_note(raw: str) -> str:
    """Friendly note shown next to each default candidate."""
    notes: dict[str, str] = {
        "~/Documents": "用户目录下的 Documents",
        "~/Library/Mobile Documents/iCloud~md~obsidian/Documents": "iCloud 同步的 Obsidian",
        "~/Nutstore Files": "Nutstore 同步盘",
        "~/坚果云": "坚果云同步盘",
    }
    return notes.get(raw, "")


async def _attach_hotspot_context(session: AsyncSession, hotspots: list[Any]) -> None:
    """Enrich hotspot ORM rows with up_name for dashboard views."""
    followed_up_ids = {
        hotspot.followed_up_id
        for hotspot in hotspots
        if getattr(hotspot, "followed_up_id", None)
    }
    if not followed_up_ids:
        return

    from aipulse.models.followed_up import FollowedUp

    rows = await session.execute(
        select(FollowedUp.id, FollowedUp.display_name).where(FollowedUp.id.in_(followed_up_ids))
    )
    names = {row_id: display_name for row_id, display_name in rows.all()}
    for hotspot in hotspots:
        follow_id = getattr(hotspot, "followed_up_id", None)
        if follow_id:
            hotspot.up_name = names.get(follow_id)
