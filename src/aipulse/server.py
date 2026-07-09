from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from aipulse.core.config import get_settings
from aipulse.scheduler.client import get_scheduler
from aipulse.scheduler.jobs.hotspot_sync import sync_all_sources
from aipulse.scheduler.webui import router as scheduler_router
from aipulse.store.database import close_db, init_db
from aipulse.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if get_settings().auto_create_tables:
        await init_db()
    scheduler = get_scheduler()
    scheduler.add_job(
        sync_all_sources,
        trigger=IntervalTrigger(minutes=30),
        id="hotspot_sync",
        replace_existing=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await close_db()


app = FastAPI(title="AIPulse", version="0.2.0", lifespan=lifespan)
app.include_router(web_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"success": True, "data": {"status": "ok"}}


web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
