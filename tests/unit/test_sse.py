"""Unit tests for the SSE manager."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from aipulse.web.sse import SseManager


@pytest.mark.unit
async def test_broadcast_reaches_all_subscribers():
    manager = SseManager(max_queue_size=8)
    queue_a = manager.register()
    queue_b = manager.register()
    await manager.broadcast("hotspot.new", '{"id":"1"}')
    assert queue_a.get_nowait()["event"] == "hotspot.new"
    assert queue_b.get_nowait()["data"] == '{"id":"1"}'
    manager.unregister(queue_a)
    manager.unregister(queue_b)


@pytest.mark.unit
async def test_broadcast_drops_oldest_when_queue_full():
    manager = SseManager(max_queue_size=1)
    queue = manager.register()
    await manager.broadcast("e1", "a")
    await manager.broadcast("e2", "b")
    assert queue.get_nowait()["event"] == "e2"
    manager.unregister(queue)


@pytest.mark.unit
async def test_subscribe_yields_heartbeat_on_timeout():
    manager = SseManager(max_queue_size=2)

    request = type("Request", (), {"is_disconnected": lambda _: asyncio.sleep(0.2)})()
    # Temporarily shrink heartbeat interval to avoid a long test.
    original_heartbeat = (
        manager.HEARTBEAT_SECONDS if hasattr(manager, "HEARTBEAT_SECONDS") else 15.0
    )
    import aipulse.web.sse as sse_module

    sse_module.HEARTBEAT_SECONDS = 0.05
    try:
        messages = []
        async for message in manager.subscribe(request):
            messages.append(message)
            if len(messages) == 1:
                break
        assert messages == [": heartbeat\n\n"]
    finally:
        sse_module.HEARTBEAT_SECONDS = original_heartbeat


@pytest.mark.unit
async def test_subscribe_yields_broadcast_message():
    manager = SseManager(max_queue_size=2)
    request = type("Request", (), {"is_disconnected": AsyncMock(side_effect=[False, True])})()
    queue = asyncio.Queue(maxsize=2)
    queue.put_nowait({"event": "hotspot.new", "data": '{"id":"1"}'})

    with patch.object(manager, "register", return_value=queue):
        messages = []
        async for message in manager.subscribe(request):
            messages.append(message)

    assert messages == ['event: hotspot.new\ndata: {"id":"1"}\n\n']
