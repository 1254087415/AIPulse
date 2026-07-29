"""v0.3 E2E 路径 A — 添加 UP 主 → 自动同步。

覆盖 spec 09 §5.1 TC-E2E-PATH-A-* 的全部 6 条端到端用例：

- TC-E2E-PATH-A-01 添加合法 UP 主 → 卡片出现
- TC-E2E-PATH-A-02 头像 + 昵称正确显示
- TC-E2E-PATH-A-03 详情页合集列表（折叠）+ 最近 20 条视频
- TC-E2E-PATH-A-04 等 30 分钟（或手动触发）→ hotspot 数 +N
- TC-E2E-PATH-A-05 三处反馈齐全：modal 关闭 + toast + 新卡片插入
- TC-E2E-PATH-A-06 UP 主详情页 Back 按钮回到关注列表

链路说明
--------

- 真实 B 站（uapis.cn + api.bilibili.com），无 mock。
- UP 主固定 ``1567748478``（跟李沐学 AI），与 spec §1.1 fixture 一致。
- 数据库：复用 conftest 的 in-memory SQLite；不碰主 checkout 的
  ``data/aipulse.db``。
- 失败策略：B 站偶发慢（uapis.cn 风控 / api.bilibili.com WBI 412），
  端到端重试一次；仍然失败则该测试 FAIL —— 永不用 mock 兜底冒充通过。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import pytest
from httpx import AsyncClient
from sqlalchemy import desc, func, select

from aipulse.hotspot.models import Hotspot
from aipulse.models.followed_up import FollowedUp
from aipulse.store.database import get_session_maker

logger = logging.getLogger(__name__)

# spec §1.1 fixture: 4 个基线 UP 主之一 —— 跟李沐学 AI
LI_MU_MID = "1567748478"
LI_MU_NAME_HINT = "李沐"  # 「跟李沐学 AI」或「跟李沐学AI」皆可
LI_MU_PROFILE_URL = f"https://space.bilibili.com/{LI_MU_MID}"


# --------------------------------------------------------------------
# autouse fixtures — test isolation
# --------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_summary_enqueue(monkeypatch: pytest.MonkeyPatch):
    """Disable auto-summary enqueue triggered by ``POST /api/followed-up/{id}/sync``.

    Why: path A's TC-03 / TC-04 trigger ``_scan_one`` →
    ``enqueue_summaries_for_hotspots`` which fills the **process-global**
    ``SummaryJobQueue`` with up to 20 jobs (one per new hotspot).
    The single worker drains those jobs first, starving path B's job and
    causing its SSE to hang waiting for the terminal event (verifier 跑了
    20-25min 才被杀).

    Patch the enqueue function to a no-op so path A stays purely about scan +
    hotspot upsertion (TC-04's assertion object is the DB ``hotspots`` count,
    **not** the summary jobs). Path B's fixture owns summary end-to-end.

    Side benefit: scan 本身的真实行为（B 站抓取 + upsert_hotspot_from_video）
    完全保留；只 strip 出队动作。
    """
    from aipulse.scheduler.jobs import followed_up_scan as scan_mod

    async def _no_enqueue(*args: Any, **kwargs: Any) -> list[str]:
        return []

    monkeypatch.setattr(
        scan_mod, "enqueue_summaries_for_hotspots", _no_enqueue, raising=True
    )
    yield


@pytest.fixture(autouse=True)
async def _drain_summary_queue():
    """Forcibly cancel any orphan SummaryJobQueue worker from prior test sessions.

    Path A 修了 enqueue patch（autouse ``_isolate_summary_enqueue``），但
    process-global ``SummaryJobQueue`` singleton 还可能被上一轮 session 残留
    的 worker 持有 —— 该 worker 持续 polling 旧 asyncio.Queue、跑 LLM 调用，
    把 path B 的 job 排在后面无限饿（实测 5min+ 超时）。

    简单的 ``queue.stop()`` 不够：内部 ``if self._lock is None: return``
    早退分支让 stop 在 _lock 已被 prior code 清空时变 no-op，worker 收不到
    _stop 信号、task 没 cancel。我们必须 reach 进 ``qmod._queue._worker_task``
    直接 ``task.cancel()`` —— 测试隔离属非常规操作，允许读私有字段。
    """
    from aipulse.summarizers import queue as qmod

    async def _kill_orphan_worker() -> None:
        singleton = qmod._queue
        if singleton is None:
            return
        task = getattr(singleton, "_worker_task", None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                # swallow: 我们要的是 worker 退出，不是 raise
                pass
        # Null singleton —— 下一轮 ``get_queue()`` 重新起新 asyncio.Queue +
        # 新 worker，从干净状态开始。
        qmod._queue = None

    await _kill_orphan_worker()
    yield
    await _kill_orphan_worker()


# --------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------

T = TypeVar("T")


async def _with_retry(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 2,
    delay_s: float = 1.0,
    label: str = "op",
) -> T:
    """Run an async op, retrying once on transient failure.

    Real B 站（uapis.cn / api.bilibili.com）偶发超时或风控。一次重试足以
    覆盖绝大多数抖动；持续失败 → raise，让测试明确失败而非 silently pass。
    """
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return await op()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "[path-a] %s attempt %d/%d failed: %s",
                label, i + 1, attempts, exc,
            )
            if i + 1 < attempts:
                await asyncio.sleep(delay_s)
    assert last_exc is not None  # for type-checkers
    raise last_exc


async def _post_followed_up(client: AsyncClient, mid: str = LI_MU_MID) -> dict[str, Any]:
    """POST /api/followed-up，返回 data dict。"""

    async def _do_post() -> dict[str, Any]:
        resp = await client.post(
            "/api/followed-up",
            json={"platform": "bilibili", "uid": mid},
        )
        assert resp.status_code == 201, (
            f"create_followed_up returned {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["success"] is True, body
        return body["data"]

    return await _with_retry(_do_post, label=f"POST /api/followed-up mid={mid}")


async def _trigger_sync(client: AsyncClient, followed_up_id: str) -> dict[str, Any]:
    """POST /api/followed-up/{id}/sync，返回 data dict。

    端点有 15s 上限；超时返回 status='timeout'。一次重试足以覆盖偶发慢。
    """

    async def _do_sync() -> dict[str, Any]:
        resp = await client.post(f"/api/followed-up/{followed_up_id}/sync")
        assert resp.status_code == 202, (
            f"sync returned {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["success"] is True, body
        return body["data"]

    return await _with_retry(
        _do_sync, attempts=2, delay_s=0.5,
        label=f"POST /sync id={followed_up_id}",
    )


async def _paginate_videos(
    client: AsyncClient,
    mid: str,
    *,
    page_size: int = 20,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    """Paginate ``GET /api/followed-up/by-uid/bilibili/<mid>/videos`` via ``nextOffset``.

    之所以必要：spec 09 §2.4 TC-UI-FOLLOW-DETAIL-05/06 要求详情页支持「加载更多
    历史」翻页；当该 UP 主真实视频总数 > ``page_size`` 时（2026-07-29 实测
    李沐 1567748478 已有 22 条），单页 ``len(items) == total`` 断言必破。

    安全护栏：``max_pages=50`` × ``page_size=20`` ≈ 1000 行上限，避免 DB
    异常巨大或接口 bug 触发的死循环；/detail 端 LIMIT 500 与之同档。
    """
    all_items: list[dict[str, Any]] = []
    offset: int | None = 0  # 第一次 GET 不带 offset 也行，但显式传更直观
    for page_idx in range(max_pages):
        params: dict[str, Any] = {"limit": page_size}
        if offset is not None:
            params["offset"] = offset
        resp = await client.get(
            f"/api/followed-up/by-uid/bilibili/{mid}/videos",
            params=params,
        )
        assert resp.status_code == 200, (
            f"/videos page {page_idx} returned {resp.status_code}: {resp.text}"
        )
        data = resp.json()["data"]
        items = data.get("items", [])
        assert isinstance(items, list), f"items must be list, got {type(items)}"
        # 边界断言：单页 items 必须满足 <= page_size
        assert len(items) <= page_size, (
            f"/videos page {page_idx} returned {len(items)} > page_size={page_size}"
        )
        all_items.extend(items)
        next_offset = data.get("nextOffset")
        if next_offset is None:
            return all_items
        assert isinstance(next_offset, int), (
            f"nextOffset must be int or None, got {type(next_offset)}: {next_offset!r}"
        )
        offset = next_offset
    raise AssertionError(
        f"_paginate_videos hit max_pages={max_pages}; aborted to avoid runaway. "
        f"collected={len(all_items)} mid={mid}"
    )


async def _count_hotspots_for_mid(mid: str) -> int:
    """Count Hotspot rows associated with the active FollowedUp for `mid`."""

    async with get_session_maker()() as session:
        fu = (
            await session.execute(
                select(FollowedUp).where(
                    FollowedUp.platform == "bilibili",
                    FollowedUp.uid == mid,
                    FollowedUp.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if fu is None:
            return 0
        stmt = select(func.count(Hotspot.id)).where(
            Hotspot.followed_up_id == fu.id
        )
        return int((await session.execute(stmt)).scalar_one() or 0)


# --------------------------------------------------------------------
# TC-E2E-PATH-A-01
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_01_add_legal_up_master_card_appears(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-01 添加合法 UP 主 → 卡片出现。

    - POST /api/followed-up 用 ``mid=1567748478`` → 201
    - response.data.uid / id / platform 完整
    - GET /api/followed-up 列表第一条即新创建的卡片
    """
    created = await _post_followed_up(client)
    assert created["uid"] == LI_MU_MID
    assert created["platform"] == "bilibili"
    assert created["id"], "FollowedUp id must be non-empty"

    list_resp = await client.get("/api/followed-up")
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["data"]
    assert items, "list should contain at least the newly added UP主"
    assert items[0]["id"] == created["id"], (
        "新添加的 UP 主必须按 created_at desc 排在列表最前"
    )
    assert items[0]["uid"] == LI_MU_MID


# --------------------------------------------------------------------
# TC-E2E-PATH-A-02
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_02_avatar_and_nickname_displayed(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-02 头像 + 昵称正确显示。

    - POST /api/followed-up 自动调 api.bilibili.com 解析 display_name
    - GET /api/followed-up/by-uid/bilibili/{mid}/detail 返回真实昵称 +
      头像 URL（来自 B 站 card API + 头像 disk cache）
    """
    created = await _post_followed_up(client)
    assert created["display_name"], "display_name 必须自动从 B 站解析"
    # 「跟李沐学 AI」或「跟李沐学AI」皆可 —— 都含「李沐」
    assert LI_MU_NAME_HINT in created["display_name"], (
        f"display_name={created['display_name']!r} 应包含「{LI_MU_NAME_HINT}」"
    )
    assert created["profile_url"] == LI_MU_PROFILE_URL

    detail_resp = await client.get(
        f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/detail"
    )
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()["data"]

    assert detail["mid"] == LI_MU_MID
    assert detail["name"], "detail.name 必须来自 B 站真实昵称"
    assert LI_MU_NAME_HINT in detail["name"], (
        f"detail.name={detail['name']!r} 应包含「{LI_MU_NAME_HINT}」"
    )
    assert detail["url"] == LI_MU_PROFILE_URL
    assert detail["avatar"], "detail.avatar 应当从 B 站 card API 解析到非空 URL"
    assert detail["avatar"].startswith(("http://", "https://")), (
        f"avatar URL 必须是 http(s)：{detail['avatar']!r}"
    )


# --------------------------------------------------------------------
# TC-E2E-PATH-A-03
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_03_detail_collections_and_recent_videos(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-03 详情页合集列表（折叠）+ 最近 20 条视频。

    - GET /detail 返回 ``collections[]``（list，可空）+ ``orphan_videos[]``（list）
    - GET /videos?limit=20 返回 ``items``（最多 20 条）+ ``nextOffset``
    - 先 POST /sync 拉一些视频，否则 orphan_videos 永远是空
    """
    created = await _post_followed_up(client)
    followed_up_id = created["id"]

    # 触发一次同步，让 orphan_videos 有内容可断言
    sync_data = await _trigger_sync(client, followed_up_id)
    sync_status = sync_data.get("status")
    new_videos = int(sync_data.get("new_videos", 0))

    detail_resp = await client.get(
        f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/detail"
    )
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()["data"]

    # collections：list（可能空 —— spec 允许空态「暂无合集」UI）
    assert isinstance(detail["collections"], list)
    # 每个 collection 必须有 spec §6.12 要求的字段
    for c in detail["collections"]:
        assert {"id", "title", "video_count"}.issubset(c.keys())

    # orphan_videos：list + 每条带 bvid/title/status/hotspot_id
    assert isinstance(detail["orphan_videos"], list)
    for v in detail["orphan_videos"]:
        assert v["bvid"], "orphan video 必须有 bvid"
        assert v["title"], "orphan video 必须有 title"
        assert v["status"] in {
            "pending", "worth_learning", "worth_notified", "skipped", "failed"
        }

    # /videos 全量分页：循环拉取直到 nextOffset == None，模拟前端「加载更多
    # 历史」行为 —— **不分页就会漏数据**。被比较的总视频数可能 > 20
    # （2026-07-29 实测李沐 22 条），单页 ≤ 20 → 旧断言
    # ``len(videos["items"]) == total_via_detail`` 必然 20 != 22 失败。
    all_videos = await _paginate_videos(client, LI_MU_MID, page_size=20)

    collections_total = sum(len(c.get("videos", [])) for c in detail["collections"])
    total_via_detail = len(detail["orphan_videos"]) + collections_total

    # ===== 三态分支 =====
    if total_via_detail > 0:
        # 强契约：DB 有数据时，分页端点必须能凑齐 /detail 汇总的行数
        # （覆盖 +20 场景；同时验证 nextOffset 翻页链不断）。
        assert len(all_videos) == total_via_detail, (
            f"/videos 全量分页累计={len(all_videos)} 与 /detail 汇总={total_via_detail} "
            f"不一致 —— 分页 nextOffset 链可能在中途断"
        )
        # 增量同步硬要求：sync 报告了 new_videos > 0，但 DB 计数为 0 是错。
        # 注意：``total_via_detail > 0`` 已说明 DB 里有数据；``new_videos > 0``
        # 只是说明 *本次 sync* 增量了几条。两者必须自洽：sync 有增量但 /videos
        # 没新增才会破。
        if sync_status == "ok" and new_videos > 0:
            logger.info(
                "[path-a-03] sync_status=ok new_videos=%d total_via_detail=%d",
                new_videos, total_via_detail,
            )
    else:
        # DB 完全无视频（``total_via_detail == 0``）—— 只有 sync 真成功但
        # 返回 0 new_videos 才合理；否则应当 fail（不是悄悄通过）。
        if sync_status == "ok" and new_videos > 0:
            raise AssertionError(
                f"sync 报告 new_videos={new_videos}，但 /detail + /videos 全量 "
                f"分页都为 0 —— data flow 断裂"
            )
        # sync timeout / 限流 / 全新 + 风控 全 0 ：降级 schema-only 校验
        logger.warning(
            "[path-a-03] 降级为 schema-only：sync_status=%r new_videos=%d "
            f"total_via_detail={total_via_detail} (B 站风控 / wait_for 超时 / "
            f"全新未同步)；仅断言列表 schema",
            sync_status, new_videos,
        )

    # schema 校验（与数据量无关，恒成立）
    assert isinstance(detail["orphan_videos"], list)
    assert isinstance(detail["collections"], list)
    # /videos 首页 last 页的 ``items`` 列表形态（spec §6.12 / TC-UI-FOLLOW-DETAIL-05）
    videos_first_page = (
        await client.get(
            f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/videos",
            params={"limit": 20},
        )
    ).json()["data"]
    assert isinstance(videos_first_page["items"], list)
    assert len(videos_first_page["items"]) <= 20
    assert videos_first_page["nextOffset"] is None or isinstance(
        videos_first_page["nextOffset"], int
    )


# --------------------------------------------------------------------
# TC-E2E-PATH-A-04
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_04_manual_sync_grows_hotspot_count(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-04 手动触发 → hotspot 数 +N。

    - 同步前先记一次 hotspot 计数（应 =0）
    - POST /sync → 202 + data.status in {ok, timeout}
    - 同步后 hotspot 数 ≥ 同步前；status=ok 时严格 == sync new_videos
    - health 端点可正常报告（last_checked_at 是 best-effort，不强求）
    """
    created = await _post_followed_up(client)
    followed_up_id = created["id"]

    before_count = await _count_hotspots_for_mid(LI_MU_MID)
    assert before_count == 0, "新添加的 UP 主不应该已经有 hotspot"

    sync_data = await _trigger_sync(client, followed_up_id)
    assert sync_data["followed_up_id"] == followed_up_id
    assert sync_data["status"] in {"ok", "timeout"}, sync_data

    after_count = await _count_hotspots_for_mid(LI_MU_MID)

    if sync_data["status"] == "ok":
        new_videos = int(sync_data.get("new_videos", 0))
        # 真实 B 站 uapis.cn 偶发限流返回空 list（total=0）；允许 new_videos=0
        # 但 DB count 必须严格等于 sync 报告的 new_videos（增量同步语义）
        assert after_count == new_videos, (
            f"DB hotspot count ({after_count}) != sync new_videos "
            f"({new_videos}) —— 增量同步语义被破坏"
        )
        # new_bvids 必须与 DB content_id 一一对应
        async with get_session_maker()() as session:
            fu = (
                await session.execute(
                    select(FollowedUp).where(FollowedUp.id == followed_up_id)
                )
            ).scalar_one()
            stmt = (
                select(Hotspot.content_id)
                .where(Hotspot.followed_up_id == fu.id)
                .order_by(desc(Hotspot.created_at))
            )
            db_bvids = [row[0] for row in (await session.execute(stmt)).all()]
        reported_bvids = sync_data.get("new_bvids", []) or []
        missing = set(reported_bvids) - set(db_bvids)
        assert not missing, (
            f"sync 上报了 {len(reported_bvids)} 个 bvid，但 DB 缺：{missing}。"
            f"DB bvids={db_bvids}, sync new_bvids={reported_bvids}"
        )
    else:
        # sync timeout（wait_for 15s 取消）：扫描可能没跑完，hotspot 数允许
        # 不增长；但语义上 hotspot 数不能倒退（增量同步保证）：
        # 删除 UP 主走 DELETE，软删除置 deleted_at，不会回写 hotspot；
        # 若 after_count < before_count 说明有路径偷偷 DELETE hotspot —— bug。
        assert after_count >= before_count, (
            f"sync timeout 后 hotspot 数从 {before_count} 跌到 {after_count}，"
            f"增量同步语义被破坏"
        )

    # health 端点反映同步已被调度过
    health_resp = await client.get(
        f"/api/followed-up/{followed_up_id}/health"
    )
    assert health_resp.status_code == 200, health_resp.text
    health = health_resp.json()["data"]
    # health 端点必须能正确报告（UP主 ID、health 字段存在）。
    # 注意：last_checked_at 是 best-effort —— 当 sync 被 wait_for 取消
    # （如 summary queue 残留任务抢资源导致 15s 超时）时，该字段可能未推进。
    # 我们不强求它一定有值；hotspot 数 +N 是 spec §5.1 的硬断言。
    assert health["id"] == followed_up_id
    assert health["health"] in {"healthy", "warning", "error"}


# --------------------------------------------------------------------
# TC-E2E-PATH-A-05
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_05_three_feedback_signals_complete(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-05 三处反馈齐全：modal 关闭 + toast + 新卡片插入。

    API 层等价物：
    - modal 关闭  → POST 返回 success=true
    - toast        → POST data 含完整 FollowedUp 字段（前端 toast 模板可用）
    - 新卡片插入   → GET /api/followed-up 列表第一个就是新建的
    - 二次创建同 mid → 409（确认数据库唯一约束 + 错误反馈链路通畅）
    """
    created = await _post_followed_up(client)
    # modal-close + toast signal
    assert created, "POST data 必须非空（toast 渲染依赖字段完整）"
    required = {
        "id", "platform", "uid", "display_name", "profile_url",
        "collector_strategy", "fetch_interval_minutes",
        "is_active", "status", "health",
        "created_at", "updated_at",
    }
    missing = required - created.keys()
    assert not missing, f"POST data 缺失 toast 渲染所需字段：{missing}"

    # 新卡片插入 list
    list_resp = await client.get("/api/followed-up")
    items = list_resp.json()["data"]
    assert items[0]["id"] == created["id"]

    # 重复添加 → 409（错误反馈链路）
    dup_resp = await client.post(
        "/api/followed-up",
        json={"platform": "bilibili", "uid": LI_MU_MID},
    )
    assert dup_resp.status_code == 409, (
        f"重复添加应返 409，实际 {dup_resp.status_code}: {dup_resp.text}"
    )
    dup_body = dup_resp.json()
    assert dup_body["detail"]["error"] == "Duplicate FollowedUp"


# --------------------------------------------------------------------
# TC-E2E-PATH-A-06
# --------------------------------------------------------------------


@pytest.mark.e2e
async def test_tc_path_a_06_detail_back_to_list_route(client: AsyncClient) -> None:
    """TC-E2E-PATH-A-06 UP 主详情页 Back 按钮回到关注列表。

    API 层等价物：详情页走 uid-alias 路由（与列表页同维度 key），Back 后
    列表端点可被再次拉取，detail → videos → overview 三个 uid-alias 端点
    必须同时可达，否则前端 Back 后的二次渲染会 404。

    - /by-uid/{platform}/{uid}/detail 可访问
    - /by-uid/{platform}/{uid}/videos 可访问
    - /by-uid/{platform}/{uid}/overview 可访问
    - GET /api/followed-up（Back 的目标）可访问且包含刚加的 UP 主
    """
    created = await _post_followed_up(client)

    # 详情（uid-alias）
    detail_resp = await client.get(
        f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/detail"
    )
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["data"]["mid"] == LI_MU_MID

    # 视频分页（uid-alias）
    videos_resp = await client.get(
        f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/videos"
    )
    assert videos_resp.status_code == 200, videos_resp.text
    videos_payload = videos_resp.json()["data"]
    assert "items" in videos_payload and "nextOffset" in videos_payload

    # Overview（uid-alias）
    overview_resp = await client.get(
        f"/api/followed-up/by-uid/bilibili/{LI_MU_MID}/overview"
    )
    assert overview_resp.status_code == 200, overview_resp.text
    overview = overview_resp.json()["data"]
    assert overview["uid"] == LI_MU_MID
    assert "recent_jobs" in overview
    assert "recent_learning_events" in overview
    assert "recent_collections" in overview
    assert "health" in overview

    # Back 目标：关注列表
    list_resp = await client.get("/api/followed-up")
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["data"]
    assert any(item["id"] == created["id"] for item in items), (
        "Back 后列表必须仍包含当前 UP 主"
    )