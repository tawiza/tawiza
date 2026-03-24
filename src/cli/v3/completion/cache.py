"""Completion cache with TTL support."""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """A cached completion entry."""

    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)


class CompletionCache:
    """Thread-safe completion cache with TTL."""

    # Default TTLs per category
    DEFAULT_TTLS = {
        "models": 60,  # 1 minute
        "tasks": 5,  # 5 seconds
        "services": 30,  # 30 seconds
        "history": 300,  # 5 minutes
    }

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        """Get a cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        entry = self._cache.get(key)
        if entry is None:
            return None

        if time.time() > entry.expires_at:
            del self._cache[key]
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a cached value.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default for key category if not specified)
        """
        if ttl is None:
            # Try to get TTL from key category
            category = key.split(":")[0] if ":" in key else key
            ttl = self.DEFAULT_TTLS.get(category, 60)

        self._cache[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl,
        )

    def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            pattern: Key pattern to match (None = invalidate all)

        Returns:
            Number of entries invalidated
        """
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        to_delete = [k for k in self._cache if pattern in k]
        for key in to_delete:
            del self._cache[key]
        return len(to_delete)

    def cleanup(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        now = time.time()
        expired = [k for k, v in self._cache.items() if now > v.expires_at]
        for key in expired:
            del self._cache[key]
        return len(expired)

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        now = time.time()
        valid = sum(1 for v in self._cache.values() if now <= v.expires_at)
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid,
            "expired_entries": len(self._cache) - valid,
        }


# Global cache instance
_global_cache = CompletionCache()


def get_cache() -> CompletionCache:
    """Get the global cache instance."""
    return _global_cache
