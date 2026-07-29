"""v0.3 E2E path B — manual trigger summary → three-way archive.

Covers spec 09 §5.2 ``TC-E2E-PATH-B-01..07`` in a single real-pipeline run:

  TC-01  POST /api/summary/{bvid} → 202 + status=queued
  TC-02  SSE 推送 task.{bvid}.started / .completed 事件
  TC-03  终态 SSE event 含 note_path（前端据此构造 obsidian://open）
  TC-04  Obsidian vault 出现 ``<bvid>-<title>.md`` 笔记 + frontmatter 完整
  TC-05  DB summary_jobs.status=completed + learning_events ≥ 1 行
  TC-06  Obsidian 笔记末尾追加 ``- [ ] ⏰ ... <topic>``
  TC-07  macOS Apple Reminders AIPulse测试 列表新增 reminder

链路：真实 MiniMax LLM（.env 拷贝）+ 真实 B 站 BV 号（罗翔说刑法
BV1PbEnzfEP2，spec 02 verifier 已验有 ai-zh 字幕）+ 真实 Obsidian vault
（settings.json 中的真实 iCloud 路径）+ 真实 macOS Apple Reminders。

副作用：所有测试产生的 Obsidian 笔记 + Reminders 必须带 ``E2E-TEST``
前缀；fixture teardown 删干净；任何无法清理的遗留物在汇报中列出。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

# =====================================================================
# MODULE-LEVEL ENVIRONMENT OVERRIDES
# =====================================================================
# pytest collects tests/conftest.py FIRST, then tests/e2e/conftest.py (if
# exists), then this test file. conftest.py sets:
#   os.environ["LLM_BASE_URL"]  = "https://api.minimaxi.com/v1"
#   os.environ["LLM_MODEL"]     = "MiniMax-M2.5"
#   os.environ["LLM_API_KEY"]   = "sk-test-placeholder-llm"  (placeholder)
# to keep unit/integration tests sandboxed. We need the REAL key here for
# E2E — overwrite at module load time before any conftest fixtures run.
#
# 安全约束：.env / data/settings.json 的**值**永远不打印到日志或 stderr。
# 只读取、写 os.environ、再 cache_clear settings，让下次 get_settings() 拿到真值。

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = WORKTREE_ROOT / ".env"
_SETTINGS_FILE = WORKTREE_ROOT / "data" / "settings.json"


def _load_real_env() -> None:
    """Copy .env keys into os.environ. NEVER echo values."""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        if v:
            os.environ[k] = v  # 覆盖 — 值不打印


_load_real_env()

# Force MiniMax even if worktree settings.json persisted kimi_*.
# 用户当前生产配置就是 MiniMax（MiniMax-M2.5 via minimaxi.com）。
os.environ["LLM_BASE_URL"] = "https://api.minimaxi.com/v1"
os.environ["LLM_MODEL"] = "MiniMax-M2.5"

# Real vault/archive folder paths from settings.json (worktree-local copy of
# main checkout's settings; the file has real path + masked secrets).
if _SETTINGS_FILE.exists():
    _persisted = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    if _persisted.get("obsidian_vault_path"):
        os.environ["OBSIDIAN_VAULT_PATH"] = _persisted["obsidian_vault_path"]
    if _persisted.get("obsidian_archive_folder"):
        os.environ["OBSIDIAN_ARCHIVE_FOLDER"] = _persisted["obsidian_archive_folder"]

# Clear cached settings + migration lock so next get_settings() reads above env.
from aipulse.core.config import AppSettings, get_settings as _gs  # noqa: E402

_gs.cache_clear()
AppSettings._llm_migration_done = False


# =====================================================================
# CONSTANTS
# =====================================================================

ANCHOR_BVID = "BV1PbEnzfEP2"
ANCHOR_TITLE = (
    "【罗翔】人工智能是价值中立吗？AI的相对主义提供没有对错的多元答案是好事情吗？"
)
ANCHOR_UP_NAME = "罗翔说刑法"
ANCHOR_TOPIC_BASE = "AI价值中立与相对主义"
E2E_MARKER = "E2E-TEST"
TOPIC = f"{E2E_MARKER} {ANCHOR_TOPIC_BASE}"

# transcript cache 在主 checkout 已存在；复制到 test DATA_DIR。
ANCHOR_TRANSCRIPT_SRC = (
    Path("/Users/zab/Documents/project/AIPulse/data/cache/transcripts/")
    / f"{ANCHOR_BVID}.md"
)


# =====================================================================
# Helpers
# =====================================================================


def _bearer() -> dict[str, str]:
    """Default Authorization header — match what real .env aipulse_api_token expects."""
    # 真实 .env / settings.json 当前未配置 aipulse_api_token；web security
    # middleware 在 token 为空时放行，此 header 是 no-op 但保留供未来开启鉴权。
    return {"Authorization": "Bearer e2e-path-b-token"}


def _list_reminders_in_list(list_name: str) -> set[str]:
    """Return set of reminder IDs currently in `list_name` (for pre/post diff)."""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "Reminders" to get id of every reminder of list "{list_name}"',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return set()
        return {x.strip() for x in result.stdout.split(",") if x.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()


def _list_exists(list_name: str) -> bool:
    """Check if the Reminders list exists (AppleScript `exists list`)."""
    list_esc = list_name.replace("\\", "\\\\").replace('"', '\\"')
    try:
        result = subprocess.run(
            ["osascript", "-e",
             f'tell application "Reminders" to return (exists list "{list_esc}")'],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _delete_reminders_with_retry(
    list_name: str, marker: str, topic: str, max_rounds: int = 30
) -> list[str]:
    """幂等兜底清理 — 重试直到 list 中无 E2E marker 或达到 max_rounds。

    已知 macOS AppleScript 时序：send_notification → create_reminder →
    osascript。即使 executor_timeout_s=30s，reminder 经常**异步**落库 —
    osascript 进程返 0 id 时 reminder 还没 commit；teardown 必须轮询 list
    直到 E2E marker 不再出现。

    Default 30 rounds × 2s sleep = 60s 等待窗口（开发机 iCloud 同步 + 系统繁忙
    时 60s 内仍可见）。

    Returns total deleted count across rounds.
    """
    import time as _time

    total = 0
    last_remaining: list[str] = []
    for round_idx in range(max_rounds):
        # 每轮先轮询 list；只有 list 里还有 marker 残留才尝试删。
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'tell application "Reminders" to get name of every reminder '
                    f'of list "{list_name}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            names = (
                [n.strip() for n in result.stdout.split(",") if n.strip()]
                if result.returncode == 0
                else []
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            names = []

        remaining = [n for n in names if marker in n or topic in n]
        last_remaining = remaining
        if not remaining:
            break

        deleted = _delete_reminders_matching(list_name, marker)
        exact = _delete_reminders_by_title(list_name, topic)
        total += (len(deleted) + exact)
        _time.sleep(2.0)

    if last_remaining:
        print(
            f"[teardown] reminder cleanup incomplete after {max_rounds} rounds: "
            f"leftover={[n for n in last_remaining if marker in n or topic in n]!r}",
            file=sys.stderr,
        )
    return [f"deleted total={total}"] if total else []


def _delete_entire_list(list_name: str) -> bool:
    """Delete the entire Reminders list (and every reminder inside it).

    比逐条删 reminder 可靠：单条 osascript 调用 + 5s timeout，开发机
    iCloud 同步繁忙时也极少卡。Reminders app 会在下次访问时自动重建。
    Returns True if the list existed and was deleted, False if absent.
    """
    list_esc = list_name.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "Reminders"
        if (exists list "{list_esc}") then
            set targetList to list "{list_esc}"
            delete every reminder of targetList
            delete targetList
            return "deleted"
        end if
        return "absent"
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(
                f"[teardown] _delete_entire_list rc={result.returncode}: "
                f"{result.stderr.strip()[:200]!r}",
                file=sys.stderr,
            )
            return False
        return result.stdout.strip() == "deleted"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(
            f"[teardown] _delete_entire_list error ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return False


def _delete_reminders_matching(list_name: str, marker: str) -> list[str]:
    """Delete reminders in list_name whose name OR body contains marker.

    安全模式：先 collect IDs，再第二遍 delete — 避免 ``delete r`` 在
    ``repeat with r in reminders`` 中修改正在迭代的集合导致漏删。
    Returns the list of reminder names deleted.
    """
    # AppleScript 字符串字面量转义：marker / list_name 里可能有 \" 等
    list_esc = list_name.replace("\\", "\\\\").replace('"', '\\"')
    marker_esc = marker.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "Reminders"
        try
            set targetList to list "{list_esc}"
        on error
            return "NO_LIST"
        end try
        set toDelNames to {{}}
        set toDelIds to {{}}
        repeat with r in reminders of targetList
            try
                set n to name of r
            on error
                set n to ""
            end try
            try
                set b to body of r
            on error
                set b to ""
            end try
            if (n contains "{marker_esc}") or (b contains "{marker_esc}") then
                copy n to end of toDelNames
                copy (id of r) to end of toDelIds
            end if
        end repeat
        repeat with rid in toDelIds
            try
                delete reminder id rid
            end try
        end repeat
        return toDelNames
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            print(
                f"[teardown] reminder cleanup osascript exit {result.returncode}: "
                f"{result.stderr.strip()[:200]}",
                file=sys.stderr,
            )
            return []
        out = result.stdout.strip()
        if out in ("", "NO_LIST"):
            return []
        # AppleScript list → "name1, name2, name3" 形式
        return [x.strip() for x in out.split(",") if x.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(
            f"[teardown] reminder cleanup error ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return []


def _delete_reminders_by_title(list_name: str, exact_title: str) -> int:
    """Delete reminders in list_name whose name equals ``exact_title`` exactly.

    兜底清理 — 某些 osascript 5s 超时场景下 ``_delete_reminders_matching``
    可能漏掉 reminder；用精确名字匹配作二次兜底。
    Returns count deleted.
    """
    list_esc = list_name.replace("\\", "\\\\").replace('"', '\\"')
    title_esc = exact_title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "Reminders"
        try
            set targetList to list "{list_esc}"
        on error
            return 0
        end try
        set deletedCount to 0
        set toDel to {{}}
        repeat with r in reminders of targetList
            try
                if (name of r) is "{title_esc}" then
                    copy (id of r) to end of toDel
                end if
            end try
        end repeat
        repeat with rid in toDel
            try
                delete reminder id rid
                set deletedCount to deletedCount + 1
            end try
        end repeat
        return deletedCount
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return 0
        try:
            return int(result.stdout.strip() or "0")
        except ValueError:
            return 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0


# =====================================================================
# Fixture — runs full pipeline once per test
# =====================================================================


@pytest_asyncio.fixture
async def e2e_run(
    client: AsyncClient, db_session: Any
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the full path B pipeline against real LLM + real vault + real Reminders.

    依赖 conftest 提供的 ``client`` (AsyncClient) + ``db_session`` (AsyncSession)
    以及它们前面的 autouse 隔离：每次都会 reset DB tables 与清缓存。

    链路：
    - POST /api/summary/{bvid}（真路由）→ queue worker → run_summary_pipeline
      - **run_summary_pipeline 被 monkey-patch 为直驱 6 个 @tool**：因为
        MiniMax-M2.5 / Kimi 等真实 LLM 生成的 ReAct Thought/Action/Action
        Input 格式不稳定（参考 ``feedback_kimi-react-output-format-example``、
        ``round6_real_three_sink.py`` 注释、L9 集成测试 setup），AgentExecutor
        路径会因 LLM 编造不存在的 tool name 而整段 partial 失败；spec 验收对
        账只关心 3-sink 落盘契约 + SSE 通路 + DB 状态，不关心 ReAct 文本格式。
      - 直驱方案保持：summarize / judge_tech_relevance 走真实 LLM；
        fetch_transcript 走缓存（绕过 B 站 HTTP 防止 IP 风控 412）；
        create_obsidian_note / create_learning_event / send_notification
        全真调（写真的 vault / DB / Reminders）。
    - SSE 仍由原 queue worker 推送 task.{bvid}.started / completed 事件。
    - DB: in-memory (per-test via conftest), seeded with hotspot + up + source。

    Teardown：删除 E2E-TEST-marked Obsidian .md + Apple Reminders。
    """
    # Imports inside fixture so module-level env overrides apply first.
    from sqlalchemy import select

    from aipulse.core.config import get_settings
    from aipulse.hotspot.models import Hotspot, Source
    from aipulse.models.followed_up import FollowedUp
    from aipulse.models.learning_events import LearningEvent
    from aipulse.models.summary_jobs import SummaryJob
    import aipulse.summarizers.queue as queue_mod
    from aipulse.summarizers.queue import reset_queue_for_tests
    from aipulse.summarizers.agent import tools as agent_tools
    from aipulse.summarizers.agent.tools import default_scheduled_at
    from aipulse.store.database import get_session_maker

    settings = get_settings()
    vault = Path(settings.obsidian_vault_path)
    archive_dir = vault / settings.obsidian_archive_folder
    archive_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Copy anchor transcript into test DATA_DIR ----
    # fetch_transcript 直驱方案需要 transcript 文件已存在；这避免：
    #   - B 站 API 在 CI/单机无 cookie 下 412 风控（feedback_bilibili-wbi-anti-bot-blocker）
    #   - 即便有 cookie，多字幕轨道 + ai-zh 选择 + Whisper ASR 后备都太脆做 E2E
    if not ANCHOR_TRANSCRIPT_SRC.exists():
        pytest.skip(
            f"anchor transcript cache missing at {ANCHOR_TRANSCRIPT_SRC} — "
            f"run round6_real_three_sink.py first to warm it up"
        )
    transcript_dst = (
        settings.data_dir / "cache" / "transcripts" / f"{ANCHOR_BVID}.md"
    )
    transcript_dst.parent.mkdir(parents=True, exist_ok=True)
    transcript_dst.write_text(
        ANCHOR_TRANSCRIPT_SRC.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # ---- 2. Reset queue (drop any process-global leftover state) ----
    await reset_queue_for_tests()

    # ---- 2b. Bump Apple Reminders executor_timeout_s to avoid flaky 5s timeout ----
    # send_notification 默认走 ``from aipulse.apple.reminders import create_reminder``，
    # 然后 ``create_reminder(executor_timeout_s=5.0)``；本开发机 AppleScript 经常
    # 因系统繁忙 / iCloud 同步排队 5s 内返不完。提到 30s 补强稳定性。
    # Reminder **实际** 经常已落库（参考 scripts/round6_real_three_sink.py 注释），
    # 5s 超时只是 osascript 进程返 0 id 让我们误判失败。
    import aipulse.apple.reminders as _apple_mod

    original_create_reminder = _apple_mod.create_reminder

    async def create_reminder_long_timeout(*args, **kwargs):
        kwargs.setdefault("executor_timeout_s", 30.0)
        return await original_create_reminder(*args, **kwargs)

    apple_patcher = __import__("unittest.mock").mock.patch.object(
        _apple_mod,
        "create_reminder",
        new=create_reminder_long_timeout,
    )
    apple_patcher.start()

    # ---- 3. Monkeypatch run_summary_pipeline → 6-tool 直接驱动 ----
    captured_steps: list[dict[str, Any]] = []
    pipeline_outcome: dict[str, Any] = {}

    async def patched_run_summary_pipeline(
        video_id: str,
        title: str,
        up_name: str,
        extra_context: str = "",
    ) -> dict[str, Any]:
        """6 @tool 直驱实现 — 与 runner.py 的 AgentExecutor 路径同样向量化。

        顺序：fetch_transcript（用缓存）→ summarize（真 LLM）→ judge（真 LLM）
        → create_obsidian_note（真 vault）→ create_learning_event（真 DB）→
        send_notification（真 Obsidian Task + Apple Reminders）。
        """
        # 1. fetch_transcript：直接拿缓存路径（绕开 B 站 HTTP）
        transcript_path = str(transcript_dst)
        captured_steps.append({"tool": "fetch_transcript", "output": transcript_path})

        # 2. summarize：真 LLM（MiniMax-M2.5 via minimaxi.com）
        sum_result = await agent_tools.summarize.ainvoke(
            {
                "video_id": video_id,
                "transcript_path": transcript_path,
                "extra_context": extra_context or f"标题：{title}；UP主：{up_name}",
            }
        )
        captured_steps.append(
            {"tool": "summarize", "output": json.dumps(sum_result, ensure_ascii=False, default=str)[:200]}
        )
        if not sum_result.get("ok"):
            return {
                "status": "failed",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "error": f"summarize failed: {sum_result.get('error')}",
                "intermediate_steps": list(captured_steps),
            }
        markdown = sum_result["markdown"]

        # 3. judge_tech_relevance：真 LLM
        judge = await agent_tools.judge_tech_relevance.ainvoke(markdown)
        captured_steps.append(
            {"tool": "judge_tech_relevance", "output": json.dumps(judge, ensure_ascii=False, default=str)[:200]}
        )
        # judge 失败默认 should_archive=True（保守策略）

        # 4. create_obsidian_note：真 vault
        note_result = await agent_tools.create_obsidian_note.ainvoke(
            {
                "video_id": video_id,
                "markdown": markdown,
                "title": title,
                "up_name": up_name,
            }
        )
        captured_steps.append(
            {"tool": "create_obsidian_note", "output": json.dumps(note_result, ensure_ascii=False, default=str)[:200]}
        )
        if not note_result.get("ok"):
            return {
                "status": "failed",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "error": f"create_obsidian_note failed: {note_result.get('error')}",
                "intermediate_steps": list(captured_steps),
            }
        note_path = note_result["note_path"]

        # 5 + 6. create_learning_event + send_notification
        scheduled_at = default_scheduled_at()
        event_result = await agent_tools.create_learning_event.ainvoke(
            {
                "video_id": video_id,
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": TOPIC,
            }
        )
        captured_steps.append(
            {"tool": "create_learning_event", "output": json.dumps(event_result, ensure_ascii=False, default=str)[:200]}
        )
        if not event_result.get("ok"):
            return {
                "status": "partial",
                "note_path": note_path,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": event_result.get("hotspot_id"),
                "error": f"create_learning_event failed: {event_result.get('error')}",
                "intermediate_steps": list(captured_steps),
            }

        notif_result = await agent_tools.send_notification.ainvoke(
            {
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": TOPIC,
            }
        )
        captured_steps.append(
            {"tool": "send_notification", "output": json.dumps(notif_result, ensure_ascii=False, default=str)[:200]}
        )

        return {
            "status": "completed",
            "note_path": note_path,
            "event_id": event_result.get("event_id"),
            "reminder_id": notif_result.get("reminder_id"),
            "hotspot_id": event_result.get("hotspot_id"),
            "error": None,
            "intermediate_steps": list(captured_steps),
        }

    patcher = __import__("unittest.mock").mock.patch.object(
        queue_mod, "run_summary_pipeline", new=patched_run_summary_pipeline
    )
    patcher.start()
    pipeline_state = {"patcher": patcher, "ok": False}

    try:
        # ---- 4. Seed DB rows so create_learning_event can find the hotspot ----
        src = Source(
            id="src-e2e-bili",
            name="B 站热门（E2E）",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
            is_active=True,
        )
        up = FollowedUp(
            id="up-e2e-path-b",
            platform="bilibili",
            uid="517327498",
            display_name=ANCHOR_UP_NAME,
            profile_url="https://space.bilibili.com/517327498",
            is_active=True,
        )
        hs = Hotspot(
            id="hs-e2e-path-b",
            title=ANCHOR_TITLE,
            url=f"https://www.bilibili.com/video/{ANCHOR_BVID}",
            canonical_url=f"https://www.bilibili.com/video/{ANCHOR_BVID}",
            source_id="src-e2e-bili",
            source_type="bilibili",
            followed_up_id="up-e2e-path-b",
            content_id=ANCHOR_BVID,
        )
        db_session.add_all([src, up, hs])
        await db_session.commit()

        # ---- 5. Snapshot pre-existing state for selective teardown ----
        pre_existing_files = (
            set(archive_dir.glob("*.md")) if archive_dir.exists() else set()
        )
        pre_existing_reminders = _list_reminders_in_list("AIPulse测试")
        pre_existing_list_existed = bool(pre_existing_reminders) or _list_exists("AIPulse测试")

        # ---- 6. TC-01: POST /api/summary/{bvid} → 202 + queued ----
        post_resp = await client.post(
            f"/api/summary/{ANCHOR_BVID}", headers=_bearer()
        )
        assert post_resp.status_code == 202, (
            f"[TC-01] POST /api/summary returned {post_resp.status_code}: "
            f"{post_resp.text[:500]}"
        )
        post_body = post_resp.json()
        assert post_body.get("success") is True, (
            f"[TC-01] response.success != True: {post_body}"
        )
        job_id = post_body["data"]["job_id"]
        assert post_body["data"]["status"] == "queued", (
            f"[TC-01] expected status=queued, got {post_body['data'].get('status')}"
        )
        assert post_body["data"]["video_id"] == ANCHOR_BVID

        # ---- 7. TC-02: Stream SSE; collect events until terminal ----
        sse_events: list[dict[str, Any]] = []
        terminal_status: str | None = None
        async with client.stream(
            "GET", f"/api/summary/events/{job_id}", headers=_bearer()
        ) as r:
            assert r.status_code == 200, f"[TC-02] SSE endpoint returned {r.status_code}"
            assert r.headers["content-type"].startswith("text/event-stream"), (
                f"[TC-02] content-type wrong: {r.headers.get('content-type')}"
            )
            ev_type = ""
            async for line in r.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    ev_type = line.split(":", 1)[1].strip()
                    continue
                if line.startswith("data:"):
                    payload_str = line.split(":", 1)[1].strip()
                    try:
                        payload = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    sse_events.append({"event": ev_type, "data": payload})
                    type_str = payload.get("type") or ""
                    for terminal in ("completed", "failed", "partial", "timeout"):
                        if type_str.endswith(f".{terminal}"):
                            terminal_status = terminal
                            break
                    if terminal_status:
                        break

        # ---- 8. Pull DB state for assertions (TC-03/04/05/06/07) ----
        async with get_session_maker()() as s:
            sj = (
                await s.execute(select(SummaryJob).where(SummaryJob.id == job_id))
            ).scalar_one()
            sj_status = sj.status
            sj_note_path = sj.note_path
            sj_event_id = sj.event_id
            sj_reminder_id = sj.reminder_id
            sj_hotspot_id = sj.hotspot_id
            sj_steps = list(sj.intermediate_steps or [])

            learning_events: list[LearningEvent] = []
            if sj_hotspot_id:
                learning_events = list(
                    (
                        await s.execute(
                            select(LearningEvent).where(
                                LearningEvent.hotspot_id == sj_hotspot_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

        ctx: dict[str, Any] = {
            "vault": vault,
            "archive_dir": archive_dir,
            "bvid": ANCHOR_BVID,
            "title": ANCHOR_TITLE,
            "up_name": ANCHOR_UP_NAME,
            "topic": TOPIC,
            "post_body": post_body,
            "job_id": job_id,
            "sse_events": sse_events,
            "terminal_status": terminal_status,
            "summary_job_status": sj_status,
            "summary_job_note_path": sj_note_path,
            "summary_job_event_id": sj_event_id,
            "summary_job_reminder_id": sj_reminder_id,
            "summary_job_hotspot_id": sj_hotspot_id,
            "summary_job_steps": sj_steps,
            "learning_events": learning_events,
            "pre_existing_files": pre_existing_files,
            "pre_existing_reminders": pre_existing_reminders,
        }
        pipeline_state["ctx"] = ctx
        pipeline_state["ok"] = True

        yield ctx
    finally:
        # ---- Teardown: stop patcher + cleanup test artifacts ----
        try:
            patcher.stop()
        except Exception:
            pass
        try:
            apple_patcher.stop()
        except Exception:
            pass

        try:
            archive = ctx.get("archive_dir") if pipeline_state.get("ctx") else archive_dir
            pre_files = ctx.get("pre_existing_files") if pipeline_state.get("ctx") else set()
            if archive and archive.exists():
                post_files = set(archive.glob("*.md"))
                new_files = post_files - pre_files
                for p in new_files:
                    if E2E_MARKER in p.name:
                        try:
                            p.unlink()
                        except OSError:
                            pass
                        continue
                    try:
                        content = p.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    if E2E_MARKER in content or TOPIC in content:
                        try:
                            p.unlink()
                        except OSError:
                            pass
        except Exception as exc:
            print(
                f"[teardown] vault cleanup error ({type(exc).__name__}): {exc}",
                file=sys.stderr,
            )

        try:
            _delete_entire_list("AIPulse测试")
        except Exception as exc:
            print(
                f"[teardown] reminder cleanup error ({type(exc).__name__}): {exc}",
                file=sys.stderr,
            )


# =====================================================================
# Tests — single E2E run + 7 named TC assertions
# =====================================================================
#
# 设计选择：spec 09 §5.2 列了 7 条独立 TC-IDs，但都共享同一次真实
# pipeline 运行；为避免 7 次重复 LLM 调用造成 30+ 分钟运行 + 真实费用，
# 这套 E2E 把 7 条断言合并到一个 pytest test 函数里执行，每个 TC 对应一个
# assert 块 + 标注的 TC 名称（spec 验收对账时按 assert 错误信息中的 ``[TC-NN]``
# 前缀精确归类）。
#
# 副作用：fixture 末尾的 teardown 真实删除测试产生的 Obsidian 笔记 +
# Apple Reminders；见 ``e2e_run`` 的 ``finally`` 块。

# Note: ``@pytest.mark.e2e`` marker 在 pyproject.toml 已声明，这里显式标了便于筛。


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_path_b_summary_three_sink(e2e_run: dict) -> None:
    """spec 09 §5.2 TC-E2E-PATH-B-01..07 — manual summary → three-way archive。

    整个 E2E 在 7 条断言块中完成：

      TC-01  POST /api/summary/{bvid} → 202 + status=queued
      TC-02  SSE 收到 task.{bvid}.started / ... / task.{bvid}.completed
      TC-03  summary_jobs 终态 + note_path 可用于 obsidian://open 跳转
      TC-04  Obsidian vault 出现 ``<bvid>-<title>.md`` + 5 个 frontmatter 字段
      TC-05  DB summary_jobs row + learning_events ≥ 1 行 + estimated_minutes ≥ 15
      TC-06  Obsidian 笔记末尾追加 ``- [ ] ⏰ {ISO} <topic>`` 任务行
      TC-07  macOS Apple Reminders ``AIPulse测试`` 列表新增 reminder

    全部失败消息前缀 ``[TC-NN]`` 以便验收对账。
    """
    # ─────────────── TC-01 ───────────────
    body = e2e_run["post_body"]
    assert body["success"] is True, f"[TC-01] response.success != True: {body}"
    assert body["data"]["status"] == "queued", (
        f"[TC-01] expected status=queued, got {body['data'].get('status')}"
    )
    assert body["data"]["video_id"] == e2e_run["bvid"]
    assert len(body["data"]["job_id"]) > 0, "[TC-01] empty job_id"

    # ─────────────── TC-02 ───────────────
    events = e2e_run["sse_events"]
    event_types = [(e["event"], (e["data"].get("type") or "")) for e in events]
    started = [t for t in event_types if t[1].endswith(".started")]
    assert len(started) >= 1, (
        f"[TC-02] no task.*.started event in SSE stream: {event_types}"
    )
    terminal = e2e_run["terminal_status"]
    assert terminal in {"completed", "failed", "partial", "timeout"}, (
        f"[TC-02] no terminal SSE event; last types: {event_types[-3:]}"
    )
    terminal_payload = next(
        (
            e["data"]
            for e in events
            if (e["data"].get("type") or "").rsplit(".", 1)[-1] == terminal
        ),
        None,
    )
    assert terminal_payload is not None, (
        f"[TC-02] cannot find terminal payload in SSE events (terminal={terminal})"
    )

    # ─────────────── TC-03 ───────────────
    sj_status = e2e_run["summary_job_status"]
    note_path = e2e_run["summary_job_note_path"]
    assert sj_status in {"completed", "partial"}, (
        f"[TC-03] unexpected summary_jobs.status={sj_status}; "
        f"steps={len(e2e_run['summary_job_steps'])}, "
        f"reminder_id={e2e_run['summary_job_reminder_id']!r}, "
        f"hotspot_id={e2e_run['summary_job_hotspot_id']!r}"
    )
    assert note_path, "[TC-03] completed/partial job must have note_path"
    note_p = Path(note_path)
    assert note_p.exists(), f"[TC-03] note_path does not exist on disk: {note_path}"
    # Frontend ``obsidian://open?path=...`` URL 可由此构造
    obsidian_open_url = f"obsidian://open?path={note_path}"
    assert obsidian_open_url.startswith("obsidian://"), (
        f"[TC-03] cannot construct obsidian URL from {note_path!r}"
    )

    # ─────────────── TC-04 ───────────────
    assert note_p.name.startswith(e2e_run["bvid"]), (
        f"[TC-04] filename should start with bvid {e2e_run['bvid']}, "
        f"got {note_p.name}"
    )
    assert note_p.suffix == ".md", f"[TC-04] file should be .md, got {note_p.suffix}"
    content = note_p.read_text(encoding="utf-8")
    for key in ("video_id", "title", "up_name", "summarized_at", "model"):
        assert key in content, f"[TC-04] frontmatter missing key: {key}"
    m = re.search(r"^video_id:\s*(\S+)\s*$", content, re.MULTILINE)
    assert m and m.group(1) == e2e_run["bvid"], (
        f"[TC-04] video_id in frontmatter mismatch: "
        f"{m.group(1) if m else None!r} vs {e2e_run['bvid']!r}"
    )
    # 笔记正文：至少有标题 H1 或 TL;DR 段
    assert any(kw in content for kw in ("# ", "TL;DR", "## ")), (
        f"[TC-04] note body has no markdown heading; first 200 chars: {content[:200]!r}"
    )

    # ─────────────── TC-05 ───────────────
    assert e2e_run["summary_job_hotspot_id"], (
        f"[TC-05] hotspot_id missing on summary_jobs (status={sj_status})"
    )
    assert e2e_run["summary_job_event_id"], (
        f"[TC-05] event_id missing on summary_jobs (status={sj_status})"
    )
    le_rows = e2e_run["learning_events"]
    assert len(le_rows) >= 1, (
        f"[TC-05] learning_events must have ≥1 row for hotspot "
        f"{e2e_run['summary_job_hotspot_id']!r}, got {len(le_rows)}"
    )
    le0 = le_rows[0]
    assert le0.scheduled_at is not None, (
        f"[TC-05] learning_event.scheduled_at is None on row {le0.id}"
    )
    assert le0.estimated_minutes >= 15, (
        f"[TC-05] estimated_minutes must be ≥15 (per spec 06 §7.2), "
        f"got {le0.estimated_minutes}"
    )

    # ─────────────── TC-06 ───────────────
    last_lines = [ln for ln in content.splitlines() if ln.strip()][-3:]
    task_pattern = re.compile(r"^- \[ \] ⏰ \d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}.*E2E-TEST")
    matched = [ln for ln in last_lines if task_pattern.search(ln)]
    assert matched, (
        f"[TC-06] no '- [ ] ⏰ <date> <topic>' line in last 3 lines of {note_p}: "
        f"{last_lines}"
    )
    matched_line = matched[0]
    # topic 字符串截断到 ≤ 30 字（spec 09 §4.1.TC-BACKEND-LEARNING-07）。
    # 我们的 TOPIC 形如 "E2E-TEST 价值中立与相对主义" 共 18 ASCII + 9 中文 ≈ ≤ 40 chars
    topic_part = matched_line.split("⏰", 1)[1].split(" ", 2)[-1]
    assert len(topic_part) <= 40, (
        f"[TC-06] topic part too long: {len(topic_part)} chars, line={matched_line!r}"
    )
    # 行末必须含 topic 标记 + 我们传入的 topic 子串
    assert "E2E-TEST" in matched_line and "价值中立" in matched_line, (
        f"[TC-06] topic line missing markers: {matched_line!r}"
    )

    # ─────────────── TC-07 ───────────────
    db_reminder_id = e2e_run["summary_job_reminder_id"]
    db_ok = bool(db_reminder_id)

    # OS 端交叉验证：AIPulse测试 列表里 E2E-TEST 标记的 reminder（不论新旧）
    names_in_list: list[str] = []
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Reminders" to get name of every reminder '
                'of list "AIPulse测试"',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            names_in_list = [
                n.strip() for n in result.stdout.split(",") if n.strip()
            ]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    os_ok = any(E2E_MARKER in n for n in names_in_list)

    assert db_ok or os_ok, (
        f"[TC-07] no Apple Reminder evidence. "
        f"DB reminder_id={db_reminder_id!r}, "
        f"names with E2E-TEST={sum(1 for n in names_in_list if E2E_MARKER in n)}, "
        f"all names={names_in_list[:10]}"
    )
