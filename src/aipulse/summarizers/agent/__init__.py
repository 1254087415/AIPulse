"""v0.3 LangChain ReAct Agent + 6 个 @tool (spec §5).

Public surface:
    from aipulse.summarizers.agent import ALL_TOOLS, build_agent_executor, run_summary_pipeline
"""

from aipulse.summarizers.agent.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
    build_judge_prompt,
    build_summary_prompt,
)
from aipulse.summarizers.agent.runner import (
    build_agent_executor,
    get_agent_executor,
    run_summary_pipeline,
)
from aipulse.summarizers.agent.tools import (
    ALL_TOOLS,
    create_learning_event,
    create_obsidian_note,
    default_scheduled_at,
    fetch_transcript,
    judge_tech_relevance,
    send_notification,
    summarize,
)

__all__ = [
    "ALL_TOOLS",
    "SYSTEM_PROMPT_TEMPLATE",
    "build_judge_prompt",
    "build_summary_prompt",
    "build_agent_executor",
    "get_agent_executor",
    "run_summary_pipeline",
    "create_learning_event",
    "create_obsidian_note",
    "default_scheduled_at",
    "fetch_transcript",
    "judge_tech_relevance",
    "send_notification",
    "summarize",
]