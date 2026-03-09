"""
Caching algorithms - Intelligent multi-level caching

Provides efficient caching implementations:
- LRUCache: Least Recently Used (O(1) get/put)
- LFUCache: Least Frequently Used (O(1) get, O(log n) put)
- MultiLevelCache: Cascading L1 → L2 → L3 cache
- RedisCache: Distributed Redis cache (L3)
- LLMCache: Semantic caching for LLM responses
- CacheStats: Metrics and monitoring
"""

from .lfu_cache import LFUCache
from .llm_cache import (
    DEFAULT_CACHE_CONFIGS,
    CacheConfig,
    CacheStrategy,
    LLMCache,
    close_llm_cache,
    get_llm_cache,
)
from .lru_cache import LRUCache
from .multi_level_cache import MultiLevelCache, create_multi_level_cache
from .repository_cache import (
    CachedDatasetRepository,
    CachedMLModelRepository,
    CachedRepositoryMixin,
    CacheKeyBuilder,
    cache_query,
    close_repository_cache,
    get_repository_cache,
    init_repository_cache,
    invalidate_cache,
)
from .stats import CacheStats

# Optional Redis cache (requires redis-py)
try:
    from .redis_cache import RedisCache, close_redis_cache, get_redis_cache
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisCache = None
    get_redis_cache = None
    close_redis_cache = None

__all__ = [
    # Base caches
    "LRUCache",
    "LFUCache",
    "MultiLevelCache",
    "create_multi_level_cache",
    # Redis cache
    "RedisCache",
    "get_redis_cache",
    "close_redis_cache",
    "REDIS_AVAILABLE",
    # LLM cache
    "LLMCache",
    "CacheStrategy",
    "CacheConfig",
    "get_llm_cache",
    "close_llm_cache",
    "DEFAULT_CACHE_CONFIGS",
    # Repository cache
    "CacheKeyBuilder",
    "cache_query",
    "invalidate_cache",
    "CachedRepositoryMixin",
    "CachedMLModelRepository",
    "CachedDatasetRepository",
    "get_repository_cache",
    "init_repository_cache",
    "close_repository_cache",
    # Stats
    "CacheStats",
]
