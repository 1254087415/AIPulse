import pytest

from aipulse.scheduler.client import build_sync_db_url, get_scheduler


@pytest.mark.unit
def test_build_sync_db_url_replaces_aiomysql():
    url = "mysql+aiomysql://user:pwd@localhost:3306/db"
    assert build_sync_db_url(url) == "mysql+pymysql://user:pwd@localhost:3306/db"


@pytest.mark.unit
def test_build_sync_db_url_replaces_sqlite_aiosqlite():
    url = "sqlite+aiosqlite:///./data/aipulse.db"
    assert build_sync_db_url(url) == "sqlite:///./data/aipulse.db"


@pytest.mark.unit
def test_get_scheduler_returns_async_scheduler():
    scheduler = get_scheduler()
    assert scheduler is not None
    assert scheduler.__class__.__name__ == "AsyncIOScheduler"
