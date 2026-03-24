"""Tests for SyncQueue."""

import asyncio

import pytest

from src.infrastructure.knowledge_graph.sync.queue import SyncItem, SyncQueue


class TestSyncItem:
    """Test SyncItem dataclass."""

    def test_create_item(self):
        """Create sync item."""
        item = SyncItem(operation="merge", node_type="Company", data={"siren": "123"})
        assert item.operation == "merge"
        assert item.node_type == "Company"

    def test_item_has_timestamp(self):
        """SyncItem has auto-generated timestamp."""
        item = SyncItem("merge", "Company", {"siren": "123"})
        assert item.timestamp is not None


class TestSyncQueue:
    """Test SyncQueue."""

    def test_create_queue(self):
        """Create empty queue."""
        queue = SyncQueue(max_size=100)
        assert queue.size == 0

    @pytest.mark.asyncio
    async def test_put_item(self):
        """Put item in queue."""
        queue = SyncQueue()
        item = SyncItem("merge", "Company", {"siren": "123"})
        result = await queue.put(item)
        assert result is True
        assert queue.size == 1

    @pytest.mark.asyncio
    async def test_get_batch(self):
        """Get batch of items."""
        queue = SyncQueue()
        for i in range(5):
            await queue.put(SyncItem("merge", "Company", {"siren": str(i)}))

        batch = await queue.get_batch(3)
        assert len(batch) == 3
        assert queue.size == 2

    @pytest.mark.asyncio
    async def test_get_batch_timeout(self):
        """Get batch with timeout returns available items."""
        queue = SyncQueue()
        await queue.put(SyncItem("merge", "Company", {"siren": "1"}))

        batch = await queue.get_batch(10, timeout=0.1)
        assert len(batch) == 1

    @pytest.mark.asyncio
    async def test_queue_full(self):
        """Queue reports when full."""
        queue = SyncQueue(max_size=2)
        await queue.put(SyncItem("merge", "Company", {"siren": "1"}))
        await queue.put(SyncItem("merge", "Company", {"siren": "2"}))
        assert queue.is_full

    @pytest.mark.asyncio
    async def test_put_fails_when_full(self):
        """Put returns False when queue is full."""
        queue = SyncQueue(max_size=1)
        await queue.put(SyncItem("merge", "Company", {"siren": "1"}))
        result = await queue.put(SyncItem("merge", "Company", {"siren": "2"}))
        assert result is False

    def test_clear(self):
        """Clear empties queue."""
        queue = SyncQueue()
        # Need to use sync put for this test
        queue._queue.put_nowait(SyncItem("merge", "Company", {"siren": "1"}))
        queue._queue.put_nowait(SyncItem("merge", "Company", {"siren": "2"}))

        count = queue.clear()
        assert count == 2
        assert queue.size == 0
