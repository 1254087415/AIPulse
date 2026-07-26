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
    get_engine,
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
os.environ["LLM_BASE_URL"] = "https://api.minimaxi.com/v1"
os.environ["LLM_MODEL"] = "MiniMax-M2.5"
# Strip any real keys the developer might have in their .env so tests always
# start from a known placeholder state.
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("KIMI_API_KEY", None)
# Provide placeholder secrets so build_agent_executor() can construct the
# ChatOpenAI client without the underlying OpenAI SDK complaining about a
# missing api_key (it falls back to OPENAI_API_KEY env var, raising OpenAIError
# if neither is set). Placeholders are ignored by tests via test isolation
# fixtures; production code paths run only when the real key has been provided
# through PATCH /api/settings.
os.environ["LLM_API_KEY"] = "sk-test-placeholder-llm"
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder-openai")


@pytest_asyncio.fixture(autouse=True)
async def _isolate_db_and_settings(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[None, None]:
    """Per-test: redirect data_dir + refresh DB engine + reset schema.

    Why per-test instead of session-scope: ``configure_test_database`` caches
    the engine URL inside ``_engine_override`` and ``isolate_data_dir`` clears
    ``get_settings`` between tests. A session-scope wiring pins the engine
    to the URL captured at session start — so once ``DATABASE_URL`` flips to
    ``:memory:`` after that capture, subsequent ``reset_db()`` / DB-backed
    fixtures still hit the *real* ``data/aipulse.db``. Recreating the
    override each test guarantees the engine always matches the current
    settings and ``data_dir`` always points to a tmp location so the
    developer's real ``data/settings.json`` is never read or written.

    Also ``reset_db()`` so every test sees a fresh, fully-migrated schema
    regardless of which other tests ran earlier — the old session-scope
    setup leaked tables across tests because the in-memory SQLite instance
    was reused; per-test isolation is the canonical pytest pattern and is
    what these tests actually require.
    """
    test_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(test_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(test_dir / "downloads"))
    get_settings.cache_clear()
    # Rebuild the DB engine so any cached get_engine() / get_session_maker()
    # lookups see the in-memory URL captured from the freshly cleared settings.
    await configure_test_database(get_settings())
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    # Drop + recreate every table so any test that calls get_session_maker()
    # directly (without using ``client`` / ``db_session``) still sees the
    # expected schema.
    await reset_db()
    yield


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
