"""Agent 初始化 + 运行入口 (spec §5.8)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.prompts import PromptTemplate

from aipulse.summarizers.agent.prompts import SYSTEM_PROMPT_TEMPLATE
from aipulse.summarizers.agent.tools import ALL_TOOLS, default_scheduled_at
from aipulse.summarizers.llm import OpenAICompatibleAdapter


logger = logging.getLogger(__name__)


REACT_PROMPT = PromptTemplate.from_template(
    """{system_prompt}

## 可用工具
{tools}

## 工具名称列表
{tool_names}

## 之前的对话
{chat_history}

## 用户输入
{input}

## Agent 思考过程
Thought: {agent_scratchpad}"""
)


def _build_chat_model():
    """Build a ChatOpenAI-compatible LangChain chat model using the Kimi endpoint."""
    from aipulse.core.config import get_settings

    from langchain_openai import ChatOpenAI

    settings = get_settings()
    api_key = settings.kimi_api_key.get_secret_value() or settings.llm_api_key.get_secret_value()
    base_url = settings.kimi_base_url or settings.llm_base_url
    model = settings.kimi_model or settings.llm_model

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=1.0,  # Kimi kimi-for-coding only supports 1.0
    )


def build_agent_executor():
    """Build ReAct Agent + AgentExecutor (singleton-friendly).

    NOTE: import of langchain.agents is deferred so import errors don't block the
    rest of the summarizer package during dev iteration.
    """
    from langchain.agents import AgentExecutor, create_react_agent

    llm = _build_chat_model()
    prompt = REACT_PROMPT.partial(system_prompt=SYSTEM_PROMPT_TEMPLATE)
    agent = create_react_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=False,
        max_iterations=10,
        max_execution_time=300,  # 5 分钟硬超时（Q141）
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


async def run_summary_pipeline(
    video_id: str,
    title: str,
    up_name: str,
    extra_context: str = "",
) -> dict[str, Any]:
    """Run the full summary pipeline via the AgentExecutor.

    Returns:
        {status: completed|failed|partial, note_path, event_id, reminder_id, error, steps}
    """
    executor = build_agent_executor()
    user_input = (
        f"请对视频 {video_id}（标题：{title}，UP主：{up_name}）执行完整总结 pipeline。"
        f"使用默认 scheduled_at（{default_scheduled_at()}）。{extra_context}"
    )
    try:
        result = await asyncio.wait_for(
            executor.ainvoke({"input": user_input, "chat_history": []}),
            timeout=300.0,
        )
        return {
            "status": "completed",
            "note_path": _extract_step(result, "create_obsidian_note", "note_path"),
            "event_id": _extract_step(result, "create_learning_event", "event_id"),
            "reminder_id": _extract_step(result, "send_notification", "reminder_id"),
            "error": None,
            "intermediate_steps": [
                {"tool": step[0].tool, "output": step[1]}
                for step in result.get("intermediate_steps", [])
            ],
        }
    except asyncio.TimeoutError:
        logger.error("Agent pipeline timeout for %s", video_id)
        return {
            "status": "partial",
            "error": "5 分钟超时，已记录 intermediate_steps",
            "intermediate_steps": [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent pipeline failed for %s", video_id)
        return {"status": "failed", "error": f"{exc!s}", "intermediate_steps": []}


def _extract_step(result: dict, tool_name: str, field: str) -> str | None:
    """Pull a field out of the tool output inside intermediate_steps."""
    for action, output in result.get("intermediate_steps", []):
        if action.tool == tool_name:
            try:
                parsed = json.loads(output) if isinstance(output, str) else output
                if isinstance(parsed, dict):
                    val = parsed.get(field)
                    if val is not None:
                        return str(val)
            except (json.JSONDecodeError, AttributeError):
                return None
    return None


# Singleton executor (lazily built on first call)
_executor_singleton = None


def get_agent_executor():
    """Return (and lazily build) the shared AgentExecutor."""
    global _executor_singleton
    if _executor_singleton is None:
        _executor_singleton = build_agent_executor()
    return _executor_singleton