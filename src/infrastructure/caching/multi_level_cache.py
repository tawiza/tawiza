"""
Multi-Level Cache - Cascading cache hierarchy

Architecture:
    L1 (LRU, fast, small)  →  L2 (LFU, medium)  →  L3 (Redis, large)
    ↓ hit                     ↓ hit               ↓ hit
    Return                    Promote to L1        Promote to L1+L2
                              ↓ miss                ↓ miss
                              Check L2             Check L3
                                                    ↓ miss
                                                    Fetch from source

Algorithm:
    Read:
    1. Check L1 (fastest) → hit: return
    2. Check L2 → hit: promote to L1, return
    3. Check L3 → hit: promote to L1+L2, return
    4. Miss all levels → fetch from source, populate all levels

    Write:
    1. Write to all levels (write-through)
    OR
    2. Write to L1 only (write-back, lazy propagation)

Benefits:
    - Hot data in L1 (ultra-fast access)
    - Warm data in L2 (frequent access)
    - Cold data in L3 (distributed, persistent)
    - Automatic promotion of accessed items
"""

from typing import TypeVar

from loguru import logger

from .lfu_cache import LFUCache
from .lru_cache import LRUCache

K = TypeVar("K")
V = TypeVar("V")

# Try to import Redis cache
try:
    from .redis_cache import REDIS_AVAILABLE, RedisCache
except ImportError:
    REDIS_AVAILABLE = False
    RedisCache = None


class MultiLevelCache[K, V]:
    """
    Multi-level cascading cache

    Features:
    - 3-level hierarchy: L1 (LRU) → L2 (LFU) → L3 (optional Redis)
    - Automatic promotion of frequently accessed items
    - Configurable eviction policies per level
    - Hit rate statistics per level
    - Async support for L3 Redis operations

    Examples:
        >>> cache = MultiLevelCache(
        ...     l1_capacity=100,
        ...     l2_capacity=500,
        ...     l1_ttl=300,
        ...     l2_ttl=900
        ... )
        >>> cache.get("key")  # Checks L1 → L2 → L3
        >>> cache.put("key", "value")  # Writes to all levels

        # With Redis L3:
        >>> cache = MultiLevelCache(enable_l3=True, redis_url="redis://localhost:6379")
        >>> await cache.connect_l3()
        >>> value = await cache.get_async("key")
    """

    def __init__(
        self,
        l1_capacity: int = 100,
        l2_capacity: int = 500,
        l1_ttl: float | None = 300,  # 5 minutes
        l2_ttl: float | None = 900,  # 15 minutes
        l3_ttl: int | None = 3600,  # 1 hour
        write_through: bool = True,
        enable_l3: bool = False,
        redis_url: str = "redis://localhost:6379/0",
        redis_key_prefix: str = "tawiza:cache:",
    ):
        """
        Initialize multi-level cache

        Args:
            l1_capacity: L1 cache capacity (LRU, fastest)
            l2_capacity: L2 cache capacity (LFU, medium)
            l1_ttl: L1 TTL in seconds
            l2_ttl: L2 TTL in seconds
            l3_ttl: L3 (Redis) TTL in seconds
            write_through: If True, write to all levels; if False, only L1
            enable_l3: Enable Redis L3 cache (requires Redis connection)
            redis_url: Redis connection URL
            redis_key_prefix: Prefix for Redis keys
        """
        # L1: LRU cache (hot data, ultra-fast)
        self.l1 = LRUCache[K, V](capacity=l1_capacity, ttl_seconds=l1_ttl)

        # L2: LFU cache (warm data, frequent access)
        self.l2 = LFUCache[K, V](capacity=l2_capacity)

        # L3: Redis cache (cold data, distributed) - optional
        self.l3: RedisCache | None = None
        self.enable_l3 = enable_l3
        self.l3_ttl = l3_ttl
        self.redis_url = redis_url
        self.redis_key_prefix = redis_key_prefix

        if enable_l3:
            if REDIS_AVAILABLE:
                self.l3 = RedisCache(
                    url=redis_url,
                    default_ttl=l3_ttl,
                    key_prefix=redis_key_prefix,
                )
                logger.info(f"L3 Redis cache configured: {redis_url}")
            else:
                logger.warning(
                    "L3 Redis cache requested but redis-py not installed. "
                    "Install with: pip install redis"
                )

        self.write_through = write_through

        # Statistics
        self.l1_hits = 0
        self.l2_hits = 0
        self.l3_hits = 0
        self.total_misses = 0

    async def connect_l3(self) -> bool:
        """
        Connect to Redis L3 cache

        Returns:
            True if connected successfully, False otherwise
        """
        if self.l3 is None:
            return False

        try:
            await self.l3.connect()
            logger.info("L3 Redis cache connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect L3 Redis cache: {e}")
            return False

    async def close_l3(self) -> None:
        """Close Redis L3 connection"""
        if self.l3 is not None:
            await self.l3.close()

    def get(self, key: K) -> V | None:
        """
        Get value from cache with cascading lookups (sync, L1/L2 only)

        Time complexity: O(1) for L1/L2

        For L3 (Redis) support, use get_async() instead.

        Args:
            key: Cache key

        Returns:
            Cached value if found in L1 or L2, None otherwise
        """
        # Check L1 (fastest)
        value = self.l1.get(key)
        if value is not None:
            self.l1_hits += 1
            return value

        # Check L2 (medium speed)
        value = self.l2.get(key)
        if value is not None:
            self.l2_hits += 1
            # Promote to L1 (data accessed from L2 is hot)
            self.l1.put(key, value)
            return value

        # Miss L1/L2 (L3 requires async)
        self.total_misses += 1
        return None

    async def get_async(self, key: K) -> V | None:
        """
        Get value from cache with cascading lookups (async, includes L3)

        Time complexity: O(1) for L1/L2, O(1) amortized for L3

        Algorithm:
        1. Check L1 → hit: return immediately
        2. Check L2 → hit: promote to L1, return
        3. Check L3 → hit: promote to L1+L2, return
        4. Miss all levels: return None

        Args:
            key: Cache key

        Returns:
            Cached value if found in any level, None otherwise
        """
        # Check L1 (fastest)
        value = self.l1.get(key)
        if value is not None:
            self.l1_hits += 1
            return value

        # Check L2 (medium speed)
        value = self.l2.get(key)
        if value is not None:
            self.l2_hits += 1
            # Promote to L1 (data accessed from L2 is hot)
            self.l1.put(key, value)
            return value

        # Check L3 (Redis, if enabled and connected)
        if self.l3 is not None and self.l3.is_connected:
            value = await self.l3.get(key)
            if value is not None:
                self.l3_hits += 1
                # Promote to L1+L2 (data accessed from L3 is warming up)
                self.l1.put(key, value)
                self.l2.put(key, value)
                return value

        # Miss all levels
        self.total_misses += 1
        return None

    def put(self, key: K, value: V) -> None:
        """
        Put value in cache (sync, L1/L2 only)

        For L3 (Redis) support, use put_async() instead.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Always write to L1
        self.l1.put(key, value)

        if self.write_through:
            # Write to L2
            self.l2.put(key, value)

    async def put_async(self, key: K, value: V, l3_ttl: int | None = None) -> None:
        """
        Put value in cache (async, includes L3)

        Time complexity: O(1) amortized

        Behavior:
        - Write-through mode: Write to all levels
        - Write-back mode: Write to L1 only (lazy propagation)

        Args:
            key: Cache key
            value: Value to cache
            l3_ttl: Optional TTL for L3 (overrides default)
        """
        # Always write to L1
        self.l1.put(key, value)

        if self.write_through:
            # Write to L2
            self.l2.put(key, value)

            # Write to L3 (Redis, if enabled and connected)
            if self.l3 is not None and self.l3.is_connected:
                await self.l3.set(key, value, ttl=l3_ttl)

    def delete(self, key: K) -> bool:
        """
        Delete key from L1/L2 cache levels (sync)

        For L3 deletion, use delete_async() instead.

        Args:
            key: Cache key

        Returns:
            True if key was present in any level
        """
        deleted_l1 = self.l1.delete(key)
        deleted_l2 = self.l2.delete(key)

        return deleted_l1 or deleted_l2

    async def delete_async(self, key: K) -> bool:
        """
        Delete key from all cache levels (async, includes L3)

        Args:
            key: Cache key

        Returns:
            True if key was present in any level
        """
        deleted_l1 = self.l1.delete(key)
        deleted_l2 = self.l2.delete(key)
        deleted_l3 = False

        if self.l3 is not None and self.l3.is_connected:
            deleted_l3 = await self.l3.delete(key)

        return deleted_l1 or deleted_l2 or deleted_l3

    def clear(self) -> None:
        """Clear L1/L2 cache levels (sync)"""
        self.l1.clear()
        self.l2.clear()

    async def clear_async(self) -> None:
        """Clear all cache levels (async, includes L3)"""
        self.l1.clear()
        self.l2.clear()

        if self.l3 is not None and self.l3.is_connected:
            await self.l3.clear()

    async def health_check(self) -> dict:
        """
        Perform health check on all cache levels

        Returns:
            Dictionary with health status per level
        """
        health = {
            "l1": True,  # In-memory, always healthy
            "l2": True,  # In-memory, always healthy
            "l3": None,  # None if not enabled
        }

        if self.l3 is not None:
            health["l3"] = await self.l3.health_check()

        return health

    def get_overall_hit_rate(self) -> float:
        """
        Calculate overall cache hit rate

        Returns:
            Hit rate as percentage (0-100)
        """
        total_hits = self.l1_hits + self.l2_hits + self.l3_hits
        total_requests = total_hits + self.total_misses

        if total_requests == 0:
            return 0.0

        return (total_hits / total_requests) * 100

    def get_stats(self) -> dict:
        """
        Get comprehensive cache statistics

        Returns:
            Dictionary with multi-level cache metrics
        """
        total_hits = self.l1_hits + self.l2_hits + self.l3_hits
        total_requests = total_hits + self.total_misses

        stats = {
            "overall": {
                "total_requests": total_requests,
                "total_hits": total_hits,
                "total_misses": self.total_misses,
                "hit_rate": self.get_overall_hit_rate(),
            },
            "l1": {
                "hits": self.l1_hits,
                "hit_percentage": (
                    (self.l1_hits / total_requests * 100)
                    if total_requests > 0
                    else 0.0
                ),
                **self.l1.get_stats(),
            },
            "l2": {
                "hits": self.l2_hits,
                "hit_percentage": (
                    (self.l2_hits / total_requests * 100)
                    if total_requests > 0
                    else 0.0
                ),
                **self.l2.get_stats(),
            },
            "config": {
                "write_through": self.write_through,
                "l3_enabled": self.enable_l3,
                "l3_ttl": self.l3_ttl,
            },
        }

        # Add L3 stats if enabled
        if self.l3 is not None:
            stats["l3"] = {
                "hits": self.l3_hits,
                "hit_percentage": (
                    (self.l3_hits / total_requests * 100)
                    if total_requests > 0
                    else 0.0
                ),
                **self.l3.get_stats(),
            }

        return stats

    async def __aenter__(self) -> "MultiLevelCache":
        """Async context manager entry"""
        if self.l3 is not None:
            await self.connect_l3()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.close_l3()

    def __repr__(self) -> str:
        """String representation"""
        l3_info = ""
        if self.l3 is not None:
            l3_status = "connected" if self.l3.is_connected else "disconnected"
            l3_info = f", L3={l3_status}"

        return (
            f"MultiLevelCache("
            f"L1={len(self.l1)}/{self.l1.capacity}, "
            f"L2={len(self.l2)}/{self.l2.capacity}{l3_info}, "
            f"hit_rate={self.get_overall_hit_rate():.1f}%)"
        )


# Factory function for creating configured cache
def create_multi_level_cache(
    l1_capacity: int = 100,
    l2_capacity: int = 500,
    enable_redis: bool = False,
    redis_url: str = "redis://localhost:6379/0",
) -> MultiLevelCache:
    """
    Factory function to create a configured multi-level cache

    Args:
        l1_capacity: L1 cache capacity
        l2_capacity: L2 cache capacity
        enable_redis: Enable Redis L3 cache
        redis_url: Redis connection URL

    Returns:
        Configured MultiLevelCache instance

    Example:
        >>> cache = create_multi_level_cache(
        ...     l1_capacity=200,
        ...     enable_redis=True,
        ...     redis_url="redis://localhost:6379/1"
        ... )
    """
    return MultiLevelCache(
        l1_capacity=l1_capacity,
        l2_capacity=l2_capacity,
        enable_l3=enable_redis,
        redis_url=redis_url,
    )
