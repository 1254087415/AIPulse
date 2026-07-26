"""Hotspot monitoring data models."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base

# v0.3: explicit string length for nullable fields added in §3.4
FOLLOWED_UP_ID_LENGTH = 32
FOLLOWED_UP_COLLECTION_ID_LENGTH = 32
LEARNING_EVENT_ID_LENGTH = 32
CONTENT_ID_LENGTH = 64
PLATFORM_USER_ID_LENGTH = 64
OBSIDIAN_PATH_LENGTH = 512
DECISION_STATUS_LENGTH = 16
LEARNING_STATUS_LENGTH = 16

URL_LENGTH = 768  # MySQL utf8mb4 index limit (768*4=3072 bytes)


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def make_uuid() -> str:
    """Generate a short UUID string."""
    return uuid.uuid4().hex[:12]


class Source(Base):
    """A configured hotspot source / collector."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    collector_class: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    default_weight: Mapped[float] = mapped_column(Float, default=1.0)
    fetch_interval_minutes: Mapped[int] = mapped_column(default=30)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)


class Hotspot(Base):
    """A single hot topic / trend item."""

    __tablename__ = "hotspots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        """Apply Python-side defaults during construction."""
        kwargs.setdefault("heat_score", 0.0)
        kwargs.setdefault("importance", "medium")
        kwargs.setdefault("decision_status", "pending")
        kwargs.setdefault("is_backfill", False)
        kwargs.setdefault("notified", False)
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("fetched_at", now_utc())
        kwargs.setdefault("created_at", now_utc())
        kwargs.setdefault("updated_at", now_utc())
        super().__init__(**kwargs)

    url: Mapped[str] = mapped_column(String(URL_LENGTH), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(URL_LENGTH), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(default=now_utc)
    heat_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    importance: Mapped[str] = mapped_column(String(16), default="medium")
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    duplicate_group_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    # v0.3 §3.4 — followed-up / learning domain linkage
    followed_up_id: Mapped[str | None] = mapped_column(
        ForeignKey("followed_up.id"), nullable=True
    )
    followed_up_collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("followed_up_collections.id"), nullable=True
    )
    content_id: Mapped[str | None] = mapped_column(String(CONTENT_ID_LENGTH), nullable=True)
    platform_user_id: Mapped[str | None] = mapped_column(
        String(PLATFORM_USER_ID_LENGTH), nullable=True
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    is_tech_related: Mapped[bool | None] = mapped_column(nullable=True)
    tech_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tech_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_status: Mapped[str] = mapped_column(
        String(DECISION_STATUS_LENGTH), default="pending"
    )
    learning_status: Mapped[str | None] = mapped_column(
        String(LEARNING_STATUS_LENGTH), nullable=True
    )
    is_backfill: Mapped[bool] = mapped_column(default=False)
    obsidian_source_path: Mapped[str | None] = mapped_column(
        String(OBSIDIAN_PATH_LENGTH), nullable=True
    )
    obsidian_summary_path: Mapped[str | None] = mapped_column(
        String(OBSIDIAN_PATH_LENGTH), nullable=True
    )
    learning_event_id: Mapped[str | None] = mapped_column(
        String(LEARNING_EVENT_ID_LENGTH), nullable=True
    )
    notified: Mapped[bool] = mapped_column(default=False)


class Keyword(Base):
    """A keyword used to filter / rank hotspots."""

    __tablename__ = "keywords"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    value: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    notify_on_match: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)


class DailyDigest(Base):
    """A daily summary digest of top hotspots."""

    __tablename__ = "daily_digests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    date: Mapped["date"] = mapped_column(nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    top_hotspot_ids: Mapped[list[Any] | None] = mapped_column(nullable=True)
    generated_at: Mapped[datetime] = mapped_column(default=now_utc)
    pushed_at: Mapped[datetime | None] = mapped_column(nullable=True)
