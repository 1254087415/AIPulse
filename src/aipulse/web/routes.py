"""Web API routes for hotspots and keywords."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.hotspot.schemas import HotspotOut, KeywordCreate
from aipulse.hotspot.service import (
    create_keyword as create_keyword_service,
)
from aipulse.hotspot.service import (
    get_hotspot as get_hotspot_service,
)
from aipulse.hotspot.service import (
    list_hotspots as list_hotspots_service,
)
from aipulse.store.database import get_session
from aipulse.web.sse import sse_manager

router = APIRouter()


@router.get("/hotspots")
async def list_hotspots_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = "",
    source: str = "",
    category: str = "",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """List hotspots with optional filters and pagination."""
    items, total = await list_hotspots_service(
        session, q=q, source=source, category=category, page=page, limit=limit
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


@router.post("/keywords")
async def create_keyword_route(
    payload: KeywordCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a new keyword."""
    keyword = await create_keyword_service(session, payload.value)
    return {"success": True, "data": {"id": keyword.id, "value": keyword.value}}


@router.get("/sse/hotspots")
async def hotspots_sse(request: Request) -> StreamingResponse:
    """Stream hotspot events to connected clients."""
    return StreamingResponse(
        sse_manager.subscribe(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
