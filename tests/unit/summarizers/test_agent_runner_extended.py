"""Extended unit tests for summarizers/agent/runner.py.

覆盖未达 80% 的路径：
- _extract_step: tool 名不匹配、Action 对象无 .tool 属性、JSON 解析失败、parsed 非 dict、字段 None
- run_summary_pipeline: TimeoutError → partial、Exception → failed
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aipulse.summarizers.agent.runner import _extract_step, run_summary_pipeline


def _make_action(tool_name: str):
    """构造一个 mock AgentAction-like 对象（含 .tool 属性）"""
    action = MagicMock()
    action.tool = tool_name
    return action


class TestExtractStep:
    """覆盖 _extract_step 各分支。"""

    @pytest.mark.unit
    def test_returns_none_when_intermediate_steps_missing(self):
        """result 无 intermediate_steps → return None"""
        assert _extract_step({}, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_returns_none_when_tool_not_found(self):
        """intermediate_steps 中无匹配 tool → return None"""
        action = _make_action("other_tool")
        result = {"intermediate_steps": [(action, json.dumps({"note_path": "/x.md"}))]}
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_extracts_field_from_string_output(self):
        """output 是 JSON 字符串 → 解析后取字段"""
        action = _make_action("create_obsidian_note")
        result = {
            "intermediate_steps": [(action, json.dumps({"note_path": "/path/to/note.md", "ok": True}))]
        }
        assert _extract_step(result, "create_obsidian_note", "note_path") == "/path/to/note.md"

    @pytest.mark.unit
    def test_extracts_field_from_dict_output(self):
        """output 已经是 dict → 直接取字段"""
        action = _make_action("create_obsidian_note")
        result = {
            "intermediate_steps": [(action, {"note_path": "/from/dict.md"})]
        }
        assert _extract_step(result, "create_obsidian_note", "note_path") == "/from/dict.md"

    @pytest.mark.unit
    def test_returns_none_when_field_missing(self):
        """parsed dict 没有目标字段 → return None"""
        action = _make_action("create_obsidian_note")
        result = {"intermediate_steps": [(action, json.dumps({"ok": True}))]}
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_returns_none_when_field_is_none(self):
        """parsed dict 字段值为 None → return None"""
        action = _make_action("create_obsidian_note")
        result = {"intermediate_steps": [(action, json.dumps({"note_path": None}))]}
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_returns_none_on_invalid_json(self):
        """output 不是合法 JSON → return None"""
        action = _make_action("create_obsidian_note")
        result = {"intermediate_steps": [(action, "not json at all")]}

        # tools.py 用 `_extract_step(result, ...)`，output 是字符串时尝试 json.loads
        # 解析失败 → return None
        # 注意：返回 None 后会被调用方当成"未执行该 tool"
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_returns_none_when_parsed_not_dict(self):
        """output 解析后不是 dict（如 list/str 数字） → return None"""
        action = _make_action("create_obsidian_note")
        # 合法 JSON 但不是 dict
        result = {"intermediate_steps": [(action, json.dumps([1, 2, 3]))]}
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_returns_none_when_action_lacks_tool_attr(self):
        """action 对象没有 .tool 属性 → AttributeError → return None"""

        class _NoToolAction:
            pass

        result = {
            "intermediate_steps": [(_NoToolAction(), json.dumps({"note_path": "/x.md"}))]
        }
        # `action.tool` 会 raise AttributeError → 被 except 捕获
        assert _extract_step(result, "create_obsidian_note", "note_path") is None

    @pytest.mark.unit
    def test_converts_non_string_value_to_string(self):
        """parsed 字段值是数字/bool → 转 str"""

        action = _make_action("create_learning_event")
        result = {
            "intermediate_steps": [(action, json.dumps({"event_id": 12345}))]
        }
        assert _extract_step(result, "create_learning_event", "event_id") == "12345"


class TestRunPipelineErrors:
    """覆盖 run_summary_pipeline 异常路径。"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_returns_partial_status(self):
        """AgentExecutor 超时 → status=partial"""

        fake_executor = MagicMock()

        async def _slow_ainvoke(*args, **kwargs):
            await asyncio.sleep(10)
            return {"intermediate_steps": []}

        fake_executor.ainvoke = _slow_ainvoke

        with patch("aipulse.summarizers.agent.runner.build_agent_executor", return_value=fake_executor):
            # 缩短 wait_for 触发 TimeoutError
            with patch("aipulse.summarizers.agent.runner.asyncio.wait_for") as mock_wait:
                async def _raise_timeout(awaitable, timeout):
                    raise asyncio.TimeoutError()
                mock_wait.side_effect = _raise_timeout
                result = await run_summary_pipeline(
                    video_id="BV1",
                    title="t",
                    up_name="up",
                )

        assert result["status"] == "partial"
        assert "超时" in result["error"]
        assert result["intermediate_steps"] == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generic_exception_returns_failed_status(self):
        """AgentExecutor 抛其他异常 → status=failed"""

        fake_executor = MagicMock()

        async def _boom_ainvoke(*args, **kwargs):
            raise RuntimeError("API exploded")

        fake_executor.ainvoke = _boom_ainvoke

        with patch("aipulse.summarizers.agent.runner.build_agent_executor", return_value=fake_executor):
            result = await run_summary_pipeline(
                video_id="BV1",
                title="t",
                up_name="up",
            )

        assert result["status"] == "failed"
        assert "API exploded" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_extracts_three_fields(self):
        """成功路径下，从 intermediate_steps 提取三个字段"""

        fake_executor = MagicMock()
        fake_executor.ainvoke = AsyncMock(
            return_value={
                "output": "ok",
                "intermediate_steps": [
                    (
                        _make_action("create_obsidian_note"),
                        json.dumps({"note_path": "/notes/x.md", "ok": True}),
                    ),
                    (
                        _make_action("create_learning_event"),
                        json.dumps({"event_id": "ev-1", "ok": True}),
                    ),
                    (
                        _make_action("send_notification"),
                        json.dumps({"reminder_id": "rm-1", "ok": True}),
                    ),
                ],
            }
        )

        with patch("aipulse.summarizers.agent.runner.build_agent_executor", return_value=fake_executor):
            result = await run_summary_pipeline(
                video_id="BV1",
                title="t",
                up_name="up",
            )

        assert result["status"] == "completed"
        assert result["note_path"] == "/notes/x.md"
        assert result["event_id"] == "ev-1"
        assert result["reminder_id"] == "rm-1"
        # intermediate_steps 也被格式化为 {tool, output}
        assert len(result["intermediate_steps"]) == 3
        assert result["intermediate_steps"][0]["tool"] == "create_obsidian_note"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_success_partial_steps(self):
        """某些 step 输出字段缺失 → 对应字段为 None，其他正常提取"""

        fake_executor = MagicMock()
        fake_executor.ainvoke = AsyncMock(
            return_value={
                "output": "ok",
                "intermediate_steps": [
                    (
                        _make_action("create_obsidian_note"),
                        json.dumps({"note_path": "/notes/x.md", "ok": True}),
                    ),
                    # create_learning_event 输出但 event_id 缺失
                    (
                        _make_action("create_learning_event"),
                        json.dumps({"ok": False, "error": "DB fail"}),
                    ),
                    # send_notification 完全没出现在 steps 里
                ],
            }
        )

        with patch("aipulse.summarizers.agent.runner.build_agent_executor", return_value=fake_executor):
            result = await run_summary_pipeline(
                video_id="BV1",
                title="t",
                up_name="up",
            )

        assert result["status"] == "completed"
        assert result["note_path"] == "/notes/x.md"
        assert result["event_id"] is None  # 字段不存在
        assert result["reminder_id"] is None  # step 缺失