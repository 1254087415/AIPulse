"""Unit tests for followed_up / followed_up_collections / learning_events models."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from aipulse.hotspot.models import Hotspot
from aipulse.models.followed_up import FollowedUp
from aipulse.models.followed_up_collections import FollowedUpCollection
from aipulse.models.learning_events import LearningEvent
from aipulse.store.models import Base


@pytest.mark.unit
def test_followed_up_tablename():
    """FollowedUp maps to the followed_up table."""
    assert FollowedUp.__tablename__ == "followed_up"


@pytest.mark.unit
def test_followed_up_required_columns_exist():
    """All spec §3.1 columns are declared on the model."""
    required = {
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
        "created_at",
        "updated_at",
        "deleted_at",
        "config",
    }
    columns = {c.name for c in inspect(FollowedUp).columns}
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.unit
def test_followed_up_defaults():
    """Defaults follow spec §3.1."""
    mapper = inspect(FollowedUp)
    cols = {c.name: c for c in mapper.columns}

    assert cols["collector_strategy"].default.arg == "uapi"
    assert cols["fetch_interval_minutes"].default.arg == 30
    assert cols["is_active"].default.arg is True
    assert cols["status"].default.arg == "active"
    assert cols["health"].default.arg == "healthy"


@pytest.mark.unit
def test_followed_up_unique_constraint_on_platform_uid():
    """UNIQUE(platform, uid) must exist on the model."""
    table = Base.metadata.tables["followed_up"]
    names = {c.name for c in table.constraints if c.name}
    assert "uq_followed_up_platform_uid" in names


@pytest.mark.unit
def test_followed_up_registered_in_base_metadata():
    """The model is registered with Base.metadata so Alembic sees it."""
    tables = set(Base.metadata.tables)
    assert "followed_up" in tables
    assert "followed_up_collections" in tables
    assert "learning_events" in tables


@pytest.mark.unit
def test_followed_up_collection_required_columns_exist():
    """FollowedUpCollection has all spec §3.2 columns."""
    required = {
        "id",
        "followed_up_id",
        "platform_collection_id",
        "title",
        "description",
        "video_count",
        "last_synced_at",
        "created_at",
        "updated_at",
    }
    columns = {c.name for c in inspect(FollowedUpCollection).columns}
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.unit
def test_learning_event_required_columns_exist():
    """LearningEvent has all spec §3.3 columns."""
    required = {
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
    }
    columns = {c.name for c in inspect(LearningEvent).columns}
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.unit
def test_hotspot_has_new_followed_up_fields():
    """Hotspot has the new nullable fields from spec §3.4."""
    columns = {c.name for c in inspect(Hotspot).columns}
    required = {
        "followed_up_id",
        "followed_up_collection_id",
        "content_id",
        "platform_user_id",
        "transcript",
        "key_points",
        "is_tech_related",
        "tech_confidence",
        "tech_reason",
        "decision_status",
        "learning_status",
        "is_backfill",
        "obsidian_source_path",
        "obsidian_summary_path",
        "learning_event_id",
        "notified",
    }
    missing = required - columns
    assert not missing, f"Missing columns: {missing}"
