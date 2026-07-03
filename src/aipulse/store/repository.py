"""Repository layer for data access."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.store.models import RssEntry, RssFeed, Task


class TaskRepository:
    """Repository for Task entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        url: str,
        content_type: str = "unknown",
        source: str = "menubar",
    ) -> Task:
        """Create a new task."""
        task = Task(url=url, content_type=content_type, source=source)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: str) -> Task | None:
        """Fetch a task by its ID."""
        return await self.session.get(Task, task_id)

    async def update_status(
        self,
        task_id: str,
        status: str,
        error_message: str | None = None,
    ) -> Task | None:
        """Update a task's status and return the refreshed task."""
        task = await self.get_by_id(task_id)
        if task is None:
            return None
        task.status = status
        if error_message is not None:
            task.error_message = error_message
        task.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update_fields(self, task_id: str, **fields: Any) -> Task | None:
        """Update arbitrary task fields and return the refreshed task."""
        task = await self.get_by_id(task_id)
        if task is None:
            return None
        for key, value in fields.items():
            setattr(task, key, value)
        task.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def list_recent(self, limit: int = 50) -> list[Task]:
        """List recent tasks ordered by creation time."""
        result = await self.session.execute(
            select(Task).order_by(Task.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_pending(self) -> list[Task]:
        """List tasks with a pending status."""
        result = await self.session.execute(
            select(Task).where(Task.status == "pending").order_by(Task.created_at.asc())
        )
        return list(result.scalars().all())


class RssFeedRepository:
    """Repository for RssFeed entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        url: str,
        title: str | None = None,
        auto_process: bool = True,
    ) -> RssFeed:
        """Create a new RSS feed."""
        feed = RssFeed(url=url, title=title, auto_process=auto_process)
        self.session.add(feed)
        await self.session.flush()
        await self.session.refresh(feed)
        return feed

    async def get_by_url(self, url: str) -> RssFeed | None:
        """Fetch a feed by URL."""
        result = await self.session.execute(select(RssFeed).where(RssFeed.url == url))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[RssFeed]:
        """List all RSS feeds."""
        result = await self.session.execute(select(RssFeed))
        return list(result.scalars().all())

    async def update_last_fetched(self, feed_id: str) -> RssFeed | None:
        """Update the last_fetched_at timestamp and return the refreshed feed."""
        feed = await self.session.get(RssFeed, feed_id)
        if feed is None:
            return None
        feed.last_fetched_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(feed)
        return feed


class RssEntryRepository:
    """Repository for RssEntry entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        feed_id: str,
        url: str,
        title: str | None = None,
        published_at: datetime | None = None,
    ) -> RssEntry:
        """Create a new RSS entry."""
        entry = RssEntry(
            feed_id=feed_id,
            url=url,
            title=title,
            published_at=published_at,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_by_url(self, url: str) -> RssEntry | None:
        """Fetch an RSS entry by URL."""
        result = await self.session.execute(select(RssEntry).where(RssEntry.url == url))
        return result.scalar_one_or_none()

    async def list_unprocessed(self, feed_id: str | None = None) -> list[RssEntry]:
        """List unprocessed RSS entries."""
        stmt = select(RssEntry).where(RssEntry.processed.is_(False))
        if feed_id:
            stmt = stmt.where(RssEntry.feed_id == feed_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_processed(self, entry_id: str) -> RssEntry | None:
        """Mark an RSS entry as processed and return the refreshed entry."""
        entry = await self.session.get(RssEntry, entry_id)
        if entry is None:
            return None
        entry.processed = True
        await self.session.flush()
        await self.session.refresh(entry)
        return entry
