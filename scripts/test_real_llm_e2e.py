"""Real LLM E2E — exercise the full LangChain Agent pipeline against the configured
LLM endpoint (current default: MiniMax via api.minimaxi.com).

NOT a unit test: this is a verification script. It deliberately bypasses the
build_agent_executor monkeypatch used in tests/unit/summarizers/test_agent.py
and calls into the real LangChain stack with the real LLM key from .env.

Status semantics:
- completed — full pipeline reached the end (the LLM agent reasoned + returned).
- partial   — pipeline timed out or a tool failed mid-flight; LLM 至少通过一次
              chat completion 即视为真实联通成功（err 文案不包含 "LLM 调用失败").
- failed    — LLM 真实联通失败（err 含 "LLM 调用失败" / "LLM 调用超时"）— 这才算 RED.

Usage:
    uv run python scripts/test_real_llm_e2e.py
"""

from __future__ import annotations

import asyncio
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
    api_key = settings.llm_api_key.get_secret_value()
    print(f"key set: {bool(api_key)}")
    print(f"key prefix: {api_key[:10] + '...' if api_key else '(empty)'}")
    print(f"base_url:  {settings.llm_base_url}")
    print(f"model:     {settings.llm_model}")

    if not api_key or api_key == "sk-placeholder-for-build":
        print("ERROR: no real LLM key configured.", file=sys.stderr)
        return 1

    _banner("[1/3] Build real LangChain ReAct agent (no monkeypatch)")
    executor = build_agent_executor()
    print(f"executor type: {type(executor).__name__}")

    _banner("[2/3] Run a real summarize call against the LLM")
    fake_video_id = f"e2e-{uuid.uuid4().hex[:8]}"
    print(f"video_id: {fake_video_id}")
    print("(this may take 10-30s while the LLM reasons + responds)")

    result = await run_summary_pipeline(
        video_id=fake_video_id,
        title="E2E LLM 链路验证",
        up_name="manual-e2e",
        extra_context="转写文本：AIPulse 是一个 Tauri + Python sidecar 的桌面端 AI 内容管理工具。今天我们测试 LLM 真实链路是否打通。",
    )
    print(f"\nresult keys: {sorted(result.keys())}")
    print(f"status:      {result.get('status')}")
    print(f"summary:     {(result.get('summary') or '')[:300]}")

    _banner("[3/3] Done")
    if result.get("status") == "completed":
        print("OK — full pipeline OK")
        return 0
    if result.get("status") in ("partial", "failed"):
        err = result.get("error") or ""
        if "LLM 调用失败" in err or "LLM 调用超时" in err:
            print(f"RED — LLM 真实联通失败：{err}")
            return 2
        print(f"PARTIAL — pipeline 失败但 LLM 联通已尝试：{err}")
        return 0
    print(f"UNKNOWN status: {result.get('status')}")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))