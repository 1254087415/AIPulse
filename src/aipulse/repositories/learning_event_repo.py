"""LearningEvent repository: Protocol interface + SQLAlchemy implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.learning_events import LearningEvent
from aipulse.store.models import now_utc


def make_uuid() -> str:
    """32-char UUID4 hex without dashes (project convention)."""
    return uuid4().hex


class LearningEventNotFoundError(Exception):
    """The requested LearningEvent id does not exist."""


class LearningEventRecord:
    """Immutable snapshot of a LearningEvent row."""

    __slots__ = (
        "id",
        "hotspot_id",
        "followed_up_id",
        "platform",
        "title",
        "summary_note_path",
        "scheduled_at",
        "estimated_minutes",
        "obsidian_task_created",
        "apple_reminder_id",
        "apple_reminders_list",
        "completed_at",
        "learning_status",
        "created_at",
        "updated_at",
    )

    def __init__(self, row: LearningEvent) -> None:
        self.id: str = row.id
        self.hotspot_id: str = row.hotspot_id
        self.followed_up_id: str = row.followed_up_id
        self.platform: str = row.platform
        self.title: str = row.title
        self.summary_note_path: Optional[str] = row.summary_note_path
        self.scheduled_at: datetime = row.scheduled_at
        self.estimated_minutes: int = row.estimated_minutes
        self.obsidian_task_created: bool = row.obsidian_task_created
        self.apple_reminder_id: Optional[str] = row.apple_reminder_id
        self.apple_reminders_list: str = row.apple_reminders_list
        self.completed_at: Optional[datetime] = row.completed_at
        self.learning_status: str = row.learning_status
        self.created_at: datetime = row.created_at
        self.updated_at: datetime = row.updated_at


class LearningEventRepository(Protocol):
    """Data-access interface for LearningEvent."""

    async def find_by_id(self, event_id: str) -> LearningEventRecord | None: ...

    async def list_upcoming(
        self,
        *,
        platform: Optional[str] = None,
        learning_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[LearningEventRecord]: ...

    async def create(
        self,
        *,
        hotspot_id: str,
        followed_up_id: str,
        title: str,
        scheduled_at: Optional[datetime] = None,
        estimated_minutes: int = 15,
        summary_note_path: Optional[str] = None,
        platform: str = "bilibili",
        apple_reminders_list: str = "学习",
    ) -> LearningEventRecord: ...

    async def mark_completed(self, event_id: str) -> LearningEventRecord: ...

    async def update_status(
        self, event_id: str, learning_status: str
    ) -> LearningEventRecord: ...


class SqlAlchemyLearningEventRepository:
    """Async SQLAlchemy implementation of :class:`LearningEventRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, event_id: str) -> LearningEventRecord | None:
        result = await self._session.execute(
            select(LearningEvent).where(LearningEvent.id == event_id)
        )
        row = result.scalar_one_or_none()
        return LearningEventRecord(row) if row else None

    async def list_upcoming(
        self,
        *,
        platform: Optional[str] = None,
        learning_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[LearningEventRecord]:
        stmt = (
            select(LearningEvent)
            .where(LearningEvent.completed_at.is_(None))
            .order_by(LearningEvent.scheduled_at.asc())
            .limit(limit)
            .offset(offset)
        )
        if platform:
            stmt = stmt.where(LearningEvent.platform == platform)
        if learning_status:
            stmt = stmt.where(LearningEvent.learning_status == learning_status)
        result = await self._session.execute(stmt)
        return [LearningEventRecord(r) for r in result.scalars().all()]

    async def create(
        self,
        *,
        hotspot_id: str,
        followed_up_id: str,
        title: str,
        scheduled_at: Optional[datetime] = None,
        estimated_minutes: int = 15,
        summary_note_path: Optional[str] = None,
        platform: str = "bilibili",
        apple_reminders_list: str = "学习",
    ) -> LearningEventRecord:
        row = LearningEvent(
            id=make_uuid(),
            hotspot_id=hotspot_id,
            followed_up_id=followed_up_id,
            title=title,
            scheduled_at=scheduled_at or now_utc(),
            estimated_minutes=estimated_minutes,
            summary_note_path=summary_note_path,
            platform=platform,
            apple_reminders_list=apple_reminders_list,
        )
        self._session.add(row)
        await self._session.flush()
        return LearningEventRecord(row)

    async def mark_completed(self, event_id: str) -> LearningEventRecord:
        return await self._update(event_id, completed_at=now_utc(), learning_status="mastered")

    async def update_status(
        self, event_id: str, learning_status: str
    ) -> LearningEventRecord:
        return await self._update(event_id, learning_status=learning_status)

    async def _update(self, event_id: str, **values: object) -> LearningEventRecord:
        values = dict(values)
        if not values:
            raise ValueError("_update() requires at least one field")
        stmt = (
            update(LearningEvent)
            .where(LearningEvent.id == event_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise LearningEventNotFoundError(f"LearningEvent id={event_id} not found")

        refreshed = await self.find_by_id(event_id)
        if refreshed is None:  # pragma: no cover - defensive
            raise LearningEventNotFoundError(
                f"LearningEvent id={event_id} disappeared after update"
            )
        return refreshed
