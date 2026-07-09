"""APScheduler job serializers."""

from apscheduler.job import Job


def serialize_job(job: Job) -> dict:
    """Serialize an APScheduler Job into a JSON-friendly dict."""
    return {
        "id": job.id,
        "name": job.name,
        "func": job.func_ref,
        "trigger": str(job.trigger),
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
    }
