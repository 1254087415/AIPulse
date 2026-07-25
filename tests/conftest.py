"""Shared pytest fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.core.config import get_settings
from aipulse.models import (  # noqa: F401  registers new follow + learning tables
    followed_up,
    followed_up_collections,
    learning_events,
)
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
# Provide placeholder secrets so build_agent_executor() can construct the
# ChatOpenAI client without the underlying OpenAI SDK complaining about a
# missing api_key (it falls back to OPENAI_API_KEY env var, raising OpenAIError
# if neither is set). Placeholders are ignored by tests via test isolation
# fixtures; production code paths run only when the real key has been provided
# through PATCH /api/settings.
os.environ.setdefault("KIMI_API_KEY", "sk-test-placeholder-kimi")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder-openai")


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


@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route AppSettings.data_dir to a fresh tmp directory per test.

    Without this, tests that touch AppSettings would read the developer's
    real ``data/settings.json`` (and write to it), causing state to leak
    across tests and silently overriding monkeypatched env vars.
    """
    test_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(test_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(test_dir / "downloads"))
    get_settings.cache_clear()
