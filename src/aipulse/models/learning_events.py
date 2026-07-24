"""LearningEvent SQLAlchemy model (v0.3 spec §3.3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base, make_uuid, now_utc


class LearningEvent(Base):
    """A learning reminder scheduled from a Hotspot.

    One Hotspot may spawn multiple LearningEvent rows (e.g. user re-archives).
    """

    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    hotspot_id: Mapped[str] = mapped_column(ForeignKey("hotspots.id"), nullable=False)
    followed_up_id: Mapped[str] = mapped_column(
        ForeignKey("followed_up.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(16), default="bilibili")
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary_note_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(default=now_utc)
    estimated_minutes: Mapped[int] = mapped_column(default=15)
    obsidian_task_created: Mapped[bool] = mapped_column(default=False)
    apple_reminder_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    apple_reminders_list: Mapped[str] = mapped_column(String(64), default="工作学习")
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    learning_status: Mapped[str] = mapped_column(String(16), default="unread")
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
