from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from aipulse.collectors import arxiv, github, news  # noqa: F401  registers collectors
from aipulse.collectors.registry import list_collectors
from aipulse.core.config import get_settings
from aipulse.hotspot.models import Source
from aipulse.scheduler.client import get_scheduler
from aipulse.scheduler.jobs.digest_generate import generate_daily_digest
from aipulse.scheduler.jobs.hotspot_sync import sync_all_sources
from aipulse.scheduler.webui import register_scheduler_listeners
from aipulse.scheduler.webui import router as scheduler_router
from aipulse.store.database import close_db, get_session_maker, init_db
from aipulse.web.routes import router as web_router

DEFAULT_SOURCE_CONFIG: dict[str, dict] = {
    "rss_news": {"feed_url": "https://www.jiqizhixin.com/rss", "name": "机器之心"},
    "github": {"language": "Python"},
    "arxiv": {"categories": ["cs.AI", "cs.CL"]},
}


async def _seed_default_sources() -> None:
    """Create default source records if the sources table is empty."""
    async with get_session_maker()() as session:
        from sqlalchemy import func, select

        count = (await session.execute(select(func.count()).select_from(Source))).scalar_one()
        if count > 0:
            return
        for source_type, collector_cls in list_collectors().items():
            config = DEFAULT_SOURCE_CONFIG.get(source_type, {})
            source = Source(
                name=config.get("name") or collector_cls.name,
                source_type=source_type,
                collector_class=f"{collector_cls.__module__}.{collector_cls.__name__}",
                config=config,
            )
            session.add(source)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if get_settings().auto_create_tables:
        await init_db()
        await _seed_default_sources()
    scheduler = get_scheduler()
    scheduler.add_job(
        sync_all_sources,
        trigger=IntervalTrigger(minutes=30),
        id="hotspot_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="digest_generate",
        replace_existing=True,
    )
    register_scheduler_listeners()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await close_db()


app = FastAPI(title="AIPulse", version="0.2.0", lifespan=lifespan)
app.include_router(web_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


@app.middleware("http")
async def security_middleware(request: Request, call_next: callable) -> Response:
    """Enforce optional API token auth and security headers."""
    path = request.url.path
    if path.startswith("/api"):
        settings = get_settings()
        token = settings.aipulse_api_token.get_secret_value()
        if token:
            header_token = request.headers.get("X-AIPulse-Token", "")
            if header_token != token:
                response = JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Unauthorized"},
                )
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                response.headers[
                    "Content-Security-Policy"
                ] = "default-src 'self'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:;"
                return response

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers[
        "Content-Security-Policy"
    ] = "default-src 'self'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:;"

    return response


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"success": True, "data": {"status": "ok"}}


web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
