"""RSS synchronization task."""

import logging
from typing import Any

from aipulse.core.content_router import classify_url
from aipulse.rss.parser import RssParser
from aipulse.store.repository import (
    RssEntryRepository,
    RssFeedRepository,
    TaskRepository,
)

logger = logging.getLogger(__name__)


class RssSync:
    """Sync RSS feeds, store entries, and submit processing tasks."""

    def __init__(
        self,
        feed_repo: RssFeedRepository,
        entry_repo: RssEntryRepository,
        task_repo: TaskRepository,
        parser: RssParser | None = None,
    ) -> None:
        self.feed_repo = feed_repo
        self.entry_repo = entry_repo
        self.task_repo = task_repo
        self.parser = parser or RssParser()

    async def sync_once(self) -> dict[str, int]:
        """Sync all feeds once and return counts of entries and tasks created."""
        feeds = await self.feed_repo.list_all()
        total_entries = 0
        total_tasks = 0
        for feed in feeds:
            try:
                entries, tasks = await self._sync_feed(feed.url, str(feed.id), feed.auto_process)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to sync feed %s: %s", feed.url, exc)
                continue
            total_entries += entries
            total_tasks += tasks
        return {"entries_created": total_entries, "tasks_created": total_tasks}

    async def _sync_feed(
        self,
        feed_url: str,
        feed_id: str,
        auto_process: bool,
    ) -> tuple[int, int]:
        """Sync a single feed and return (entries_created, tasks_created)."""
        items = await self.parser.parse_feed(feed_url)
        entries_created = 0
        tasks_created = 0
        for item in items:
            if not item.url:
                continue
            existing = await self.entry_repo.get_by_url(item.url)
            if existing is not None:
                continue
            await self.entry_repo.create(
                feed_id=feed_id,
                url=item.url,
                title=item.title,
                published_at=item.published_at,
            )
            entries_created += 1
            if auto_process:
                content_type = await classify_url(item.url)
                await self.task_repo.create(
                    url=item.url,
                    content_type=content_type.value,
                    source="rss",
                )
                tasks_created += 1
        await self.feed_repo.update_last_fetched(feed_id)
        return entries_created, tasks_created


def start_scheduler(
    sync: RssSync,
    interval_minutes: int = 15,
    scheduler: Any | None = None,
) -> Any:
    """Start an APScheduler background job to sync RSS feeds periodically.

    Args:
        sync: The RssSync instance to run.
        interval_minutes: Minutes between sync runs.
        scheduler: Optional existing scheduler instance. If None, a new
            BackgroundScheduler is created and started.

    Returns:
        The configured scheduler instance.
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()

    async def _job() -> None:
        await sync.sync_once()

    def _wrapper() -> None:
        import asyncio

        asyncio.run(_job())

    scheduler.add_job(
        _wrapper,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="rss_sync",
        replace_existing=True,
    )
    return scheduler
