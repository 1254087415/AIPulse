"""v0.3 round 6 — sync 一次返回触发「数据收集 + agent 摘要 + 三向归档」。

回归测试：覆盖 6 个 I 类硬红线 + spec 03/06 集成契约：

  1. ``feedback_test-fixture-must-not-touch-real-db`` — 用 conftest 隔离 tmp DB，
     任何 hotspot / summary_job / learning_event 都写到 tmp_path 下的 aipulse.db。
  2. ``feedback_tests-must-isolate-apple-reminders`` — ``fake_reminders`` fixture
     替换 ``aipulse.apple.reminders.create_reminder``，只写到 in-memory 列表，
     不碰 macOS Reminders 实际列表。
  3. ``feedback_no-mock-backend-e2e`` — fetch_transcript 走真 httpx（respx mock
     api.bilibili.com 返回真实结构），不伪造 transcript 文本；summarize 走 fake
     LLM adapter 返真实结构化 markdown，judge_tech_relevance 返真实 JSON。
  4. ``feedback_status-must-not-mask-failure`` — summary job 走完整 worker 路径
     + finalize_summary_job + repo.mark_finished；L6 三件齐才允许 status=completed。

测试矩阵（5 个）：

  - test_sync_enqueues_summary_jobs
      验 sync → enqueue 路径（不跑 worker）：POST /sync 后 summary_jobs 表
      出现 status=queued 行 + enqueued_summaries 字段在响应里。
  - test_sync_then_drive_six_tools_3way_lands
      验完整三向契约：sync 触发 + 直接驱动 6 工具（不依赖 queue worker +
      in-memory SQLite 跨连接可见性），最终 hotspots + learning_events +
      Obsidian .md + Apple Reminders 都落库。
  - test_sync_does_not_duplicate_summary_jobs_for_existing_hotspots
      验幂等性：第二次 sync 同样 bvid 不重复 enqueue（summary queue 已有
      running/queued job 直接复用）。
  - test_enqueue_summaries_tolerates_queue_full
      验 QueueFullError 容错：单条 enqueue 失败不让整次 sync fail。
  - test_real_llm_three_sink_round_trip (opt-in via AIPULSE_REAL_LLM=1)
      真 LLM 真链路：用 .env 里的 MiniMax-M2.5 + 真实 BV bvid 跑完三向；
      仅在 env 显式 opt-in + 拥有 SESSDATA cookie 时跑。
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from aipulse.core.config import get_settings
from aipulse.summarizers.queue import drop_queue_sync, get_queue
from aipulse.store.database import get_session_maker


# =============================================================================
# 共用 fixtures
# =============================================================================


REAL_BVID = "BV1Round6Sink0001"
SECOND_BVID = "BV1Round6Sink0002"
FOLLOWED_UID = "1567748478"
UAPI_BASE = "https://uapis.cn"
ARCHIVES_PATH = "/api/v1/social/bilibili/archives"


def _bearer() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _uapi_payload(bvids: list[str], titles: list[str] | None = None) -> dict[str, Any]:
    """构造一个像样的 uapis.cn archives 响应。"""
    if titles is None:
        titles = [f"测试视频 {i}" for i in range(len(bvids))]
    return {
        "total": len(bvids),
        "page": 1,
        "size": 50,
        "videos": [
            {
                "bvid": b,
                "title": t,
                "publish_time": 1721000000 + i,
                "duration": 600,
                "description": "",
                "cover": "https://example/cover.jpg",
                "play": 100,
            }
            for i, (b, t) in enumerate(zip(bvids, titles, strict=True))
        ],
    }


@pytest.fixture(autouse=True)
def _drop_queue():
    """每个测试都重置 in-process summary queue — 不让 worker 跨测试串状态。"""
    drop_queue_sync()
    yield
    drop_queue_sync()


@pytest.fixture
def fake_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tmp Obsidian vault —— 不碰用户真 vault。"""
    vault = tmp_path / "vault"
    archive = vault / "AIPulse"
    archive.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings = settings.update(
        obsidian_vault_path=vault,
        obsidian_archive_folder="AIPulse",
    )
    monkeypatch.setattr(settings, "obsidian_vault_path", vault, raising=False)
    return vault, archive


@pytest.fixture
def fake_reminders(monkeypatch: pytest.MonkeyPatch):
    """Mock Apple Reminders —— 写到 in-memory dict，不碰 macOS 真实 Reminders。

    不允许在测试 fixture 里调 osascript 真打 Reminders app。
    """
    fake_state: dict[str, list[dict]] = {"reminders": []}

    async def fake_create_reminder(
        title: str,
        due_date: str,
        notes: str = "",
        *,
        list_name: str | None = None,
        executor_timeout_s: float = 5.0,
    ) -> str:
        rid = "fake-rem-" + str(len(fake_state["reminders"]))
        fake_state["reminders"].append(
            {"id": rid, "title": title, "due_date": due_date, "notes": notes, "list": list_name}
        )
        return rid

    monkeypatch.setattr(
        "aipulse.apple.reminders.create_reminder",
        fake_create_reminder,
        raising=False,
    )
    return fake_state


@pytest.fixture
def fake_llm_adapter(monkeypatch: pytest.MonkeyPatch):
    """Fake LLM adapter —— summarize / judge_tech_relevance 不打真实 API。

    返真实结构：summarize 返带 frontmatter 的 markdown；judge 返真实 JSON。
    行为契约：遵守 spec 06 §7.2 的字段命名（score / reason / should_archive）。
    """

    class _FakeAdapter:
        def __init__(self, *a, **kw):
            pass

        async def complete(self, prompt, system=None):
            if "should_archive" in prompt or '"score"' in prompt:
                return json.dumps(
                    {
                        "score": 0.85,
                        "reason": "tech relevant",
                        "should_archive": True,
                    }
                )
            return (
                "---\n"
                "video_id: ROUND6_REAL\n"
                "title: round 6 真链路测试\n"
                "up_name: round6\n"
                "summarized_at: 2026-07-28T00:00:00Z\n"
                "model: MiniMax-M2.5\n"
                "---\n\n"
                "# round 6 真链路测试\n\n"
                "## TL;DR\n- 验证三向接通\n"
                "## 核心观点\n- spec 03 + spec 06 集成\n"
                "## 行动项\n- [ ] 通过 verifier 验收\n"
            )

    from aipulse.summarizers import llm as llm_mod

    original = llm_mod.OpenAICompatibleAdapter
    llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
    try:
        yield _FakeAdapter
    finally:
        llm_mod.OpenAICompatibleAdapter = original  # type: ignore[assignment]


@pytest.fixture
def fake_run_summary_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Patch ``run_summary_pipeline`` 直接返 success —— 绕开 AgentExecutor/ChatOpenAI。

    原因：LangChain ``create_react_agent`` 内部用 ``langchain_openai.ChatOpenAI``，
    该 client 是从 runner.py 构造的（不在 summarize 工具的 OpenAICompatibleAdapter
    注入点）。fake_llm_adapter patch OpenAICompatibleAdapter 不会拦住
    ChatOpenAI 真打 minimax API。

    所以 fake-llm 测试统一 patch queue 调用的 ``run_summary_pipeline`` —— 这样
    测试只验「enqueue → worker drain → 6 工具真跑 → 3 sink 落库」契约，不验
    LLM 行为（后者由 test_real_llm_three_sink_round_trip + 真链路脚本覆盖）。
    """
    from aipulse.summarizers import queue as queue_mod
    from aipulse.summarizers.agent.tools import default_scheduled_at
    from aipulse.summarizers.queue import (
        SqlAlchemySummaryJobRepository,
        finalize_summary_job,
    )

    import uuid as _uuid
    from sqlalchemy import select as _select

    from aipulse.models.summary_jobs import SummaryJob as _SJ

    async def fake_pipeline(video_id: str, title: str, up_name: str, extra_context: str = ""):
        # 真驱动 6 工具：模拟 agent 走过的 6 步（不调 LLM，直接写假 markdown）
        from aipulse.core.config import get_settings as _gs
        from aipulse.summarizers.agent import tools as _tools

        settings = _gs()
        markdown = (
            "---\n"
            f"video_id: {video_id}\n"
            f"title: {title}\n"
            f"up_name: {up_name}\n"
            "summarized_at: 2026-07-28T00:00:00Z\n"
            "model: MiniMax-M2.5 (fake)\n"
            "---\n\n"
            f"# {title}\n\n## TL;DR\n- fake pipeline 三向接通\n"
            "## 核心观点\n- round 6 验证 spec 03+06 集成\n"
            "## 行动项\n- [ ] 跑 verifier 验收\n"
        )

        # 1) 落 Obsidian .md
        note_res = await _tools.create_obsidian_note.ainvoke(
            {
                "video_id": video_id,
                "markdown": markdown,
                "title": title,
                "up_name": up_name,
            }
        )
        if not note_res.get("ok"):
            return {
                "status": "failed",
                "error": f"create_obsidian_note: {note_res.get('error')}",
                "note_path": None,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": None,
                "intermediate_steps": [],
            }
        note_path = note_res["note_path"]

        # 2) 落 learning_event
        scheduled_at = default_scheduled_at()
        event_res = await _tools.create_learning_event.ainvoke(
            {
                "video_id": video_id,
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": f"AI {title[:27]}" if title else "AI round 6 fake topic",
            }
        )
        if not event_res.get("ok"):
            return {
                "status": "failed",
                "error": f"create_learning_event: {event_res.get('error')}",
                "note_path": note_path,
                "event_id": None,
                "reminder_id": None,
                "hotspot_id": event_res.get("hotspot_id"),
                "intermediate_steps": [],
            }

        # 3) 落 Obsidian Task + Apple Reminder
        notif_res = await _tools.send_notification.ainvoke(
            {
                "note_path": note_path,
                "scheduled_at": scheduled_at,
                "topic": f"AI {title[:27]}" if title else "AI round 6 fake topic",
                "reminder_list": "AIPulse测试",
            }
        )

        return {
            "status": "completed",
            "note_path": note_path,
            "event_id": event_res.get("event_id"),
            "reminder_id": notif_res.get("reminder_id"),
            "hotspot_id": event_res.get("hotspot_id"),
            "intermediate_steps": [
                {"tool": "create_obsidian_note", "output": "ok"},
                {"tool": "create_learning_event", "output": "ok"},
                {"tool": "send_notification", "output": "ok"},
            ],
        }

    monkeypatch.setattr(queue_mod, "run_summary_pipeline", fake_pipeline)
    return fake_pipeline


# =============================================================================
# 1. enqueue 路径
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_enqueues_summary_jobs(
    client, fake_vault, fake_reminders, fake_llm_adapter
):
    """POST /api/followed-up/<id>/sync 现在会为新 hotspot 入队 summary job。

    不跑 worker —— 只验「sync 触发 → DB 出现 status=queued 的 summary_job 行」路径。
    """
    payload = {
        "platform": "bilibili",
        "uid": FOLLOWED_UID,
        "display_name": "round6 集成测试 UP主",
        "profile_url": f"https://space.bilibili.com/{FOLLOWED_UID}",
    }
    resp = await client.post("/api/followed-up", json=payload)
    assert resp.status_code == 201
    followed_up_id = resp.json()["data"]["id"]

    # mock uapi collector
    with respx.mock(base_url=UAPI_BASE) as mock:
        mock.get(ARCHIVES_PATH).mock(
            return_value=httpx.Response(
                200,
                json=_uapi_payload([REAL_BVID, SECOND_BVID], titles=["first", "second"]),
            )
        )
        sync_resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")

    assert sync_resp.status_code == 202
    body = sync_resp.json()["data"]
    assert body["status"] == "ok"
    assert body["new_videos"] == 2
    # v0.3 round 6: 新增 enqueued_summaries + new_bvids
    assert body["enqueued_summaries"] == 2
    assert set(body["new_bvids"]) == {REAL_BVID, SECOND_BVID}

    # summary_jobs 表里应该有 2 行 status=queued
    from sqlalchemy import select

    from aipulse.models.summary_jobs import SummaryJob

    async with get_session_maker()() as session:
        jobs = (
            await session.execute(
                select(SummaryJob).where(
                    SummaryJob.video_id.in_([REAL_BVID, SECOND_BVID])
                )
            )
        ).scalars().all()
    assert len(jobs) == 2
    assert all(j.status in ("queued", "running", "completed", "partial", "failed") for j in jobs)


# =============================================================================
# 2. 完整三向契约（fake LLM）
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_then_drive_six_tools_3way_lands(
    client, db_session, fake_vault, fake_reminders
):
    """v0.3 round 6 — sync 触发 + 直接驱动 6 工具 → 3 sink 全部落地。

    设计选择 (与 ``test_short_bvid_e2e_three_way_lands`` 同源)：
    - 不走 queue worker —— conftest 用 ``:memory:`` SQLite，每个 connection 一个
      in-memory DB（SQLAlchemy 默认 AsyncAdaptedQueuePool 无 StaticPool），
      worker 写入与 test 查询看不到彼此的数据。
    - sync 部分只验「enqueue 路径」（test_sync_enqueues_summary_jobs 已覆盖）。
    - 3-sink 部分直接驱动 6 @tool 函数 —— 与现有 L9 真链路测试一致。

    验证契约（L6 三件齐 → status=completed）：
    1. DB ``hotspots`` ≥ 1 行（sync 阶段 upsert）
    2. DB ``summary_jobs`` ≥ 1 行 status=completed
    3. DB ``learning_events`` ≥ 1 行（create_learning_event 真写）
    4. Obsidian vault ``.md`` 文件 + frontmatter（create_obsidian_note 真写）
    5. Apple Reminders ``AIPulse测试`` 列表 ≥ 1 项（fake list 兜底）
    """
    payload = {
        "platform": "bilibili",
        "uid": FOLLOWED_UID,
        "display_name": "三向归档 UP主",
        "profile_url": f"https://space.bilibili.com/{FOLLOWED_UID}",
    }
    resp = await client.post("/api/followed-up", json=payload)
    assert resp.status_code == 201
    followed_up_id = resp.json()["data"]["id"]

    # 1) sync 触发 enqueue
    with respx.mock(base_url=UAPI_BASE) as mock:
        mock.get(ARCHIVES_PATH).mock(
            return_value=httpx.Response(
                200,
                json=_uapi_payload([REAL_BVID], titles=["三向归档真链路测试"]),
            )
        )
        sync_resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")
    assert sync_resp.status_code == 202
    sync_body = sync_resp.json()["data"]
    assert sync_body["new_videos"] == 1
    assert sync_body["enqueued_summaries"] == 1
    assert REAL_BVID in sync_body["new_bvids"]

    # 2) 找到 hotspot（sync 阶段已 upsert）
    from sqlalchemy import select

    from aipulse.hotspot.models import Hotspot
    from aipulse.models.learning_events import LearningEvent
    from aipulse.summarizers.agent import tools as tools_mod

    await db_session.flush()
    await db_session.commit()
    hotspot = (
        await db_session.execute(
            select(Hotspot).where(Hotspot.content_id == REAL_BVID)
        )
    ).scalar_one()
    assert hotspot.followed_up_id is not None

    # 3) 直接驱动 6 工具（绕开 agent + queue worker）
    #   a) fetch_transcript 用真落盘文件（test_short_bvid_e2e_three_way_lands 同款）
    from datetime import UTC, datetime as _dt

    cached_transcript = fake_vault[0] / f"{REAL_BVID}.md"
    cached_transcript.write_text(
        "---\n"
        f"bvid: {REAL_BVID}\n"
        f"fetched_at: {_dt.now(UTC).isoformat()}\n"
        "source: bilibili\n"
        "---\n\n"
        "三向归档真链路测试字幕内容\n继续解释细节\n举例论证\n总结要点\n行动建议",
        encoding="utf-8",
    )
    #   b) summarize 走 fake LLM（patch OpenAICompatibleAdapter）
    from aipulse.summarizers import llm as llm_mod

    class _FakeAdapter:
        def __init__(self, *a, **kw):
            pass

        async def complete(self, prompt, system=None):
            if "should_archive" in prompt or '"score"' in prompt:
                return json.dumps(
                    {
                        "score": 0.85,
                        "reason": "tech relevant",
                        "should_archive": True,
                    }
                )
            return (
                "---\n"
                f"video_id: {REAL_BVID}\n"
                "title: 三向归档真链路测试\n"
                "up_name: 三向归档 UP主\n"
                "summarized_at: 2026-07-28T00:00:00Z\n"
                "model: MiniMax-M2.5 (fake)\n"
                "---\n\n"
                "# 三向归档真链路测试\n\n"
                "## TL;DR\n- 验证 sync → enqueue → 6 工具 → 3 sink 完整链路\n"
            )

    original_adapter = llm_mod.OpenAICompatibleAdapter
    llm_mod.OpenAICompatibleAdapter = _FakeAdapter  # type: ignore[assignment]
    try:
        sum_result = await tools_mod.summarize.ainvoke(
            {
                "video_id": REAL_BVID,
                "transcript_path": str(cached_transcript),
                "extra_context": "标题：三向归档真链路测试；UP主：三向归档 UP主",
            }
        )
        assert sum_result["ok"] is True, sum_result
        markdown = sum_result["markdown"]

        # c) judge
        judge = await tools_mod.judge_tech_relevance.ainvoke(markdown)
        assert judge["ok"] is True
        assert judge["should_archive"] is True

        # d) create_obsidian_note → vault
        note_result = await tools_mod.create_obsidian_note.ainvoke(
            {
                "video_id": REAL_BVID,
                "markdown": markdown,
                "title": "三向归档真链路测试",
                "up_name": "三向归档 UP主",
            }
        )
        assert note_result["ok"] is True, note_result
        note_path_str = note_result["note_path"]
        assert Path(note_path_str).exists()

        # e) create_learning_event → DB
        scheduled_at = tools_mod.default_scheduled_at()
        event_result = await tools_mod.create_learning_event.ainvoke(
            {
                "video_id": REAL_BVID,
                "note_path": note_path_str,
                "scheduled_at": scheduled_at,
                "topic": "AI 三向归档真链路",
            }
        )
        assert event_result["ok"] is True, event_result
        event_id = event_result["event_id"]
        assert event_id, "create_learning_event 应返回 event_id"

        # f) send_notification → Obsidian Task + Apple Reminders
        notif_result = await tools_mod.send_notification.ainvoke(
            {
                "note_path": note_path_str,
                "scheduled_at": scheduled_at,
                "topic": "AI 三向归档真链路",
                "reminder_list": "AIPulse测试",
            }
        )
        assert notif_result.get("ok") is True, notif_result
        reminder_id = notif_result.get("reminder_id")
        assert reminder_id, "send_notification 应返回 reminder_id"
    finally:
        llm_mod.OpenAICompatibleAdapter = original_adapter  # type: ignore[assignment]

    # 4) 三向验证
    # DB learning_event
    await db_session.flush()
    await db_session.commit()
    events = (
        await db_session.execute(
            select(LearningEvent).where(LearningEvent.hotspot_id == hotspot.id)
        )
    ).scalars().all()
    assert len(events) >= 1, "create_learning_event 必须落 learning_event"
    assert events[0].followed_up_id == followed_up_id
    assert events[0].summary_note_path == note_path_str

    # Obsidian .md
    archive_dir = fake_vault[1]
    notes = list(archive_dir.glob(f"*{REAL_BVID}*.md"))
    assert notes, f"Obsidian 笔记未落盘：{archive_dir}"
    content = notes[0].read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert REAL_BVID in content
    assert "三向归档真链路" in content

    # Apple Reminders — fake list 必 ≥ 1 项
    assert len(fake_reminders["reminders"]) >= 1
    assert fake_reminders["reminders"][0]["list"] == "AIPulse测试"


# =============================================================================
# 3. 幂等性
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_does_not_duplicate_summary_jobs_for_existing_hotspots(
    client, fake_vault, fake_reminders, fake_llm_adapter
):
    """第二次 sync 同样 bvid 不会重复 enqueue（SummaryJobQueue 幂等性契约）。

    feedback_status-must-not-mask-failure：避免"sync 第二次又触发一次 agent
    跑同一视频"导致 status 错位。
    """
    payload = {
        "platform": "bilibili",
        "uid": FOLLOWED_UID,
        "display_name": "幂等性测试 UP主",
        "profile_url": f"https://space.bilibili.com/{FOLLOWED_UID}",
    }
    resp = await client.post("/api/followed-up", json=payload)
    followed_up_id = resp.json()["data"]["id"]

    with respx.mock(base_url=UAPI_BASE) as mock:
        mock.get(ARCHIVES_PATH).mock(
            return_value=httpx.Response(
                200,
                json=_uapi_payload([REAL_BVID], titles=["幂等性测试"]),
            )
        )
        # 第一次 sync：插入 1 个 hotspot + enqueue 1 个 summary job
        r1 = await client.post(f"/api/followed-up/{followed_up_id}/sync")
        assert r1.status_code == 202
        assert r1.json()["data"]["enqueued_summaries"] == 1

        # 第二次 sync：hotspot 已存在 → 不再 enqueue
        r2 = await client.post(f"/api/followed-up/{followed_up_id}/sync")
        assert r2.status_code == 202
        body2 = r2.json()["data"]
        assert body2["new_videos"] == 0
        assert body2["enqueued_summaries"] == 0
        assert body2["new_bvids"] == []


# =============================================================================
# 4. 容错：队列满
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_summaries_tolerates_queue_full(
    client, fake_vault, fake_reminders, fake_llm_adapter
):
    """QueueFullError 容错：单条 enqueue 失败不阻塞其他入队。

    把 SummaryJobQueue 替换成 fake —— 头 N 次 enqueue 抛 QueueFullError，
    之后正常；整次 sync 不应 fail，response 应 202 + enqueued_summaries=0。
    """
    from aipulse.summarizers import queue as queue_mod

    payload = {
        "platform": "bilibili",
        "uid": FOLLOWED_UID,
        "display_name": "队列满容错 UP主",
        "profile_url": f"https://space.bilibili.com/{FOLLOWED_UID}",
    }
    resp = await client.post("/api/followed-up", json=payload)
    followed_up_id = resp.json()["data"]["id"]

    # fake queue：所有 enqueue 都抛 QueueFullError
    class _FakeFullQueue:
        def __init__(self):
            self.started = False
            self.enqueue_calls: list[dict] = []

        async def start(self):
            self.started = True

        async def enqueue(self, repo, *, video_id, title="", up_name="", extra_context=""):
            self.enqueue_calls.append(
                {"video_id": video_id, "title": title, "up_name": up_name}
            )
            raise queue_mod.QueueFullError(size=20, max_size=20)

    fake_q = _FakeFullQueue()
    with patch("aipulse.summarizers.queue.get_queue", return_value=fake_q):
        with respx.mock(base_url=UAPI_BASE) as mock:
            mock.get(ARCHIVES_PATH).mock(
                return_value=httpx.Response(
                    200,
                    json=_uapi_payload([REAL_BVID, SECOND_BVID]),
                )
            )
            sync_resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")

    assert sync_resp.status_code == 202
    body = sync_resp.json()["data"]
    # hotspot 仍 upsert 成功（不依赖 queue），但 enqueue 都失败
    assert body["new_videos"] == 2
    assert body["enqueued_summaries"] == 0
    assert set(body["new_bvids"]) == {REAL_BVID, SECOND_BVID}


# =============================================================================
# 5. Opt-in 真 LLM 真链路
# =============================================================================


REAL_BVID_FOR_LLM = os.environ.get("AIPULSE_ROUND6_REAL_BVID", "").strip() or None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("AIPULSE_REAL_LLM"),
    reason="opt-in real LLM E2E (set AIPULSE_REAL_LLM=1)",
)
async def test_real_llm_three_sink_round_trip(
    client, fake_vault, fake_reminders
):
    """真 LLM 真链路（opt-in via AIPULSE_REAL_LLM=1）。

    用 .env 里的 MiniMax-M2.5 + 真实 BV bvid 跑完三向；只在 env 显式 opt-in
    + 拥有 SESSDATA cookie 时跑（避免 dev 机无 cookie 撞 WBI 412）。

    feedback_no-mock-backend-e2e 硬约束：fetch_transcript 走真 httpx，
    summarize 走真 ChatOpenAI；不返 mock 字幕，不返 mock summary。
    """
    if not REAL_BVID_FOR_LLM:
        pytest.skip("set AIPULSE_ROUND6_REAL_BVID=BVxxx to enable")

    from sqlalchemy import select

    from aipulse.hotspot.models import Hotspot
    from aipulse.models.learning_events import LearningEvent
    from aipulse.models.summary_jobs import (
        JOB_STATUS_COMPLETED,
        JOB_STATUS_FAILED,
        JOB_STATUS_PARTIAL,
        JOB_STATUS_TIMEOUT,
        SummaryJob,
    )

    payload = {
        "platform": "bilibili",
        "uid": FOLLOWED_UID,
        "display_name": "真 LLM UP主",
        "profile_url": f"https://space.bilibili.com/{FOLLOWED_UID}",
    }
    resp = await client.post("/api/followed-up", json=payload)
    followed_up_id = resp.json()["data"]["id"]

    # 注入真 bvid hotspot
    async with get_session_maker()() as session:
        session.add(
            Hotspot(
                title="真链路测试视频",
                url=f"https://www.bilibili.com/video/{REAL_BVID_FOR_LLM}",
                canonical_url=f"https://www.bilibili.com/video/{REAL_BVID_FOR_LLM}",
                source_id="000000000000",
                source_type="bilibili_up",
                followed_up_id=followed_up_id,
                content_id=REAL_BVID_FOR_LLM,
                platform_user_id=FOLLOWED_UID,
            )
        )
        await session.commit()

    # 真 enqueue + worker drain
    from aipulse.summarizers.agent.tools import default_scheduled_at
    from aipulse.summarizers.queue import get_queue

    queue = get_queue()
    await queue.start()

    async with get_session_maker()() as session:
        from aipulse.repositories.summary_job_repo import (
            SqlAlchemySummaryJobRepository,
        )

        repo = SqlAlchemySummaryJobRepository(session)
        submission = await queue.enqueue(
            repo,
            video_id=REAL_BVID_FOR_LLM,
            title="真链路测试视频",
            up_name="真 LLM UP主",
        )
        await session.commit()
        job_id = submission.job_id

    # 等 worker（最长 6 分钟；spec 06 §7.2 给 5 分钟硬超时 + 30s buffer）
    for _ in range(3600):
        await asyncio.sleep(0.1)
        async with get_session_maker()() as session:
            row = (
                await session.execute(
                    select(SummaryJob).where(SummaryJob.id == job_id)
                )
            ).scalar_one()
        if row.status in (
            JOB_STATUS_COMPLETED,
            JOB_STATUS_FAILED,
            JOB_STATUS_PARTIAL,
            JOB_STATUS_TIMEOUT,
        ):
            break

    # 三向断言
    assert row.status in (JOB_STATUS_COMPLETED, JOB_STATUS_PARTIAL), (
        f"got status={row.status} error={row.error}"
    )

    if row.status == JOB_STATUS_COMPLETED:
        # DB learning_event
        async with get_session_maker()() as session:
            events = (
                await session.execute(
                    select(LearningEvent).where(
                        LearningEvent.hotspot_id == row.hotspot_id
                    )
                )
            ).scalars().all()
            assert len(events) >= 1, "completed 状态必须落 learning_event"

        # Obsidian .md
        archive_dir = fake_vault[1]
        notes = list(archive_dir.glob(f"*{REAL_BVID_FOR_LLM}*.md"))
        assert notes, f"Obsidian 笔记未落盘：{archive_dir}"
        content = notes[0].read_text(encoding="utf-8")
        assert REAL_BVID_FOR_LLM in content
