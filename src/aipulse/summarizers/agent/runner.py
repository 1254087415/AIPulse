"""Agent 初始化 + 运行入口 (spec §5.8)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
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
    """Build a ChatOpenAI-compatible LangChain chat model for the LLM endpoint.

    Note on `api_key=None`: the underlying OpenAI SDK enforces that `api_key`
    is set at construction time (it falls back to the `OPENAI_API_KEY` env var,
    failing with `openai.OpenAIError` when neither is present). To keep
    ``build_agent_executor()`` callable in test / startup paths where no key
    has been configured yet, we substitute a sentinel placeholder. Real
    invocations reach the LLM endpoint only when a PATCH /api/settings or
    ``.env`` has populated an actual key — at which point the placeholder is
    replaced by the real value on the next ``build_agent_executor()`` call.
    """
    from aipulse.core.config import get_settings

    from langchain_openai import ChatOpenAI

    settings = get_settings()
    api_key = settings.llm_api_key.get_secret_value()
    if not api_key:
        api_key = "sk-placeholder-for-build"
    base_url = settings.llm_base_url
    model = settings.llm_model

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=1.0,
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
    # L7 (2026-07-26): 用 LangChain callback 实时捕获每个 tool call 到外层
    # mutable list —— 即便 asyncio.wait_for 触发 TimeoutError、LangChain 内部
    # intermediate_steps 被 cancel 清掉，callback 已记录过的步骤不会丢失。
    # error 字段文案必须和 intermediate_steps 实际内容一致（feedback
    # status-must-not-mask-failure 硬约束）。
    captured_steps: list[dict[str, Any]] = []
    step_capture = _StepCaptureCallback(captured_steps)

    try:
        result = await asyncio.wait_for(
            executor.ainvoke(
                {"input": user_input, "chat_history": []},
                config={"callbacks": [step_capture]},
            ),
            timeout=300.0,
        )
        return {
            "status": "completed",
            "note_path": _extract_step(result, "create_obsidian_note", "note_path"),
            "event_id": _extract_step(result, "create_learning_event", "event_id"),
            "reminder_id": _extract_step(result, "send_notification", "reminder_id"),
            "hotspot_id": _extract_step(result, "create_learning_event", "hotspot_id"),
            "error": None,
            "intermediate_steps": [
                {"tool": step[0].tool, "output": step[1]}
                for step in result.get("intermediate_steps", [])
            ],
        }
    except asyncio.TimeoutError:
        # L7: error 文案如实反映 captured_steps 状态。若 captured_steps 为空
        # 说明 LangChain 在 cancel 之前还没触发任何 on_tool_end（如 LLM 调用
        # 阶段就超时）→ 文案必须说"未记录"。
        logger.error(
            "Agent pipeline timeout for %s after 300s (captured_steps=%d)",
            video_id,
            len(captured_steps),
        )
        if captured_steps:
            err_msg = (
                f"5 分钟超时，已记录 {len(captured_steps)} 个 intermediate_steps"
            )
        else:
            err_msg = "5 分钟超时，未记录 intermediate_steps（cancel 前 callback 未触发）"
        return {
            "status": "partial",
            "error": err_msg,
            "intermediate_steps": list(captured_steps),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent pipeline failed for %s", video_id)
        # L7: 同样如实记录 captured_steps，不撒谎
        return {
            "status": "failed",
            "error": f"{exc!s}",
            "intermediate_steps": list(captured_steps),
        }


def _extract_step(result: dict, tool_name: str, field: str) -> str | None:
    """Pull a field out of the tool output inside intermediate_steps."""
    for action, output in result.get("intermediate_steps", []):
        try:
            action_tool = getattr(action, "tool", None)
        except AttributeError:  # pragma: no cover  # defensive — getattr default prevents this
            continue
        if action_tool != tool_name:
            continue
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


class _StepCaptureCallback(AsyncCallbackHandler):
    """LangChain async callback —— 每个 tool call 完成后把 (tool, output) 写到外部 list。

    L7 (2026-07-26) 修复 silent-failure：即便 asyncio.wait_for 因超时 cancel
    inner task，callback 已 fire 的步骤仍然保留；TimeoutError 路径能返回
    真实 intermediate_steps 而非真空。
    """

    def __init__(self, sink: list[dict[str, Any]]) -> None:
        super().__init__()
        self._sink = sink
        # on_tool_start 时按 run_id 记 tool 名，on_tool_end 时查回。
        self._run_id_to_tool: dict[str, str] = {}

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        tool_name = (serialized or {}).get("name") or "unknown"
        self._run_id_to_tool[str(run_id)] = tool_name

    async def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:
        tool_name = self._run_id_to_tool.pop(str(run_id), "unknown")
        try:
            output_str = output if isinstance(output, str) else json.dumps(output)
        except (TypeError, ValueError):
            output_str = str(output)
        self._sink.append({"tool": tool_name, "output": output_str})