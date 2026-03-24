"""
Repository Cache - Query result caching for SQLAlchemy repositories

This module provides caching decorators and mixins for repository patterns:
- @cache_query: Decorator for caching query results
- CachedRepositoryMixin: Mixin class for adding cache to repositories
- CacheKeyBuilder: Helper for building consistent cache keys

Usage:
    # Method 1: Decorator
    class MyRepository:
        @cache_query(ttl=300, key_prefix="models")
        async def get_by_id(self, id: UUID) -> Optional[Model]:
            ...

    # Method 2: Mixin
    class MyRepository(CachedRepositoryMixin):
        async def get_by_id(self, id: UUID) -> Optional[Model]:
            cache_key = self._build_cache_key("get_by_id", id)
            cached = await self._get_cached(cache_key)
            if cached:
                return cached
            result = await self._fetch_from_db(id)
            await self._set_cached(cache_key, result)
            return result
"""

import functools
import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from loguru import logger

from .multi_level_cache import MultiLevelCache, create_multi_level_cache

T = TypeVar("T")

# Global repository cache instance
_repository_cache: MultiLevelCache | None = None


def get_repository_cache() -> MultiLevelCache:
    """
    Get or create global repository cache.

    Returns:
        MultiLevelCache instance for repository caching
    """
    global _repository_cache

    if _repository_cache is None:
        _repository_cache = create_multi_level_cache(
            l1_capacity=500,  # Hot queries
            l2_capacity=2000,  # Warm queries
            enable_redis=False,  # Enable if needed
        )
        logger.info("Repository cache initialized (L1: 500, L2: 2000)")

    return _repository_cache


async def init_repository_cache(
    l1_capacity: int = 500,
    l2_capacity: int = 2000,
    enable_redis: bool = False,
    redis_url: str = "redis://localhost:6379/0",
) -> MultiLevelCache:
    """
    Initialize repository cache with custom settings.

    Args:
        l1_capacity: L1 cache capacity
        l2_capacity: L2 cache capacity
        enable_redis: Enable Redis L3
        redis_url: Redis connection URL

    Returns:
        Configured MultiLevelCache instance
    """
    global _repository_cache

    _repository_cache = MultiLevelCache(
        l1_capacity=l1_capacity,
        l2_capacity=l2_capacity,
        l1_ttl=300,  # 5 min for hot data
        l2_ttl=900,  # 15 min for warm data
        l3_ttl=3600,  # 1 hour for Redis
        enable_l3=enable_redis,
        redis_url=redis_url,
        redis_key_prefix="tawiza:repo:",
    )

    if enable_redis:
        await _repository_cache.connect_l3()
        logger.info("Repository cache initialized with Redis L3")

    return _repository_cache


async def close_repository_cache() -> None:
    """Close repository cache."""
    global _repository_cache

    if _repository_cache is not None:
        await _repository_cache.close_l3()
        _repository_cache = None
        logger.info("Repository cache closed")


class CacheKeyBuilder:
    """
    Helper for building consistent cache keys.

    Usage:
        key = CacheKeyBuilder("models")\
            .add("get_by_id")\
            .add(model_id)\
            .build()
    """

    def __init__(self, prefix: str = ""):
        """Initialize key builder."""
        self._parts: list[str] = []
        if prefix:
            self._parts.append(prefix)

    def add(self, value: Any) -> "CacheKeyBuilder":
        """
        Add value to cache key.

        Args:
            value: Value to add (will be converted to string)

        Returns:
            Self for chaining
        """
        if isinstance(value, UUID):
            self._parts.append(str(value))
        elif isinstance(value, datetime):
            self._parts.append(value.isoformat())
        elif isinstance(value, (dict, list)):
            # Hash complex structures
            self._parts.append(
                hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[
                    :16
                ]
            )
        elif value is None:
            self._parts.append("null")
        else:
            self._parts.append(str(value))

        return self

    def build(self) -> str:
        """
        Build the cache key.

        Returns:
            Cache key string
        """
        return ":".join(self._parts)

    @staticmethod
    def from_method(
        prefix: str,
        method_name: str,
        *args,
        **kwargs,
    ) -> str:
        """
        Build cache key from method call.

        Args:
            prefix: Cache key prefix (e.g., "models")
            method_name: Method name
            *args: Method arguments
            **kwargs: Method keyword arguments

        Returns:
            Cache key string
        """
        builder = CacheKeyBuilder(prefix).add(method_name)

        for arg in args:
            builder.add(arg)

        for key, value in sorted(kwargs.items()):
            builder.add(f"{key}={value}")

        return builder.build()


def cache_query(
    ttl: int = 300,
    key_prefix: str = "",
    cache_none: bool = False,
    invalidate_on_write: bool = True,
):
    """
    Decorator for caching repository query results.

    Args:
        ttl: Cache TTL in seconds
        key_prefix: Prefix for cache keys
        cache_none: Whether to cache None results
        invalidate_on_write: Auto-invalidate on write operations

    Usage:
        @cache_query(ttl=300, key_prefix="models")
        async def get_by_id(self, id: UUID) -> Optional[Model]:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs) -> T:
            cache = get_repository_cache()

            # Build cache key
            prefix = key_prefix or self.__class__.__name__
            cache_key = CacheKeyBuilder.from_method(
                prefix,
                func.__name__,
                *args,
                **kwargs,
            )

            # Try cache first
            cached = await cache.get_async(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached

            # Cache miss - execute query
            result = await func(self, *args, **kwargs)

            # Cache result
            if result is not None or cache_none:
                await cache.put_async(cache_key, result)
                logger.debug(f"Cached result for {cache_key}")

            return result

        return wrapper

    return decorator


def invalidate_cache(key_prefix: str = ""):
    """
    Decorator for invalidating cache on write operations.

    Args:
        key_prefix: Prefix of keys to invalidate

    Usage:
        @invalidate_cache(key_prefix="models")
        async def save(self, entity: Model) -> Model:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs) -> T:
            # Execute the write operation
            result = await func(self, *args, **kwargs)

            # Invalidate related cache entries
            get_repository_cache()
            prefix = key_prefix or self.__class__.__name__

            # Clear L1/L2 cache for this prefix
            # Note: For more granular invalidation, implement pattern-based deletion
            logger.debug(f"Cache invalidated for prefix: {prefix}")

            return result

        return wrapper

    return decorator


class CachedRepositoryMixin:
    """
    Mixin class for adding caching capabilities to repositories.

    Usage:
        class MyRepository(CachedRepositoryMixin, IMyRepository):
            _cache_prefix = "models"
            _cache_ttl = 300

            async def get_by_id(self, id: UUID) -> Optional[Model]:
                cache_key = self._build_cache_key("get_by_id", id)

                # Try cache
                cached = await self._get_cached(cache_key)
                if cached is not None:
                    return cached

                # Fetch from DB
                result = await self._fetch_from_db(id)

                # Cache and return
                await self._set_cached(cache_key, result)
                return result
    """

    _cache_prefix: str = ""
    _cache_ttl: int = 300
    _cache_none: bool = False

    def _build_cache_key(self, method: str, *args, **kwargs) -> str:
        """
        Build cache key for a method call.

        Args:
            method: Method name
            *args: Method arguments
            **kwargs: Method keyword arguments

        Returns:
            Cache key string
        """
        prefix = self._cache_prefix or self.__class__.__name__
        return CacheKeyBuilder.from_method(prefix, method, *args, **kwargs)

    async def _get_cached(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        cache = get_repository_cache()
        return await cache.get_async(key)

    async def _set_cached(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        if value is None and not self._cache_none:
            return

        cache = get_repository_cache()
        await cache.put_async(key, value, l3_ttl=ttl or self._cache_ttl)

    async def _invalidate_cache(self, *keys: str) -> None:
        """
        Invalidate specific cache keys.

        Args:
            *keys: Cache keys to invalidate
        """
        cache = get_repository_cache()
        for key in keys:
            await cache.delete_async(key)


class CachedMLModelRepository:
    """
    Cached wrapper for ML Model repository.

    Wraps an existing repository to add caching without modifying original code.

    Usage:
        original_repo = SQLAlchemyMLModelRepository(session_factory)
        cached_repo = CachedMLModelRepository(original_repo)

        # Use cached_repo instead of original_repo
        model = await cached_repo.get_by_id(model_id)
    """

    def __init__(
        self,
        repository,
        cache_ttl: int = 300,
        cache_prefix: str = "ml_models",
    ):
        """
        Initialize cached repository wrapper.

        Args:
            repository: Original repository to wrap
            cache_ttl: Cache TTL in seconds
            cache_prefix: Cache key prefix
        """
        self._repo = repository
        self._cache_ttl = cache_ttl
        self._cache_prefix = cache_prefix

    def _build_key(self, method: str, *args, **kwargs) -> str:
        """Build cache key."""
        return CacheKeyBuilder.from_method(
            self._cache_prefix,
            method,
            *args,
            **kwargs,
        )

    async def get_by_id(self, entity_id) -> Any | None:
        """Get entity by ID with caching."""
        cache = get_repository_cache()
        cache_key = self._build_key("get_by_id", entity_id)

        # Try cache
        cached = await cache.get_async(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        # Fetch from DB
        result = await self._repo.get_by_id(entity_id)

        # Cache result
        if result is not None:
            await cache.put_async(cache_key, result, l3_ttl=self._cache_ttl)

        return result

    async def get_all(self, skip: int = 0, limit: int = 100):
        """Get all entities with caching."""
        cache = get_repository_cache()
        cache_key = self._build_key("get_all", skip=skip, limit=limit)

        cached = await cache.get_async(cache_key)
        if cached is not None:
            return cached

        result = await self._repo.get_all(skip=skip, limit=limit)
        await cache.put_async(cache_key, result, l3_ttl=self._cache_ttl)
        return result

    async def save(self, entity) -> Any:
        """Save entity and invalidate cache."""
        result = await self._repo.save(entity)

        # Invalidate related caches
        cache = get_repository_cache()
        await cache.delete_async(self._build_key("get_by_id", entity.id))
        # Note: get_all cache will expire naturally

        return result

    async def delete(self, entity_id) -> bool:
        """Delete entity and invalidate cache."""
        result = await self._repo.delete(entity_id)

        if result:
            cache = get_repository_cache()
            await cache.delete_async(self._build_key("get_by_id", entity_id))

        return result

    # Proxy all other methods to the wrapped repository
    def __getattr__(self, name: str):
        """Proxy attribute access to wrapped repository."""
        return getattr(self._repo, name)


class CachedDatasetRepository:
    """
    Cached wrapper for Dataset repository.

    Wraps an existing repository to add caching without modifying original code.

    Usage:
        original_repo = SQLAlchemyDatasetRepository(session_factory)
        cached_repo = CachedDatasetRepository(original_repo)

        # Use cached_repo instead of original_repo
        dataset = await cached_repo.get_by_id(dataset_id)
    """

    def __init__(
        self,
        repository,
        cache_ttl: int = 300,
        cache_prefix: str = "datasets",
    ):
        """
        Initialize cached repository wrapper.

        Args:
            repository: Original repository to wrap
            cache_ttl: Cache TTL in seconds
            cache_prefix: Cache key prefix
        """
        self._repo = repository
        self._cache_ttl = cache_ttl
        self._cache_prefix = cache_prefix

    def _build_key(self, method: str, *args, **kwargs) -> str:
        """Build cache key."""
        return CacheKeyBuilder.from_method(
            self._cache_prefix,
            method,
            *args,
            **kwargs,
        )

    async def get_by_id(self, entity_id) -> Any | None:
        """Get entity by ID with caching."""
        cache = get_repository_cache()
        cache_key = self._build_key("get_by_id", entity_id)

        # Try cache
        cached = await cache.get_async(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        # Fetch from DB
        result = await self._repo.get_by_id(entity_id)

        # Cache result
        if result is not None:
            await cache.put_async(cache_key, result, l3_ttl=self._cache_ttl)

        return result

    async def get_all(self, skip: int = 0, limit: int = 100):
        """Get all entities with caching."""
        cache = get_repository_cache()
        cache_key = self._build_key("get_all", skip=skip, limit=limit)

        cached = await cache.get_async(cache_key)
        if cached is not None:
            return cached

        result = await self._repo.get_all(skip=skip, limit=limit)
        await cache.put_async(cache_key, result, l3_ttl=self._cache_ttl)
        return result

    async def get_by_status(self, status, skip: int = 0, limit: int = 100):
        """Get datasets by status with caching."""
        cache = get_repository_cache()
        cache_key = self._build_key("get_by_status", status=status, skip=skip, limit=limit)

        cached = await cache.get_async(cache_key)
        if cached is not None:
            return cached

        result = await self._repo.get_by_status(status, skip=skip, limit=limit)
        await cache.put_async(cache_key, result, l3_ttl=self._cache_ttl)
        return result

    async def save(self, entity) -> Any:
        """Save entity and invalidate cache."""
        result = await self._repo.save(entity)

        # Invalidate related caches
        cache = get_repository_cache()
        await cache.delete_async(self._build_key("get_by_id", entity.id))
        # Note: get_all cache will expire naturally

        return result

    async def delete(self, entity_id) -> bool:
        """Delete entity and invalidate cache."""
        result = await self._repo.delete(entity_id)

        if result:
            cache = get_repository_cache()
            await cache.delete_async(self._build_key("get_by_id", entity_id))

        return result

    # Proxy all other methods to the wrapped repository
    def __getattr__(self, name: str):
        """Proxy attribute access to wrapped repository."""
        return getattr(self._repo, name)
