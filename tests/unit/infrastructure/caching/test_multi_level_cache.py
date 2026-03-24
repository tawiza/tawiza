"""Tests for Multi-Level Cache.

This module tests:
- Cache initialization with L1/L2/L3 levels
- Cascading lookups and promotion
- Write-through vs write-back modes
- Statistics and hit rates
- Async operations with L3 Redis
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.caching.multi_level_cache import (
    MultiLevelCache,
    create_multi_level_cache,
)


class TestMultiLevelCacheInitialization:
    """Test suite for cache initialization."""

    def test_default_initialization(self):
        """Cache should initialize with default L1/L2 levels."""
        cache = MultiLevelCache()

        assert cache.l1 is not None
        assert cache.l2 is not None
        assert cache.l3 is None  # Not enabled by default
        assert cache.write_through is True

    def test_custom_capacities(self):
        """Cache should accept custom capacities."""
        cache = MultiLevelCache(
            l1_capacity=50,
            l2_capacity=200,
        )

        assert cache.l1.capacity == 50
        assert cache.l2.capacity == 200

    def test_l3_disabled_by_default(self):
        """L3 Redis cache should be disabled by default."""
        cache = MultiLevelCache()

        assert cache.l3 is None
        assert cache.enable_l3 is False

    def test_l3_enabled_without_redis(self):
        """L3 should handle missing redis gracefully."""
        # With REDIS_AVAILABLE mocked as False
        with patch("src.infrastructure.caching.multi_level_cache.REDIS_AVAILABLE", False):
            cache = MultiLevelCache(enable_l3=True)
            # Should not raise, just log warning
            assert cache.l3 is None

    def test_write_through_mode(self):
        """Should configure write-through mode."""
        cache = MultiLevelCache(write_through=True)
        assert cache.write_through is True

    def test_write_back_mode(self):
        """Should configure write-back mode."""
        cache = MultiLevelCache(write_through=False)
        assert cache.write_through is False

    def test_initial_statistics(self):
        """Statistics should start at zero."""
        cache = MultiLevelCache()

        assert cache.l1_hits == 0
        assert cache.l2_hits == 0
        assert cache.l3_hits == 0
        assert cache.total_misses == 0


class TestL1L2Operations:
    """Test suite for L1/L2 cache operations (sync)."""

    def test_put_stores_in_l1(self):
        """Put should store value in L1."""
        cache = MultiLevelCache()
        cache.put("key1", "value1")

        assert cache.l1.get("key1") == "value1"

    def test_put_stores_in_l2_with_write_through(self):
        """Put with write-through should store in L2."""
        cache = MultiLevelCache(write_through=True)
        cache.put("key1", "value1")

        assert cache.l2.get("key1") == "value1"

    def test_put_does_not_store_in_l2_without_write_through(self):
        """Put without write-through should not store in L2."""
        cache = MultiLevelCache(write_through=False)
        cache.put("key1", "value1")

        assert cache.l2.get("key1") is None

    def test_get_l1_hit(self):
        """Get should return value from L1 and increment hit counter."""
        cache = MultiLevelCache()
        cache.l1.put("key1", "value1")

        result = cache.get("key1")

        assert result == "value1"
        assert cache.l1_hits == 1
        assert cache.l2_hits == 0

    def test_get_l2_hit_promotes_to_l1(self):
        """Get from L2 should promote value to L1."""
        cache = MultiLevelCache()
        cache.l2.put("key1", "value1")

        result = cache.get("key1")

        assert result == "value1"
        assert cache.l2_hits == 1
        assert cache.l1.get("key1") == "value1"  # Promoted to L1

    def test_get_miss_all_levels(self):
        """Get should return None and increment miss counter."""
        cache = MultiLevelCache()

        result = cache.get("nonexistent")

        assert result is None
        assert cache.total_misses == 1

    def test_delete_from_l1_and_l2(self):
        """Delete should remove from both L1 and L2."""
        cache = MultiLevelCache()
        cache.put("key1", "value1")

        result = cache.delete("key1")

        assert result is True
        assert cache.l1.get("key1") is None
        assert cache.l2.get("key1") is None

    def test_delete_nonexistent_key(self):
        """Delete nonexistent key should return False."""
        cache = MultiLevelCache()

        result = cache.delete("nonexistent")

        assert result is False

    def test_clear_removes_all_from_l1_l2(self):
        """Clear should remove all entries from L1 and L2."""
        cache = MultiLevelCache()
        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.clear()

        assert cache.l1.get("key1") is None
        assert cache.l1.get("key2") is None


class TestAsyncOperations:
    """Test suite for async operations with L3."""

    @pytest.mark.asyncio
    async def test_get_async_l1_hit(self):
        """get_async should return from L1 first."""
        cache = MultiLevelCache()
        cache.l1.put("key1", "value1")

        result = await cache.get_async("key1")

        assert result == "value1"
        assert cache.l1_hits == 1

    @pytest.mark.asyncio
    async def test_get_async_l2_hit_promotes(self):
        """get_async from L2 should promote to L1."""
        cache = MultiLevelCache()
        cache.l2.put("key1", "value1")

        result = await cache.get_async("key1")

        assert result == "value1"
        assert cache.l2_hits == 1
        assert cache.l1.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_get_async_l3_hit_promotes_to_l1_l2(self):
        """get_async from L3 should promote to L1 and L2."""
        # Mock L3 Redis cache
        mock_l3 = MagicMock()
        mock_l3.is_connected = True
        mock_l3.get = AsyncMock(return_value="value1")

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        result = await cache.get_async("key1")

        assert result == "value1"
        assert cache.l3_hits == 1
        assert cache.l1.get("key1") == "value1"  # Promoted to L1
        assert cache.l2.get("key1") == "value1"  # Promoted to L2

    @pytest.mark.asyncio
    async def test_get_async_miss_all_levels(self):
        """get_async should return None when miss all levels."""
        mock_l3 = MagicMock()
        mock_l3.is_connected = True
        mock_l3.get = AsyncMock(return_value=None)

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        result = await cache.get_async("nonexistent")

        assert result is None
        assert cache.total_misses == 1

    @pytest.mark.asyncio
    async def test_put_async_writes_to_all_levels(self):
        """put_async with write-through should write to all levels."""
        mock_l3 = MagicMock()
        mock_l3.is_connected = True
        mock_l3.set = AsyncMock()

        cache = MultiLevelCache(write_through=True)
        cache.l3 = mock_l3

        await cache.put_async("key1", "value1")

        assert cache.l1.get("key1") == "value1"
        assert cache.l2.get("key1") == "value1"
        mock_l3.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_async_removes_from_all_levels(self):
        """delete_async should remove from all levels."""
        mock_l3 = MagicMock()
        mock_l3.is_connected = True
        mock_l3.delete = AsyncMock(return_value=True)

        cache = MultiLevelCache()
        cache.l3 = mock_l3
        cache.put("key1", "value1")

        result = await cache.delete_async("key1")

        assert result is True
        mock_l3.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_async_clears_all_levels(self):
        """clear_async should clear all levels including L3."""
        mock_l3 = MagicMock()
        mock_l3.is_connected = True
        mock_l3.clear = AsyncMock()

        cache = MultiLevelCache()
        cache.l3 = mock_l3
        cache.put("key1", "value1")

        await cache.clear_async()

        assert cache.l1.get("key1") is None
        mock_l3.clear.assert_called_once()


class TestL3Connection:
    """Test suite for L3 Redis connection management."""

    @pytest.mark.asyncio
    async def test_connect_l3_success(self):
        """connect_l3 should connect to Redis."""
        mock_l3 = MagicMock()
        mock_l3.connect = AsyncMock()

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        result = await cache.connect_l3()

        assert result is True
        mock_l3.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_l3_no_l3_configured(self):
        """connect_l3 should return False when L3 not configured."""
        cache = MultiLevelCache()

        result = await cache.connect_l3()

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_l3_failure(self):
        """connect_l3 should handle connection failure."""
        mock_l3 = MagicMock()
        mock_l3.connect = AsyncMock(side_effect=Exception("Connection refused"))

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        result = await cache.connect_l3()

        assert result is False

    @pytest.mark.asyncio
    async def test_close_l3(self):
        """close_l3 should close Redis connection."""
        mock_l3 = MagicMock()
        mock_l3.close = AsyncMock()

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        await cache.close_l3()

        mock_l3.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should work as async context manager."""
        mock_l3 = MagicMock()
        mock_l3.connect = AsyncMock()
        mock_l3.close = AsyncMock()

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        async with cache:
            pass

        mock_l3.close.assert_called_once()


class TestStatistics:
    """Test suite for cache statistics."""

    def test_get_overall_hit_rate_no_requests(self):
        """Hit rate should be 0 with no requests."""
        cache = MultiLevelCache()

        assert cache.get_overall_hit_rate() == 0.0

    def test_get_overall_hit_rate_100_percent(self):
        """Hit rate should be 100% when all hits."""
        cache = MultiLevelCache()
        cache.l1_hits = 10
        cache.l2_hits = 5
        cache.l3_hits = 0
        cache.total_misses = 0

        assert cache.get_overall_hit_rate() == 100.0

    def test_get_overall_hit_rate_50_percent(self):
        """Hit rate should calculate correctly."""
        cache = MultiLevelCache()
        cache.l1_hits = 5
        cache.l2_hits = 0
        cache.l3_hits = 0
        cache.total_misses = 5

        assert cache.get_overall_hit_rate() == 50.0

    def test_get_stats_returns_comprehensive_stats(self):
        """get_stats should return comprehensive statistics."""
        cache = MultiLevelCache()
        cache.put("key1", "value1")
        cache.get("key1")  # L1 hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()

        assert "overall" in stats
        assert "l1" in stats
        assert "l2" in stats
        assert "config" in stats
        assert stats["overall"]["total_hits"] == 1
        assert stats["overall"]["total_misses"] == 1
        assert stats["config"]["write_through"] is True

    def test_get_stats_includes_l3_when_enabled(self):
        """get_stats should include L3 stats when enabled."""
        mock_l3 = MagicMock()
        mock_l3.get_stats = MagicMock(return_value={"connected": True})

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        stats = cache.get_stats()

        assert "l3" in stats


class TestHealthCheck:
    """Test suite for health check."""

    @pytest.mark.asyncio
    async def test_health_check_l1_l2_only(self):
        """Health check should report L1/L2 as healthy."""
        cache = MultiLevelCache()

        health = await cache.health_check()

        assert health["l1"] is True
        assert health["l2"] is True
        assert health["l3"] is None

    @pytest.mark.asyncio
    async def test_health_check_with_l3(self):
        """Health check should include L3 status."""
        mock_l3 = MagicMock()
        mock_l3.health_check = AsyncMock(return_value=True)

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        health = await cache.health_check()

        assert health["l3"] is True


class TestRepr:
    """Test suite for string representation."""

    def test_repr_without_l3(self):
        """Repr should show L1/L2 status."""
        cache = MultiLevelCache(l1_capacity=100, l2_capacity=500)

        repr_str = repr(cache)

        assert "MultiLevelCache" in repr_str
        assert "L1=0/100" in repr_str
        assert "L2=0/500" in repr_str

    def test_repr_with_l3(self):
        """Repr should show L3 status when enabled."""
        mock_l3 = MagicMock()
        mock_l3.is_connected = True

        cache = MultiLevelCache()
        cache.l3 = mock_l3

        repr_str = repr(cache)

        assert "L3=connected" in repr_str


class TestFactoryFunction:
    """Test suite for factory function."""

    def test_create_multi_level_cache_defaults(self):
        """Factory should create cache with defaults."""
        cache = create_multi_level_cache()

        assert cache.l1.capacity == 100
        assert cache.l2.capacity == 500
        assert cache.l3 is None

    def test_create_multi_level_cache_custom(self):
        """Factory should accept custom configuration."""
        cache = create_multi_level_cache(
            l1_capacity=200,
            l2_capacity=1000,
        )

        assert cache.l1.capacity == 200
        assert cache.l2.capacity == 1000
