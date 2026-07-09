"""Scheduler Web UI API endpoints."""

from fastapi import APIRouter

from aipulse.scheduler.client import get_scheduler
from aipulse.scheduler.serializers import serialize_job
from aipulse.store.models import now_utc

router = APIRouter(prefix="/scheduler")


@router.get("/jobs")
def list_jobs() -> dict:
    """List all scheduled jobs."""
    jobs = [serialize_job(job) for job in get_scheduler().get_jobs()]
    return {"success": True, "data": jobs}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str) -> dict:
    """Trigger a scheduled job to run immediately."""
    get_scheduler().reschedule_job(job_id, trigger="date", run_date=now_utc())
    return {"success": True, "data": {"job_id": job_id}}
