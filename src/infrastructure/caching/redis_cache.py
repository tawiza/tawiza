"""
Redis Cache Adapter - L3 distributed caching layer

This module provides a Redis-based cache implementation for use as L3
in the multi-level cache hierarchy. It supports:
- Async operations with redis-py
- JSON serialization for complex values
- TTL (time-to-live) support
- Connection pooling
- Health checks and metrics

Usage:
    cache = RedisCache(url="redis://localhost:6379/0")
    await cache.connect()
    await cache.set("key", {"data": "value"}, ttl=300)
    value = await cache.get("key")
"""

import json
import os
from typing import TypeVar

from loguru import logger

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

K = TypeVar("K")
V = TypeVar("V")

# Try to import redis, gracefully handle if not installed
try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py not installed. Install with: pip install redis")


class RedisCache[K, V]:
    """
    Redis-based distributed cache (L3)

    Features:
    - Async operations for non-blocking I/O
    - JSON serialization for complex values
    - Configurable TTL per key
    - Connection pooling for performance
    - Automatic reconnection on failure
    - Hit/miss statistics

    Examples:
        >>> cache = RedisCache(url="redis://localhost:6379/0", default_ttl=900)
        >>> await cache.connect()
        >>> await cache.set("user:123", {"name": "Alice"})
        >>> user = await cache.get("user:123")
        >>> await cache.close()
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        default_ttl: int | None = 900,  # 15 minutes
        max_connections: int = 50,
        key_prefix: str = "tawiza:",
        socket_timeout: float = 5.0,
    ):
        """
        Initialize Redis cache

        Args:
            url: Redis connection URL
            default_ttl: Default TTL in seconds (None = no expiration)
            max_connections: Maximum pool connections
            key_prefix: Prefix for all keys (namespace isolation)
            socket_timeout: Socket timeout in seconds
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis-py is not installed. Install with: pip install redis")

        self.url = url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.key_prefix = key_prefix
        self.socket_timeout = socket_timeout

        self._pool: ConnectionPool | None = None
        self._client: redis.Redis | None = None
        self._connected = False

        # Statistics
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.sets = 0
        self.deletes = 0

    def _make_key(self, key: K) -> str:
        """Create namespaced key"""
        return f"{self.key_prefix}{key}"

    def _serialize(self, value: V) -> str:
        """Serialize value to JSON string"""
        return json.dumps(value, default=str)

    def _deserialize(self, data: str) -> V:
        """Deserialize JSON string to value"""
        return json.loads(data)

    async def connect(self) -> None:
        """
        Establish connection to Redis

        Creates connection pool and verifies connectivity.
        """
        try:
            self._pool = ConnectionPool.from_url(
                self.url,
                max_connections=self.max_connections,
                socket_timeout=self.socket_timeout,
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Verify connection
            await self._client.ping()
            self._connected = True

            logger.info(f"Redis cache connected: {self.url}")

        except Exception as e:
            self._connected = False
            self.errors += 1
            logger.error(f"Redis connection failed: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._connected = False
        logger.info("Redis cache connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis"""
        return self._connected

    async def get(self, key: K) -> V | None:
        """
        Get value from Redis

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if not self._connected or not self._client:
            self.misses += 1
            return None

        try:
            redis_key = self._make_key(key)
            data = await self._client.get(redis_key)

            if data is None:
                self.misses += 1
                return None

            self.hits += 1
            return self._deserialize(data)

        except Exception as e:
            self.errors += 1
            logger.warning(f"Redis get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: K,
        value: V,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value in Redis

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None uses default_ttl)

        Returns:
            True if successful, False otherwise
        """
        if not self._connected or not self._client:
            return False

        try:
            redis_key = self._make_key(key)
            serialized = self._serialize(value)
            expire = ttl if ttl is not None else self.default_ttl

            if expire:
                await self._client.setex(redis_key, expire, serialized)
            else:
                await self._client.set(redis_key, serialized)

            self.sets += 1
            return True

        except Exception as e:
            self.errors += 1
            logger.warning(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, key: K) -> bool:
        """
        Delete key from Redis

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        if not self._connected or not self._client:
            return False

        try:
            redis_key = self._make_key(key)
            result = await self._client.delete(redis_key)
            self.deletes += 1
            return result > 0

        except Exception as e:
            self.errors += 1
            logger.warning(f"Redis delete error for key {key}: {e}")
            return False

    async def exists(self, key: K) -> bool:
        """Check if key exists in Redis"""
        if not self._connected or not self._client:
            return False

        try:
            redis_key = self._make_key(key)
            return await self._client.exists(redis_key) > 0

        except Exception:
            self.errors += 1
            return False

    async def clear(self, pattern: str = "*") -> int:
        """
        Clear keys matching pattern

        Args:
            pattern: Key pattern to match (default: all keys with prefix)

        Returns:
            Number of keys deleted
        """
        if not self._connected or not self._client:
            return 0

        try:
            full_pattern = f"{self.key_prefix}{pattern}"
            keys = await self._client.keys(full_pattern)

            if not keys:
                return 0

            deleted = await self._client.delete(*keys)
            logger.info(f"Redis cache cleared {deleted} keys matching '{pattern}'")
            return deleted

        except Exception as e:
            self.errors += 1
            logger.error(f"Redis clear error: {e}")
            return 0

    async def health_check(self) -> bool:
        """
        Perform health check

        Returns:
            True if Redis is healthy, False otherwise
        """
        if not self._connected or not self._client:
            return False

        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def get_info(self) -> dict:
        """Get Redis server info"""
        if not self._connected or not self._client:
            return {}

        try:
            info = await self._client.info()
            return {
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": info.get("db0", {}).get("keys", 0),
            }
        except Exception:
            return {}

    def get_hit_rate(self) -> float:
        """
        Calculate cache hit rate

        Returns:
            Hit rate as percentage (0-100)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def get_stats(self) -> dict:
        """
        Get comprehensive cache statistics

        Returns:
            Dictionary with cache metrics
        """
        total_ops = self.hits + self.misses
        return {
            "connected": self._connected,
            "url": self.url,
            "key_prefix": self.key_prefix,
            "default_ttl": self.default_ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.get_hit_rate(),
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "total_operations": total_ops + self.sets + self.deletes,
        }

    async def __aenter__(self) -> "RedisCache":
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        await self.close()

    def __repr__(self) -> str:
        """String representation"""
        status = "connected" if self._connected else "disconnected"
        return f"RedisCache(url={self.url}, status={status}, hit_rate={self.get_hit_rate():.1f}%)"


# Singleton instance for global access
_redis_cache: RedisCache | None = None


async def get_redis_cache(
    url: str | None = None,
    **kwargs,
) -> RedisCache:
    """
    Get or create global Redis cache instance

    Args:
        url: Redis connection URL (defaults to REDIS_URL env var)
        **kwargs: Additional RedisCache arguments

    Returns:
        RedisCache instance
    """
    global _redis_cache

    if _redis_cache is None or not _redis_cache.is_connected:
        effective_url = url or _REDIS_URL
        _redis_cache = RedisCache(url=effective_url, **kwargs)
        await _redis_cache.connect()

    return _redis_cache


async def close_redis_cache() -> None:
    """Close global Redis cache instance"""
    global _redis_cache

    if _redis_cache is not None:
        await _redis_cache.close()
        _redis_cache = None
