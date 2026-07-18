"""Hotspot business service layer."""

import json
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.archive.obsidian import ObsidianArchiver
from aipulse.collectors.base import HotspotCandidate
from aipulse.core.config import get_settings
from aipulse.hotspot.models import DailyDigest, Hotspot, Keyword, Source
from aipulse.hotspot.processor import calculate_heat_score, normalize_url
from aipulse.hotspot.summarizer import analyze_hotspot
from aipulse.summarizers.base import SummaryResult
from aipulse.web.sse import sse_manager

SIMILARITY_THRESHOLD = 0.8
_MAX_ERROR_LENGTH = 500


def sanitize_error_message(message: str | None) -> str:
    """Strip sensitive patterns from error messages before persistence.

    Removes URLs, file-system paths, and trims to a safe length so that
    backend details are not leaked to clients via ``source.last_error``.
    """
    if not message:
        return ""
    sanitized = str(message)
    sanitized = re.sub(r"https?://[^\s\"']+", "[URL]", sanitized)
    sanitized = re.sub(r"/([A-Za-z0-9_.~-]+/)+[A-Za-z0-9_.~-]*", "[PATH]", sanitized)
    sanitized = re.sub(r"[A-Za-z0-9_]+-[A-Za-z0-9_-]{8,}", "[TOKEN]", sanitized)
    if len(sanitized) > _MAX_ERROR_LENGTH:
        sanitized = sanitized[:_MAX_ERROR_LENGTH] + "..."
    return sanitized


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
    importance: str = "",
    category: str = "",
    sort: str = "",
    order: str = "",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Hotspot], int]:
    """List hotspots with optional filters, sorting and pagination."""
    stmt = select(Hotspot)
    if q:
        stmt = stmt.where(Hotspot.title.ilike(f"%{q}%"))
    if source:
        stmt = stmt.where(Hotspot.source_type == source)
    if importance:
        stmt = stmt.where(Hotspot.importance == importance)
    if category:
        stmt = stmt.where(Hotspot.category == category)

    sort_column = Hotspot.heat_score
    if sort == "published_at":
        sort_column = Hotspot.published_at
    sort_order = sort_column.desc() if order == "asc" else sort_column.desc()
    if order == "asc":
        sort_order = sort_column.asc()

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(sort_order).offset((page - 1) * limit).limit(limit)
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


async def list_keywords(session: AsyncSession) -> list[Keyword]:
    """Return all keywords ordered by creation time."""
    result = await session.execute(select(Keyword).order_by(Keyword.created_at.desc()))
    return list(result.scalars().all())


async def update_keyword(
    session: AsyncSession, keyword_id: str, payload: dict[str, Any]
) -> Keyword | None:
    """Update a keyword's active/notify flags."""
    keyword = await session.get(Keyword, keyword_id)
    if keyword is None:
        return None
    if "is_active" in payload:
        keyword.is_active = payload["is_active"]
    if "notify_on_match" in payload:
        keyword.notify_on_match = payload["notify_on_match"]
    await session.commit()
    await session.refresh(keyword)
    return keyword


async def delete_keyword(session: AsyncSession, keyword_id: str) -> bool:
    """Delete a keyword by id."""
    keyword = await session.get(Keyword, keyword_id)
    if keyword is None:
        return False
    await session.delete(keyword)
    await session.commit()
    return True


async def list_sources(session: AsyncSession) -> list[Source]:
    """Return all sources ordered by creation time."""
    result = await session.execute(select(Source).order_by(Source.created_at.desc()))
    return list(result.scalars().all())


async def update_source(
    session: AsyncSession, source_id: str, payload: dict[str, Any]
) -> Source | None:
    """Update source configuration."""
    source = await session.get(Source, source_id)
    if source is None:
        return None
    if "config" in payload:
        source.config = payload["config"]
    if "default_weight" in payload:
        source.default_weight = payload["default_weight"]
    if "fetch_interval_minutes" in payload:
        source.fetch_interval_minutes = payload["fetch_interval_minutes"]
    if "is_active" in payload:
        source.is_active = payload["is_active"]
    await session.commit()
    await session.refresh(source)
    return source


async def list_digests(session: AsyncSession, limit: int = 30) -> list[DailyDigest]:
    """Return recent daily digests ordered by date descending."""
    result = await session.execute(
        select(DailyDigest).order_by(DailyDigest.date.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_digest(session: AsyncSession) -> DailyDigest | None:
    """Return the most recent daily digest."""
    result = await session.execute(
        select(DailyDigest).order_by(DailyDigest.date.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def generate_digest(session: AsyncSession) -> DailyDigest:
    """Generate a daily digest from the top hotspots of the last 24 hours."""
    from datetime import UTC, date, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = (
        select(Hotspot)
        .where(Hotspot.published_at >= cutoff)
        .order_by(Hotspot.heat_score.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    hotspots = list(result.scalars().all())

    if not hotspots:
        # Fallback to the top 10 hotspots regardless of time window.
        stmt = select(Hotspot).order_by(Hotspot.heat_score.desc()).limit(10)
        result = await session.execute(stmt)
        hotspots = list(result.scalars().all())

    today = date.today()
    title = f"AIPulse AI 热点日报 · {today.strftime('%Y-%m-%d')}"
    lines = [f"# {title}", ""]
    for idx, hotspot in enumerate(hotspots, start=1):
        lines.append(f"{idx}. [{hotspot.title}]({hotspot.url})")
        if hotspot.summary:
            lines.append(f"   - {hotspot.summary}")
    lines.append("")
    lines.append(f"共收录 {len(hotspots)} 条热点。")
    content = "\n".join(lines)

    digest = DailyDigest(
        date=today,
        title=title,
        content=content,
        top_hotspot_ids=[h.id for h in hotspots],
    )
    session.add(digest)
    await session.commit()
    await session.refresh(digest)
    return digest


async def get_related_hotspots(
    session: AsyncSession, hotspot_id: str, limit: int = 10
) -> list[Hotspot]:
    """Return hotspots related by category or source type."""
    hotspot = await session.get(Hotspot, hotspot_id)
    if hotspot is None:
        return []
    stmt = select(Hotspot).where(Hotspot.id != hotspot_id)
    if hotspot.category:
        stmt = stmt.where(Hotspot.category == hotspot.category)
    else:
        stmt = stmt.where(Hotspot.source_type == hotspot.source_type)
    stmt = stmt.order_by(Hotspot.heat_score.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def archive_hotspot(session: AsyncSession, hotspot_id: str) -> dict[str, str] | None:
    """Archive a hotspot to Obsidian and return the written note paths."""
    hotspot = await session.get(Hotspot, hotspot_id)
    if hotspot is None:
        return None

    archiver = ObsidianArchiver(get_settings())
    if not archiver.is_configured():
        raise FileNotFoundError("Obsidian vault path is not configured or does not exist")

    content = _HotspotArchiveContent(
        platform=hotspot.source_type,
        url=hotspot.url,
        title=hotspot.title,
    )
    summary = SummaryResult(
        title=hotspot.title,
        summary=hotspot.summary or "",
        key_points=[],
        tags=[hotspot.category] if hotspot.category else [],
        raw_markdown=hotspot.summary or "",
    )
    paths = await archiver.archive(content, summary, transcript=None, settings=get_settings())

    hotspot.status = "archived"
    await session.commit()

    return {
        "source_note_path": str(paths.source_note_path),
        "summary_note_path": str(paths.summary_note_path),
    }


class _HotspotArchiveContent:
    """Minimal content wrapper for archiving a hotspot."""

    def __init__(self, platform: str, url: str, title: str) -> None:
        self.platform = platform
        self.url = url
        self.title = title
        self.author = None
