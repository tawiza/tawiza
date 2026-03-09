"""Tests for BatchWriter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.knowledge_graph.sync.batch_writer import BatchWriter, SyncConfig
from src.infrastructure.knowledge_graph.sync.queue import SyncItem, SyncQueue


class TestSyncConfig:
    """Test SyncConfig."""

    def test_default_config(self):
        """Default sync config."""
        config = SyncConfig()
        assert config.batch_size == 100
        assert config.flush_interval == 5.0

    def test_custom_config(self):
        """Custom sync config."""
        config = SyncConfig(batch_size=50, flush_interval=2.0)
        assert config.batch_size == 50
        assert config.flush_interval == 2.0


class TestBatchWriter:
    """Test BatchWriter."""

    def test_create_writer(self):
        """Create batch writer."""
        queue = SyncQueue()
        client = MagicMock()
        writer = BatchWriter(queue, client)
        assert writer is not None
        assert not writer.is_running

    @pytest.mark.asyncio
    async def test_flush_batch(self):
        """Flush batch to Neo4j."""
        queue = SyncQueue()
        client = MagicMock()
        client.execute_write = AsyncMock(return_value=[{"count": 2}])

        writer = BatchWriter(queue, client)

        # Add items
        await queue.put(SyncItem("merge", "Company", {"siren": "111", "name": "A"}))
        await queue.put(SyncItem("merge", "Company", {"siren": "222", "name": "B"}))

        # Flush
        count = await writer.flush()
        assert count == 2
        client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_empty_queue(self):
        """Flush empty queue returns 0."""
        queue = SyncQueue()
        client = MagicMock()
        writer = BatchWriter(queue, client)

        count = await writer.flush()
        assert count == 0

    @pytest.mark.asyncio
    async def test_flush_groups_by_type(self):
        """Flush groups items by node type."""
        queue = SyncQueue()
        client = MagicMock()
        client.execute_write = AsyncMock(return_value=[{"count": 1}])

        writer = BatchWriter(queue, client)

        # Add items of different types
        await queue.put(SyncItem("merge", "Company", {"siren": "111"}))
        await queue.put(SyncItem("merge", "Territory", {"code": "34"}))

        await writer.flush()
        # Should have 2 calls (one per type)
        assert client.execute_write.call_count == 2

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Start and stop background task."""
        queue = SyncQueue()
        client = MagicMock()
        client.execute_write = AsyncMock(return_value=[])

        config = SyncConfig(flush_interval=0.1)
        writer = BatchWriter(queue, client, config)

        await writer.start()
        assert writer.is_running

        await asyncio.sleep(0.05)
        await writer.stop()
        assert not writer.is_running

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self):
        """Stop flushes remaining items."""
        queue = SyncQueue()
        client = MagicMock()
        client.execute_write = AsyncMock(return_value=[{"count": 1}])

        config = SyncConfig(flush_interval=10.0)  # Long interval
        writer = BatchWriter(queue, client, config)

        await writer.start()
        await queue.put(SyncItem("merge", "Company", {"siren": "111"}))

        # Stop should flush
        await writer.stop()
        client.execute_write.assert_called()
