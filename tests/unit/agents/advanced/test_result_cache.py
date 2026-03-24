#!/usr/bin/env python3
"""
Tests unitaires pour le Result Cache System
Couvre: LRUCache, AgentResultCache, SmartCache, CacheManager
"""

import asyncio
import time

import pytest

from src.infrastructure.agents.advanced.result_cache import (
    AgentResultCache,
    CacheEntry,
    CacheManager,
    CacheStrategy,
    LRUCache,
    SmartCache,
)


class TestCacheEntry:
    """Tests pour CacheEntry"""

    def test_cache_entry_creation(self):
        """Test création d'une entrée de cache"""
        entry = CacheEntry(key="test-key", value={"data": "test"}, ttl=3600.0)

        assert entry.key == "test-key"
        assert entry.value == {"data": "test"}
        assert entry.ttl == 3600.0
        assert entry.access_count == 0

    def test_cache_entry_is_expired(self):
        """Test détection d'expiration"""
        # Entry without TTL never expires
        entry1 = CacheEntry("key1", "value1", ttl=None)
        assert entry1.is_expired() is False

        # Entry with past TTL is expired
        entry2 = CacheEntry("key2", "value2", ttl=0.001)
        time.sleep(0.002)
        assert entry2.is_expired() is True

    def test_cache_entry_access(self):
        """Test enregistrement d'accès"""
        entry = CacheEntry("key", "value")
        initial_time = entry.last_accessed

        time.sleep(0.01)
        entry.access()

        assert entry.access_count == 1
        assert entry.last_accessed > initial_time


class TestLRUCache:
    """Tests pour LRUCache"""

    @pytest.mark.asyncio
    async def test_lru_cache_basic_operations(self):
        """Test opérations basiques get/put"""
        cache = LRUCache(max_size=10, max_memory_mb=1.0)

        # Put and get
        await cache.put("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_lru_cache_miss(self):
        """Test cache miss"""
        cache = LRUCache(max_size=10)

        result = await cache.get("nonexistent")

        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_lru_cache_eviction_by_size(self):
        """Test éviction par taille maximale"""
        cache = LRUCache(max_size=3)

        # Add 3 entries
        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.put("key3", "value3")

        # Add 4th should evict oldest
        await cache.put("key4", "value4")

        # key1 should be evicted (oldest)
        result = await cache.get("key1")
        assert result is None

        # Others should exist
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_lru_cache_ordering(self):
        """Test que l'ordre LRU est maintenu"""
        cache = LRUCache(max_size=3)

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.put("key3", "value3")

        # Access key1 (move to end)
        await cache.get("key1")

        # Add key4, should evict key2 (oldest untouched)
        await cache.put("key4", "value4")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_lru_cache_ttl_expiration(self):
        """Test expiration TTL"""
        cache = LRUCache(max_size=10)

        # Add with short TTL
        await cache.put("key1", "value1", ttl=0.1)

        # Should be available immediately
        assert await cache.get("key1") == "value1"

        # Wait for expiration
        await asyncio.sleep(0.15)

        # Should be expired
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_lru_cache_update_existing(self):
        """Test mise à jour d'une entrée existante"""
        cache = LRUCache(max_size=10)

        await cache.put("key1", "value1")
        await cache.put("key1", "value2")  # Update

        result = await cache.get("key1")
        assert result == "value2"

    @pytest.mark.asyncio
    async def test_lru_cache_clear(self):
        """Test vidage du cache"""
        cache = LRUCache(max_size=10)

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert cache.hits == 0
        assert cache.misses == 2

    @pytest.mark.asyncio
    async def test_lru_cache_stats(self):
        """Test statistiques du cache"""
        cache = LRUCache(max_size=10)

        await cache.put("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = await cache.get_stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0


class TestAgentResultCache:
    """Tests pour AgentResultCache"""

    @pytest.mark.asyncio
    async def test_agent_cache_basic_operations(self):
        """Test opérations basiques avec cache d'agent"""
        cache = AgentResultCache(max_size=10)

        # Cache a result
        await cache.cache_result(
            agent_type="data_analyst",
            task_type="analyze",
            parameters={"data": "test"},
            result={"output": "analyzed"},
        )

        # Retrieve it
        result = await cache.get_result(
            agent_type="data_analyst", task_type="analyze", parameters={"data": "test"}
        )

        assert result == {"output": "analyzed"}

    @pytest.mark.asyncio
    async def test_agent_cache_key_generation(self):
        """Test que les clés sont générées de façon déterministe"""
        cache = AgentResultCache(max_size=10)

        # Same parameters should generate same key
        await cache.cache_result("agent", "task", {"a": 1, "b": 2}, "result1")

        result = await cache.get_result("agent", "task", {"b": 2, "a": 1})
        assert result == "result1"  # Order doesn't matter

    @pytest.mark.asyncio
    async def test_agent_cache_invalidation(self):
        """Test invalidation du cache par agent"""
        cache = AgentResultCache(max_size=10)

        # Cache results for different agents
        await cache.cache_result("agent1", "task", {"data": "test"}, "result1")
        await cache.cache_result("agent2", "task", {"data": "test"}, "result2")

        # Invalidate agent1
        await cache.invalidate_agent_cache("agent1")

        # agent1 should be gone
        assert await cache.get_result("agent1", "task", {"data": "test"}) is None

        # agent2 should still exist
        assert await cache.get_result("agent2", "task", {"data": "test"}) == "result2"

    @pytest.mark.asyncio
    async def test_agent_cache_stats(self):
        """Test statistiques du cache d'agent"""
        cache = AgentResultCache(max_size=10)

        await cache.cache_result("agent1", "task", {"data": "test"}, "result")
        await cache.get_result("agent1", "task", {"data": "test"})

        stats = await cache.get_stats()

        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert "agents" in stats
        assert stats["total_agents"] == 1

    @pytest.mark.asyncio
    async def test_agent_cache_clear(self):
        """Test vidage complet du cache"""
        cache = AgentResultCache(max_size=10)

        await cache.cache_result("agent1", "task", {"data": "test"}, "result1")
        await cache.cache_result("agent2", "task", {"data": "test"}, "result2")

        await cache.clear()

        assert await cache.get_result("agent1", "task", {"data": "test"}) is None
        assert await cache.get_result("agent2", "task", {"data": "test"}) is None


class TestSmartCache:
    """Tests pour SmartCache"""

    @pytest.mark.asyncio
    async def test_smart_cache_record_access(self):
        """Test enregistrement des accès"""
        agent_cache = AgentResultCache(max_size=10)
        smart_cache = SmartCache(agent_cache)

        await smart_cache.record_access("agent1", "task1")
        await smart_cache.record_access("agent1", "task2")

        assert len(smart_cache.access_patterns) == 2

    @pytest.mark.asyncio
    async def test_smart_cache_predict_next_tasks(self):
        """Test prédiction des prochaines tâches"""
        agent_cache = AgentResultCache(max_size=10)
        smart_cache = SmartCache(agent_cache)

        # Record multiple accesses
        for _ in range(5):
            await smart_cache.record_access("agent1", "task1")

        for _ in range(3):
            await smart_cache.record_access("agent1", "task2")

        # Predict
        predictions = await smart_cache.predict_next_tasks("agent1")

        assert len(predictions) > 0
        assert "agent1:task1" in predictions  # Most frequent

    @pytest.mark.asyncio
    async def test_smart_cache_access_pattern_limit(self):
        """Test que les patterns sont limités"""
        agent_cache = AgentResultCache(max_size=10)
        smart_cache = SmartCache(agent_cache)

        # Record more than 100 accesses
        for i in range(150):
            await smart_cache.record_access("agent1", "task1")

        pattern_key = "agent1:task1"
        assert pattern_key in smart_cache.access_patterns
        assert len(smart_cache.access_patterns[pattern_key]) <= 100


class TestCacheManager:
    """Tests pour CacheManager"""

    @pytest.mark.asyncio
    async def test_cache_manager_basic_operations(self):
        """Test opérations basiques du gestionnaire"""
        manager = CacheManager(max_size=10, enable_smart_cache=True)

        # Put and get
        await manager.put(
            agent_type="agent1", task_type="task1", parameters={"data": "test"}, result="result1"
        )

        result = await manager.get(
            agent_type="agent1", task_type="task1", parameters={"data": "test"}
        )

        assert result == "result1"

    @pytest.mark.asyncio
    async def test_cache_manager_enable_disable(self):
        """Test activation/désactivation du cache"""
        manager = CacheManager(max_size=10)

        # Cache something
        await manager.put("agent", "task", {"data": "test"}, "result")

        # Disable cache
        await manager.disable()

        # Get should return None
        result = await manager.get("agent", "task", {"data": "test"})
        assert result is None

        # Enable again
        await manager.enable()

        # Put again
        await manager.put("agent", "task", {"data": "test"}, "result")
        result = await manager.get("agent", "task", {"data": "test"})
        assert result == "result"

    @pytest.mark.asyncio
    async def test_cache_manager_invalidate(self):
        """Test invalidation par agent"""
        manager = CacheManager(max_size=10)

        await manager.put("agent1", "task", {"data": "test"}, "result1")
        await manager.put("agent2", "task", {"data": "test"}, "result2")

        await manager.invalidate("agent1")

        assert await manager.get("agent1", "task", {"data": "test"}) is None
        assert await manager.get("agent2", "task", {"data": "test"}) == "result2"

    @pytest.mark.asyncio
    async def test_cache_manager_stats(self):
        """Test statistiques complètes"""
        manager = CacheManager(max_size=10, enable_smart_cache=True)

        await manager.put("agent", "task", {"data": "test"}, "result")
        await manager.get("agent", "task", {"data": "test"})

        stats = await manager.get_stats()

        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "is_enabled" in stats
        assert stats["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_cache_manager_with_ttl(self):
        """Test avec TTL personnalisé"""
        manager = CacheManager(max_size=10, default_ttl=0.1)

        await manager.put("agent", "task", {"data": "test"}, "result", ttl=0.1)

        # Should exist immediately
        assert await manager.get("agent", "task", {"data": "test"}) == "result"

        # Wait for expiration
        await asyncio.sleep(0.15)

        # Should be expired
        assert await manager.get("agent", "task", {"data": "test"}) is None

    @pytest.mark.asyncio
    async def test_cache_manager_clear(self):
        """Test vidage complet"""
        manager = CacheManager(max_size=10)

        await manager.put("agent1", "task", {"data": "test"}, "result1")
        await manager.put("agent2", "task", {"data": "test"}, "result2")

        await manager.clear()

        assert await manager.get("agent1", "task", {"data": "test"}) is None
        assert await manager.get("agent2", "task", {"data": "test"}) is None


# Performance tests
@pytest.mark.slow
class TestCachePerformance:
    """Tests de performance du cache"""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self):
        """Test performance des cache hits"""
        manager = CacheManager(max_size=1000)

        # Populate cache
        for i in range(100):
            await manager.put("agent", "task", {"index": i}, f"result-{i}")

        # Measure cache hit time
        start = time.time()
        for i in range(100):
            result = await manager.get("agent", "task", {"index": i})
            assert result == f"result-{i}"

        duration = time.time() - start
        avg_time = duration / 100

        # Cache hits should be very fast (<1ms per hit)
        assert avg_time < 0.001, f"Cache hit too slow: {avg_time * 1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_cache_memory_eviction(self):
        """Test éviction par limite mémoire"""
        # Cache with small memory limit
        cache = LRUCache(max_size=1000, max_memory_mb=0.01)  # 10KB

        # Add many entries (will trigger memory-based eviction)
        for i in range(100):
            large_value = "x" * 1000  # ~1KB each
            await cache.put(f"key-{i}", large_value)

        # Cache should have evicted old entries
        stats = await cache.get_stats()
        assert stats["size"] < 100  # Some were evicted
        assert stats["memory_usage_mb"] <= 0.01  # Under limit


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
