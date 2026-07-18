"""Shared pytest fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.core.config import get_settings
from aipulse.server import app
from aipulse.store.database import (
    configure_test_database,
    get_session_maker,
    reset_db,
)

# Use an isolated in-memory database and enable automatic table creation for
# tests. Patching via environment variables ensures get_settings() callers
# (including the server lifespan) observe the same test configuration.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")

# Override settings that may be loaded from the local .env file so that tests
# observe the same values as the code defaults regardless of the developer's
# environment configuration.
os.environ["LLM_BASE_URL"] = "https://api.kimi.com/coding/v1"
os.environ["LLM_MODEL"] = "kimi-for-coding"
os.environ.pop("LLM_API_KEY", None)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _use_test_database() -> None:
    """Route all database access to an in-memory SQLite instance."""
    await configure_test_database(get_settings())


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with a clean schema."""
    await reset_db()
    async with get_session_maker()() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for the FastAPI app."""
    await reset_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
