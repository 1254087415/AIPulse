"""Scheduler Web UI API endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aipulse.scheduler.client import get_scheduler
from aipulse.scheduler.models import SchedulerJobLog
from aipulse.scheduler.serializers import serialize_job
from aipulse.store.database import get_session
from aipulse.store.models import now_utc

router = APIRouter(prefix="/scheduler")


def _get_scheduler():
    """Dependency wrapper for the APScheduler singleton."""
    return get_scheduler()


@router.get("/jobs")
def list_jobs(scheduler: AsyncIOScheduler = Depends(_get_scheduler)) -> dict:  # noqa: B008
    """List all scheduled jobs."""
    jobs = [serialize_job(job) for job in scheduler.get_jobs()]
    return {"success": True, "data": jobs}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, scheduler: AsyncIOScheduler = Depends(_get_scheduler)) -> dict:  # noqa: B008
    """Trigger a scheduled job to run immediately."""
    scheduler.reschedule_job(job_id, trigger="date", run_date=now_utc())
    return {"success": True, "data": {"job_id": job_id}}


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: str, scheduler: AsyncIOScheduler = Depends(_get_scheduler)) -> dict:  # noqa: B008
    """Pause a scheduled job."""
    scheduler.pause_job(job_id)
    return {"success": True, "data": {"job_id": job_id, "paused": True}}


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str, scheduler: AsyncIOScheduler = Depends(_get_scheduler)) -> dict:  # noqa: B008
    """Resume a paused scheduled job."""
    scheduler.resume_job(job_id)
    return {"success": True, "data": {"job_id": job_id, "paused": False}}


@router.get("/logs")
async def list_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> dict:
    """List recent scheduler job execution logs."""
    result = await session.execute(
        select(SchedulerJobLog)
        .order_by(SchedulerJobLog.started_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": item.id,
                "job_id": item.job_id,
                "job_name": item.job_name,
                "status": item.status,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                "message": item.message,
                "exception": item.exception,
            }
            for item in items
        ],
    }


def _on_job_executed(event) -> None:
    """APScheduler event listener for successful job executions."""
    from aipulse.store.database import get_session_maker

    async def persist() -> None:
        async with get_session_maker()() as session:
            log = SchedulerJobLog(
                job_id=event.job_id,
                job_name=event.job_id,
                status="success",
                finished_at=datetime.now(UTC),
                raw_metadata={"retval": str(event.retval) if event.retval is not None else None},
            )
            session.add(log)
            await session.commit()

    try:
        import asyncio

        asyncio.create_task(persist())
    except RuntimeError:
        pass


def _on_job_error(event) -> None:
    """APScheduler event listener for failed job executions."""
    from aipulse.store.database import get_session_maker

    async def persist() -> None:
        async with get_session_maker()() as session:
            log = SchedulerJobLog(
                job_id=event.job_id,
                job_name=event.job_id,
                status="error",
                finished_at=datetime.now(UTC),
                exception=str(event.exception) if event.exception else None,
            )
            session.add(log)
            await session.commit()

    try:
        import asyncio

        asyncio.create_task(persist())
    except RuntimeError:
        pass


def register_scheduler_listeners() -> None:
    """Register APScheduler event listeners for execution logging."""
    scheduler = get_scheduler()
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
