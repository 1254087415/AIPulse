"""Unit tests for FollowedUpCollectionRepository (Phase 8 A4 FIX).

The contract is the spec §5 surface:

- ``find_by_id(collection_id)``
- ``list_by_followed_up(followed_up_id)``
- ``upsert_by_platform_id(followed_up_id, platform_collection_id, title,
  description, video_count)``
- ``delete(collection_id)``
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.followed_up import FollowedUp
from aipulse.models.followed_up_collections import FollowedUpCollection
from aipulse.repositories.followed_up_collection_repo import (
    FollowedUpCollectionNotFoundError,
    FollowedUpCollectionRecord,
    FollowedUpCollectionRepository,
    SqlAlchemyFollowedUpCollectionRepository,
)


async def _seed_followed_up(session: AsyncSession) -> str:
    row = FollowedUp(
        id="fup_test_seed",
        platform="bilibili",
        uid="1111111",
        display_name="SeedUP",
        profile_url="https://space.bilibili.com/1111111",
        collector_strategy="uapi",
    )
    session.add(row)
    await session.flush()
    return row.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_creates_new_collection(db_session: AsyncSession) -> None:
    """First upsert must create a row keyed on (followed_up_id, platform_collection_id)."""
    followed_up_id = await _seed_followed_up(db_session)

    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)
    record = await repo.upsert_by_platform_id(
        followed_up_id=followed_up_id,
        platform_collection_id="col_001",
        title="Reading List",
        description="hot takes",
        video_count=12,
    )

    assert record.id
    assert record.followed_up_id == followed_up_id
    assert record.platform_collection_id == "col_001"
    assert record.title == "Reading List"
    assert record.description == "hot takes"
    assert record.video_count == 12

    refreshed = await db_session.get(FollowedUpCollection, record.id)
    assert refreshed is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_updates_existing_collection(db_session: AsyncSession) -> None:
    """A second upsert for the same key must update, not duplicate."""
    followed_up_id = await _seed_followed_up(db_session)
    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)

    first = await repo.upsert_by_platform_id(
        followed_up_id=followed_up_id,
        platform_collection_id="col_002",
        title="Original",
        description=None,
        video_count=3,
    )
    second = await repo.upsert_by_platform_id(
        followed_up_id=followed_up_id,
        platform_collection_id="col_002",
        title="Renamed",
        description="now documented",
        video_count=5,
    )

    assert first.id == second.id
    assert second.title == "Renamed"
    assert second.description == "now documented"
    assert second.video_count == 5

    listed = await repo.list_by_followed_up(followed_up_id)
    assert len(listed) == 1
    assert listed[0].id == second.id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_by_followed_up_filters_other_ups(
    db_session: AsyncSession,
) -> None:
    """list_by_followed_up must only return rows for the requested followed_up."""
    fu_a = await _seed_followed_up(db_session)
    other = FollowedUp(
        id="fup_other",
        platform="bilibili",
        uid="2222222",
        display_name="OtherUP",
        profile_url="https://space.bilibili.com/2222222",
        collector_strategy="uapi",
    )
    db_session.add(other)
    await db_session.flush()

    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)
    await repo.upsert_by_platform_id(
        followed_up_id=fu_a,
        platform_collection_id="col_a",
        title="A",
        description=None,
        video_count=1,
    )
    await repo.upsert_by_platform_id(
        followed_up_id="fup_other",
        platform_collection_id="col_b",
        title="B",
        description=None,
        video_count=1,
    )

    a_listed = await repo.list_by_followed_up(fu_a)
    assert len(a_listed) == 1
    assert a_listed[0].platform_collection_id == "col_a"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_by_id_returns_none_when_missing(
    db_session: AsyncSession,
) -> None:
    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)
    assert await repo.find_by_id("does-not-exist") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_removes_row(db_session: AsyncSession) -> None:
    """delete must hard-remove the row and raise when missing."""
    followed_up_id = await _seed_followed_up(db_session)
    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)
    record = await repo.upsert_by_platform_id(
        followed_up_id=followed_up_id,
        platform_collection_id="col_del",
        title="Bye",
        description=None,
        video_count=0,
    )

    await repo.delete(record.id)
    assert await repo.find_by_id(record.id) is None
    assert await db_session.get(FollowedUpCollection, record.id) is None

    with pytest.raises(FollowedUpCollectionNotFoundError):
        await repo.delete(record.id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_record_is_immutable_snapshot(
    db_session: AsyncSession,
) -> None:
    """FollowedUpCollectionRecord must use __slots__ (immutable snapshot)."""
    followed_up_id = await _seed_followed_up(db_session)
    repo: FollowedUpCollectionRepository = SqlAlchemyFollowedUpCollectionRepository(db_session)
    record = await repo.upsert_by_platform_id(
        followed_up_id=followed_up_id,
        platform_collection_id="col_slots",
        title="Slots",
        description=None,
        video_count=0,
    )
    assert isinstance(record, FollowedUpCollectionRecord)
    assert hasattr(record, "__slots__")
    with pytest.raises(AttributeError):
        record.title = "hijack"  # type: ignore[misc]