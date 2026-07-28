"""补全 summarizers/agent/* 模块到 100% 覆盖。

Target missing lines:
- runner.py 130-131: _extract_step action 无 .tool 属性 (AttributeError branch)
- runner.py 152-154: get_agent_executor() singleton 懒构建
- tools.py 105: fetch_transcript asyncio.TimeoutError
- tools.py 207: create_obsidian_note 未配置 obsidian_vault_path
- tools.py 288-290: create_learning_event 内部 Exception
- tools.py 336: send_notification reminder_id 写入 results
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Register Task / Source / Hotspot tables for Base.metadata.create_all
from aipulse.store import models as _store_models  # noqa: F401
from aipulse.hotspot import models as _hotspot_models  # noqa: F401
from aipulse.models import learning_events, followed_up, followed_up_collections  # noqa: F401

from aipulse.summarizers.agent import runner
from aipulse.summarizers.agent.tools import (
    create_obsidian_note,
    create_learning_event,
    fetch_transcript,
    send_notification,
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db() -> None:
    """保证 DB schema 一致。"""
    from aipulse.store.database import reset_db

    await reset_db()


# ============================================================
# runner.py — missing line 130-131 (_extract_step AttributeError)
# ============================================================


class TestRunnerExtractStepEdgeCases:
    @pytest.mark.unit
    def test_extract_step_skips_action_without_tool_attr(self):
        """action 没有 .tool 属性（AttributeError）→ 跳过这条 step (130-131)"""
        class _BadAction:
            @property
            def tool(self):
                raise AttributeError("no tool")

        bad_action = _BadAction()
        good_action = MagicMock()
        good_action.tool = "summarize"
        output = json.dumps({"summary_markdown": "the summary"})

        result = {
            "intermediate_steps": [
                (bad_action, "irrelevant"),
                (good_action, output),
            ]
        }
        assert runner._extract_step(result, "summarize", "summary_markdown") == "the summary"

    @pytest.mark.unit
    def test_extract_step_all_actions_have_no_tool(self):
        """所有 action 都没 tool → 返回 None"""
        result = {"intermediate_steps": []}
        assert runner._extract_step(result, "summarize", "summary_markdown") is None


class TestRunnerSingletonInit:
    @pytest.mark.unit
    def test_get_agent_executor_lazy_builds_singleton(self):
        """get_agent_executor() 第一次调用构建 singleton (152-154)

        patch build_agent_executor 让其返回 fake executor。
        重置 module-level _executor_singleton（确保走 None branch）。
        """
        fake_executor = MagicMock(name="fake_executor")
        with patch(
            "aipulse.summarizers.agent.runner.build_agent_executor",
            return_value=fake_executor,
        ) as mock_build:
            # patch 整个 module 内的 _executor_singleton 在测试期间为 None，
            # finally 恢复原值（可能是 None 或真实 executor）。这样不会污染后续测试。
            with patch.object(runner, "_executor_singleton", None):
                e1 = runner.get_agent_executor()
                e2 = runner.get_agent_executor()

        assert mock_build.call_count == 1
        assert e1 is fake_executor
        assert e2 is fake_executor


# ============================================================
# tools.py — missing line 105 (fetch_transcript TimeoutError)
# ============================================================


class TestFetchTranscriptTimeout:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_returns_localized_error(self):
        """asyncio.TimeoutError → '[ERROR] 字幕拉取超时（30s）：{video_id}' (105)

        使用 respx 拦截 httpx request 抛 TimeoutError，触发 except 分支。
        """
        import respx

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__regex=r".*").mock(side_effect=asyncio.TimeoutError())
            result = await fetch_transcript.ainvoke({"video_id": "BV_TIMEOUT"})

        assert "[ERROR] 字幕拉取超时（30s）" in result
        assert "BV_TIMEOUT" in result


# ============================================================
# tools.py — missing line 207 (create_obsidian_note 未配置 vault)
# ============================================================


class TestCreateObsidianNoteMissingVault:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_vault_returns_error(self):
        """obsidian_vault_path=None → 不创建文件，返回 ok=False (207)"""
        settings = MagicMock()
        settings.obsidian_vault_path = None  # falsy → 走 not vault branch
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV_NO_VAULT",
                    "markdown": "hello",
                    "title": "T",
                    "up_name": "U",
                }
            )
        assert result["ok"] is False
        assert "未配置 obsidian_vault_path" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_string_vault_returns_error(self):
        """obsidian_vault_path="" → falsy → 走 not vault branch"""
        settings = MagicMock()
        settings.obsidian_vault_path = ""
        settings.obsidian_archive_folder = "AIPulse"
        settings.kimi_model = "kimi-for-coding"

        with patch("aipulse.summarizers.agent.tools.get_settings", return_value=settings):
            result = await create_obsidian_note.ainvoke(
                {
                    "video_id": "BV_EMPTY",
                    "markdown": "hi",
                    "title": "T",
                    "up_name": "U",
                }
            )
        assert result["ok"] is False


# ============================================================
# tools.py — missing line 288-290 (create_learning_event Exception)
# ============================================================


class TestCreateLearningEventException:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_internal_db_exception_returns_error(self):
        """create_learning_event 内部抛错 → ok=False + error (288-290)

        策略：patch `aipulse.store.database.get_session_maker` — 它是 create_learning_event
        内部 lazy import 的 source module。async with session_maker() 的 session.execute
        抛 RuntimeError。
        """
        from aipulse.store import database as db_mod

        class _BrokenSession:
            """session.execute 抛 RuntimeError — 触发 except 分支。"""

            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *args):
                return None

            async def execute(self_inner, *args, **kwargs):
                raise RuntimeError("simulated DB failure")

            def add(self_inner, obj):
                return obj

            async def commit(self_inner):
                return None

            async def rollback(self_inner):
                return None

            async def refresh(self_inner, obj):
                return None

        class _BrokenMaker:
            def __call__(self_inner):
                return _BrokenSession()

        with patch.object(db_mod, "get_session_maker", return_value=_BrokenMaker()):
            result = await create_learning_event.ainvoke(
                {
                    "video_id": "BV_DB_FAIL",
                    "note_path": "/x.md",
                    "scheduled_at": "2026-01-01T00:00:00",
                    "topic": "topic",
                }
            )

        assert result["ok"] is False
        assert "DB 写入失败" in result["error"]


# ============================================================
# tools.py — missing line 336 (send_notification reminder_id)
# ============================================================


class TestSendNotificationReminderId:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reminder_id_stored_in_results(self, tmp_path):
        """create_reminder 返回 reminder_id → results["reminder_id"] = ... (336)

        注入 fake aipulse.apple.reminders module 让 import 成功，且 create_reminder
        返回 reminder_id 字符串，让 line 336 赋值执行。
        """
        note = tmp_path / "note.md"
        note.write_text("# title\n", encoding="utf-8")

        fake_reminders_mod = MagicMock()
        fake_reminders_mod.create_reminder = AsyncMock(return_value="rm-test-1")

        with patch.dict(
            "sys.modules", {"aipulse.apple.reminders": fake_reminders_mod}
        ):
            with patch("sys.platform", "darwin"):
                result = await send_notification.ainvoke(
                    {
                        "note_path": str(note),
                        "scheduled_at": "2026-12-31T15:30:00",
                        "topic": "review topic",
                    }
                )

        assert result["ok"] is True
        assert result["obsidian_task"] is True
        assert result["reminder_id"] == "rm-test-1"
        assert "reminder_error" not in result