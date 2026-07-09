"""SQLAlchemy data models."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def make_uuid() -> str:
    """Generate a short UUID string."""
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    """Base ORM class."""

    type_annotation_map = {
        dict[str, Any]: JSON,
        list[Any]: JSON,
    }


class Task(Base):
    """A content processing task."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), default="unknown")
    source: Mapped[str] = mapped_column(String(32), default="menubar")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_moments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    source_note_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_note_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)


class RssFeed(Base):
    """An RSS subscription source."""

    __tablename__ = "rss_feeds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    url: Mapped[str] = mapped_column(String(768), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_process: Mapped[bool] = mapped_column(default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)


class RssEntry(Base):
    """A single entry fetched from an RSS feed."""

    __tablename__ = "rss_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    feed_id: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    processed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
