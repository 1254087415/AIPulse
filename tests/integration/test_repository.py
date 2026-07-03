"""Repository CRUD smoke tests."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.core.config import AppSettings, reset_settings
from aipulse.store.database import (
    close_db,
    configure_test_database,
    get_session_maker,
    init_db,
)
from aipulse.store.repository import (
    RssEntryRepository,
    RssFeedRepository,
    TaskRepository,
)


@pytest.fixture
async def db_session(tmp_path: Path) -> AsyncSession:
    reset_settings()
    settings = AppSettings(
        data_dir=tmp_path / "data",
        download_dir=tmp_path / "data" / "downloads",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aipulse.db",
    )
    await configure_test_database(settings)
    await init_db()
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
    await close_db()


@pytest.mark.integration
async def test_task_repository_create_and_get(db_session: AsyncSession) -> None:
    repo = TaskRepository(db_session)
    task = await repo.create("https://example.com", content_type="article")
    assert task.id
    assert task.url == "https://example.com"
    assert task.content_type == "article"

    fetched = await repo.get_by_id(task.id)
    assert fetched is not None
    assert fetched.id == task.id


@pytest.mark.integration
async def test_task_repository_update_status(db_session: AsyncSession) -> None:
    repo = TaskRepository(db_session)
    task = await repo.create("https://example.com")
    updated = await repo.update_status(task.id, "running", "busy")
    assert updated is not None
    assert updated.status == "running"
    assert updated.error_message == "busy"


@pytest.mark.integration
async def test_task_repository_update_fields(db_session: AsyncSession) -> None:
    repo = TaskRepository(db_session)
    task = await repo.create("https://example.com")
    updated = await repo.update_fields(task.id, title="Example", summary="summary text")
    assert updated is not None
    assert updated.title == "Example"
    assert updated.summary == "summary text"


@pytest.mark.integration
async def test_task_repository_list_recent_and_pending(db_session: AsyncSession) -> None:
    repo = TaskRepository(db_session)
    await repo.create("https://a.com")
    task = await repo.create("https://b.com")
    await repo.update_status(task.id, "completed")
    recent = await repo.list_recent(limit=10)
    assert len(recent) >= 2
    pending = await repo.list_pending()
    assert len(pending) >= 1
    assert any(t.url == "https://a.com" for t in pending)


@pytest.mark.integration
async def test_rss_feed_repository_create_and_get(db_session: AsyncSession) -> None:
    repo = RssFeedRepository(db_session)
    feed = await repo.create("https://example.com/feed", title="Example Feed")
    assert feed.id
    fetched = await repo.get_by_url("https://example.com/feed")
    assert fetched is not None
    assert fetched.title == "Example Feed"


@pytest.mark.integration
async def test_rss_feed_repository_update_last_fetched(db_session: AsyncSession) -> None:
    repo = RssFeedRepository(db_session)
    feed = await repo.create("https://example.com/feed")
    updated = await repo.update_last_fetched(feed.id)
    assert updated is not None
    assert updated.last_fetched_at is not None


@pytest.mark.integration
async def test_rss_entry_repository_create_and_mark_processed(
    db_session: AsyncSession,
) -> None:
    feed_repo = RssFeedRepository(db_session)
    feed = await feed_repo.create("https://example.com/feed")
    entry_repo = RssEntryRepository(db_session)
    entry = await entry_repo.create(feed.id, "https://example.com/post", title="Post")
    assert entry.id

    unprocessed = await entry_repo.list_unprocessed(feed_id=feed.id)
    assert len(unprocessed) == 1

    marked = await entry_repo.mark_processed(entry.id)
    assert marked is not None
    assert marked.processed is True

    unprocessed = await entry_repo.list_unprocessed()
    assert len(unprocessed) == 0
