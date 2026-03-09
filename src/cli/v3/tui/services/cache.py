"""Cache Service for TUI - Reduces redundant computations and API calls.

This module provides caching functionality to improve TUI performance by:
- Caching expensive metric computations
- Debouncing rapid updates
- Throttling refresh rates
- Managing memory efficiently
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

T = TypeVar('T')


@dataclass
class CacheEntry[T]:
    """A cached value with metadata."""
    value: T
    created_at: datetime
    expires_at: datetime
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now() > self.expires_at

    def touch(self) -> None:
        """Update hit count."""
        self.hits += 1


class LRUCache[T]:
    """Least Recently Used cache with size limit and TTL."""

    def __init__(self, max_size: int = 100, default_ttl: float = 60.0):
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds
        """
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.touch()
        self._hits += 1

        return entry.value

    def set(self, key: str, value: T, ttl: float | None = None) -> None:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        ttl = ttl if ttl is not None else self._default_ttl
        now = datetime.now()

        entry = CacheEntry(
            value=value,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl)
        )

        # Remove old entry if exists
        if key in self._cache:
            del self._cache[key]

        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl": self._default_ttl,
        }


class Debouncer:
    """Debounce rapid function calls."""

    def __init__(self, delay: float = 0.1):
        """Initialize debouncer.

        Args:
            delay: Minimum delay between calls in seconds
        """
        self._delay = delay
        self._pending: dict[str, asyncio.Task] = {}

    async def debounce(self, key: str, func: Callable, *args, **kwargs) -> None:
        """Debounce a function call.

        Args:
            key: Unique key for this debounce group
            func: Function to call
            *args, **kwargs: Arguments to pass to function
        """
        # Cancel pending call if exists
        if key in self._pending:
            self._pending[key].cancel()

        async def delayed_call():
            await asyncio.sleep(self._delay)
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
            del self._pending[key]

        self._pending[key] = asyncio.create_task(delayed_call())

    def cancel(self, key: str) -> None:
        """Cancel a pending debounced call."""
        if key in self._pending:
            self._pending[key].cancel()
            del self._pending[key]

    def cancel_all(self) -> None:
        """Cancel all pending calls."""
        for task in self._pending.values():
            task.cancel()
        self._pending.clear()


class Throttler:
    """Throttle function calls to a maximum rate."""

    def __init__(self, interval: float = 1.0):
        """Initialize throttler.

        Args:
            interval: Minimum interval between calls in seconds
        """
        self._interval = interval
        self._last_call: dict[str, float] = {}

    def should_call(self, key: str) -> bool:
        """Check if a call should be allowed.

        Args:
            key: Unique key for this throttle group

        Returns:
            True if call is allowed, False if throttled
        """
        now = time.time()
        last = self._last_call.get(key, 0)

        if now - last >= self._interval:
            self._last_call[key] = now
            return True

        return False

    def reset(self, key: str) -> None:
        """Reset throttle for a key."""
        if key in self._last_call:
            del self._last_call[key]


class MetricsCache:
    """Specialized cache for system metrics."""

    def __init__(self, update_interval: float = 2.0):
        """Initialize metrics cache.

        Args:
            update_interval: How often to refresh metrics
        """
        self._cache = LRUCache[float](max_size=50, default_ttl=update_interval)
        self._throttler = Throttler(update_interval)
        self._history: dict[str, list] = {}
        self._max_history = 100

    def get_metric(self, name: str) -> float | None:
        """Get a cached metric value."""
        return self._cache.get(name)

    def set_metric(self, name: str, value: float) -> None:
        """Cache a metric value and add to history."""
        self._cache.set(name, value)

        # Add to history
        if name not in self._history:
            self._history[name] = []

        self._history[name].append(value)

        # Trim history
        if len(self._history[name]) > self._max_history:
            self._history[name] = self._history[name][-self._max_history:]

    def get_history(self, name: str, count: int = 20) -> list:
        """Get historical values for a metric."""
        history = self._history.get(name, [])
        return history[-count:]

    def should_update(self, name: str) -> bool:
        """Check if metric should be updated (throttled)."""
        return self._throttler.should_call(name)


# Global instances
_cache: LRUCache | None = None
_metrics_cache: MetricsCache | None = None
_debouncer: Debouncer | None = None


def get_cache() -> LRUCache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = LRUCache(max_size=200, default_ttl=60.0)
    return _cache


def get_metrics_cache() -> MetricsCache:
    """Get global metrics cache instance."""
    global _metrics_cache
    if _metrics_cache is None:
        _metrics_cache = MetricsCache(update_interval=2.0)
    return _metrics_cache


def get_debouncer() -> Debouncer:
    """Get global debouncer instance."""
    global _debouncer
    if _debouncer is None:
        _debouncer = Debouncer(delay=0.1)
    return _debouncer


# Decorator for caching function results
def cached(ttl: float = 60.0, key_prefix: str = ""):
    """Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key
            key = f"{key_prefix}{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

            # Check cache
            result = cache.get(key)
            if result is not None:
                return result

            # Call function
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key
            key = f"{key_prefix}{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

            # Check cache
            result = cache.get(key)
            if result is not None:
                return result

            # Call function
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Decorator for throttling function calls
def throttled(interval: float = 1.0):
    """Decorator to throttle function calls.

    Args:
        interval: Minimum interval between calls in seconds
    """
    throttler = Throttler(interval)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = func.__name__
            if throttler.should_call(key):
                return await func(*args, **kwargs)
            return None

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = func.__name__
            if throttler.should_call(key):
                return func(*args, **kwargs)
            return None

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
