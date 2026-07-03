"""Database engine and session management singleton."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aipulse.core.config import AppSettings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the cached async database engine."""
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False, future=True)


@lru_cache(maxsize=1)
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the cached async session factory."""
    return async_sessionmaker(
        bind=get_engine(), class_=AsyncSession, expire_on_commit=False
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with get_session_maker()() as session:
        yield session


async def init_db() -> None:
    """Create all database tables."""
    from aipulse.store.models import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the cached database engine and clear related caches."""
    engine = get_engine()
    await engine.dispose()
    get_engine.cache_clear()
    get_session_maker.cache_clear()


async def reset_db() -> None:
    """Drop and recreate all database tables (useful in tests)."""
    from aipulse.store.models import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def configure_test_database(settings: AppSettings | None = None) -> None:
    """Configure an in-memory SQLite database for tests."""
    from aipulse.core.config import get_settings

    target = settings or get_settings()
    engine = create_async_engine(str(target.database_url), echo=False, future=True)
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    # Rebind the cached engine to the test engine.
    get_engine.__wrapped__ = lambda _settings=target: create_async_engine(
        str(_settings.database_url), echo=False, future=True
    )
    _ = engine
