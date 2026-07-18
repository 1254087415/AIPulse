"""Scheduler execution log models."""

from datetime import datetime
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base, make_uuid, now_utc


class SchedulerJobLog(Base):
    """Execution log entry for a scheduled job."""

    __tablename__ = "scheduler_job_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    exception: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
