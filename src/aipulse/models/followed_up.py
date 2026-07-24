"""FollowedUp SQLAlchemy model (v0.3 spec §3.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base, make_uuid, now_utc


class FollowedUp(Base):
    """A UP主 / content creator that the user actively follows.

    See docs/superpowers/specs/v0.3-followed-up-and-summary/01-foundation-data-model.md
    for full field semantics.
    """

    __tablename__ = "followed_up"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(256), nullable=False)
    collector_strategy: Mapped[str] = mapped_column(String(16), default="uapi")
    last_cursor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(default=30)
    is_active: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    health: Mapped[str] = mapped_column(String(16), default="healthy")
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        # SQLite treats NULL as distinct in unique constraints, so including
        # ``deleted_at`` allows reactivating a soft-deleted (platform, uid) by
        # inserting a new row with ``deleted_at = NULL``. PostgreSQL would
        # require a partial unique index instead.
        UniqueConstraint(
            "platform", "uid", "deleted_at", name="uq_followed_up_platform_uid"
        ),
    )
