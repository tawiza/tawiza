"""Hybrid cache combining in-memory LRU and SQLite persistence."""

from typing import Any

from loguru import logger

from src.infrastructure.datasources.cache.base import CacheConfig, CacheStats
from src.infrastructure.datasources.cache.memory import MemCache
from src.infrastructure.datasources.cache.sqlite import SQLiteCache


class HybridCache:
    """Two-tier cache: fast RAM (L1) + persistent SQLite (L2).

    Architecture:
    - L1 (MemCache): Fast, limited size, LRU eviction
    - L2 (SQLiteCache): Slower, unlimited, persistent

    Read Strategy:
    1. Check L1 (memory) first
    2. On L1 miss, check L2 (SQLite)
    3. On L2 hit, promote to L1
    4. On L2 miss, return None

    Write Strategy:
    1. Write to both L1 and L2
    2. L1 may evict (LRU), L2 persists

    Benefits:
    - Hot data served from RAM (fast)
    - Cold data persists across restarts
    - Automatic promotion of frequently accessed data

    Usage:
        cache = HybridCache(config)
        await cache.initialize()
        await cache.set("key", {"data": "value"}, ttl=3600)
        result = await cache.get("key")
    """

    def __init__(self, config: CacheConfig | None = None):
        self._config = config or CacheConfig()
        self._l1 = MemCache(self._config)
        self._l2 = SQLiteCache(self._config)
        self._promotions = 0  # L2 -> L1 promotions

    async def initialize(self) -> None:
        """Initialize SQLite cache (memory needs no init)."""
        await self._l2.initialize()
        logger.info("Hybrid cache initialized (L1: memory, L2: SQLite)")

    async def close(self) -> None:
        """Close SQLite connection."""
        await self._l2.close()

    async def get(self, key: str) -> Any | None:
        """Get value from cache (L1 then L2).

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        # Try L1 (memory) first
        value = await self._l1.get(key)
        if value is not None:
            return value

        # Try L2 (SQLite)
        value = await self._l2.get(key)
        if value is not None:
            # Promote to L1 for faster future access
            await self._l1.set(key, value)
            self._promotions += 1
            logger.debug(f"Cache L2->L1 promotion: {key}")
            return value

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in both caches.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        # Write to both levels
        await self._l1.set(key, value, ttl)
        await self._l2.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        """Delete from both caches.

        Args:
            key: Cache key to delete
        """
        await self._l1.delete(key)
        await self._l2.delete(key)

    async def clear(self, pattern: str | None = None) -> int:
        """Clear entries from both caches.

        Args:
            pattern: Optional pattern to match

        Returns:
            Total entries cleared
        """
        l1_count = await self._l1.clear(pattern)
        l2_count = await self._l2.clear(pattern)
        return l1_count + l2_count

    async def stats(self) -> CacheStats:
        """Get combined statistics.

        Returns:
            Combined cache statistics
        """
        l1_stats = await self._l1.stats()
        l2_stats = await self._l2.stats()

        return CacheStats(
            hits=l1_stats.hits + l2_stats.hits,
            misses=l2_stats.misses,  # Only L2 misses are true misses
            size=l1_stats.size + l2_stats.size,
            memory_items=l1_stats.memory_items,
            sqlite_items=l2_stats.sqlite_items,
        )

    async def cleanup_expired(self) -> int:
        """Cleanup expired entries from both caches.

        Returns:
            Total entries removed
        """
        l1_count = await self._l1.cleanup_expired()
        l2_count = await self._l2.cleanup_expired()
        return l1_count + l2_count

    async def clear_source(self, source: str) -> int:
        """Clear all entries for a specific source.

        Args:
            source: Source name (e.g., "bodacc")

        Returns:
            Number of entries cleared
        """
        pattern = f"{source}:*"
        return await self.clear(pattern)

    @property
    def promotions(self) -> int:
        """Number of L2->L1 promotions (indicates L1 effectiveness)."""
        return self._promotions

    async def warm_from_sqlite(self, source: str | None = None, limit: int = 100) -> int:
        """Pre-load frequently accessed entries into L1.

        Args:
            source: Optional source to warm (e.g., "bodacc")
            limit: Max entries to load

        Returns:
            Number of entries loaded
        """
        # This would require a query to get recent/frequent entries
        # For now, this is a placeholder for future optimization
        logger.info(f"Cache warming not yet implemented (source={source}, limit={limit})")
        return 0
