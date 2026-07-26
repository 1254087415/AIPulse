"""Unit tests for archive_service 三方向归档 (spec F6).

完全 mock agent tools + Apple Reminders，验证三方向归档：
- note_path 必须存在才视为 ok
- DB 失败容错
- Apple 失败不影响 Obsidian Task 写入
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aipulse.archive.service import (
    ArchiveOutcome,
    append_obsidian_task,
    archive_three_way,
    record_learning_event,
)


@pytest.fixture
def fake_obsidian_vault(tmp_path, monkeypatch):
    """Mock ``settings.obsidian_vault_path`` -> tmp."""
    from aipulse.core import config as cfg

    monkeypatch.setattr(
        cfg.get_settings(),
        "obsidian_vault_path",
        tmp_path / "vault",
        raising=False,
    )
    return tmp_path / "vault"


def _mock_tool(coroutine_fn):
    """Build a mock that mimics StructuredTool.ainvoke semantics."""
    m = MagicMock()
    m.ainvoke = AsyncMock(side_effect=coroutine_fn)
    return m


@pytest.mark.unit
@pytest.mark.asyncio
async def test_append_obsidian_task_writes_markdown_line(
    fake_obsidian_vault, monkeypatch
) -> None:
    note = fake_obsidian_vault / "AIPulse" / "BV1.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("body\n", encoding="utf-8")

    ok = await append_obsidian_task(
        str(note),
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="LangChain ReAct",
    )
    assert ok is True
    content = note.read_text(encoding="utf-8")
    assert "- [ ] ⏰" in content
    assert "LangChain ReAct" in content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_append_obsidian_task_fails_when_note_missing(fake_obsidian_vault) -> None:
    ok = await append_obsidian_task(
        str(fake_obsidian_vault / "nope.md"),
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="x",
    )
    assert ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_record_learning_event_returns_id(monkeypatch) -> None:
    import aipulse.summarizers.agent.tools as tools_mod

    async def fake(payload):
        return {"ok": True, "event_id": "evt-fake"}

    fake_tool = _mock_tool(fake)
    monkeypatch.setattr(tools_mod, "create_learning_event", fake_tool)

    eid = await record_learning_event(
        video_id="BV1",
        note_path="/tmp/note.md",
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="t",
    )
    assert eid == "evt-fake"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_record_learning_event_handles_failure(monkeypatch) -> None:
    import aipulse.summarizers.agent.tools as tools_mod

    async def fake(payload):
        return {"ok": False, "error": "db down"}

    fake_tool = _mock_tool(fake)
    monkeypatch.setattr(tools_mod, "create_learning_event", fake_tool)

    eid = await record_learning_event(
        video_id="BV1",
        note_path="/tmp/note.md",
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="t",
    )
    assert eid is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_archive_three_way_ok(fake_obsidian_vault, monkeypatch) -> None:
    import aipulse.summarizers.agent.tools as tools_mod

    async def fake_note(payload):
        target = fake_obsidian_vault / "AIPulse" / f"{payload['video_id']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload["markdown"], encoding="utf-8")
        return {"ok": True, "note_path": str(target)}

    async def fake_evt(payload):
        return {"ok": True, "event_id": "evt1"}

    monkeypatch.setattr(tools_mod, "create_obsidian_note", _mock_tool(fake_note))
    monkeypatch.setattr(tools_mod, "create_learning_event", _mock_tool(fake_evt))
    monkeypatch.setattr("sys.platform", "linux")

    out: ArchiveOutcome = await archive_three_way(
        video_id="BV1",
        title="t",
        up_name="up",
        markdown="hello body",
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="topic1",
    )
    assert out.note_path is not None
    assert out.learning_event_id == "evt1"
    assert out.reminder_id is None  # not on linux
    body = (fake_obsidian_vault / "AIPulse" / "BV1.md").read_text("utf-8")
    assert "topic1" in body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_archive_three_way_obsidian_failure_returns_error(
    fake_obsidian_vault, monkeypatch
) -> None:
    import aipulse.summarizers.agent.tools as tools_mod

    async def fake_note(payload):
        return {"ok": False, "error": "vault not configured"}

    monkeypatch.setattr(tools_mod, "create_obsidian_note", _mock_tool(fake_note))

    out = await archive_three_way(
        video_id="BV1",
        title="t",
        up_name="up",
        markdown="body",
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="topic1",
    )
    assert out.note_path is None
    assert out.errors and "obsidian_note" in out.errors[0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_archive_three_way_db_failure_still_writes_obsidian(
    fake_obsidian_vault, monkeypatch
) -> None:
    import aipulse.summarizers.agent.tools as tools_mod

    async def fake_note(payload):
        target = fake_obsidian_vault / "AIPulse" / f"{payload['video_id']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("body", encoding="utf-8")
        return {"ok": True, "note_path": str(target)}

    async def fake_evt(payload):
        return {"ok": False, "error": "db down"}

    monkeypatch.setattr(tools_mod, "create_obsidian_note", _mock_tool(fake_note))
    monkeypatch.setattr(tools_mod, "create_learning_event", _mock_tool(fake_evt))
    monkeypatch.setattr("sys.platform", "linux")

    out = await archive_three_way(
        video_id="BV1",
        title="t",
        up_name="up",
        markdown="x",
        scheduled_at="2026-08-01T10:00:00+00:00",
        topic="topic2",
    )
    assert out.note_path is not None
    assert out.learning_event_id is None
    assert out.obsidian_task_written is True
    assert "learning_event" in out.errors
