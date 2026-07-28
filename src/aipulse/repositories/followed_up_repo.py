"""FollowedUp repository: Protocol interface + SQLAlchemy implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional, Protocol, Sequence
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.followed_up import FollowedUp


def make_uuid() -> str:
    """32-char UUID4 hex without dashes (project convention)."""
    return uuid4().hex


# ==============================================================
# Errors
# ==============================================================


class FollowError(Exception):
    """Base error for the follow module."""


class DuplicateFollowedUpError(FollowError):
    """An active (platform, uid) row already exists."""

    def __init__(self, message: str, *, existing_id: str | None = None) -> None:
        super().__init__(message)
        self.existing_id = existing_id


class FollowedUpNotFoundError(FollowError):
    """The requested FollowedUp id does not exist."""


# ==============================================================
# Immutable record (decouples callers from ORM Session)
# ==============================================================


class FollowedUpRecord:
    """Immutable snapshot of a FollowedUp row."""

    __slots__ = (
        "id",
        "platform",
        "uid",
        "display_name",
        "profile_url",
        "collector_strategy",
        "last_cursor_id",
        "fetch_interval_minutes",
        "is_active",
        "status",
        "health",
        "last_checked_at",
        "last_error",
        "failed_at",
        "deleted_at",
        "config",
        "created_at",
        "updated_at",
    )

    def __init__(self, row: FollowedUp) -> None:
        self.id: str = row.id
        self.platform: str = row.platform
        self.uid: str = row.uid
        self.display_name: str = row.display_name
        self.profile_url: str = row.profile_url
        self.collector_strategy: str = row.collector_strategy
        self.last_cursor_id: Optional[str] = row.last_cursor_id
        self.fetch_interval_minutes: int = row.fetch_interval_minutes
        self.is_active: bool = row.is_active
        self.status: str = row.status
        self.health: str = row.health
        self.last_checked_at: Optional[datetime] = row.last_checked_at
        self.last_error: Optional[str] = row.last_error
        self.failed_at: Optional[datetime] = row.failed_at
        self.deleted_at: Optional[datetime] = row.deleted_at
        self.config: Optional[dict[str, Any]] = row.config
        self.created_at: datetime = row.created_at
        self.updated_at: datetime = row.updated_at


# ==============================================================
# Protocol
# ==============================================================


class FollowedUpRepository(Protocol):
    """Data-access interface for FollowedUp."""

    async def find_by_id(self, followed_up_id: str) -> FollowedUpRecord | None: ...

    async def get_by_platform_uid(
        self, platform: str, uid: str
    ) -> FollowedUpRecord | None: ...

    async def list_all(
        self, *, include_deleted: bool = False
    ) -> Sequence[FollowedUpRecord]: ...

    async def count_active(self) -> int:
        """Count currently active FollowedUp rows (exclude soft-deleted)."""
        ...

    async def create(
        self,
        *,
        platform: str,
        uid: str,
        display_name: str,
        profile_url: str,
        collector_strategy: str = "uapi",
        fetch_interval_minutes: int = 30,
        config: Optional[dict[str, Any]] = None,
    ) -> FollowedUpRecord: ...

    async def update(
        self,
        followed_up_id: str,
        *,
        display_name: Optional[str] = None,
        collector_strategy: Optional[str] = None,
        fetch_interval_minutes: Optional[int] = None,
        is_active: Optional[bool] = None,
        status: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> FollowedUpRecord: ...

    async def soft_delete(self, followed_up_id: str) -> FollowedUpRecord: ...


# ==============================================================
# SQLAlchemy implementation
# ==============================================================


class SqlAlchemyFollowedUpRepository:
    """Async SQLAlchemy implementation of :class:`FollowedUpRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, followed_up_id: str) -> FollowedUpRecord | None:
        result = await self._session.execute(
            select(FollowedUp).where(FollowedUp.id == followed_up_id)
        )
        row = result.scalar_one_or_none()
        return FollowedUpRecord(row) if row else None

    async def get_by_platform_uid(
        self, platform: str, uid: str
    ) -> FollowedUpRecord | None:
        """Return the active (non-deleted) row for the given platform+uid."""
        result = await self._session.execute(
            select(FollowedUp).where(
                FollowedUp.platform == platform,
                FollowedUp.uid == uid,
                FollowedUp.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        return FollowedUpRecord(row) if row else None

    async def list_all(
        self, *, include_deleted: bool = False
    ) -> Sequence[FollowedUpRecord]:
        stmt = select(FollowedUp).order_by(FollowedUp.created_at.desc())
        if not include_deleted:
            stmt = stmt.where(FollowedUp.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return [FollowedUpRecord(r) for r in result.scalars().all()]

    async def count_active(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count(FollowedUp.id)).where(FollowedUp.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def create(
        self,
        *,
        platform: str,
        uid: str,
        display_name: str,
        profile_url: str,
        collector_strategy: str = "uapi",
        fetch_interval_minutes: int = 30,
        config: Optional[dict[str, Any]] = None,
    ) -> FollowedUpRecord:
        existing = await self.get_by_platform_uid(platform, uid)
        if existing is not None:
            raise DuplicateFollowedUpError(
                f"FollowedUp {platform}:{uid} already exists (id={existing.id})",
                existing_id=existing.id,
            )

        row = FollowedUp(
            id=make_uuid(),
            platform=platform,
            uid=uid,
            display_name=display_name,
            profile_url=profile_url,
            collector_strategy=collector_strategy,
            fetch_interval_minutes=fetch_interval_minutes,
            config=config,
        )
        self._session.add(row)
        await self._session.flush()
        return FollowedUpRecord(row)

    async def update(
        self,
        followed_up_id: str,
        *,
        display_name: Optional[str] = None,
        collector_strategy: Optional[str] = None,
        fetch_interval_minutes: Optional[int] = None,
        is_active: Optional[bool] = None,
        status: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> FollowedUpRecord:
        values: dict[str, Any] = {}
        if display_name is not None:
            values["display_name"] = display_name
        if collector_strategy is not None:
            values["collector_strategy"] = collector_strategy
        if fetch_interval_minutes is not None:
            values["fetch_interval_minutes"] = fetch_interval_minutes
        if is_active is not None:
            values["is_active"] = is_active
        if status is not None:
            values["status"] = status
        if config is not None:
            values["config"] = config
        if not values:
            raise ValueError("update() requires at least one field")

        stmt = (
            update(FollowedUp)
            .where(FollowedUp.id == followed_up_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise FollowedUpNotFoundError(f"FollowedUp id={followed_up_id} not found")

        refreshed = await self.find_by_id(followed_up_id)
        if refreshed is None:  # pragma: no cover - defensive
            raise FollowedUpNotFoundError(
                f"FollowedUp id={followed_up_id} disappeared after update"
            )
        return refreshed

    async def soft_delete(self, followed_up_id: str) -> FollowedUpRecord:
        now = datetime.now(UTC)
        stmt = (
            update(FollowedUp)
            .where(FollowedUp.id == followed_up_id)
            .values(deleted_at=now, is_active=False)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise FollowedUpNotFoundError(f"FollowedUp id={followed_up_id} not found")

        refreshed = await self.find_by_id(followed_up_id)
        if refreshed is None:  # pragma: no cover - defensive
            raise FollowedUpNotFoundError(
                f"FollowedUp id={followed_up_id} disappeared after soft_delete"
            )
        return refreshed
