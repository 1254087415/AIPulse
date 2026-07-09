"""APScheduler client singleton."""

from functools import lru_cache

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aipulse.core.config import get_settings


def build_sync_db_url(async_url: str) -> str:
    """APScheduler's SQLAlchemyJobStore requires a synchronous engine."""
    sync_url = async_url.replace("+aiomysql", "+pymysql")
    if sync_url.startswith("sqlite+aiosqlite://"):
        sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return sync_url


@lru_cache(maxsize=1)
def get_scheduler() -> AsyncIOScheduler:
    """Return the cached APScheduler instance configured with a sync job store."""
    settings = get_settings()
    return AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=build_sync_db_url(settings.database_url))}
    )
