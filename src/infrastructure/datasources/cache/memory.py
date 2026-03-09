"""In-memory LRU cache implementation."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.infrastructure.datasources.cache.base import (
    CacheConfig,
    CacheStats,
    deserialize_value,
    serialize_value,
)


@dataclass
class CacheEntry:
    """A single cache entry with expiration."""

    value: str  # JSON-serialized
    expires_at: datetime
    created_at: datetime

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.utcnow() > self.expires_at


class MemCache:
    """In-memory LRU cache with TTL support.

    Features:
    - LRU eviction when max size reached
    - Per-entry TTL expiration
    - Thread-safe through OrderedDict operations
    - Zero external dependencies

    Usage:
        cache = MemCache(max_items=1000)
        await cache.set("key", {"data": "value"}, ttl=3600)
        result = await cache.get("key")
    """

    def __init__(self, config: CacheConfig | None = None):
        self._config = config or CacheConfig()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache expired: {key}")
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1

        return deserialize_value(entry.value)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        # Determine TTL
        if ttl is None:
            # Extract source from key (format: "source:method:params")
            source = key.split(":")[0] if ":" in key else "default"
            ttl = self._config.get_ttl(source)

        now = datetime.utcnow()
        entry = CacheEntry(
            value=serialize_value(value),
            expires_at=now + timedelta(seconds=ttl),
            created_at=now,
        )

        # If key exists, remove it first (will be re-added at end)
        if key in self._cache:
            del self._cache[key]

        # Check if we need to evict
        while len(self._cache) >= self._config.max_memory_items:
            # Remove oldest (first) item
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache LRU eviction: {oldest_key}")

        self._cache[key] = entry
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    async def delete(self, key: str) -> None:
        """Delete a specific key from cache.

        Args:
            key: Cache key to delete
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted: {key}")

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Optional pattern to match (e.g., "bodacc:*")

        Returns:
            Number of entries cleared
        """
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries")
            return count

        # Pattern matching (simple prefix with *)
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        else:
            keys_to_delete = [k for k in self._cache if k == pattern]

        for key in keys_to_delete:
            del self._cache[key]

        logger.info(f"Cache cleared pattern '{pattern}': {len(keys_to_delete)} entries")
        return len(keys_to_delete)

    async def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            Current cache statistics
        """
        # Clean expired entries first
        now = datetime.utcnow()
        expired_keys = [k for k, v in self._cache.items() if v.expires_at < now]
        for key in expired_keys:
            del self._cache[key]

        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            size=len(self._cache),
            memory_items=len(self._cache),
            sqlite_items=0,
        )

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        now = datetime.utcnow()
        expired_keys = [k for k, v in self._cache.items() if v.expires_at < now]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)
