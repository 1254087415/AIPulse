"""Unit tests for archive/service.py — push coverage ≥80%.

覆盖：
- ArchiveOutcome.ok property (note_path + no errors)
- append_obsidian_task: 退化路径（note 存在、OSError、note 不存在）
- record_learning_event: 成功 / 失败
- archive_three_way: obsidian 失败直接退出、learning_event 失败容忍、task 失败、Reminder 异常容忍
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.archive.service import (
    ArchiveOutcome,
    append_obsidian_task,
    archive_three_way,
    record_learning_event,
)


class TestArchiveOutcome:
    @pytest.mark.unit
    def test_ok_true_when_note_path_set_and_no_errors(self):
        out = ArchiveOutcome(
            note_path="/x.md", learning_event_id="ev", reminder_id="rm",
            obsidian_task_written=True, errors=[]
        )
        assert out.ok is True

    @pytest.mark.unit
    def test_ok_false_when_note_path_none(self):
        out = ArchiveOutcome(
            note_path=None, learning_event_id=None, reminder_id=None,
            obsidian_task_written=False, errors=[]
        )
        assert out.ok is False

    @pytest.mark.unit
    def test_ok_false_when_errors_present(self):
        out = ArchiveOutcome(
            note_path="/x.md", learning_event_id="ev", reminder_id="rm",
            obsidian_task_written=True, errors=["obsidian_task"]
        )
        assert out.ok is False


class TestAppendObsidianTask:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_appends_task_line_when_path_exists(self, tmp_path):
        """退化路径：note_path 存在 → 追加 task line"""
        note = tmp_path / "x.md"
        note.write_text("# title\n", encoding="utf-8")

        scheduled = "2026-12-31T15:30:00"

        # 把 agent_tools.send_notification 替换成没有 .coroutine 属性的 fake，
        # 触发 append_obsidian_task 的退化路径
        from aipulse.summarizers.agent import tools as agent_tools

        original_sn = agent_tools.send_notification
        # 替换为简单 namespace（没有 coroutine）
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            ok = await append_obsidian_task(
                str(note), scheduled_at=scheduled, topic="review this"
            )
        finally:
            agent_tools.send_notification = original_sn

        assert ok is True
        content = note.read_text(encoding="utf-8")
        assert "review this" in content
        assert "- [ ] ⏰" in content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_returns_false_when_path_missing(self):
        """note_path 不存在 → 返回 False"""
        from aipulse.summarizers.agent import tools as agent_tools

        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            ok = await append_obsidian_task(
                "/nonexistent/path/note.md",
                scheduled_at="2026-01-01T00:00:00",
                topic="x",
            )
        finally:
            agent_tools.send_notification = original_sn

        assert ok is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_handles_oserror(self, tmp_path):
        """写文件 OSError → 返回 False（路径是目录而非文件）"""
        from aipulse.summarizers.agent import tools as agent_tools

        # 给一个路径，但它是目录 → open() 时抛 IsADirectoryError (OSError 子类)
        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            ok = await append_obsidian_task(
                str(tmp_path),  # 目录
                scheduled_at="2026-01-01T00:00:00",
                topic="x",
            )
        finally:
            agent_tools.send_notification = original_sn

        assert ok is False


class TestRecordLearningEvent:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_event_id_on_success(self):
        from aipulse.summarizers.agent import tools as agent_tools

        fake_tool = MagicMock()
        fake_tool.ainvoke = AsyncMock(return_value={"ok": True, "event_id": "ev-99"})

        with patch.object(agent_tools, "create_learning_event", fake_tool):
            event_id = await record_learning_event(
                video_id="BV1",
                note_path="/x.md",
                scheduled_at="2026-01-01T00:00:00",
                topic="t",
            )
        assert event_id == "ev-99"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        from aipulse.summarizers.agent import tools as agent_tools

        fake_tool = MagicMock()
        fake_tool.ainvoke = AsyncMock(
            return_value={"ok": False, "error": "hotspot not found"}
        )

        with patch.object(agent_tools, "create_learning_event", fake_tool):
            event_id = await record_learning_event(
                video_id="BV1",
                note_path="/x.md",
                scheduled_at="2026-01-01T00:00:00",
                topic="t",
            )
        assert event_id is None


class TestArchiveThreeWay:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_obsidian_failure_short_circuits(self, tmp_path):
        """create_obsidian_note 失败 → 整体返回 None note_path + error"""
        from aipulse.summarizers.agent import tools as agent_tools

        fake_cnote = MagicMock()
        fake_cnote.ainvoke = AsyncMock(
            return_value={"ok": False, "error": "vault missing"}
        )

        # vault 路径不存在 → obsidian 写入失败
        with patch(
            "aipulse.summarizers.agent.tools.get_settings",
            return_value=_settings_with_vault(tmp_path / "missing"),
        ):
            with patch.object(agent_tools, "create_obsidian_note", fake_cnote):
                out = await archive_three_way(
                    video_id="BV1",
                    title="t",
                    up_name="up",
                    markdown="# body",
                    scheduled_at="2026-01-01T00:00:00",
                    topic="topic",
                )

        assert out.note_path is None
        assert out.ok is False
        assert any("obsidian_note" in e for e in out.errors)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_append_task_uses_fallback_when_no_coroutine(self, tmp_path):
        """append_obsidian_task fallback：tools.send_notification 无 coroutine 属性"""
        from aipulse.summarizers.agent import tools as agent_tools

        vault = tmp_path / "vault"
        vault.mkdir()
        settings = _settings_with_vault(vault)

        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            with patch(
                "aipulse.summarizers.agent.tools.get_settings",
                return_value=settings,
            ):
                # Patch create_learning_event 走 fallback 以保证 archive 完整路径
                fake_cle = MagicMock()
                fake_cle.ainvoke = AsyncMock(
                    return_value={"ok": True, "event_id": "ev-fb"}
                )
                with patch.object(agent_tools, "create_learning_event", fake_cle):
                    out = await archive_three_way(
                        video_id="BV1",
                        title="t",
                        up_name="up",
                        markdown="# body",
                        scheduled_at="2026-01-01T00:00:00",
                        topic="fallback topic",
                    )
        finally:
            agent_tools.send_notification = original_sn

        assert out.note_path is not None
        assert out.obsidian_task_written is True
        from pathlib import Path
        content = Path(out.note_path).read_text(encoding="utf-8")
        assert "fallback topic" in content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_path_with_all_components(self, tmp_path):
        """三方向都成功：real create_obsidian_note 写入 vault + create_learning_event patched + fallback append"""
        from aipulse.summarizers.agent import tools as agent_tools

        vault = tmp_path / "vault"
        vault.mkdir()
        settings = _settings_with_vault(vault)

        # Patch create_learning_event: 让 archive_three_way 走 DB stub
        fake_cle = MagicMock()
        fake_cle.ainvoke = AsyncMock(
            return_value={"ok": True, "event_id": "ev-1"}
        )

        # send_notification 不被 archive_three_way 直接调用（走 append_obsidian_task），
        # 但 append_obsidian_task 内部会因为 hasattr(_sn, "coroutine") 走 fallback。
        # patch send_notification 为无 .coroutine 属性 → fallback 路径 → 写文件成功。
        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            with patch(
                "aipulse.summarizers.agent.tools.get_settings",
                return_value=settings,
            ):
                with patch.object(agent_tools, "create_learning_event", fake_cle):
                    out = await archive_three_way(
                        video_id="BV1",
                        title="t",
                        up_name="up",
                        markdown="# body",
                        scheduled_at="2026-01-01T00:00:00",
                        topic="topic",
                    )
        finally:
            agent_tools.send_notification = original_sn

        assert out.note_path is not None
        assert out.learning_event_id == "ev-1"
        assert out.obsidian_task_written is True
        assert out.errors == []
        assert out.ok is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_learning_event_failure_recorded_as_error(self, tmp_path):
        """learning_event 失败 → 记录 error 但不影响其它步骤"""
        from aipulse.summarizers.agent import tools as agent_tools

        vault = tmp_path / "vault"
        vault.mkdir()
        settings = _settings_with_vault(vault)

        fake_cle = MagicMock()
        fake_cle.ainvoke = AsyncMock(
            return_value={"ok": False, "error": "no hotspot"}
        )

        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            with patch(
                "aipulse.summarizers.agent.tools.get_settings",
                return_value=settings,
            ):
                with patch.object(agent_tools, "create_learning_event", fake_cle):
                    out = await archive_three_way(
                        video_id="BV1",
                        title="t",
                        up_name="up",
                        markdown="# body",
                        scheduled_at="2026-01-01T00:00:00",
                        topic="topic",
                    )
        finally:
            agent_tools.send_notification = original_sn

        assert out.note_path is not None
        assert out.learning_event_id is None
        assert "learning_event" in out.errors

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_apple_reminders_failure_does_not_fail_overall(self, tmp_path):
        """Apple Reminders 抛异常 → 不进 errors，整体仍 ok"""
        from aipulse.summarizers.agent import tools as agent_tools

        vault = tmp_path / "vault"
        vault.mkdir()
        settings = _settings_with_vault(vault)

        fake_cle = MagicMock()
        fake_cle.ainvoke = AsyncMock(
            return_value={"ok": True, "event_id": "ev-1"}
        )

        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            with patch(
                "aipulse.summarizers.agent.tools.get_settings",
                return_value=settings,
            ):
                with patch.object(agent_tools, "create_learning_event", fake_cle):
                    with patch("sys.platform", "darwin"):
                        # 给 sys.modules 注入一个 fake reminders module
                        fake_reminders_mod = MagicMock()
                        fake_reminders_mod.create_reminder = AsyncMock(
                            side_effect=RuntimeError("Reminders daemon down")
                        )
                        with patch.dict(
                            "sys.modules",
                            {"aipulse.apple.reminders": fake_reminders_mod},
                        ):
                            out = await archive_three_way(
                                video_id="BV1",
                                title="t",
                                up_name="up",
                                markdown="# body",
                                scheduled_at="2026-01-01T00:00:00",
                                topic="topic",
                            )
        finally:
            agent_tools.send_notification = original_sn

        # Apple Reminders 失败不算 error
        assert out.note_path is not None
        assert out.ok is True  # note + 没 errors

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_obsidian_task_failure_recorded_as_error(self, tmp_path):
        """Obsidian task 写入失败 → errors 含 obsidian_task

        用 vault 设置为 tmp_path（中间创建但 archive 会 fallback 检查 p.exists()），
        但 patch create_obsidian_note 返回 note_path 指向一个不存在的文件，
        让 append_obsidian_task fallback 路径找不到 note → 失败。
        """
        from aipulse.summarizers.agent import tools as agent_tools

        fake_cnote = MagicMock()
        fake_cnote.ainvoke = AsyncMock(
            return_value={"ok": True, "note_path": "/nonexistent/note.md"}
        )
        fake_cle = MagicMock()
        fake_cle.ainvoke = AsyncMock(
            return_value={"ok": True, "event_id": "ev-1"}
        )

        original_sn = agent_tools.send_notification
        agent_tools.send_notification = type("NoCoroTool", (), {})()
        try:
            with patch.object(agent_tools, "create_obsidian_note", fake_cnote):
                with patch.object(agent_tools, "create_learning_event", fake_cle):
                    out = await archive_three_way(
                        video_id="BV1",
                        title="t",
                        up_name="up",
                        markdown="# body",
                        scheduled_at="2026-01-01T00:00:00",
                        topic="topic",
                    )
        finally:
            agent_tools.send_notification = original_sn

        assert out.obsidian_task_written is False
        assert "obsidian_task" in out.errors


# ---------- helpers ----------

def _settings_with_vault(vault_path: Path):
    s = MagicMock()
    s.obsidian_vault_path = vault_path
    s.obsidian_archive_folder = "AIPulse"
    s.kimi_model = "kimi-for-coding"
    return s