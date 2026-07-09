"""Hotspot repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.hotspot.models import Hotspot


class HotspotRepository:
    """Async repository for hotspot CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Hotspot:
        """Create and persist a new hotspot."""
        hotspot = Hotspot(**kwargs)
        self.session.add(hotspot)
        await self.session.flush()
        await self.session.refresh(hotspot)
        return hotspot

    async def list_recent(self, limit: int = 50) -> list[Hotspot]:
        """Return the most relevant recent hotspots."""
        result = await self.session.execute(
            select(Hotspot)
            .order_by(Hotspot.heat_score.desc(), Hotspot.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_canonical_url(self, canonical_url: str) -> Hotspot | None:
        """Fetch a hotspot by its canonical URL."""
        result = await self.session.execute(
            select(Hotspot).where(Hotspot.canonical_url == canonical_url)
        )
        return result.scalar_one_or_none()
