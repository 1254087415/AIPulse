"""Integration tests for spec 06 plan §Task 3 — ``POST /api/hotspots/{id}/archive``.

验证 archive API 调 ``archive_three_way()`` 三方向存储：
- DB learning_events
- Obsidian Task checkbox
- Apple Reminders（mock fake_reminders，按总结主题选业务列表）

不依赖真外部 LLM/网络；Apple Reminders mock 走 fake_reminders。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from aipulse.hotspot.models import Hotspot, Source
from aipulse.store.database import reset_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_database_before_each_test():
    await reset_db()


@pytest.fixture
def fake_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把 ``settings.obsidian_vault_path`` 指到 tmp_path/vault。"""
    from aipulse.core.config import get_settings

    vault = tmp_path / "vault"
    archive = vault / "Tasks"
    archive.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings = settings.update(
        obsidian_vault_path=vault,
        obsidian_archive_folder="Tasks",
    )
    monkeypatch.setattr(settings, "obsidian_vault_path", vault, raising=False)
    return vault, archive


@pytest.fixture
def fake_reminders(monkeypatch: pytest.MonkeyPatch):
    """Mock Apple Reminders — 走 in-memory 列表，不触发 macOS 副作用。"""
    fake_state: dict[str, list[dict]] = {"reminders": []}

    async def fake_create_reminder(
        title: str,
        due_date: str,
        notes: str = "",
        *,
        list_name: str | None = None,
        executor_timeout_s: float = 5.0,
    ) -> str:
        rid = "fake-rem-" + str(len(fake_state["reminders"]))
        fake_state["reminders"].append(
            {
                "id": rid,
                "title": title,
                "due_date": due_date,
                "notes": notes,
                "list": list_name,
            }
        )
        return rid

    monkeypatch.setattr(
        "aipulse.apple.reminders.create_reminder",
        fake_create_reminder,
        raising=False,
    )
    return fake_state


async def _seed_hotspot(db_session) -> tuple[str, str]:
    """最小 Source + FollowedUp + Hotspot 三件套，返回 (hotspot_id, up_display_name)。"""
    from aipulse.models.followed_up import FollowedUp

    src = Source(
        id="src-arch-1",
        name="B 站归档测试",
        source_type="bilibili",
        collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
        is_active=True,
    )
    up = FollowedUp(
        id="up-arch-1",
        platform="bilibili",
        uid="20000001",
        display_name="ArchiveTestUP",
        profile_url="https://space.bilibili.com/20000001",
        is_active=True,
    )
    hs = Hotspot(
        id="hs-arch-1",
        title="LangChain ReAct 学习",
        url="https://www.bilibili.com/video/BV1arch",
        canonical_url="https://www.bilibili.com/video/BV1arch",
        source_id="src-arch-1",
        source_type="bilibili",
        followed_up_id="up-arch-1",
        content_id="BV1arch",
        summary="# LangChain ReAct 学习\n\n核心要点 ...\n",
    )
    db_session.add_all([src, up, hs])
    await db_session.commit()
    return hs.id, up.display_name


@pytest.mark.integration
async def test_archive_hotspot_three_way_lands(
    client, db_session, fake_vault, fake_reminders
):
    """POST /api/hotspots/{id}/archive → 三方向存储成功。"""
    vault, archive = fake_vault
    hotspot_id, _ = await _seed_hotspot(db_session)

    response = await client.post(f"/api/hotspots/{hotspot_id}/archive")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["note_path"] is not None
    assert Path(data["note_path"]).exists()
    assert data["learning_event_id"] is not None
    assert data["reminder_id"] is not None
    assert data["obsidian_task_written"] is True
    assert data["errors"] == []

    # 1. Obsidian note 真的写到 vault
    assert Path(data["note_path"]).read_text("utf-8").startswith("---")

    # 2. Obsidian Task checkbox 追加
    body_text = Path(data["note_path"]).read_text("utf-8")
    assert "- [ ] ⏰" in body_text

    # 3. Apple Reminders 只创建一条，并按学习类总结落到「学习」列表。
    assert len(fake_reminders["reminders"]) == 1
    assert fake_reminders["reminders"][0]["list"] == "学习"

    # 4. learning_events 真行
    from sqlalchemy import select

    from aipulse.models.learning_events import LearningEvent

    async with db_session.bind.connect() as _:
        pass
    rows = (
        await db_session.execute(
            select(LearningEvent).where(LearningEvent.hotspot_id == hotspot_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    # spec 06 §7.2：fallback 15（fake_vault 没有 transcript cache）
    assert rows[0].estimated_minutes == 15


@pytest.mark.integration
async def test_archive_hotspot_returns_404_when_missing(
    client, fake_vault, fake_reminders
):
    """hotspot_id 不存在 → 404。"""
    response = await client.post("/api/hotspots/does-not-exist/archive")
    assert response.status_code == 404
    assert "Hotspot not found" in response.text


@pytest.mark.integration
async def test_archive_hotspot_response_envelope_shape(
    client, db_session, fake_vault, fake_reminders
):
    """返回数据契约：四件 + errors。"""
    hotspot_id, _ = await _seed_hotspot(db_session)
    response = await client.post(f"/api/hotspots/{hotspot_id}/archive")
    assert response.status_code == 200
    data = response.json()["data"]
    for key in (
        "note_path",
        "learning_event_id",
        "reminder_id",
        "obsidian_task_written",
        "errors",
    ):
        assert key in data
