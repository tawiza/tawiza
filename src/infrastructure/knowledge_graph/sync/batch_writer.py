"""Background batch writer for Neo4j sync."""
import asyncio
import contextlib
from dataclasses import dataclass

from loguru import logger

from .cypher_builder import CypherBuilder
from .queue import SyncQueue


@dataclass
class SyncConfig:
    """Sync configuration."""
    batch_size: int = 100
    flush_interval: float = 5.0
    max_retries: int = 3


class BatchWriter:
    """
    Background task for batch-writing to Neo4j.

    Flushes queue when:
    - batch_size items accumulated
    - flush_interval seconds elapsed
    """

    def __init__(
        self,
        queue: SyncQueue,
        client,  # Neo4jClient
        config: SyncConfig | None = None
    ):
        """Initialize batch writer."""
        self.queue = queue
        self.client = client
        self.config = config or SyncConfig()
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if background task is running."""
        return self._running and self._task is not None

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("BatchWriter started")

    async def stop(self) -> None:
        """Stop background task and flush remaining."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        # Final flush
        if self.queue.size > 0:
            await self.flush()
        logger.info("BatchWriter stopped")

    async def _run_loop(self) -> None:
        """Background loop."""
        while self._running:
            try:
                # Wait for batch or timeout
                await asyncio.sleep(self.config.flush_interval)

                if self.queue.size >= self.config.batch_size or self.queue.size > 0:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BatchWriter error: {e}")

    async def flush(self) -> int:
        """
        Flush current batch to Neo4j.

        Returns:
            Number of items flushed
        """
        items = await self.queue.get_batch(
            self.config.batch_size,
            timeout=0.1
        )

        if not items:
            return 0

        # Group by node type for efficient batching
        by_type = {}
        for item in items:
            key = (item.operation, item.node_type)
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(item)

        total = 0
        for (_op, node_type), type_items in by_type.items():
            try:
                query, params = CypherBuilder.build_batch(type_items)
                result = await self.client.execute_write(query, params)
                count = result[0].get("count", len(type_items)) if result else len(type_items)
                total += count
                logger.debug(f"Flushed {count} {node_type} items")
            except Exception as e:
                logger.error(f"Failed to flush {node_type}: {e}")

        return total
