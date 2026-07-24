"""SummaryJob SQLAlchemy model (v0.3 spec §5.5).

记录每个 video 的总结 pipeline 运行状态，用于 SSE 持久化与后续异步查询。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aipulse.store.models import Base, make_uuid, now_utc


# Status 状态机：
#   queued -> running -> (completed | failed | partial)
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_PARTIAL = "partial"
JOB_STATUS_TIMEOUT = "timeout"

ALL_JOB_STATUSES = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
    JOB_STATUS_TIMEOUT,
}


class SummaryJob(Base):
    """A single summary pipeline run for a Bilibili video.

    由 ``/api/summary/{video_id}`` 触发，worker 异步消费 ``SummaryJobQueue``
    并把 run_summary_pipeline 的结果回写到本表 + 通过 SSE 推送给订阅者。
    """

    __tablename__ = "summary_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_uuid)
    video_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hotspot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    up_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=JOB_STATUS_QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reminder_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intermediate_steps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    steps_emitted: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
