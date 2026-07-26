"""Unit tests for the v0.3 ReAct Agent (spec §5).

验证：
- prompts 字符串拼接
- runner build_agent_executor 不抛异常
- ALL_TOOLS 含 6 个工具
- default_scheduled_at 返回 ISO8601
- judge 默认 fallback 行为（score=0.7, should_archive=True）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aipulse.summarizers.agent import ALL_TOOLS, build_agent_executor, run_summary_pipeline
from aipulse.summarizers.agent.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
    build_judge_prompt,
    build_summary_prompt,
)
from aipulse.summarizers.agent.tools import (
    create_learning_event,
    create_obsidian_note,
    default_scheduled_at,
    fetch_transcript,
    judge_tech_relevance,
    send_notification,
    summarize,
)


class TestPrompts:
    @pytest.mark.unit
    def test_system_prompt_includes_all_six_tools(self):
        for tool_name in (
            "fetch_transcript",
            "summarize",
            "judge_tech_relevance",
            "create_obsidian_note",
            "create_learning_event",
            "send_notification",
        ):
            assert tool_name in SYSTEM_PROMPT_TEMPLATE

    @pytest.mark.unit
    def test_build_summary_prompt_includes_transcript(self):
        out = build_summary_prompt(transcript="hello world", extra_context="title: t")
        assert "hello world" in out
        assert "title: t" in out

    @pytest.mark.unit
    def test_build_summary_prompt_handles_empty_context(self):
        out = build_summary_prompt(transcript="x")
        assert "(无)" in out

    @pytest.mark.unit
    def test_build_judge_prompt_truncates_markdown(self):
        # 用两个不同的字符序列方便判断哪个被保留
        head = "HEADMARKER" + ("x" * 1000)
        tail = ("y" * 1000) + "TAILMARKER"
        md = head + tail  # 总长 2020（< 3000 → 完整保留）

        out = build_judge_prompt(markdown=md)
        # 短 markdown：完整保留
        assert "HEADMARKER" in out
        assert "TAILMARKER" in out

        # 长 markdown：截断到 3000 → tail 部分被砍掉
        long_md = ("x" * 3000) + ("Q" * 5000)
        out_long = build_judge_prompt(markdown=long_md)
        # 5000 个 Q 都在 [3000:] 之后 -> 截断后整段消失
        assert "QQQQQ" not in out_long

    @pytest.mark.unit
    def test_build_judge_prompt_contains_score_threshold(self):
        out = build_judge_prompt(markdown="x")
        assert "score >= 0.6" in out


class TestTools:
    @pytest.mark.unit
    def test_all_tools_have_six_entries(self):
        assert len(ALL_TOOLS) == 6

    @pytest.mark.unit
    def test_default_scheduled_at_is_future_iso(self):
        s = default_scheduled_at()
        parsed = datetime.fromisoformat(s)
        # 应当在未来 23-25 小时
        now = datetime.now(UTC)
        delta = parsed - now
        assert timedelta(hours=23) <= delta <= timedelta(hours=25)


class TestSummarizeTool:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_returns_error_on_empty_transcript(self):
        # summarize 是 langchain @tool，需要 .ainvoke 或 .func 拿到底层函数
        result = await summarize.ainvoke(
            {"video_id": "BV1", "transcript": "", "extra_context": ""}
        )
        assert result["ok"] is False
        assert "字幕" in result["error"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summarize_returns_error_on_error_transcript(self):
        result = await summarize.ainvoke(
            {"video_id": "BV1", "transcript": "[ERROR] 字幕不可用", "extra_context": ""}
        )
        assert result["ok"] is False


class TestJudgeTool:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_judge_tech_relevance_handles_invalid_json(self):
        # judge 内部 `from aipulse.summarizers.llm import OpenAICompatibleAdapter`
        # 在函数体内 — 替换 aipulse.summarizers.llm.OpenAICompatibleAdapter
        from aipulse.summarizers import llm as llm_mod

        class _FakeAdapter:
            def __init__(self, *args, **kwargs):
                pass

            async def complete(self, prompt, system=None):
                return "this is not JSON at all"

        original = llm_mod.OpenAICompatibleAdapter
        llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
        try:
            result = await judge_tech_relevance.ainvoke({"markdown": "x" * 100})
        finally:
            llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]

        assert result["ok"] is False
        assert result["score"] == 0.7
        assert result["should_archive"] is True


class TestAgentExecutor:
    @pytest.mark.unit
    def test_build_agent_executor_returns_executor(self):
        # 不实际触发 LLM 调用 — 只验证构建成功
        executor = build_agent_executor()
        assert executor is not None
        # AgentExecutor 有 max_iterations 和 max_execution_time
        assert executor.max_iterations == 10
        assert executor.max_execution_time == 300


class TestRunPipelineContract:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_summary_pipeline_returns_dict(self):
        # mock executor 来避免真实 LLM 调用
        from unittest.mock import AsyncMock, MagicMock, patch

        fake_executor = MagicMock()
        fake_executor.ainvoke = AsyncMock(
            return_value={
                "intermediate_steps": [],
                "output": "ok",
            }
        )

        with patch("aipulse.summarizers.agent.runner.get_agent_executor", return_value=fake_executor):
            result = await run_summary_pipeline(
                video_id="BV1",
                title="t",
                up_name="up",
            )

        assert result["status"] == "completed"
        assert "intermediate_steps" in result