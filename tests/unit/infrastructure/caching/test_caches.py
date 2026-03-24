"""
Unit tests for caching infrastructure

Tests for:
- LRUCache (Least Recently Used)
- LFUCache (Least Frequently Used)
- MultiLevelCache (Multi-level cascading cache)
- CacheStats (Statistics tracking)
"""

import time
from datetime import datetime, timedelta

import pytest

from src.infrastructure.caching.lfu_cache import LFUCache, LFUEntry
from src.infrastructure.caching.lru_cache import CacheEntry, LRUCache
from src.infrastructure.caching.multi_level_cache import MultiLevelCache
from src.infrastructure.caching.stats import CacheStats


class TestCacheEntry:
    """Test CacheEntry metadata and expiration"""

    def test_cache_entry_creation(self):
        """Test creating cache entry with default values"""
        entry = CacheEntry(value="test_value")
        assert entry.value == "test_value"
        assert entry.access_count == 0
        assert entry.ttl_seconds is None
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.accessed_at, datetime)

    def test_cache_entry_with_ttl(self):
        """Test cache entry with TTL"""
        entry = CacheEntry(value="test", ttl_seconds=1.0)
        assert not entry.is_expired()

        # Wait for expiration
        time.sleep(1.1)
        assert entry.is_expired()

    def test_cache_entry_touch(self):
        """Test touch updates access metadata"""
        entry = CacheEntry(value="test")
        initial_count = entry.access_count
        initial_time = entry.accessed_at

        time.sleep(0.01)  # Small delay
        entry.touch()

        assert entry.access_count == initial_count + 1
        assert entry.accessed_at > initial_time

    def test_cache_entry_no_expiration(self):
        """Test entry without TTL never expires"""
        entry = CacheEntry(value="test", ttl_seconds=None)
        assert not entry.is_expired()

        time.sleep(0.1)
        assert not entry.is_expired()


class TestLRUCache:
    """Test LRU (Least Recently Used) Cache"""

    def test_basic_operations(self):
        """Test basic get/put operations"""
        cache = LRUCache(capacity=3)

        # Put items
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Get items
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

        # Check size
        assert cache.size() == 3
        assert len(cache) == 3

    def test_lru_eviction(self):
        """Test LRU eviction policy"""
        cache = LRUCache(capacity=3)

        # Fill cache
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key1 (make it recently used)
        cache.get("key1")

        # Add new item (should evict key2, the least recently used)
        cache.put("key4", "value4")

        assert cache.get("key1") == "value1"  # Still present
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"  # Still present
        assert cache.get("key4") == "value4"  # Newly added

        # Check eviction counter
        assert cache.evictions == 1

    def test_lru_update_existing_key(self):
        """Test updating existing key moves it to end"""
        cache = LRUCache(capacity=3)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Update key1
        cache.put("key1", "updated_value1")

        # Add new item (should evict key2, not key1)
        cache.put("key4", "value4")

        assert cache.get("key1") == "updated_value1"
        assert cache.get("key2") is None

    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        cache = LRUCache(capacity=10, ttl_seconds=0.5)

        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(0.6)
        assert cache.get("key1") is None

        # Check miss counter increased
        assert cache.misses == 1

    def test_hit_miss_statistics(self):
        """Test hit/miss tracking"""
        cache = LRUCache(capacity=10)

        cache.put("key1", "value1")

        # Hit
        cache.get("key1")
        assert cache.hits == 1
        assert cache.misses == 0

        # Miss
        cache.get("key2")
        assert cache.hits == 1
        assert cache.misses == 1

        # Hit rate
        assert cache.get_hit_rate() == 50.0

    def test_delete_operation(self):
        """Test deleting keys"""
        cache = LRUCache(capacity=10)

        cache.put("key1", "value1")
        assert "key1" in cache

        result = cache.delete("key1")
        assert result is True
        assert "key1" not in cache

        # Delete non-existent key
        result = cache.delete("key2")
        assert result is False

    def test_clear_operation(self):
        """Test clearing cache"""
        cache = LRUCache(capacity=10)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        cache.clear()
        assert cache.size() == 0
        assert cache.get("key1") is None

    def test_contains_operator(self):
        """Test 'in' operator"""
        cache = LRUCache(capacity=10)

        cache.put("key1", "value1")
        assert "key1" in cache
        assert "key2" not in cache

    def test_get_stats(self):
        """Test statistics retrieval"""
        cache = LRUCache(capacity=10, ttl_seconds=300)

        cache.put("key1", "value1")
        cache.get("key1")
        cache.get("key2")
        cache.put("key2", "value2")

        stats = cache.get_stats()
        assert stats["capacity"] == 10
        assert stats["size"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["ttl_seconds"] == 300

    def test_invalid_capacity(self):
        """Test error on invalid capacity"""
        with pytest.raises(ValueError):
            LRUCache(capacity=0)

        with pytest.raises(ValueError):
            LRUCache(capacity=-1)

    def test_repr(self):
        """Test string representation"""
        cache = LRUCache(capacity=10)
        cache.put("key1", "value1")
        cache.get("key1")

        repr_str = repr(cache)
        assert "LRUCache" in repr_str
        assert "capacity=10" in repr_str
        assert "size=1" in repr_str


class TestLFUCache:
    """Test LFU (Least Frequently Used) Cache"""

    def test_basic_operations(self):
        """Test basic get/put operations"""
        cache = LFUCache(capacity=3)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

        assert cache.size() == 3

    def test_frequency_tracking(self):
        """Test frequency tracking on access"""
        cache = LFUCache(capacity=3)

        cache.put("key1", "value1")

        # Access multiple times
        cache.get("key1")
        cache.get("key1")
        cache.get("key1")

        # Check frequency
        entry = cache.cache["key1"]
        assert entry.frequency == 4  # 1 (put) + 3 (get)

    def test_lfu_eviction(self):
        """Test LFU eviction policy"""
        cache = LFUCache(capacity=3)

        # Add items
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key1 and key3 multiple times (increase frequency)
        cache.get("key1")
        cache.get("key1")
        cache.get("key3")

        # key1: freq=3, key2: freq=1, key3: freq=2
        # Add new item (should evict key2, least frequently used)
        cache.put("key4", "value4")

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Evicted (lowest frequency)
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

        assert cache.evictions == 1

    def test_lfu_lru_tiebreaker(self):
        """Test LRU tiebreaker for same frequency"""
        cache = LFUCache(capacity=3)

        # Add items with same frequency (1)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # All have frequency 1, should evict key1 (least recently used)
        cache.put("key4", "value4")

        assert cache.get("key1") is None  # Evicted (LRU among LFU)
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_update_existing_key(self):
        """Test updating existing key maintains frequency"""
        cache = LFUCache(capacity=3)

        cache.put("key1", "value1")
        cache.get("key1")  # freq = 2

        # Update value
        cache.put("key1", "updated_value1")

        # Frequency should increase
        entry = cache.cache["key1"]
        assert entry.frequency == 3
        assert entry.value == "updated_value1"

    def test_frequency_distribution(self):
        """Test frequency distribution tracking"""
        cache = LFUCache(capacity=5)

        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        cache.get("key1")
        cache.get("key1")
        cache.get("key2")

        # key1: freq=3, key2: freq=2, key3: freq=1
        dist = cache.get_frequency_distribution()
        assert dist[1] == 1  # key3
        assert dist[2] == 1  # key2
        assert dist[3] == 1  # key1

    def test_min_frequency_tracking(self):
        """Test min_freq tracking"""
        cache = LFUCache(capacity=3)

        cache.put("key1", "value1")
        assert cache.min_freq == 1

        cache.get("key1")
        assert cache.min_freq == 2  # Only one item, freq increased

        cache.put("key2", "value2")
        assert cache.min_freq == 1  # New item with freq 1

    def test_delete_operation(self):
        """Test deleting keys updates frequency map"""
        cache = LFUCache(capacity=10)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        result = cache.delete("key1")
        assert result is True
        assert "key1" not in cache

        result = cache.delete("key3")
        assert result is False

    def test_delete_updates_min_freq(self):
        """Test deleting min_freq item updates min_freq"""
        cache = LFUCache(capacity=3)

        cache.put("key1", "value1")  # freq=1
        cache.put("key2", "value2")  # freq=1
        cache.get("key2")  # freq=2

        assert cache.min_freq == 1

        # Delete key1 (only item with freq=1)
        cache.delete("key1")

        # min_freq should update to 2
        assert cache.min_freq == 2

    def test_clear_operation(self):
        """Test clearing cache"""
        cache = LFUCache(capacity=10)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()
        assert cache.size() == 0
        assert cache.min_freq == 0

    def test_hit_miss_statistics(self):
        """Test hit/miss tracking"""
        cache = LFUCache(capacity=10)

        cache.put("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        assert cache.hits == 1
        assert cache.misses == 1
        assert cache.get_hit_rate() == 50.0

    def test_get_stats(self):
        """Test statistics retrieval"""
        cache = LFUCache(capacity=10)

        cache.put("key1", "value1")
        cache.get("key1")
        cache.get("key2")

        stats = cache.get_stats()
        assert stats["capacity"] == 10
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["min_frequency"] == 2
        assert "frequency_distribution" in stats

    def test_invalid_capacity(self):
        """Test error on invalid capacity"""
        with pytest.raises(ValueError):
            LFUCache(capacity=0)

        with pytest.raises(ValueError):
            LFUCache(capacity=-1)

    def test_repr(self):
        """Test string representation"""
        cache = LFUCache(capacity=10)
        cache.put("key1", "value1")

        repr_str = repr(cache)
        assert "LFUCache" in repr_str
        assert "capacity=10" in repr_str
        assert "min_freq=" in repr_str


class TestMultiLevelCache:
    """Test Multi-Level Cache"""

    def test_initialization(self):
        """Test multi-level cache initialization"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50, l1_ttl=300, l2_ttl=900)

        assert cache.l1.capacity == 10
        assert cache.l2.capacity == 50
        assert cache.write_through is True

    def test_l1_hit(self):
        """Test L1 cache hit"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50)

        cache.put("key1", "value1")
        value = cache.get("key1")

        assert value == "value1"
        assert cache.l1_hits == 1
        assert cache.l2_hits == 0
        assert cache.total_misses == 0

    def test_l2_hit_promotes_to_l1(self):
        """Test L2 hit promotes to L1"""
        cache = MultiLevelCache(l1_capacity=2, l2_capacity=10, write_through=True)

        # Fill L1 and L2
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")  # Evicts key1 from L1

        # key1 should be in L2 but not L1
        assert cache.l1.get("key1") is None
        assert cache.l2.get("key1") == "value1"

        # Access key1 (L2 hit, should promote to L1)
        value = cache.get("key1")

        assert value == "value1"
        assert cache.l2_hits == 1
        assert cache.l1.get("key1") == "value1"  # Promoted to L1

    def test_cache_miss_all_levels(self):
        """Test miss on all cache levels"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50)

        value = cache.get("nonexistent")

        assert value is None
        assert cache.l1_hits == 0
        assert cache.l2_hits == 0
        assert cache.total_misses == 1

    def test_write_through_mode(self):
        """Test write-through writes to all levels"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50, write_through=True)

        cache.put("key1", "value1")

        # Should be in both L1 and L2
        assert cache.l1.get("key1") == "value1"
        assert cache.l2.get("key1") == "value1"

    def test_write_back_mode(self):
        """Test write-back writes to L1 only"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50, write_through=False)

        cache.put("key1", "value1")

        # Should be in L1 only
        assert cache.l1.get("key1") == "value1"
        assert cache.l2.get("key1") is None

    def test_delete_all_levels(self):
        """Test delete removes from all levels"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50, write_through=True)

        cache.put("key1", "value1")
        assert cache.l1.get("key1") == "value1"
        assert cache.l2.get("key1") == "value1"

        result = cache.delete("key1")
        assert result is True
        assert cache.l1.get("key1") is None
        assert cache.l2.get("key1") is None

    def test_clear_all_levels(self):
        """Test clear removes from all levels"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50, write_through=True)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()

        assert cache.l1.size() == 0
        assert cache.l2.size() == 0

    def test_level_propagation(self):
        """Test data propagation between levels"""
        cache = MultiLevelCache(l1_capacity=2, l2_capacity=5, write_through=True)

        # Add items
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")  # Evicts key1 from L1

        # key1 in L2, not L1
        assert "key1" not in cache.l1
        assert "key1" in cache.l2

        # Access key1 (promotes from L2 to L1)
        cache.get("key1")
        assert "key1" in cache.l1

    def test_overall_hit_rate(self):
        """Test overall hit rate calculation"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.get("key1")  # L1 hit
        cache.get("key2")  # L1 hit
        cache.get("key3")  # Miss

        # 2 hits, 1 miss = 66.67%
        hit_rate = cache.get_overall_hit_rate()
        assert abs(hit_rate - 66.67) < 0.1

    def test_get_stats(self):
        """Test comprehensive statistics"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50)

        cache.put("key1", "value1")
        cache.get("key1")
        cache.get("key2")

        stats = cache.get_stats()

        assert "overall" in stats
        assert "l1" in stats
        assert "l2" in stats
        assert "config" in stats

        assert stats["overall"]["total_hits"] == 1
        assert stats["overall"]["total_misses"] == 1
        assert stats["l1"]["hits"] == 1
        assert stats["config"]["write_through"] is True

    def test_l1_ttl_expiration(self):
        """Test L1 TTL expiration with L2 fallback"""
        cache = MultiLevelCache(
            l1_capacity=10, l2_capacity=50, l1_ttl=0.3, l2_ttl=None, write_through=True
        )

        cache.put("key1", "value1")

        # Wait for L1 to expire
        time.sleep(0.4)

        # Should get from L2 and promote to L1
        value = cache.get("key1")
        assert value == "value1"
        assert cache.l2_hits == 1

    def test_repr(self):
        """Test string representation"""
        cache = MultiLevelCache(l1_capacity=10, l2_capacity=50)
        cache.put("key1", "value1")

        repr_str = repr(cache)
        assert "MultiLevelCache" in repr_str
        assert "L1=" in repr_str
        assert "L2=" in repr_str


class TestCacheStats:
    """Test CacheStats"""

    def test_initialization(self):
        """Test stats initialization"""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.clears == 0
        assert isinstance(stats.start_time, datetime)

    def test_record_operations(self):
        """Test recording operations"""
        stats = CacheStats()

        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_eviction()
        stats.record_set()
        stats.record_delete()
        stats.record_clear()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.evictions == 1
        assert stats.sets == 1
        assert stats.deletes == 1
        assert stats.clears == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation"""
        stats = CacheStats()

        # No requests
        assert stats.get_hit_rate() == 0.0

        # 3 hits, 1 miss = 75%
        stats.record_hit()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()

        assert stats.get_hit_rate() == 75.0

    def test_uptime_tracking(self):
        """Test uptime tracking"""
        stats = CacheStats()

        time.sleep(0.1)

        uptime = stats.get_uptime_seconds()
        assert uptime >= 0.1
        assert uptime < 1.0

    def test_requests_per_second(self):
        """Test requests per second calculation"""
        stats = CacheStats()

        # No requests
        assert stats.get_requests_per_second() == 0.0

        stats.record_hit()
        stats.record_hit()
        stats.record_miss()

        time.sleep(0.1)

        rps = stats.get_requests_per_second()
        assert rps > 0

    def test_to_dict(self):
        """Test conversion to dictionary"""
        stats = CacheStats()

        stats.record_hit()
        stats.record_miss()

        data = stats.to_dict()

        assert data["hits"] == 1
        assert data["misses"] == 1
        assert "hit_rate" in data
        assert "uptime_seconds" in data
        assert "requests_per_second" in data
        assert "start_time" in data

    def test_reset(self):
        """Test resetting statistics"""
        stats = CacheStats()

        stats.record_hit()
        stats.record_miss()
        stats.record_eviction()

        old_start_time = stats.start_time
        time.sleep(0.05)

        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.start_time > old_start_time


class TestCacheIntegration:
    """Integration tests for cache behavior"""

    def test_lru_vs_lfu_eviction_difference(self):
        """Test different eviction behaviors between LRU and LFU"""
        lru = LRUCache(capacity=3)
        lfu = LFUCache(capacity=3)

        # Add same items to both
        for cache in [lru, lfu]:
            cache.put("key1", "value1")
            cache.put("key2", "value2")
            cache.put("key3", "value3")

        # Access key1 multiple times (high frequency)
        for _ in range(5):
            lfu.get("key1")

        # Access key3 once (recent access for LRU)
        lru.get("key3")

        # Add new item
        lru.put("key4", "value4")
        lfu.put("key4", "value4")

        # LRU evicts key1 or key2 (least recently used)
        # LFU evicts key2 or key3 (least frequently used)
        assert lru.get("key3") == "value3"  # Recently accessed
        assert lfu.get("key1") == "value1"  # Frequently accessed

    def test_multi_level_cache_hierarchy(self):
        """Test complete multi-level cache hierarchy"""
        cache = MultiLevelCache(l1_capacity=2, l2_capacity=5, write_through=True)

        # Add items
        for i in range(7):
            cache.put(f"key{i}", f"value{i}")

        # Recent items in L1
        assert cache.l1.size() == 2

        # More items in L2
        assert cache.l2.size() == 5

        # Access old item (should promote to L1)
        value = cache.get("key0")
        if value is not None:  # If still in L2
            assert cache.l1.get("key0") == "value0"

    def test_cache_performance_characteristics(self):
        """Test that caches maintain O(1) performance"""
        import time

        cache = LRUCache(capacity=1000)

        # Measure put performance
        start = time.perf_counter()
        for i in range(1000):
            cache.put(f"key{i}", f"value{i}")
        put_time = time.perf_counter() - start

        # Measure get performance
        start = time.perf_counter()
        for i in range(1000):
            cache.get(f"key{i}")
        get_time = time.perf_counter() - start

        # Operations should be very fast (< 0.1s for 1000 operations)
        assert put_time < 0.1
        assert get_time < 0.1

    def test_concurrent_cache_operations(self):
        """Test cache behavior with various operation patterns"""
        cache = LRUCache(capacity=10)

        # Mixed operations
        cache.put("key1", "value1")
        cache.get("key1")  # hit 1
        cache.put("key1", "updated")
        cache.delete("key2")
        cache.get("key3")  # miss 1

        # Verify state after operations (before final get)
        assert cache.hits == 1
        assert cache.misses == 1  # Only key3 miss, delete doesn't count as miss

        # Verify value consistency
        assert cache.get("key1") == "updated"  # hit 2
