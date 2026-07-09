"""Hotspot business service layer."""

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.collectors.base import HotspotCandidate
from aipulse.hotspot.models import Hotspot, Keyword, Source
from aipulse.hotspot.processor import calculate_heat_score, normalize_url
from aipulse.hotspot.summarizer import analyze_hotspot
from aipulse.web.sse import sse_manager

SIMILARITY_THRESHOLD = 0.8


async def process_candidates(
    session: AsyncSession,
    candidates: list[HotspotCandidate],
    source: Source,
) -> int:
    """Deduplicate and persist candidates; return count of newly created hotspots."""
    new_count = 0
    for candidate in candidates:
        canonical = normalize_url(candidate.url)
        existing = await session.execute(select(Hotspot).where(Hotspot.canonical_url == canonical))
        if existing.scalar_one_or_none() is not None:
            continue
        analysis = await analyze_hotspot(source.name, candidate.content or candidate.title)
        if not analysis.is_real:
            continue
        heat = calculate_heat_score(
            interactions=candidate.raw_metadata.get("interactions", {}),
            source_weight=source.default_weight,
            published_at=candidate.published_at,
            keyword_matches=[],
            source_count=1,
            quality_score=analysis.relevance,
        )
        hotspot = Hotspot(
            id=uuid.uuid4().hex[:12],
            title=candidate.title,
            url=candidate.url,
            canonical_url=canonical,
            summary=analysis.summary,
            source_id=source.id,
            source_type=candidate.source_type,
            published_at=candidate.published_at,
            heat_score=heat,
            importance=analysis.importance,
            category=analysis.category,
            status="new",
            raw_metadata=candidate.raw_metadata,
        )
        session.add(hotspot)
        await session.flush()
        await sse_manager.broadcast("hotspot.new", json.dumps({"id": hotspot.id}))
        new_count += 1
    await session.commit()
    return new_count


async def list_hotspots(
    session: AsyncSession,
    q: str = "",
    source: str = "",
    category: str = "",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Hotspot], int]:
    """List hotspots with optional filters and pagination."""
    stmt = select(Hotspot)
    if q:
        stmt = stmt.where(Hotspot.title.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Hotspot.source_type == source)
    if category:
        stmt = stmt.where(Hotspot.category == category)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Hotspot.heat_score.desc()).offset((page - 1) * limit).limit(limit)
    items = (await session.execute(stmt)).scalars().all()
    return list(items), int(total)


async def get_hotspot(session: AsyncSession, hotspot_id: str) -> Hotspot | None:
    """Fetch a single hotspot by id."""
    return (
        await session.execute(select(Hotspot).where(Hotspot.id == hotspot_id))
    ).scalar_one_or_none()


async def create_keyword(session: AsyncSession, value: str) -> Keyword:
    """Create and persist a new keyword."""
    keyword = Keyword(value=value)
    session.add(keyword)
    await session.commit()
    await session.refresh(keyword)
    return keyword
