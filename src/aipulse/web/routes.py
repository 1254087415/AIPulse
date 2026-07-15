"""Web API routes for hotspots and keywords."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.hotspot.schemas import (
    DailyDigestOut,
    HotspotOut,
    KeywordCreate,
    KeywordOut,
    KeywordUpdate,
    SourceOut,
    SourceUpdate,
)
from aipulse.hotspot.service import (
    archive_hotspot as archive_hotspot_service,
)
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
    update_keyword as update_keyword_service,
)
from aipulse.hotspot.service import (
    update_source as update_source_service,
)
from aipulse.store.database import get_session
from aipulse.store.models import now_utc
from aipulse.web.sse import sse_manager

router = APIRouter()


@router.get("/hotspots")
async def list_hotspots_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(max_length=128)] = "",
    source: Annotated[str, Query(max_length=64)] = "",
    importance: Annotated[str, Query(max_length=64)] = "",
    category: Annotated[str, Query(max_length=64)] = "",
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
        sort=sort,
        order=order,
        page=page,
        limit=limit,
    )
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
    """Archive a hotspot to Obsidian."""
    try:
        paths = await archive_hotspot_service(session, hotspot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if paths is None:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return {"success": True, "data": paths}


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
) -> dict[str, Any]:
    """Generate today's digest from current hotspots."""
    digest = await generate_digest_service(session)
    return {"success": True, "data": DailyDigestOut.model_validate(digest)}


@router.get("/sse/hotspots")
async def hotspots_sse(request: Request) -> StreamingResponse:
    """Stream hotspot events to connected clients."""
    return StreamingResponse(
        sse_manager.subscribe(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
