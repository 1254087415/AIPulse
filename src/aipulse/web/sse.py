"""Server-Sent Events manager with bounded subscriber queues."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from fastapi import Request

HEARTBEAT_SECONDS = 15.0


class SseManager:
    """Manages broadcasting events to connected SSE clients."""

    def __init__(self, max_queue_size: int = 64):
        self._max_queue_size = max_queue_size
        self._queues: set[asyncio.Queue] = set()

    def register(self) -> asyncio.Queue:
        """Register a new subscriber queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._queues.add(queue)
        return queue

    def unregister(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._queues.discard(queue)

    async def subscribe(self, request: Request) -> AsyncGenerator[str, None]:
        """Yield SSE messages for a single client until it disconnects."""
        queue = self.register()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"event: {message['event']}\ndata: {message['data']}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self.unregister(queue)

    async def broadcast(self, event: str, data: str) -> None:
        """Broadcast an event payload to all connected clients."""
        for queue in list(self._queues):
            if queue.full():
                queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait({"event": event, "data": data})


sse_manager = SseManager()
