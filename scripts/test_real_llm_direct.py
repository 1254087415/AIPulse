"""Direct LLM API call via LangChain ChatOpenAI (no ReAct/Agent).

Sanity-check that the configured LLM endpoint (current default: MiniMax via
api.minimaxi.com) responds with a non-empty content field. Bypasses
build_agent_executor() entirely so the test does not depend on Obsidian vault /
Reminders / DB tools being reachable.

Usage:
    uv run python scripts/test_real_llm_direct.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from aipulse.core.config import get_settings  # noqa: E402


async def main() -> int:
    settings = get_settings()
    api_key = settings.llm_api_key.get_secret_value()
    print(f"key set: {bool(api_key)}")
    print(f"key prefix: {api_key[:10] + '...' if api_key else '(empty)'}")
    print(f"base_url:  {settings.llm_base_url}")
    print(f"model:     {settings.llm_model}")
    if not api_key:
        print("ERROR: no key", file=sys.stderr)
        return 1

    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        temperature=1.0,
    )
    print("\nInvoking LLM with a single HumanMessage...")
    resp = await llm.ainvoke([
        HumanMessage(content="用一句话解释什么是 ReAct Agent。中文回答，不超过 50 字。"),
    ])
    content = resp.content if isinstance(resp.content, str) else str(resp.content)
    print(f"\nfinish_reason: {getattr(resp, 'response_metadata', {}).get('finish_reason')}")
    print(f"content ({len(content)} chars): {content!r}")
    return 0 if content and len(content) > 5 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))