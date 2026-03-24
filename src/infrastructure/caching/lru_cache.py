"""
LRU Cache - Least Recently Used caching algorithm

Time complexity: O(1) for both get and put operations
Space complexity: O(capacity)

Implementation uses:
- OrderedDict for O(1) access and ordering
- move_to_end() for O(1) reordering

Algorithm:
    When cache is full and new item added:
    1. Remove least recently used item (first in OrderedDict)
    2. Add new item (automatically becomes most recent)

    On access:
    1. Move accessed item to end (mark as recently used)
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry[V]:
    """Cache entry with metadata"""

    value: V
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: float | None = None

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    def touch(self) -> None:
        """Mark entry as accessed"""
        self.accessed_at = datetime.now()
        self.access_count += 1


class LRUCache[K, V]:
    """
    LRU Cache implementation with O(1) complexity

    Features:
    - O(1) get and put operations
    - Automatic eviction of least recently used items
    - Optional TTL (time-to-live) support
    - Hit/miss statistics

    Examples:
        >>> cache = LRUCache(capacity=100, ttl_seconds=300)
        >>> cache.put("key1", "value1")
        >>> value = cache.get("key1")  # Returns "value1"
        >>> stats = cache.get_stats()
    """

    def __init__(
        self,
        capacity: int = 100,
        ttl_seconds: float | None = None,
    ):
        """
        Initialize LRU cache

        Args:
            capacity: Maximum number of items in cache
            ttl_seconds: Time-to-live in seconds (None = no expiration)
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: K) -> V | None:
        """
        Get value from cache

        Time complexity: O(1)

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            return None

        # Move to end (mark as recently used) - O(1)
        self.cache.move_to_end(key)

        # Update access metadata
        entry.touch()

        self.hits += 1
        return entry.value

    def put(self, key: K, value: V) -> None:
        """
        Put value in cache

        Time complexity: O(1)

        Args:
            key: Cache key
            value: Value to cache
        """
        # If key exists, update and move to end
        if key in self.cache:
            self.cache[key].value = value
            self.cache[key].touch()
            self.cache.move_to_end(key)
            return

        # If at capacity, evict least recently used (first item)
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)  # Remove first (least recent)
            self.evictions += 1

        # Add new entry
        entry = CacheEntry(value=value, ttl_seconds=self.ttl_seconds)
        self.cache[key] = entry

    def delete(self, key: K) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if key was present, False otherwise
        """
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from cache"""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)

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
        Get cache statistics

        Returns:
            Dictionary with cache metrics
        """
        return {
            "capacity": self.capacity,
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": self.get_hit_rate(),
            "ttl_seconds": self.ttl_seconds,
        }

    def __len__(self) -> int:
        """Get cache size"""
        return len(self.cache)

    def __contains__(self, key: K) -> bool:
        """Check if key in cache"""
        return key in self.cache

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"LRUCache(capacity={self.capacity}, "
            f"size={len(self.cache)}, "
            f"hit_rate={self.get_hit_rate():.1f}%)"
        )
