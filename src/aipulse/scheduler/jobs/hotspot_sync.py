"""Hotspot sync scheduled job."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from aipulse.collectors.registry import get_collector
from aipulse.hotspot.models import Source
from aipulse.hotspot.service import process_candidates
from aipulse.store.database import get_session_maker

logger = logging.getLogger(__name__)


async def sync_all_sources() -> int:
    """Fetch and process all active sources, returning total candidates processed."""
    processed = 0
    async with get_session_maker()() as session:
        sources = (
            (await session.execute(select(Source).where(Source.is_active.is_(True))))
            .scalars()
            .all()
        )
        for source in sources:
            collector = None
            try:
                collector_cls = get_collector(source.source_type)
                collector = collector_cls.from_source(source)
                try:
                    raw_items = await collector.fetch()
                    candidates = [collector.normalize(item) for item in raw_items]
                    processed += await process_candidates(session, candidates, source)
                finally:
                    await collector.close()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                logger.exception("Failed to sync source %s (%s)", source.id, source.name)
                source.last_error = str(exc)
                source.failed_at = datetime.now(UTC)
                try:
                    await session.commit()
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to persist source error for %s", source.id)
    return processed
