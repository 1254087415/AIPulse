"""v0.3 E2E path C — failure injection + manual retry.

Covers spec 09 §5.3 ``TC-E2E-PATH-C-01..05`` in a single real-pipeline run:

  TC-01  Inject Kimi API 500 → POST /api/summary/{bvid} → 202 + queued
  TC-02  SSE 推送 task.{bvid}.failed 事件 (error message carries 500 marker)
  TC-03  Failed tab 数据源: GET /api/summary/jobs 包含此 job, status=failed
  TC-04  POST /api/summary/job/{job_id}/retry → 202 + 新 job_id 入队
  TC-05  新 job status=completed (audit trail: 旧 job 仍 failed, 新 job 走通三方向)

链路 (按 plan 08 Task 3 允许的 mock 点):
- 失败注入阶段: monkey-patch ``run_summary_pipeline`` 返回 ``status=failed`` payload
  (等价于 plan 描述的「mock kimi endpoint 返回 500」) — 队列、DB、SSE、retry 端点
  全部走真实代码路径, **不 mock**。
- 重试阶段: unpatch, 改走 path B 的 6-tool 直驱 (summarize/judge 真 LLM, 笔记/DB/
  Reminders 真写入)。这等价于「改回正确 API key → 重新入队 → 走通三方向」。

真实副作用 + E2E-TEST 标记 + teardown 删除沿用 path B 纪律:
- Reminders AIPulse测试 列表不存在
- Obsidian vault 无 E2E-TEST 残留
- DB 临时库, 不碰主 checkout 的 data/aipulse.db
"""

from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

# =====================================================================
# MODULE-LEVEL ENVIRONMENT OVERRIDES
# =====================================================================
# 与 path B 同款: 加载真 .env + 真 settings.json, 不打印值, 强制 MiniMax。

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
os.environ["LLM_BASE_URL"] = "https://api.minimaxi.com/v1"
os.environ["LLM_MODEL"] = "MiniMax-M2.5"

# Real vault/archive folder paths from settings.json
if _SETTINGS_FILE.exists():
    _persisted = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    if _persisted.get("obsidian_vault_path"):
        os.environ["OBSIDIAN_VAULT_PATH"] = _persisted["obsidian_vault_path"]
    if _persisted.get("obsidian_archive_folder"):
        os.environ["OBSIDIAN_ARCHIVE_FOLDER"] = _persisted["obsidian_archive_folder"]

# Clear cached settings + migration lock
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
ANCHOR_UP_UID = "517327498"
E2E_MARKER = "E2E-TEST"
TOPIC = f"{E2E_MARKER} pathC 失败重试链路验收"
SYNTHETIC_500_MARKER = "synthetic-500"

ANCHOR_TRANSCRIPT_SRC = (
    Path("/Users/zab/Documents/project/AIPulse/data/cache/transcripts/")
    / f"{ANCHOR_BVID}.md"
)


# =====================================================================
# Helpers — Reminders cleanup (复用 path B 纪律)
# =====================================================================


def _delete_entire_list(list_name: str) -> bool:
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


def _list_reminders_in_list(list_name: str) -> set[str]:
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


# =====================================================================
# Fixture — runs full path C pipeline
# =====================================================================


@pytest_asyncio.fixture
async def e2e_run(
    tmp_path: Path,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the full path C pipeline: inject failure → verify → retry → verify.

    不依赖 conftest 的 ``client`` / ``db_session`` — 这两个 fixture 在
    conftest 启动时已绑定到 ``:memory:`` SQLite, queue worker 跨 connection
    看不到 enqueue 提交的数据 (SQLAlchemy 默认 AsyncAdaptedQueuePool, 每
    connection 独立 in-memory DB)。

    本 fixture 自行重建 file-based engine (``sqlite+aiosqlite:///{tmp}``),
    所有 connection 共享一个 on-disk DB, queue worker 找得到 enqueue row。

    链路:
    - Phase 1 (TC-01..03): patched ``run_summary_pipeline`` 返 ``status=failed``
      触发 finalize 走 failed 分支。SSE 推 ``task.{bvid}.failed`` 事件。
    - Phase 2 (TC-04..05): POST /api/summary/job/{old}/retry → 新 job 入队;
      patcher 切到 real mode 走 path B 6-tool 直驱 + 真 LLM, 终态
      ``completed`` + 三方向落盘。

    Teardown: 删除 E2E-TEST-marked Obsidian .md + AIPulse测试 列表。
    """
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
    from aipulse.store.database import (
        configure_test_database,
        get_session_maker,
    )
    from httpx import ASGITransport
    from aipulse.server import app

    # ---- 0. Build file-based engine BEFORE any other fixture touches DB ----
    # 关键: 必须先 dispose 旧 engine + 彻底停掉旧 worker task, 否则
    # 跨 test 状态下 conftest autouse 已建了 :memory: engine, 旧 worker
    # 拿着旧 session_maker 引用查不到新 file DB 的 row。
    from aipulse.summarizers.queue import get_queue as _get_queue
    from aipulse.store.database import get_engine, reset_db

    # 0a. 停掉所有残留 worker — 多轮 cancel + wait, 防止 cancel 还在
    # asyncio 调度队列里时新 engine 已就绪、worker 拿到旧 session_maker
    # 引用后查不到新 DB 的 row。
    for _attempt in range(3):
        _q = _get_queue()
        if _q is not None:
            _task = getattr(_q, "_worker_task", None)
            if _task is not None and not _task.done():
                _task.cancel()
                try:
                    await asyncio.wait_for(_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
                    pass
        if _q is None or getattr(_q, "_worker_task", None) is None or _q._worker_task.done():
            break

    # 0b. Dispose 旧 engine, 强制关闭所有 connection
    try:
        old_engine = get_engine()
        await old_engine.dispose()
    except Exception:
        pass

    # 0c. 完全重置 queue singleton + DB engine
    from aipulse.summarizers import queue as _qmod

    _qmod._queue = None
    _qmod.drop_queue_sync()

    # 等一轮 event loop tick 确保所有 cancellable task 真的退出
    await asyncio.sleep(0)

    db_file = tmp_path / "path_c_failure.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    await configure_test_database(get_settings())

    get_engine.cache_clear()
    get_session_maker.cache_clear()
    await reset_db()  # create tables on file DB

    # 0d. Build our own client + session against the new engine ----
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    db_session_maker = get_session_maker()
    db_session = db_session_maker()

    settings = get_settings()
    vault = Path(settings.obsidian_vault_path)
    archive_dir = vault / settings.obsidian_archive_folder
    archive_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Copy anchor transcript into test DATA_DIR (real phase needs it) ----
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

    # ---- 2. Reset queue singleton + cancel stale worker (path B 同款) ----
    from aipulse.summarizers import queue as _qmod

    _singleton = _qmod._queue
    if _singleton is not None:
        _task = getattr(_singleton, "_worker_task", None)
        if _task is not None and not _task.done():
            _task.cancel()
            try:
                await _task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _qmod._queue = None
    await reset_queue_for_tests()

    # ---- 2b. Bump Apple Reminders executor timeout (path B 同款) ----
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

    # ---- 3. Pipeline mode switcher (closure) ----
    # ``mode == "fail"`` → return synthetic 500 payload
    # ``mode == "real"`` → run path B 6-tool direct drive with real LLM
    pipeline_state: dict[str, Any] = {"mode": "fail"}
    captured: dict[str, list[Any]] = {
        "phase1_steps": [],
        "phase2_steps": [],
    }

    async def patched_run_summary_pipeline(
        video_id: str,
        title: str,
        up_name: str,
        extra_context: str = "",
    ) -> dict[str, Any]:
        """Two-mode patched pipeline. See ``pipeline_state["mode"]``."""
        mode = pipeline_state["mode"]
        bucket = (
            captured["phase1_steps"] if mode == "fail" else captured["phase2_steps"]
        )
        if mode == "fail":
            # ---- Phase 1: synthetic 500 from mocked Kimi API ----
            # finalize_summary_job 看到 ``error`` + 缺 ``note_path`` + 缺
            # ``hotspot_id`` → 走 failed 分支 (L6 contract)。
            bucket.append(
                {
                    "tool": "synthetic_kimi_500",
                    "output": f"LLM API returned 500: {SYNTHETIC_500_MARKER}",
                }
            )
            return {
                "status": "failed",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "error": (
                    f"LLM API returned 500 (mocked): {SYNTHETIC_500_MARKER} — "
                    "this is a synthetic failure for E2E path C"
                ),
                "intermediate_steps": list(bucket),
            }

        # ---- Phase 2: 6-tool direct drive with REAL MiniMax LLM ----
        # 与 path B e2e_run.patched_run_summary_pipeline 同款, 唯一区别是
        # topic + marker 不同 (TOPIC), 防止与 path B 残留冲突。
        transcript_path = str(transcript_dst)
        bucket.append({"tool": "fetch_transcript", "output": transcript_path})

        sum_result = await agent_tools.summarize.ainvoke(
            {
                "video_id": video_id,
                "transcript_path": transcript_path,
                "extra_context": extra_context or f"标题：{title}；UP主：{up_name}",
            }
        )
        bucket.append(
            {
                "tool": "summarize",
                "output": json.dumps(sum_result, ensure_ascii=False, default=str)[:200],
            }
        )
        if not sum_result.get("ok"):
            return {
                "status": "failed",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "error": f"summarize failed: {sum_result.get('error')}",
                "intermediate_steps": list(bucket),
            }
        markdown = sum_result["markdown"]

        judge = await agent_tools.judge_tech_relevance.ainvoke(markdown)
        bucket.append(
            {
                "tool": "judge_tech_relevance",
                "output": json.dumps(judge, ensure_ascii=False, default=str)[:200],
            }
        )

        note_result = await agent_tools.create_obsidian_note.ainvoke(
            {
                "video_id": video_id,
                "markdown": markdown,
                "title": title,
                "up_name": up_name,
            }
        )
        bucket.append(
            {
                "tool": "create_obsidian_note",
                "output": json.dumps(note_result, ensure_ascii=False, default=str)[:200],
            }
        )
        if not note_result.get("ok"):
            return {
                "status": "failed",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "error": f"create_obsidian_note failed: {note_result.get('error')}",
                "intermediate_steps": list(bucket),
            }
        note_path = note_result["note_path"]

        scheduled_at = default_scheduled_at()
        event_result = await agent_tools.create_learning_event.ainvoke(
            {
                "video_id": video_id,
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": TOPIC,
            }
        )
        bucket.append(
            {
                "tool": "create_learning_event",
                "output": json.dumps(event_result, ensure_ascii=False, default=str)[:200],
            }
        )
        if not event_result.get("ok"):
            return {
                "status": "partial",
                "note_path": note_path,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": event_result.get("hotspot_id"),
                "error": f"create_learning_event failed: {event_result.get('error')}",
                "intermediate_steps": list(bucket),
            }

        notif_result = await agent_tools.send_notification.ainvoke(
            {
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": TOPIC,
            }
        )
        bucket.append(
            {
                "tool": "send_notification",
                "output": json.dumps(notif_result, ensure_ascii=False, default=str)[:200],
            }
        )

        return {
            "status": "completed",
            "note_path": note_path,
            "event_id": event_result.get("event_id"),
            "reminder_id": notif_result.get("reminder_id"),
            "hotspot_id": event_result.get("hotspot_id"),
            "error": None,
            "intermediate_steps": list(bucket),
        }

    patcher = __import__("unittest.mock").mock.patch.object(
        queue_mod, "run_summary_pipeline", new=patched_run_summary_pipeline
    )
    patcher.start()

    pre_existing_files = (
        set(archive_dir.glob("*.md")) if archive_dir.exists() else set()
    )
    pre_existing_reminders = _list_reminders_in_list("AIPulse测试")

    try:
        # ---- 4. Seed DB rows ----
        src = Source(
            id="src-e2e-path-c",
            name="B 站热门（E2E path C）",
            source_type="bilibili",
            collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
            is_active=True,
        )
        up = FollowedUp(
            id="up-e2e-path-c",
            platform="bilibili",
            uid=ANCHOR_UP_UID,
            display_name=ANCHOR_UP_NAME,
            profile_url=f"https://space.bilibili.com/{ANCHOR_UP_UID}",
            is_active=True,
        )
        hs = Hotspot(
            id="hs-e2e-path-c",
            title=ANCHOR_TITLE,
            url=f"https://www.bilibili.com/video/{ANCHOR_BVID}",
            canonical_url=f"https://www.bilibili.com/video/{ANCHOR_BVID}",
            source_id="src-e2e-path-c",
            source_type="bilibili",
            followed_up_id="up-e2e-path-c",
            content_id=ANCHOR_BVID,
        )
        db_session.add_all([src, up, hs])
        await db_session.commit()

        # ---- 5. TC-01: POST /api/summary/{bvid} → 202 + queued (in fail mode) ----
        assert pipeline_state["mode"] == "fail"
        post1 = await client.post(
            f"/api/summary/{ANCHOR_BVID}", headers=_bearer()
        )
        assert post1.status_code == 202, (
            f"[TC-01] POST /api/summary returned {post1.status_code}: "
            f"{post1.text[:500]}"
        )
        body1 = post1.json()
        assert body1.get("success") is True, (
            f"[TC-01] response.success != True: {body1}"
        )
        old_job_id = body1["data"]["job_id"]
        assert body1["data"]["status"] == "queued", (
            f"[TC-01] expected status=queued, got {body1['data'].get('status')}"
        )
        assert body1["data"]["video_id"] == ANCHOR_BVID

        # ---- 6. TC-02: SSE 收 task.{bvid}.failed (短超时, 失败模式) ----
        sse_events_phase1: list[dict[str, Any]] = []
        terminal_phase1: str | None = None
        SSE_TIMEOUT_S = 60.0
        try:
            async with asyncio.timeout(SSE_TIMEOUT_S):
                async with client.stream(
                    "GET", f"/api/summary/events/{old_job_id}", headers=_bearer()
                ) as r:
                    assert r.status_code == 200, (
                        f"[TC-02] SSE endpoint returned {r.status_code}"
                    )
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
                            sse_events_phase1.append({"event": ev_type, "data": payload})
                            type_str = payload.get("type") or ""
                            for terminal in (
                                "completed", "failed", "partial", "timeout"
                            ):
                                if type_str.endswith(f".{terminal}"):
                                    terminal_phase1 = terminal
                                    break
                            if terminal_phase1:
                                break
        except (TimeoutError, asyncio.TimeoutError):
            raise AssertionError(
                f"[TC-02] SSE phase-1 timeout after {SSE_TIMEOUT_S:.0f}s — "
                f"patcher fail mode 没让 worker 推 failed 事件。events="
                f"{sse_events_phase1}"
            )

        # ---- 7. Pull DB state for phase 1 ----
        async with get_session_maker()() as s:
            sj1 = (
                await s.execute(
                    select(SummaryJob).where(SummaryJob.id == old_job_id)
                )
            ).scalar_one()
            sj1_status = sj1.status
            sj1_error = sj1.error
            sj1_completed_at = sj1.completed_at
            sj1_note_path = sj1.note_path
            sj1_steps = list(sj1.intermediate_steps or [])

        ctx: dict[str, Any] = {
            "vault": vault,
            "archive_dir": archive_dir,
            "bvid": ANCHOR_BVID,
            "title": ANCHOR_TITLE,
            "up_name": ANCHOR_UP_NAME,
            "topic": TOPIC,
            "post1_body": body1,
            "old_job_id": old_job_id,
            "phase1_sse_events": sse_events_phase1,
            "phase1_terminal": terminal_phase1,
            "phase1_summary_status": sj1_status,
            "phase1_summary_error": sj1_error,
            "phase1_summary_completed_at": sj1_completed_at,
            "phase1_summary_note_path": sj1_note_path,
            "phase1_steps": sj1_steps,
            "pipeline_state": pipeline_state,
            "captured": captured,
            "pre_existing_files": pre_existing_files,
            "pre_existing_reminders": pre_existing_reminders,
        }

        yield ctx
    finally:
        # ---- Teardown: stop patchers + cleanup artifacts ----
        try:
            patcher.stop()
        except Exception:
            pass
        try:
            apple_patcher.stop()
        except Exception:
            pass

        try:
            if archive_dir and archive_dir.exists():
                post_files = set(archive_dir.glob("*.md"))
                new_files = post_files - pre_existing_files
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
# Tests — single E2E run with 5 named TC assertions
# =====================================================================
#
# 设计选择 (与 path B 同款): 5 个 TC 共享一次 pipeline run, 每个 TC 对应
# 一个 assert 块 + `[TC-NN]` 前缀, 验收对账时按错误信息精确归类。


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_path_c_failure_inject_then_retry(e2e_run: dict) -> None:
    """spec 09 §5.3 TC-E2E-PATH-C-01..05 — failure injection + manual retry。

    链路 (全在一次 fixture run 内):
      TC-01  POST /api/summary/{bvid} (mock 失败模式) → 202 + status=queued
      TC-02  SSE 收 task.{bvid}.failed 事件, error 字段含 synthetic-500 标记
      TC-03  GET /api/summary/jobs?limit=20 含此 job, status=failed
      TC-04  POST /api/summary/job/{old}/retry → 202 + new_job_id, 切到 real 模式
      TC-05  新 job 终态 completed + learning_events ≥ 1 行 + Obsidian 笔记
             末尾追加 task line + DB summary_jobs 含新 job_id
    """
    # ─────────────── TC-01 ───────────────
    body = e2e_run["post1_body"]
    assert body["success"] is True, f"[TC-01] response.success != True: {body}"
    assert body["data"]["status"] == "queued", (
        f"[TC-01] expected status=queued, got {body['data'].get('status')}"
    )
    assert body["data"]["video_id"] == e2e_run["bvid"]
    old_job_id = e2e_run["old_job_id"]
    assert old_job_id and len(old_job_id) > 0, "[TC-01] empty job_id"

    # ─────────────── TC-02 ───────────────
    events = e2e_run["phase1_sse_events"]
    event_types = [(e["event"], (e["data"].get("type") or "")) for e in events]
    failed_events = [t for t in event_types if t[1].endswith(".failed")]
    assert len(failed_events) >= 1, (
        f"[TC-02] no task.*.failed event in SSE stream: {event_types}"
    )
    terminal = e2e_run["phase1_terminal"]
    assert terminal == "failed", (
        f"[TC-02] expected terminal=failed, got {terminal!r}; "
        f"last types: {event_types[-3:]}"
    )
    failed_payload = next(
        (
            e["data"]
            for e in events
            if (e["data"].get("type") or "").rsplit(".", 1)[-1] == "failed"
        ),
        None,
    )
    assert failed_payload is not None, (
        f"[TC-02] cannot find failed payload in SSE events"
    )
    # error 字段必须含 synthetic 500 marker (证明真实走到了 mock 的 fail 分支,
    # 不是「queued 之后没 worker 跑就被 timeout」之类的误判)
    failed_error = failed_payload.get("error") or ""
    assert SYNTHETIC_500_MARKER in failed_error, (
        f"[TC-02] SSE failed event error missing synthetic-500 marker: "
        f"{failed_error!r}"
    )
    # DB summary_jobs 也得是 failed (SSE 推 + DB 写 是两个独立 sink, 都必须)
    db_status = e2e_run["phase1_summary_status"]
    assert db_status == "failed", (
        f"[TC-02] expected summary_jobs.status=failed, got {db_status!r}"
    )
    assert e2e_run["phase1_summary_completed_at"] is not None, (
        "[TC-02] failed job should still set completed_at (terminal marker)"
    )
    assert e2e_run["phase1_summary_note_path"] is None, (
        f"[TC-02] failed job must have note_path=None, "
        f"got {e2e_run['phase1_summary_note_path']!r}"
    )
    db_error = e2e_run["phase1_summary_error"] or ""
    assert SYNTHETIC_500_MARKER in db_error, (
        f"[TC-02] DB summary_jobs.error missing synthetic-500 marker: "
        f"{db_error!r}"
    )
    # 失败阶段的 intermediate_steps 应该记录了 mock 走的路径
    steps = e2e_run["phase1_steps"]
    assert any("synthetic_kimi_500" in (s.get("tool") or "") for s in steps), (
        f"[TC-02] phase-1 intermediate_steps should record synthetic failure, "
        f"got tools={[s.get('tool') for s in steps]}"
    )

    # ─────────────── TC-03 ───────────────
    # FollowFailedPanel 走 listSummaryJobs({ limit: 20 }) → /api/summary/jobs。
    # 服务端不过滤 status, 客户端筛 status in {failed, partial, timeout}。
    # 这里直接用同样的端点 + 同样过滤, 模拟前端「失败 tab」数据源。
    from sqlalchemy import select as _select

    from aipulse.models.summary_jobs import SummaryJob as _SJ
    from aipulse.store.database import get_session_maker as _gsm
    from httpx import ASGITransport, AsyncClient
    from aipulse.server import app

    async with _gsm()() as s:
        all_jobs = (
            await s.execute(
                _select(_SJ).order_by(_SJ.created_at.desc()).limit(20)
            )
        ).scalars().all()
        failed_jobs = [
            j for j in all_jobs
            if j.status in {"failed", "partial", "timeout"}
        ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        http_jobs_resp = await http_client.get(
            "/api/summary/jobs?limit=20", headers=_bearer()
        )
        assert http_jobs_resp.status_code == 200, (
            f"[TC-03] GET /api/summary/jobs returned "
            f"{http_jobs_resp.status_code}: {http_jobs_resp.text[:500]}"
        )
        http_jobs_body = http_jobs_resp.json()
        http_jobs = (
            http_jobs_body.get("data") if http_jobs_body.get("success") else []
        )

    http_failed = [
        j for j in (http_jobs or [])
        if j.get("status") in {"failed", "partial", "timeout"}
    ]
    assert any(
        j.get("id") == old_job_id for j in http_failed
    ), (
        f"[TC-03] HTTP /api/summary/jobs 失败列表不含 old_job_id={old_job_id}; "
        f"got http_failed ids={[j.get('id') for j in http_failed]}; "
        f"all http jobs={[j.get('id') for j in (http_jobs or [])]} "
        f"statuses={[j.get('status') for j in (http_jobs or [])]}"
    )
    # DB-side 同样要见到 (real source of truth)
    assert any(j.id == old_job_id for j in failed_jobs), (
        f"[TC-03] DB 失败列表不含 old_job_id={old_job_id}; "
        f"got DB failed ids={[j.id for j in failed_jobs]}"
    )

    # ─────────────── TC-04 ───────────────
    # 切 patcher 到 real mode, 调 retry 端点
    e2e_run["pipeline_state"]["mode"] = "real"
    from httpx import ASGITransport, AsyncClient as _AC
    from aipulse.server import app as _app

    async with _AC(transport=ASGITransport(app=_app), base_url="http://test") as retry_client:
        retry_resp = await retry_client.post(
            f"/api/summary/job/{old_job_id}/retry",
            headers=_bearer(),
        )
        assert retry_resp.status_code == 202, (
            f"[TC-04] POST /retry returned {retry_resp.status_code}: "
            f"{retry_resp.text[:500]}"
        )
        retry_body = retry_resp.json()
        assert retry_body.get("success") is True, (
            f"[TC-04] retry response.success != True: {retry_body}"
        )
        new_job_id = retry_body["data"]["new_job_id"]
        assert new_job_id and new_job_id != old_job_id, (
            f"[TC-04] retry must create a NEW job_id, got new={new_job_id!r} "
            f"vs old={old_job_id!r}"
        )
        assert retry_body["data"]["old_job_id"] == old_job_id, (
            f"[TC-04] retry response should echo old_job_id"
        )
        assert retry_body["data"]["video_id"] == e2e_run["bvid"]

        # ---- 7. Stream SSE for new job (real mode, 5min hard timeout) ----
        sse_events_phase2: list[dict[str, Any]] = []
        terminal_phase2: str | None = None
        SSE_TIMEOUT_S = 300.0
        try:
            async with asyncio.timeout(SSE_TIMEOUT_S):
                async with retry_client.stream(
                    "GET", f"/api/summary/events/{new_job_id}", headers=_bearer()
                ) as r:
                    assert r.status_code == 200, (
                        f"[TC-04] retry SSE returned {r.status_code}"
                    )
                    assert r.headers["content-type"].startswith("text/event-stream"), (
                        f"[TC-04] retry SSE content-type wrong: "
                        f"{r.headers.get('content-type')}"
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
                            sse_events_phase2.append({"event": ev_type, "data": payload})
                            type_str = payload.get("type") or ""
                            for terminal in (
                                "completed", "failed", "partial", "timeout"
                            ):
                                if type_str.endswith(f".{terminal}"):
                                    terminal_phase2 = terminal
                                    break
                            if terminal_phase2:
                                break
        except (TimeoutError, asyncio.TimeoutError):
            raise AssertionError(
                f"[TC-04] retry SSE timeout after {SSE_TIMEOUT_S:.0f}s — "
                f"real LLM 链路卡住。events={sse_events_phase2}"
            )

    # ---- Pull DB state for phase 2 ----
    from aipulse.models.learning_events import LearningEvent as _LE
    from aipulse.store.database import get_session_maker as _gsm2

    async with _gsm2()() as s:
        sj2 = (
            await s.execute(_select(_SJ).where(_SJ.id == new_job_id))
        ).scalar_one()
        sj2_status = sj2.status
        sj2_note_path = sj2.note_path
        sj2_event_id = sj2.event_id
        sj2_reminder_id = sj2.reminder_id
        sj2_hotspot_id = sj2.hotspot_id
        sj2_steps = list(sj2.intermediate_steps or [])

        sj1_again = (
            await s.execute(_select(_SJ).where(_SJ.id == old_job_id))
        ).scalar_one()
        old_audit_status = sj1_again.status

        learning_events: list[_LE] = []
        if sj2_hotspot_id:
            learning_events = list(
                (
                    await s.execute(
                        _select(_LE).where(_LE.hotspot_id == sj2_hotspot_id)
                    )
                )
                .scalars()
                .all()
            )

    # ─────────────── TC-05 ───────────────
    # (a) 新 job 终态 completed (走通三方向)
    assert terminal_phase2 == "completed", (
        f"[TC-05] expected terminal=completed for retry, got "
        f"{terminal_phase2!r}; last events="
        f"{[(e['event'], e['data'].get('type')) for e in sse_events_phase2[-3:]]}"
    )
    assert sj2_status == "completed", (
        f"[TC-05] expected new job status=completed, got {sj2_status!r}; "
        f"steps={len(sj2_steps)}, reminder_id={sj2_reminder_id!r}, "
        f"hotspot_id={sj2_hotspot_id!r}"
    )
    # (b) Obsidian 笔记 + 至少 5 个 frontmatter 字段
    assert sj2_note_path, "[TC-05] completed retry must have note_path"
    note_p = Path(sj2_note_path)
    assert note_p.exists(), f"[TC-05] note_path not on disk: {sj2_note_path}"
    assert note_p.name.startswith(e2e_run["bvid"]), (
        f"[TC-05] filename should start with bvid, got {note_p.name}"
    )
    content = note_p.read_text(encoding="utf-8")
    for key in ("video_id", "title", "up_name", "summarized_at", "model"):
        assert key in content, f"[TC-05] frontmatter missing key: {key}"
    # (c) 笔记末尾 task line 携带 E2E-TEST marker (cleanup 凭证)
    last_lines = [ln for ln in content.splitlines() if ln.strip()][-3:]
    task_pattern = re.compile(r"^- \[ \] ⏰ \d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}.*E2E-TEST")
    assert any(task_pattern.search(ln) for ln in last_lines), (
        f"[TC-05] no E2E-TEST task line in note last 3 lines: {last_lines}"
    )
    # (d) learning_events ≥ 1 行 (三方向中的 DB 方向)
    assert len(learning_events) >= 1, (
        f"[TC-05] learning_events must have ≥1 row for hotspot "
        f"{sj2_hotspot_id!r}"
    )
    le0 = learning_events[0]
    assert le0.estimated_minutes >= 15, (
        f"[TC-05] estimated_minutes must be ≥15, got {le0.estimated_minutes}"
    )
    # (e) 旧 job audit trail 保留 (status=failed), 不被 retry 覆盖
    assert old_audit_status == "failed", (
        f"[TC-05] old job audit status must remain 'failed' for retry trail, "
        f"got {old_audit_status!r}"
    )
    # (f) FollowFailedPanel 端到端: GET /api/summary/jobs 现在 latest job
    # for this video_id 是 completed (不再是 failed)
    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as check_client:
        check_resp = await check_client.get(
            "/api/summary/jobs?limit=20", headers=_bearer()
        )
        assert check_resp.status_code == 200, (
            f"[TC-05] final /api/summary/jobs returned "
            f"{check_resp.status_code}"
        )
        check_jobs = check_resp.json().get("data") or []
        latest_for_video = next(
            (
                j for j in check_jobs
                if j.get("video_id") == e2e_run["bvid"]
            ),
            None,
        )
        assert latest_for_video is not None, (
            f"[TC-05] latest job for {e2e_run['bvid']} not in /api/summary/jobs"
        )
        assert latest_for_video.get("id") == new_job_id, (
            f"[TC-05] latest job for video should be the new (completed) job, "
            f"got id={latest_for_video.get('id')!r} vs new={new_job_id!r}"
        )
        assert latest_for_video.get("status") == "completed", (
            f"[TC-05] latest job status should be 'completed' (retry 成功), "
            f"got {latest_for_video.get('status')!r}"
        )
    # (g) reminder 双路 OR 断言: DB 写入了 reminder_id, 或 OS 端
    # AIPulse测试 列表有 E2E-TEST 标记的 reminder
    db_reminder_id = sj2_reminder_id
    db_ok = bool(db_reminder_id)

    os_names: list[str] = []
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
            os_names = [n.strip() for n in result.stdout.split(",") if n.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    os_ok = any(E2E_MARKER in n for n in os_names)

    assert db_ok or os_ok, (
        f"[TC-05] no Apple Reminder evidence for retry. "
        f"DB reminder_id={db_reminder_id!r}, "
        f"OS names with E2E-TEST="
        f"{sum(1 for n in os_names if E2E_MARKER in n)}; "
        f"all names={os_names[:10]}"
    )


# =====================================================================
# Helper for Authorization header
# =====================================================================


def _bearer() -> dict[str, str]:
    """Default Authorization header."""
    return {"Authorization": "Bearer e2e-path-c-token"}
