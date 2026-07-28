"""FollowedUpCollection repository: Protocol + SQLAlchemy implementation.

Spec §5 / Phase 8 A4 FIX.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, Sequence
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.followed_up_collections import FollowedUpCollection
from aipulse.store.models import now_utc


def make_uuid() -> str:
    """32-char UUID4 hex without dashes (project convention)."""
    return uuid4().hex


class FollowedUpCollectionNotFoundError(Exception):
    """The requested FollowedUpCollection id does not exist."""


class FollowedUpCollectionRecord:
    """Immutable snapshot of a FollowedUpCollection row."""

    __slots__ = (
        "_initialized",
        "id",
        "followed_up_id",
        "platform_collection_id",
        "title",
        "description",
        "video_count",
        "last_synced_at",
        "created_at",
        "updated_at",
    )

    def __init__(self, row: FollowedUpCollection) -> None:
        object.__setattr__(self, "_initialized", False)
        self.id: str = row.id
        self.followed_up_id: str = row.followed_up_id
        self.platform_collection_id: str = row.platform_collection_id
        self.title: str = row.title
        self.description: Optional[str] = row.description
        self.video_count: int = row.video_count
        self.last_synced_at: Optional[datetime] = row.last_synced_at
        self.created_at: datetime = row.created_at
        self.updated_at: datetime = row.updated_at
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_initialized", False):
            raise AttributeError(
                f"FollowedUpCollectionRecord is immutable (cannot set {name!r})"
            )
        object.__setattr__(self, name, value)


class FollowedUpCollectionRepository(Protocol):
    """Data-access interface for FollowedUpCollection."""

    async def find_by_id(self, collection_id: str) -> FollowedUpCollectionRecord | None: ...

    async def list_by_followed_up(
        self, followed_up_id: str
    ) -> Sequence[FollowedUpCollectionRecord]: ...

    async def upsert_by_platform_id(
        self,
        *,
        followed_up_id: str,
        platform_collection_id: str,
        title: str,
        description: Optional[str],
        video_count: int,
    ) -> FollowedUpCollectionRecord: ...

    async def delete(self, collection_id: str) -> None: ...


class SqlAlchemyFollowedUpCollectionRepository:
    """Async SQLAlchemy implementation of :class:`FollowedUpCollectionRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, collection_id: str) -> FollowedUpCollectionRecord | None:
        row = await self._session.get(FollowedUpCollection, collection_id)
        return FollowedUpCollectionRecord(row) if row else None

    async def list_by_followed_up(
        self, followed_up_id: str
    ) -> Sequence[FollowedUpCollectionRecord]:
        stmt = (
            select(FollowedUpCollection)
            .where(FollowedUpCollection.followed_up_id == followed_up_id)
            .order_by(FollowedUpCollection.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [FollowedUpCollectionRecord(r) for r in result.scalars().all()]

    async def upsert_by_platform_id(
        self,
        *,
        followed_up_id: str,
        platform_collection_id: str,
        title: str,
        description: Optional[str],
        video_count: int,
    ) -> FollowedUpCollectionRecord:
        """Insert or update by the (followed_up_id, platform_collection_id) key.

        The collector calls this every sync tick so we want a single round
        trip and a stable id. Uses SQLite's ON CONFLICT for portability
        (Postgres would need ``postgresql.insert`` with ``on_conflict``).
        """
        now = now_utc()
        stmt = sqlite_insert(FollowedUpCollection).values(
            id=make_uuid(),
            followed_up_id=followed_up_id,
            platform_collection_id=platform_collection_id,
            title=title,
            description=description,
            video_count=video_count,
            last_synced_at=now,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["followed_up_id", "platform_collection_id"],
            set_={
                "title": title,
                "description": description,
                "video_count": video_count,
                "last_synced_at": now,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)

        select_stmt = select(FollowedUpCollection).where(
            FollowedUpCollection.followed_up_id == followed_up_id,
            FollowedUpCollection.platform_collection_id == platform_collection_id,
        )
        row = (await self._session.execute(select_stmt)).scalar_one()
        return FollowedUpCollectionRecord(row)

    async def delete(self, collection_id: str) -> None:
        result = await self._session.execute(
            delete(FollowedUpCollection).where(FollowedUpCollection.id == collection_id)
        )
        if result.rowcount == 0:
            raise FollowedUpCollectionNotFoundError(
                f"FollowedUpCollection id={collection_id} not found"
            )