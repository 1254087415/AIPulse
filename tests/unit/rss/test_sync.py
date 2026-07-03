"""Tests for RSS synchronization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.core.content_router import ContentType
from aipulse.rss.parser import RssEntryItem, RssParser
from aipulse.rss.sync import RssSync, start_scheduler
from aipulse.store.models import RssFeed


@pytest.fixture
def feed_repo() -> MagicMock:
    return MagicMock(spec=["list_all", "update_last_fetched"])


@pytest.fixture
def entry_repo() -> MagicMock:
    return MagicMock(spec=["get_by_url", "create"])


@pytest.fixture
def task_repo() -> MagicMock:
    return MagicMock(spec=["create"])


@pytest.fixture
def parser() -> RssParser:
    parser = RssParser()
    parser.parse_feed = AsyncMock(return_value=[
        RssEntryItem(title="Article 1", url="https://example.com/1", published_at=None),
        RssEntryItem(title="Article 2", url="https://example.com/2", published_at=None),
    ])
    return parser


@pytest.fixture
def rss_sync(
    feed_repo: MagicMock,
    entry_repo: MagicMock,
    task_repo: MagicMock,
    parser: RssParser,
) -> RssSync:
    return RssSync(
        feed_repo=feed_repo,
        entry_repo=entry_repo,
        task_repo=task_repo,
        parser=parser,
    )


@pytest.mark.unit
async def test_sync_once_creates_entries_and_tasks(rss_sync: RssSync) -> None:
    feed = RssFeed(
        id="feed-1",
        url="https://example.com/feed.xml",
        auto_process=True,
    )
    rss_sync.feed_repo.list_all = AsyncMock(return_value=[feed])
    rss_sync.entry_repo.get_by_url = AsyncMock(return_value=None)
    rss_sync.entry_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.task_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.feed_repo.update_last_fetched = AsyncMock(return_value=feed)

    with patch("aipulse.rss.sync.classify_url", return_value=ContentType.GENERIC_ARTICLE):
        result = await rss_sync.sync_once()

    assert result == {"entries_created": 2, "tasks_created": 2}
    assert rss_sync.entry_repo.create.await_count == 2
    assert rss_sync.task_repo.create.await_count == 2
    rss_sync.feed_repo.update_last_fetched.assert_awaited_once_with("feed-1")


@pytest.mark.unit
async def test_sync_once_skips_existing_entries(rss_sync: RssSync) -> None:
    feed = RssFeed(
        id="feed-1",
        url="https://example.com/feed.xml",
        auto_process=True,
    )
    rss_sync.feed_repo.list_all = AsyncMock(return_value=[feed])
    rss_sync.entry_repo.get_by_url = AsyncMock(return_value=MagicMock())
    rss_sync.entry_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.task_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.feed_repo.update_last_fetched = AsyncMock(return_value=feed)

    result = await rss_sync.sync_once()

    assert result == {"entries_created": 0, "tasks_created": 0}
    rss_sync.entry_repo.create.assert_not_awaited()
    rss_sync.task_repo.create.assert_not_awaited()


@pytest.mark.unit
async def test_sync_once_no_tasks_when_auto_process_false(rss_sync: RssSync) -> None:
    feed = RssFeed(
        id="feed-1",
        url="https://example.com/feed.xml",
        auto_process=False,
    )
    rss_sync.feed_repo.list_all = AsyncMock(return_value=[feed])
    rss_sync.entry_repo.get_by_url = AsyncMock(return_value=None)
    rss_sync.entry_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.task_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.feed_repo.update_last_fetched = AsyncMock(return_value=feed)

    result = await rss_sync.sync_once()

    assert result == {"entries_created": 2, "tasks_created": 0}
    rss_sync.task_repo.create.assert_not_awaited()


@pytest.mark.unit
async def test_sync_once_handles_feed_failure(rss_sync: RssSync) -> None:
    feed = RssFeed(
        id="feed-1",
        url="https://example.com/feed.xml",
        auto_process=True,
    )
    rss_sync.feed_repo.list_all = AsyncMock(return_value=[feed])
    rss_sync.parser.parse_feed = AsyncMock(side_effect=RuntimeError("parse failed"))

    result = await rss_sync.sync_once()

    assert result == {"entries_created": 0, "tasks_created": 0}


@pytest.mark.unit
async def test_sync_once_skips_entries_without_url(rss_sync: RssSync) -> None:
    rss_sync.parser.parse_feed = AsyncMock(return_value=[
        RssEntryItem(title="No URL", url="", published_at=None),
    ])
    feed = RssFeed(
        id="feed-1",
        url="https://example.com/feed.xml",
        auto_process=True,
    )
    rss_sync.feed_repo.list_all = AsyncMock(return_value=[feed])
    rss_sync.entry_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.task_repo.create = AsyncMock(return_value=MagicMock())
    rss_sync.feed_repo.update_last_fetched = AsyncMock(return_value=feed)

    result = await rss_sync.sync_once()

    assert result == {"entries_created": 0, "tasks_created": 0}
    rss_sync.entry_repo.create.assert_not_awaited()


@pytest.mark.unit
def test_start_scheduler_adds_job() -> None:
    sync = MagicMock(spec=RssSync)
    scheduler = MagicMock()

    result = start_scheduler(sync, interval_minutes=10, scheduler=scheduler)

    assert result is scheduler
    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args.kwargs
    assert call_kwargs["id"] == "rss_sync"
    assert call_kwargs["replace_existing"] is True
    assert call_kwargs["trigger"].interval.total_seconds() == 600


@pytest.mark.unit
def test_start_scheduler_starts_background_scheduler() -> None:
    sync = MagicMock(spec=RssSync)
    scheduler = MagicMock()

    start_scheduler(sync, scheduler=scheduler)

    scheduler.start.assert_not_called()

    with patch("apscheduler.schedulers.background.BackgroundScheduler") as mock_cls:
        mock_scheduler = MagicMock()
        mock_cls.return_value = mock_scheduler
        start_scheduler(sync)
        mock_scheduler.start.assert_called_once()
