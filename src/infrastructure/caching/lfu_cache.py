"""
LFU Cache - Least Frequently Used caching algorithm

Time complexity:
- get: O(1)
- put: O(1) amortized

Space complexity: O(capacity)

Implementation uses:
- HashMap for O(1) value lookup
- HashMap of frequency → LinkedList for O(1) eviction
- Min frequency tracking for O(1) LFU identification

Algorithm:
    Each frequency has a LinkedList of keys with that frequency.
    Min frequency points to the frequency bucket with least used items.

    On access:
    1. Move key from freq[f] to freq[f+1]
    2. Update min_freq if needed

    On eviction:
    1. Remove first item from min_freq bucket (LRU among LFU)
"""

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class LFUEntry[V]:
    """LFU cache entry"""

    value: V
    frequency: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update access metadata"""
        self.accessed_at = datetime.now()
        self.frequency += 1


class LFUCache[K, V]:
    """
    LFU Cache implementation with O(1) operations

    Features:
    - O(1) get operation
    - O(1) amortized put operation
    - Evicts least frequently used items
    - Among items with same frequency, evicts least recently used (LRU)

    Examples:
        >>> cache = LFUCache(capacity=100)
        >>> cache.put("popular", "value")
        >>> cache.get("popular")  # freq = 2
        >>> cache.get("popular")  # freq = 3
        >>> # "popular" less likely to be evicted
    """

    def __init__(self, capacity: int = 500):
        """
        Initialize LFU cache

        Args:
            capacity: Maximum number of items in cache
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity

        # Core data structures
        self.cache: dict[K, LFUEntry[V]] = {}  # key → entry
        self.freq_map: dict[int, OrderedDict[K, None]] = defaultdict(OrderedDict)  # freq → keys
        self.min_freq = 0  # Current minimum frequency

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _update_frequency(self, key: K) -> None:
        """
        Update frequency for a key

        Time complexity: O(1)

        Args:
            key: Cache key
        """
        entry = self.cache[key]
        old_freq = entry.frequency

        # Remove from old frequency bucket
        del self.freq_map[old_freq][key]

        # If old frequency bucket is now empty and was min_freq,
        # increment min_freq
        if not self.freq_map[old_freq] and old_freq == self.min_freq:
            self.min_freq += 1

        # Increment frequency
        entry.touch()
        new_freq = entry.frequency

        # Add to new frequency bucket
        self.freq_map[new_freq][key] = None

    def get(self, key: K) -> V | None:
        """
        Get value from cache

        Time complexity: O(1)

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if key not in self.cache:
            self.misses += 1
            return None

        # Update frequency
        self._update_frequency(key)

        self.hits += 1
        return self.cache[key].value

    def put(self, key: K, value: V) -> None:
        """
        Put value in cache

        Time complexity: O(1) amortized

        Args:
            key: Cache key
            value: Value to cache
        """
        if self.capacity <= 0:
            return

        # If key exists, update value and frequency
        if key in self.cache:
            self.cache[key].value = value
            self._update_frequency(key)
            return

        # If at capacity, evict LFU item
        if len(self.cache) >= self.capacity:
            # Get LFU bucket (min_freq)
            lfu_bucket = self.freq_map[self.min_freq]

            # Remove first item (LRU among LFU)
            evict_key, _ = lfu_bucket.popitem(last=False)
            del self.cache[evict_key]
            self.evictions += 1

        # Add new entry with frequency 1
        entry = LFUEntry(value=value, frequency=1)
        self.cache[key] = entry
        self.freq_map[1][key] = None
        self.min_freq = 1

    def delete(self, key: K) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if key was present, False otherwise
        """
        if key not in self.cache:
            return False

        entry = self.cache[key]
        freq = entry.frequency

        # Remove from cache and frequency map
        del self.cache[key]
        del self.freq_map[freq][key]

        # Clean up empty frequency bucket
        if not self.freq_map[freq]:
            del self.freq_map[freq]
            if freq == self.min_freq:
                # Find new min_freq
                if self.freq_map:
                    self.min_freq = min(self.freq_map.keys())
                else:
                    self.min_freq = 0

        return True

    def clear(self) -> None:
        """Clear all entries from cache"""
        self.cache.clear()
        self.freq_map.clear()
        self.min_freq = 0

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

    def get_frequency_distribution(self) -> dict[int, int]:
        """
        Get distribution of frequencies

        Returns:
            Dictionary mapping frequency → count of keys
        """
        return {freq: len(keys) for freq, keys in self.freq_map.items()}

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
            "min_frequency": self.min_freq,
            "frequency_distribution": self.get_frequency_distribution(),
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
            f"LFUCache(capacity={self.capacity}, "
            f"size={len(self.cache)}, "
            f"hit_rate={self.get_hit_rate():.1f}%, "
            f"min_freq={self.min_freq})"
        )
