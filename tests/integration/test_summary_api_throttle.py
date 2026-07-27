"""L3: 总结队列上限 20 + 超出返回 429。

策略：patch ``run_summary_pipeline`` 慢跑（2s/job），保证 worker drain 速度
远小于 25 个并发 POST 涌入速度。期望 25 并发 → 20×202 + 4..5×429。
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

import aipulse.summarizers.queue as queue_mod
from aipulse.summarizers.queue import (
    QUEUE_MAX_SIZE,
    drop_queue_sync,
)


def _bearer() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def slow_pipeline(monkeypatch):
    """patch run_summary_pipeline 慢跑（2s/job），确保并发期间 worker 几乎不 drain。

    25 个并发 POST 总耗时 < 200ms（网络 + asyncio gather），远小于 2s sleep，
    所以 worker 在 burst 期间只来得及 drain 0 个（或偶尔 1 个最坏情况）。
    """
    drop_queue_sync()

    async def slow(video_id, title, up_name, extra_context=""):
        await asyncio.sleep(2.0)
        return {
            "status": "completed",
            "note_path": None,
            "event_id": None,
            "reminder_id": None,
            "error": None,
            "intermediate_steps": [],
        }

    patcher = patch.object(queue_mod, "run_summary_pipeline", new=slow)
    patcher.start()
    try:
        yield slow
    finally:
        patcher.stop()
        drop_queue_sync()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_returns_429_when_queue_full(
    client, slow_pipeline
) -> None:
    """L3 主断言：并发 25 POST → 20×202 + 4..5×429（worker 慢到 burst 期间 ≤1 drain）。"""
    N = 25
    bvids = [f"BVthrottle{i:03d}" for i in range(N)]
    responses = await asyncio.gather(
        *(client.post(f"/api/summary/{bid}", headers=_bearer()) for bid in bvids),
        return_exceptions=False,
    )

    statuses = [r.status_code for r in responses]
    n_202 = sum(1 for s in statuses if s == 202)
    n_429 = sum(1 for s in statuses if s == 429)

    # worker 2s/job，burst < 200ms：worker 在 burst 期间最多 drain 0..1 个
    # 严苛断言：1 + 20 = 21 个成功；4..5 个 429。允许 [4, 5] 区间防 worker
    # 刚好在 gather 收尾前完成一个的 race。
    assert n_429 in (4, 5), f"expected 4..5×429, got {n_429}; statuses={statuses}"
    assert n_202 + n_429 == N, f"202+429 must equal {N}, got {n_202}+{n_429}"

    # 429 body 含 QUEUE_FULL 错误码 + max_size
    body_429 = next(r.json() for r in responses if r.status_code == 429)
    detail = body_429.get("detail") or {}
    assert detail.get("error") == "QUEUE_FULL"
    assert detail.get("max_size") == QUEUE_MAX_SIZE


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_normal_traffic_all_202(client) -> None:
    """队列不满时所有请求都返 202（回归保护）。"""
    async def instant(video_id, title, up_name, extra_context=""):
        return {
            "status": "completed",
            "note_path": None,
            "event_id": None,
            "reminder_id": None,
            "error": None,
            "intermediate_steps": [],
        }

    patcher = patch.object(queue_mod, "run_summary_pipeline", new=instant)
    patcher.start()
    try:
        responses = []
        for i in range(5):
            r = await client.post(f"/api/summary/BVok{i}", headers=_bearer())
            responses.append(r)
        await asyncio.sleep(0.3)
        statuses = [r.status_code for r in responses]
        assert all(s == 202 for s in statuses), f"got {statuses}"
    finally:
        patcher.stop()
        drop_queue_sync()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_max_size_constant_is_20() -> None:
    """队列上限常量本身 = 20。"""
    assert QUEUE_MAX_SIZE == 20


@pytest.mark.unit
@pytest.mark.asyncio
async def test_queue_unit_raises_queue_full_on_overflow(slow_pipeline) -> None:
    """单测：直接灌满 Queue(maxsize=20) 后再 put_nowait 必抛 QueueFullError。"""
    from aipulse.summarizers.queue import JobSubmission, get_queue

    queue = get_queue()
    # 启动 worker + slow_pipeline
    await queue.start()
    assert queue._queue is not None
    assert queue._queue.maxsize == QUEUE_MAX_SIZE

    # 灌满
    for i in range(QUEUE_MAX_SIZE):
        queue._queue.put_nowait(
            JobSubmission(job_id=f"u-{i}", video_id=f"v-{i}")
        )

    # 再 put_nowait → asyncio.QueueFull
    with pytest.raises(asyncio.QueueFull):
        queue._queue.put_nowait(JobSubmission(job_id="overflow", video_id="overflow"))