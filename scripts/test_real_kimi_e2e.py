"""Real Kimi E2E — exercise the full LangChain Agent pipeline against api.kimi.com.

NOT a unit test: this is a verification script. It deliberately bypasses the
build_agent_executor monkeypatch used in tests/unit/summarizers/test_agent.py
and calls into the real LangChain stack with the real Kimi API key from .env.

Usage:
    uv run python scripts/test_real_kimi_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Ensure src/ is on sys.path so we can import aipulse.* without installing.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from aipulse.core.config import get_settings  # noqa: E402
from aipulse.summarizers.agent.runner import (  # noqa: E402
    build_agent_executor,
    run_summary_pipeline,
)


def _banner(msg: str) -> None:
    print("\n" + "=" * 72)
    print(msg)
    print("=" * 72)


async def main() -> int:
    settings = get_settings()
    api_key = settings.kimi_api_key.get_secret_value()
    print(f"key set: {bool(api_key)}")
    print(f"key prefix: {api_key[:10] + '...' if api_key else '(empty)'}")
    print(f"base_url:  {settings.kimi_base_url}")
    print(f"model:     {settings.kimi_model}")

    if not api_key or api_key == "sk-placeholder-for-build":
        print("ERROR: no real Kimi key configured.", file=sys.stderr)
        return 1

    _banner("[1/3] Build real LangChain ReAct agent (no monkeypatch)")
    executor = build_agent_executor()
    print(f"executor type: {type(executor).__name__}")

    _banner("[2/3] Run a real summarize call against api.kimi.com")
    fake_video_id = f"e2e-{uuid.uuid4().hex[:8]}"
    print(f"video_id: {fake_video_id}")
    print("(this may take 10-30s while Kimi reasons + responds)")

    result = await run_summary_pipeline(
        video_id=fake_video_id,
        title="E2E Kimi 链路验证",
        up_name="manual-e2e",
        extra_context="转写文本：AIPulse 是一个 Tauri + Python sidecar 的桌面端 AI 内容管理工具。今天我们测试 Kimi 真实链路是否打通。",
    )
    print(f"\nresult keys: {sorted(result.keys())}")
    print(f"status:      {result.get('status')}")
    print(f"summary:     {(result.get('summary') or '')[:300]}")

    _banner("[3/3] Done")
    if result.get("status") == "failed":
        print(f"FAILED: {result.get('error')}")
        return 2
    print("OK — real Kimi call returned a summary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))