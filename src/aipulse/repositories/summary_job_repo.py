"""SummaryJob repository: Protocol interface + SQLAlchemy implementation."""

from datetime import datetime
from typing import Any, Optional, Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.models.summary_jobs import (
    ALL_JOB_STATUSES,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_TIMEOUT,
    SummaryJob,
)
from aipulse.store.models import now_utc


class SummaryJobNotFoundError(Exception):
    """The requested SummaryJob id does not exist."""


class SummaryJobRecord:
    """Immutable snapshot of a SummaryJob row."""

    __slots__ = (
        "id",
        "video_id",
        "hotspot_id",
        "title",
        "up_name",
        "status",
        "error",
        "note_path",
        "event_id",
        "reminder_id",
        "intermediate_steps",
        "steps_emitted",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    )

    def __init__(self, row: SummaryJob) -> None:
        self.id: str = row.id
        self.video_id: str = row.video_id
        self.hotspot_id: Optional[str] = row.hotspot_id
        self.title: Optional[str] = row.title
        self.up_name: Optional[str] = row.up_name
        self.status: str = row.status
        self.error: Optional[str] = row.error
        self.note_path: Optional[str] = row.note_path
        self.event_id: Optional[str] = row.event_id
        self.reminder_id: Optional[str] = row.reminder_id
        self.intermediate_steps: list[dict[str, Any]] = list(row.intermediate_steps or [])
        self.steps_emitted: int = row.steps_emitted
        self.created_at: datetime = row.created_at
        self.updated_at: datetime = row.updated_at
        self.started_at: Optional[datetime] = row.started_at
        self.completed_at: Optional[datetime] = row.completed_at


class SummaryJobRepository(Protocol):
    async def create(
        self,
        *,
        video_id: str,
        title: str | None = None,
        up_name: str | None = None,
        hotspot_id: str | None = None,
    ) -> SummaryJobRecord: ...

    async def find_by_id(self, job_id: str) -> SummaryJobRecord | None: ...

    async def list_recent(self, limit: int = 50) -> Sequence[SummaryJobRecord]: ...

    async def list_for_video(
        self, video_id: str, limit: int = 10
    ) -> Sequence[SummaryJobRecord]: ...

    async def mark_started(self, job_id: str) -> SummaryJobRecord: ...

    async def append_steps(
        self, job_id: str, steps: list[dict[str, Any]]
    ) -> SummaryJobRecord: ...

    async def mark_finished(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None = None,
        note_path: str | None = None,
        event_id: str | None = None,
        reminder_id: str | None = None,
        intermediate_steps: list[dict[str, Any]] | None = None,
    ) -> SummaryJobRecord: ...


class SqlAlchemySummaryJobRepository:
    """Async SQLAlchemy implementation of :class:`SummaryJobRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        video_id: str,
        title: str | None = None,
        up_name: str | None = None,
        hotspot_id: str | None = None,
    ) -> SummaryJobRecord:
        row = SummaryJob(
            video_id=video_id,
            title=title,
            up_name=up_name,
            hotspot_id=hotspot_id,
            status=JOB_STATUS_QUEUED,
        )
        self._session.add(row)
        await self._session.flush()
        return SummaryJobRecord(row)

    async def find_by_id(self, job_id: str) -> SummaryJobRecord | None:
        result = await self._session.execute(
            select(SummaryJob).where(SummaryJob.id == job_id)
        )
        row = result.scalar_one_or_none()
        return SummaryJobRecord(row) if row else None

    async def list_recent(self, limit: int = 50) -> Sequence[SummaryJobRecord]:
        stmt = (
            select(SummaryJob)
            .order_by(SummaryJob.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [SummaryJobRecord(r) for r in result.scalars().all()]

    async def list_for_video(
        self, video_id: str, limit: int = 10
    ) -> Sequence[SummaryJobRecord]:
        stmt = (
            select(SummaryJob)
            .where(SummaryJob.video_id == video_id)
            .order_by(SummaryJob.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [SummaryJobRecord(r) for r in result.scalars().all()]

    async def mark_started(self, job_id: str) -> SummaryJobRecord:
        row = await self._require(job_id)
        row.status = JOB_STATUS_RUNNING
        row.started_at = now_utc()
        row.updated_at = now_utc()
        await self._session.flush()
        return SummaryJobRecord(row)

    async def append_steps(
        self, job_id: str, steps: list[dict[str, Any]]
    ) -> SummaryJobRecord:
        row = await self._require(job_id)
        existing = list(row.intermediate_steps or [])
        existing.extend(steps)
        row.intermediate_steps = existing
        row.steps_emitted = len(existing)
        row.updated_at = now_utc()
        await self._session.flush()
        return SummaryJobRecord(row)

    async def mark_finished(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None = None,
        note_path: str | None = None,
        event_id: str | None = None,
        reminder_id: str | None = None,
        intermediate_steps: list[dict[str, Any]] | None = None,
    ) -> SummaryJobRecord:
        if status not in ALL_JOB_STATUSES:
            raise ValueError(f"unknown finish status={status!r}")
        row = await self._require(job_id)
        row.status = status
        row.error = error
        row.note_path = note_path
        row.event_id = event_id
        row.reminder_id = reminder_id
        if intermediate_steps is not None:
            row.intermediate_steps = list(intermediate_steps)
        row.completed_at = now_utc()
        row.updated_at = now_utc()
        await self._session.flush()
        return SummaryJobRecord(row)

    async def _require(self, job_id: str) -> SummaryJob:
        result = await self._session.execute(
            select(SummaryJob).where(SummaryJob.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise SummaryJobNotFoundError(f"SummaryJob id={job_id} not found")
        return row

    async def annotate(
        self,
        job_id: str,
        *,
        hotspot_id: str | None = None,
        title: str | None = None,
        up_name: str | None = None,
    ) -> SummaryJobRecord:
        """Attach hotspot/title/up_name context to a freshly-created job.

        Runs in the caller's session; the caller is responsible for committing.
        """
        row = await self._require(job_id)
        if hotspot_id is not None:
            row.hotspot_id = hotspot_id
        if title is not None:
            row.title = title
        if up_name is not None:
            row.up_name = up_name
        await self._session.flush()
        return SummaryJobRecord(row)
