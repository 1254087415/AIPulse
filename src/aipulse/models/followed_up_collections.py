"""FollowedUpCollection SQLAlchemy model (v0.3 spec §3.2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base, make_uuid, now_utc


class FollowedUpCollection(Base):
    """A video collection / playlist owned by a FollowedUp."""

    __tablename__ = "followed_up_collections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    followed_up_id: Mapped[str] = mapped_column(
        ForeignKey("followed_up.id"), nullable=False
    )
    platform_collection_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_count: Mapped[int] = mapped_column(default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    __table_args__ = (
        UniqueConstraint(
            "followed_up_id", "platform_collection_id", name="uq_collection_per_up"
        ),
    )
