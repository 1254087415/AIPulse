"""Integration tests for FollowedUp / LearningEvent repositories."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.followed_up import FollowedUp
from aipulse.models.learning_events import LearningEvent
from aipulse.repositories.followed_up_repo import (
    DuplicateFollowedUpError,
    FollowedUpNotFoundError,
    SqlAlchemyFollowedUpRepository,
)
from aipulse.repositories.learning_event_repo import (
    SqlAlchemyLearningEventRepository,
)


@pytest.mark.integration
async def test_create_followed_up_persists_row(db_session: AsyncSession):
    """Repository create round-trips a FollowedUp through the real DB."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    record = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    refreshed = await repo.find_by_id(record.id)
    assert refreshed is not None
    assert refreshed.platform == "bilibili"
    assert refreshed.uid == "1567748478"
    assert refreshed.display_name == "Miyabi"
    assert refreshed.profile_url == "https://space.bilibili.com/1567748478"
    assert refreshed.is_active is True
    assert refreshed.deleted_at is None


@pytest.mark.integration
async def test_create_duplicate_active_followed_up_raises(
    db_session: AsyncSession,
) -> None:
    """Duplicate (platform, uid) when active is rejected."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    with pytest.raises(DuplicateFollowedUpError):
        await repo.create(
            platform="bilibili",
            uid="1567748478",
            display_name="Miyabi 2",
            profile_url="https://space.bilibili.com/1567748478",
        )


@pytest.mark.integration
async def test_create_after_soft_delete_allowed(db_session: AsyncSession) -> None:
    """After a soft delete, re-adding the same (platform, uid) succeeds."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    first = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    await repo.soft_delete(first.id)
    await db_session.commit()

    reborn = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi again",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    assert reborn.id != first.id
    assert reborn.deleted_at is None


@pytest.mark.integration
async def test_get_by_platform_uid(db_session: AsyncSession) -> None:
    """find_by_platform_uid returns the active row, not the soft-deleted one."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    a = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()
    await repo.soft_delete(a.id)
    await db_session.commit()

    b = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi v2",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    active = await repo.get_by_platform_uid("bilibili", "1567748478")
    assert active is not None
    assert active.id == b.id
    assert active.display_name == "Miyabi v2"
    assert active.deleted_at is None


@pytest.mark.integration
async def test_list_all_excludes_soft_deleted(db_session: AsyncSession) -> None:
    """list_all(include_deleted=False) hides soft-deleted rows."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    a = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi A",
        profile_url="https://space.bilibili.com/1567748478",
    )
    b = await repo.create(
        platform="bilibili",
        uid="999",
        display_name="Other UP",
        profile_url="https://space.bilibili.com/999",
    )
    await db_session.commit()
    await repo.soft_delete(a.id)
    await db_session.commit()

    rows = await repo.list_all(include_deleted=False)
    ids = {r.id for r in rows}
    assert b.id in ids
    assert a.id not in ids


@pytest.mark.integration
async def test_list_all_include_deleted(db_session: AsyncSession) -> None:
    """list_all(include_deleted=True) returns both active and soft-deleted rows."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    a = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="A",
        profile_url="https://space.bilibili.com/1567748478",
    )
    b = await repo.create(
        platform="bilibili",
        uid="999",
        display_name="B",
        profile_url="https://space.bilibili.com/999",
    )
    await db_session.commit()
    await repo.soft_delete(a.id)
    await db_session.commit()

    rows = await repo.list_all(include_deleted=True)
    ids = {r.id for r in rows}
    assert {a.id, b.id} <= ids


@pytest.mark.integration
async def test_update_partial_fields(db_session: AsyncSession) -> None:
    """update() mutates only the supplied fields."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    record = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Original",
        profile_url="https://space.bilibili.com/1567748478",
        fetch_interval_minutes=30,
    )
    await db_session.commit()

    updated = await repo.update(
        record.id, display_name="Updated", fetch_interval_minutes=120
    )
    await db_session.commit()

    assert updated.display_name == "Updated"
    assert updated.fetch_interval_minutes == 120
    assert updated.platform == "bilibili"
    assert updated.uid == "1567748478"


@pytest.mark.integration
async def test_update_unknown_id_raises(db_session: AsyncSession) -> None:
    """update() against a missing id raises FollowedUpNotFoundError."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    with pytest.raises(FollowedUpNotFoundError):
        await repo.update("missing-id", display_name="x")


@pytest.mark.integration
async def test_soft_delete_records_timestamp(db_session: AsyncSession) -> None:
    """soft_delete() sets deleted_at and is_active=False."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    record = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="A",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    deleted = await repo.soft_delete(record.id)
    await db_session.commit()

    assert deleted.is_active is False
    assert deleted.deleted_at is not None


@pytest.mark.integration
async def test_soft_delete_unknown_id_raises(db_session: AsyncSession) -> None:
    repo = SqlAlchemyFollowedUpRepository(db_session)
    with pytest.raises(FollowedUpNotFoundError):
        await repo.soft_delete("missing-id")


@pytest.mark.integration
async def test_learning_event_create_and_list(db_session: AsyncSession) -> None:
    """LearningEventRepository persists and returns events ordered by scheduled_at."""
    from datetime import UTC, datetime, timedelta

    repo_up = SqlAlchemyFollowedUpRepository(db_session)
    up = await repo_up.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    # Need a hotspot to satisfy the FK
    from aipulse.hotspot.models import Hotspot, Source

    source = Source(name="s", source_type="rss", collector_class="rss")
    db_session.add(source)
    await db_session.flush()
    hotspot = Hotspot(
        title="t",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss",
    )
    db_session.add(hotspot)
    await db_session.flush()

    repo_le = SqlAlchemyLearningEventRepository(db_session)
    later = datetime.now(UTC) + timedelta(days=1)
    earlier = datetime.now(UTC) + timedelta(hours=1)

    await repo_le.create(
        hotspot_id=hotspot.id,
        followed_up_id=up.id,
        title="Later event",
        scheduled_at=later,
    )
    await repo_le.create(
        hotspot_id=hotspot.id,
        followed_up_id=up.id,
        title="Earlier event",
        scheduled_at=earlier,
    )
    await db_session.commit()

    upcoming = await repo_le.list_upcoming()
    assert [e.title for e in upcoming] == ["Earlier event", "Later event"]


@pytest.mark.integration
async def test_learning_event_mark_completed(db_session: AsyncSession) -> None:
    """mark_completed() sets status to mastered and completed_at."""
    from aipulse.hotspot.models import Hotspot, Source

    repo_up = SqlAlchemyFollowedUpRepository(db_session)
    up = await repo_up.create(
        platform="bilibili",
        uid="1567748478",
        display_name="Miyabi",
        profile_url="https://space.bilibili.com/1567748478",
    )
    await db_session.commit()

    source = Source(name="s", source_type="rss", collector_class="rss")
    db_session.add(source)
    await db_session.flush()
    hotspot = Hotspot(
        title="t",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        source_id=source.id,
        source_type="rss",
    )
    db_session.add(hotspot)
    await db_session.flush()

    repo_le = SqlAlchemyLearningEventRepository(db_session)
    event = await repo_le.create(
        hotspot_id=hotspot.id,
        followed_up_id=up.id,
        title="Event",
    )
    await db_session.commit()

    completed = await repo_le.mark_completed(event.id)
    await db_session.commit()

    assert completed.completed_at is not None
    assert completed.learning_status == "mastered"


@pytest.mark.integration
async def test_learning_event_record_round_trips(db_session: AsyncSession) -> None:
    """FollowedUp returned by create has ORM attributes decoupled."""
    repo = SqlAlchemyFollowedUpRepository(db_session)
    record = await repo.create(
        platform="bilibili",
        uid="1567748478",
        display_name="A",
        profile_url="https://space.bilibili.com/1567748478",
        config={"space_url": "https://space.bilibili.com/1567748478"},
    )
    await db_session.commit()

    fetched = await repo.find_by_id(record.id)
    assert fetched is not None
    assert fetched.config == {"space_url": "https://space.bilibili.com/1567748478"}


@pytest.mark.integration
def test_followed_up_orm_class_is_registered() -> None:
    """The ORM class is usable directly (smoke test)."""
    target = FollowedUp
    assert target.__tablename__ == "followed_up"
    target2 = LearningEvent
    assert target2.__tablename__ == "learning_events"
