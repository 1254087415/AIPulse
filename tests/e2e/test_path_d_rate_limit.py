"""v0.3 E2E path D — queue rate limit (429 overflow).

Covers spec 09 §5.4 ``TC-E2E-PATH-D-01..04`` in a single real-pipeline run:

  TC-01  Concurrently POST 25 different videos → burst hits server
  TC-02  First 20 返回 202 + queue_position (job 入队, 后续会被 worker 跑)
  TC-03  Last 5 返回 429 + QUEUE_FULL detail (HTTP body + DB row 验证双侧)
  TC-04  Worker drain 后 queue 释放 → 新 POST → 202 (queue release 验证)

链路 (与 path B/C 同款):
- File-based SQLite (queue worker 跨 connection 可见)
- 拒绝全 mock: queue / DB / HTTP 层全真实, 仅 patch ``run_summary_pipeline``
  (spec 允许的 mock 点: 前 5 行)。

worker pause 策略（关键）:
- spec 锁定 20×202 + 5×429 严苛断言 (不能接受 integration test [4, 5] 软断言)。
- 实现: 替换 ``queue.start`` 为 no-op, 让 worker 在 burst 期间完全不动。
  put_nowait 严格 20 个成功 + 5 个 QueueFull → 429, 确定性。
- TC-D-04: 恢复 ``queue.start`` → 真正启动 worker → drain 20 个 → 新 POST → 202。
- pipeline 返回 hotspot_id + note_path 满足 finalize contract → status=completed。

429 语义 (fae2e1d commit before enqueue) 关键点:
- QueueFull 时 row 已 commit 保留 (audit trail), 不再 rollback。
- 429 响应结构不变, 但 DB 里 429 的 job 行存在 (status=queued, worker 永不
  处理, 因为 put_nowait 失败)。
- 测试必须双侧断言: HTTP 429 body + DB 5 行 queued row。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
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
# 与 path B/C 同款: 加载真 .env + 真 settings.json, 不打印值, 强制 MiniMax。

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

# Test marker for tracing: 25 个唯一的 bvid, 避免 idempotency check 复用。
N_BURST = 25
N_EXPECTED_202 = 20
N_EXPECTED_429 = 5
TOTAL_BVIDS = N_BURST  # 25

# Drain stage: 用一个全新的 bvid 证明 queue 已释放。
DRAIN_RECHECK_BVID = "BVpathDnew001"


def _bearer() -> dict[str, str]:
    return {"Authorization": "Bearer e2e-path-d-token"}


# =====================================================================
# Helpers — DB-isolation cleanup (path B/C 同款, 不需要 Reminders / vault)
# =====================================================================


def _delete_reminders_list_if_test_only(list_name: str) -> bool:
    """最安全的兜底: 只有当 list 完全空且名字像 E2E 测试所有时才删。

    Path D 不应产生任何 Reminders 副作用 (worker 没跑完, no create_learning_event),
    但作为浅 teardown 保险, 只在 list 名字含 '测试' 时检查删除。
    """
    if "测试" not in list_name:
        return False
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
        return result.returncode == 0 and result.stdout.strip() == "deleted"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# =====================================================================
# Fixture — runs full path D pipeline
# =====================================================================


@pytest_asyncio.fixture
async def e2e_run(
    tmp_path: Path,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the full path D rate-limit pipeline.

    链路 (单 fixture run 覆盖全部 4 个 TC):
      - 文件 SQLite, 跨 connection 可见 (queue worker 找到 enqueue row)
      - ``run_summary_pipeline`` patch 为 event-gated blocked_pipeline:
        worker 拉到 job 后 block 在 event, 队列不会被抢空
      - 25 个不同 bvid 并发 POST → 20×202 + 5×429 确定性
      - HTTP body + DB 双侧断言 (post-fa2e1d 429 语义: row commit 保留)
      - 释放 event → worker 跑完 20 个 → recheck POST → 202

    Teardown: 释放 blocker + 停 patcher + drop_queue_sync + 关 session。
    """
    from unittest.mock import patch

    from aipulse.core.config import get_settings
    from aipulse.hotspot.models import Hotspot, Source
    from aipulse.models.followed_up import FollowedUp
    from aipulse.models.summary_jobs import SummaryJob
    import aipulse.summarizers.queue as queue_mod
    from aipulse.summarizers.queue import (
        QUEUE_MAX_SIZE,
        JobSubmission,
        drop_queue_sync,
        get_queue,
        reset_queue_for_tests,
    )
    from aipulse.store.database import (
        configure_test_database,
        get_engine,
        get_session_maker,
        reset_db,
    )
    from httpx import ASGITransport
    from aipulse.server import app

    # ---- 0. Stop any stale worker from a prior test (path C 同款) ----
    for _attempt in range(5):
        _q = queue_mod._queue
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

    try:
        old_engine = get_engine()
        await old_engine.dispose()
    except Exception:
        pass

    queue_mod._queue = None
    queue_mod.drop_queue_sync()

    for _ in range(3):
        await asyncio.sleep(0)
    await asyncio.sleep(0.3)

    # ---- 1. File-based SQLite ----
    db_file = tmp_path / "path_d_rate_limit.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    await configure_test_database(get_settings())
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    await reset_db()

    for _ in range(2):
        await asyncio.sleep(0)

    # ---- 2. Build client + db session ----
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    db_session_maker = get_session_maker()
    db_session = db_session_maker()

    # ---- 3. Pipeline + worker pause strategy ----
    # 关键: spec 锁定 20×202 + 5×429 (严苛)。若 worker 在 burst 期间跑了
    # 哪怕 1 个 job, 队列实际就能容纳 21 个 → 21×202 + 4×429 (与 integration
    # test 同款 race)。要让 20×202 + 5×429 严格成立, worker **必须** 不在
    # burst 期间跑。
    #
    # 策略:
    #   a) Patch ``run_summary_pipeline`` 为 instant (不阻塞, 跑得快)
    #   b) 在 burst 期间把 ``queue.start`` 换成 no-op, HTTP 路由调
    #      ``queue.start()`` 也是 no-op → worker 永不跑
    #   c) 25 个并发 POST: 每个 create+commit+put_nowait, queue 从 0 堆到 20,
    #      后 5 个 QueueFull → 429。**严格 20×202 + 5×429**。
    #   d) Burst 完后恢复 ``queue.start``, 真正启动 worker, 20 个 job 在
    #      ~ 50ms 内 drain 完 (instant pipeline)。
    #   e) 新 POST 一个 bvid → 202 (queue 已 free)。

    pipeline_state: dict[str, int] = {"completed": 0}

    async def instant_pipeline(
        video_id: str,
        title: str,
        up_name: str,
        extra_context: str = "",
    ) -> dict[str, Any]:
        """Instant pipeline, no LLM/Obsidian I/O. Worker drain 极快。

        返回 ``hotspot_id`` + ``note_path`` 满足 finalize_summary_job 的
        contract → status=completed (而不是 partial / failed)。
        """
        from aipulse.hotspot.models import Hotspot as _HS
        from sqlalchemy import select as _sel

        async with db_session_maker() as s:
            hs = (
                await s.execute(_sel(_HS).where(_HS.content_id == video_id))
            ).scalar_one_or_none()
            hotspot_id = hs.id if hs else None
        pipeline_state["completed"] += 1
        return {
            "status": "completed",
            "note_path": f"/tmp/{video_id}.md",  # 假路径, 测试不验证文件存在
            "event_id": None,
            "reminder_id": None,
            "hotspot_id": hotspot_id,
            "error": None,
            "intermediate_steps": [],
        }

    patcher = patch.object(queue_mod, "run_summary_pipeline", new=instant_pipeline)
    patcher.start()

    # ---- 3b. Pause worker: stop queue.start() from creating a worker task ----
    # 直接调用 _ensure_loop_state 让 queue/lock/stop 初始化, 但不真正
    # create worker task。HTTP 路由进站时 ``queue.start()`` 会拿到 paused
    # 版本 (no-op), 队列创建由 ``enqueue_submission`` 自己的
    # ``_ensure_loop_state`` 兜底。
    queue = get_queue()
    await queue._ensure_loop_state()
    _real_start = queue.start

    async def paused_start():
        """No-op: 阻止 worker 在 burst 期间启动 (严苛 20+5 必需)。"""
        return None

    # ⚠️ queue.start 必须替换 INSTANCE attribute (class method shadow),
    # 不能换 module attribute (instance bound method 已经缓存)。
    queue.start = paused_start  # type: ignore[method-assign]

    # ---- 4. Seed DB: 1 source + 1 up + 25 unique hotspots (different bvid) ----
    src = Source(
        id="src-e2e-path-d",
        name="B 站热门（E2E path D）",
        source_type="bilibili",
        collector_class="aipulse.collectors.bilibili.HotBilibiliCollector",
        is_active=True,
    )
    up = FollowedUp(
        id="up-e2e-path-d",
        platform="bilibili",
        uid="100000000",
        display_name="E2E path D UP主",
        profile_url="https://space.bilibili.com/100000000",
        is_active=True,
    )
    db_session.add_all([src, up])
    await db_session.commit()

    # 25 个 unique bvid → 幂等性检查必每条新建
    bvids = [f"BVpathD{i:03d}" for i in range(N_BURST)]
    for i, bvid in enumerate(bvids):
        hs = Hotspot(
            id=f"hs-e2e-path-d-{i:03d}",
            title=f"path D test video {i}",
            url=f"https://www.bilibili.com/video/{bvid}",
            canonical_url=f"https://www.bilibili.com/video/{bvid}",
            source_id="src-e2e-path-d",
            source_type="bilibili",
            followed_up_id="up-e2e-path-d",
            content_id=bvid,
        )
        db_session.add(hs)
    await db_session.commit()

    # ---- 5. (no reset_queue_for_tests here — it would wipe our paused_start) ----

    try:
        ctx: dict[str, Any] = {
            "client": client,
            "db_session_maker": db_session_maker,
            "bvids": bvids,
            "pipeline_state": pipeline_state,
            "QUEUE_MAX_SIZE": QUEUE_MAX_SIZE,
            "queue": queue,
            "_real_start": _real_start,
            "paused_start": paused_start,
        }
        yield ctx
    finally:
        # ---- Teardown ----
        # Restore real start method BEFORE stop(), 否则 stop() / start() 走 paused 路径
        try:
            _q = get_queue()
            if _q is not None and _real_start is not None:
                _q.start = _real_start  # type: ignore[method-assign]
        except Exception:
            pass
        try:
            patcher.stop()
        except Exception:
            pass
        try:
            await client.aclose()
        except Exception:
            pass
        try:
            _q = get_queue()
            if _q is not None:
                await _q.stop()
        except Exception:
            pass
        try:
            await reset_queue_for_tests()
        except Exception:
            pass
        drop_queue_sync()
        try:
            await db_session.close()
        except Exception:
            pass
        # 兜底清理: 如果 setup 阶段意外创建了 AIPulse测试 列表, 删掉
        try:
            _delete_reminders_list_if_test_only("AIPulse测试")
        except Exception:
            pass


# =====================================================================
# Tests — single E2E run with 4 named TC assertions
# =====================================================================
# 与 path B/C 同款: 4 个 TC 共享一次 fixture run, 每个 TC 对应一个 assert 块
# + `[TC-NN]` 前缀, 验收对账时按错误信息精确归类。


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_path_d_rate_limit_429_overflow(e2e_run: dict) -> None:
    """spec 09 §5.4 TC-E2E-PATH-D-01..04 — 队列上限 20 + 429 overflow。

    链路 (全在一次 fixture run 内):
      TC-01  并发 POST 25 个不同 bvid → 25 个响应全回来 (worker 被 paused)
      TC-02  20×202 + 唯一 job_id (data.job_id) + data.status='queued'
      TC-03  5×429 + detail.error='QUEUE_FULL' + detail.max_size=20 + DB 5 行
      TC-04  unpause worker → drain 20 → 新 POST → 202
    """
    from sqlalchemy import select

    from aipulse.hotspot.models import Hotspot
    from aipulse.models.summary_jobs import SummaryJob

    client = e2e_run["client"]
    bvids = e2e_run["bvids"]
    pipeline_state = e2e_run["pipeline_state"]
    db_session_maker = e2e_run["db_session_maker"]
    queue = e2e_run["queue"]
    _real_start = e2e_run["_real_start"]
    queue_max = e2e_run["QUEUE_MAX_SIZE"]

    assert queue_max == 20, f"QUEUE_MAX_SIZE must be 20, got {queue_max}"

    # ─────────────── TC-D-01 ───────────────
    # 25 个 bvid 并发 POST, asyncio.gather 全部 launch 后等待
    async def post_one(bvid: str) -> tuple[str, int, dict[str, Any]]:
        r = await client.post(f"/api/summary/{bvid}", headers=_bearer())
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:500]}
        return (bvid, r.status_code, body)

    print(
        f"[TC-D-01] launching {N_BURST} concurrent POSTs (QUEUE_MAX_SIZE={queue_max})",
        file=sys.stderr,
    )
    results = await asyncio.gather(*(post_one(b) for b in bvids))
    statuses = [s for _, s, _ in results]

    n_202 = sum(1 for s in statuses if s == 202)
    n_429 = sum(1 for s in statuses if s == 429)
    n_other = sum(1 for s in statuses if s not in (202, 429))

    print(
        f"[TC-D-01] burst done: n_202={n_202}, n_429={n_429}, other={n_other}, "
        f"statuses={statuses}",
        file=sys.stderr,
    )

    # 阻塞策略保证严苛 20 + 5: worker 拉到 1 个后 block, 队列堆积 ≤ 20。
    assert n_202 == N_EXPECTED_202, (
        f"[TC-D-01/02] expected exactly {N_EXPECTED_202}×202, got {n_202}; "
        f"statuses={statuses}"
    )
    assert n_429 == N_EXPECTED_429, (
        f"[TC-D-03] expected exactly {N_EXPECTED_429}×429, got {n_429}; "
        f"statuses={statuses}"
    )
    assert n_other == 0, (
        f"[TC-D-01] expected only 202+429 statuses, got {n_other} other(s); "
        f"statuses={statuses}"
    )
    assert n_202 + n_429 == TOTAL_BVIDS, (
        f"[TC-D-01] 202+429 must equal {TOTAL_BVIDS}, got {n_202}+{n_429}"
    )

    # ─────────────── TC-D-02 ───────────────
    # HTTP 202 body: success=true + data.job_id + data.status=queued
    success_results = [r for r in results if r[1] == 202]
    assert len(success_results) == N_EXPECTED_202, (
        f"[TC-D-02] filter sanity: expected {N_EXPECTED_202} successes, "
        f"got {len(success_results)}"
    )
    for bvid, status, body in success_results:
        assert body.get("success") is True, (
            f"[TC-D-02] {bvid} response.success != True: {body}"
        )
        data = body.get("data") or {}
        assert data.get("job_id"), f"[TC-D-02] {bvid} missing data.job_id: {body}"
        assert data.get("status") == "queued", (
            f"[TC-D-02] {bvid} expected status=queued, got {data.get('status')!r}"
        )
        assert data.get("video_id") == bvid, (
            f"[TC-D-02] {bvid} echoed video_id mismatch: {data}"
        )
        assert data.get("reused") is False, (
            f"[TC-D-02] {bvid} expected reused=false, got {data.get('reused')!r}"
        )

    job_ids = [r[2]["data"]["job_id"] for r in success_results]
    assert len(set(job_ids)) == N_EXPECTED_202, (
        f"[TC-D-02] all {N_EXPECTED_202} job_ids must be unique, got "
        f"{len(set(job_ids))} unique: {job_ids}"
    )

    # ─────────────── TC-D-03 ───────────────
    # HTTP 429 body: detail.error='QUEUE_FULL' + detail.max_size + message 含
    # 「队列已满」字样
    rejected_results = [r for r in results if r[1] == 429]
    assert len(rejected_results) == N_EXPECTED_429, (
        f"[TC-D-03] filter sanity: expected {N_EXPECTED_429} rejected, "
        f"got {len(rejected_results)}"
    )
    for bvid, status, body in rejected_results:
        detail = body.get("detail") or {}
        assert detail.get("error") == "QUEUE_FULL", (
            f"[TC-D-03] {bvid} expected detail.error='QUEUE_FULL', got {detail}"
        )
        assert detail.get("max_size") == queue_max, (
            f"[TC-D-03] {bvid} expected detail.max_size={queue_max}, "
            f"got {detail.get('max_size')!r}"
        )
        assert "size" in detail, (
            f"[TC-D-03] {bvid} detail should include current size: {detail}"
        )
        msg = detail.get("message") or ""
        assert "队列已满" in msg, (
            f"[TC-D-03] {bvid} message should mention '队列已满': {msg!r}"
        )

    # ─────────────── TC-D-03 (post-fa2e1d 429 语义) ───────────────
    # 关键: QueueFull 时 row 已 commit 保留 (audit trail), 不再 rollback。
    # 验证 DB 里有 5 行 status=queued (worker 永不处理, 因为 put_nowait 失败)。
    rejected_bvids = [r[0] for r in rejected_results]
    async with db_session_maker() as s:
        rejected_jobs = (
            await s.execute(
                select(SummaryJob).where(SummaryJob.video_id.in_(rejected_bvids))
            )
        ).scalars().all()
    assert len(rejected_jobs) == N_EXPECTED_429, (
        f"[TC-D-03] DB must contain {N_EXPECTED_429} rejected rows (post-fa2e1d "
        f"audit trail), got {len(rejected_jobs)} for bvids={rejected_bvids}"
    )
    rejected_row_statuses = [j.status for j in rejected_jobs]
    assert all(st == "queued" for st in rejected_row_statuses), (
        f"[TC-D-03] 429 rows must have status=queued (worker never picked them, "
        f"put_nowait failed before queue ownership), got {rejected_row_statuses}"
    )
    # rejected rows 也得有 video_id + 初始 created_at
    rejected_vid_set = {j.video_id for j in rejected_jobs}
    assert rejected_vid_set == set(rejected_bvids), (
        f"[TC-D-03] DB rejected rows video_id mismatch: "
        f"expected={rejected_bvids}, got={rejected_vid_set}"
    )

    # ─────────────── TC-D-02 (DB 双侧) ───────────────
    # 202 响应对应的 DB row 也存在 + status=queued (worker 暂停期间没跑)
    succeeded_bvids = [r[0] for r in success_results]
    async with db_session_maker() as s:
        succeeded_jobs = (
            await s.execute(
                select(SummaryJob).where(SummaryJob.video_id.in_(succeeded_bvids))
            )
        ).scalars().all()
    assert len(succeeded_jobs) == N_EXPECTED_202, (
        f"[TC-D-02] DB must contain {N_EXPECTED_202} success rows, got "
        f"{len(succeeded_jobs)}"
    )
    succeeded_row_statuses = [j.status for j in succeeded_jobs]
    assert all(st == "queued" for st in succeeded_row_statuses), (
        f"[TC-D-02] success rows should still be queued (worker paused during "
        f"burst), got {succeeded_row_statuses}"
    )

    # ─────────────── TC-D-04 ───────────────
    # Unpause worker: 恢复 queue.start, 真正启动 worker → drain 20 个 job →
    # 新 POST → 202
    print("[TC-D-04] unpausing worker, waiting for drain", file=sys.stderr)
    queue.start = _real_start  # type: ignore[method-assign]
    await queue.start()

    # 等所有 20 个 job 走到 completed（轮询最多 10s）
    deadline = asyncio.get_event_loop().time() + 10.0
    n_completed = 0
    last_statuses: list[str] = []
    while asyncio.get_event_loop().time() < deadline:
        async with db_session_maker() as s:
            all_rows = (
                await s.execute(
                    select(SummaryJob).where(
                        SummaryJob.video_id.in_(succeeded_bvids)
                    )
                )
            ).scalars().all()
        last_statuses = [r.status for r in all_rows]
        n_completed = sum(1 for st in last_statuses if st == "completed")
        if n_completed == N_EXPECTED_202:
            break
        await asyncio.sleep(0.1)
    print(
        f"[TC-D-04] final poll: {n_completed}/{N_EXPECTED_202} jobs completed, "
        f"statuses={last_statuses}, pipeline_state.completed={pipeline_state['completed']}",
        file=sys.stderr,
    )

    print(
        f"[TC-D-04] drain done: {n_completed}/{N_EXPECTED_202} jobs completed, "
        f"pipeline_state.completed={pipeline_state['completed']}",
        file=sys.stderr,
    )
    assert n_completed == N_EXPECTED_202, (
        f"[TC-D-04] expected all {N_EXPECTED_202} jobs completed after drain, "
        f"got {n_completed}/{N_EXPECTED_202}; pipeline_state.completed="
        f"{pipeline_state['completed']}"
    )

    # 新 POST 一个全新 bvid → 202 (queue 已释放)
    new_bvid = DRAIN_RECHECK_BVID
    async with db_session_maker() as s:
        hs_new = Hotspot(
            id="hs-e2e-path-d-new",
            title="path D drain recheck video",
            url=f"https://www.bilibili.com/video/{new_bvid}",
            canonical_url=f"https://www.bilibili.com/video/{new_bvid}",
            source_id="src-e2e-path-d",
            source_type="bilibili",
            followed_up_id="up-e2e-path-d",
            content_id=new_bvid,
        )
        s.add(hs_new)
        await s.commit()

    new_resp = await client.post(f"/api/summary/{new_bvid}", headers=_bearer())
    assert new_resp.status_code == 202, (
        f"[TC-D-04] post-drain POST should return 202 (queue free), got "
        f"{new_resp.status_code}: {new_resp.text[:500]}"
    )
    new_body = new_resp.json()
    assert new_body.get("success") is True, (
        f"[TC-D-04] post-drain response.success != True: {new_body}"
    )
    new_data = new_body.get("data") or {}
    assert new_data.get("status") == "queued", (
        f"[TC-D-04] post-drain status should be queued: {new_data}"
    )
    assert new_data.get("video_id") == new_bvid, (
        f"[TC-D-04] post-drain video_id mismatch: {new_data}"
    )
    assert new_data.get("job_id"), (
        f"[TC-D-04] post-drain response missing job_id: {new_body}"
    )

    # 同时确认: 之前 5 个 429 row 状态没变 (worker drain 不应该影响它们)
    async with db_session_maker() as s:
        still_queued = (
            await s.execute(
                select(SummaryJob).where(SummaryJob.video_id.in_(rejected_bvids))
            )
        ).scalars().all()
    still_queued_statuses = [j.status for j in still_queued]
    assert all(st == "queued" for st in still_queued_statuses), (
        f"[TC-D-04] 429 rows should remain queued (no auto-retry), got "
        f"{still_queued_statuses}"
    )
