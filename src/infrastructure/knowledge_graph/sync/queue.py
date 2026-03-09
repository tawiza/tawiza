"""Async queue for Neo4j sync operations."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SyncItem:
    """Item to sync to Neo4j."""
    operation: str  # merge, create, delete
    node_type: str  # Company, Establishment, etc.
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    relationship: dict[str, Any] | None = None


class SyncQueue:
    """
    Async queue for buffering Neo4j sync operations.

    Supports batch retrieval for efficient writes.
    """

    def __init__(self, max_size: int = 10000):
        """Initialize queue with max size."""
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._max_size = max_size

    @property
    def size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    async def put(self, item: SyncItem) -> bool:
        """
        Add item to queue.

        Returns:
            True if added, False if queue full
        """
        try:
            self._queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False

    async def get_batch(
        self,
        batch_size: int,
        timeout: float | None = None
    ) -> list[SyncItem]:
        """
        Get a batch of items from queue.

        Args:
            batch_size: Max items to retrieve
            timeout: Max seconds to wait for items

        Returns:
            List of SyncItems (may be less than batch_size)
        """
        items = []
        deadline = asyncio.get_event_loop().time() + (timeout or 0)

        while len(items) < batch_size:
            try:
                if timeout:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=remaining
                    )
                else:
                    item = self._queue.get_nowait()
                items.append(item)
            except (TimeoutError, asyncio.QueueEmpty):
                break

        return items

    def clear(self) -> int:
        """Clear all items. Returns count of cleared items."""
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count
