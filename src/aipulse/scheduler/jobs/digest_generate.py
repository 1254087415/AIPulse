"""Daily digest scheduled job."""

from aipulse.hotspot.service import generate_digest
from aipulse.store.database import get_session_maker


async def generate_daily_digest() -> None:
    """Generate daily digest of top hotspots and persist it."""
    async with get_session_maker()() as session:
        await generate_digest(session)
