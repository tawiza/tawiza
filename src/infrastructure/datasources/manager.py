"""DataSourceManager - Facade for all data sources."""

from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.datasources.base import (
    DataSourceAdapter,
    SyncStatus,
)
from src.infrastructure.datasources.cache.base import (
    CacheProtocol,
    CacheStats,
    cache_key,
)


class DataSourceManager:
    """Unified interface for all data sources.

    This facade coordinates multiple adapters and provides
    a single API for searching, retrieving, and syncing data.

    Usage:
        manager = DataSourceManager()
        manager.register(SireneAdapter(...))
        manager.register(BodaccAdapter(...))

        # Search all sources
        results = await manager.search({"query": "IA Lille"})

        # Get specific enterprise (tries all sources)
        enterprise = await manager.get_enterprise("12345678901234")

        # With caching enabled
        from src.infrastructure.datasources.cache import HybridCache
        cache = HybridCache()
        await cache.initialize()
        manager = DataSourceManager(cache=cache)
    """

    def __init__(self, cache: CacheProtocol | None = None):
        self._adapters: dict[str, DataSourceAdapter] = {}
        self._cache = cache

    @property
    def adapters(self) -> dict[str, DataSourceAdapter]:
        """Get all registered adapters."""
        return self._adapters

    def register(self, adapter: DataSourceAdapter) -> None:
        """Register a data source adapter.

        Args:
            adapter: Adapter implementing DataSourceAdapter protocol
        """
        self._adapters[adapter.name] = adapter
        logger.info(f"Registered data source adapter: {adapter.name}")

    def unregister(self, name: str) -> None:
        """Unregister an adapter by name."""
        if name in self._adapters:
            del self._adapters[name]
            logger.info(f"Unregistered data source adapter: {name}")

    async def search(
        self,
        query: dict[str, Any],
        sources: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Search across multiple data sources.

        Args:
            query: Search parameters
            sources: List of adapter names to search (None = all)
            use_cache: Whether to use cache (default True)

        Returns:
            Combined results from all sources
        """
        adapters_to_search = (
            [self._adapters[s] for s in sources if s in self._adapters]
            if sources
            else list(self._adapters.values())
        )

        all_results = []
        for adapter in adapters_to_search:
            try:
                # Try cache first
                key = cache_key(adapter.name, "search", query)
                if use_cache and self._cache:
                    cached = await self._cache.get(key)
                    if cached is not None:
                        logger.debug(f"Cache hit: {adapter.name} search")
                        all_results.extend(cached)
                        continue

                # Fetch from source
                results = await adapter.search(query)
                # Tag results with source
                for r in results:
                    r["_source"] = adapter.name

                # Store in cache
                if use_cache and self._cache and results:
                    await self._cache.set(key, results)

                all_results.extend(results)
            except Exception as e:
                logger.error(f"Search failed for {adapter.name}: {e}")

        return all_results

    async def get_enterprise(
        self, siret: str, use_cache: bool = True
    ) -> dict[str, Any] | None:
        """Get enterprise data, trying all sources.

        Args:
            siret: Enterprise SIRET number
            use_cache: Whether to use cache (default True)

        Returns:
            Enterprise data or None if not found
        """
        for adapter in self._adapters.values():
            try:
                # Try cache first
                key = cache_key(adapter.name, "get_by_id", {"siret": siret})
                if use_cache and self._cache:
                    cached = await self._cache.get(key)
                    if cached is not None:
                        logger.debug(f"Cache hit: {adapter.name} get_by_id")
                        return cached

                result = await adapter.get_by_id(siret)
                if result:
                    result["_source"] = adapter.name
                    # Store in cache
                    if use_cache and self._cache:
                        await self._cache.set(key, result)
                    return result
            except Exception as e:
                logger.warning(f"get_by_id failed for {adapter.name}: {e}")

        return None

    async def get_merged_enterprise(self, siret: str) -> dict[str, Any] | None:
        """Get enterprise data merged from all sources.

        Args:
            siret: Enterprise SIRET number

        Returns:
            Merged enterprise data from all available sources
        """
        merged: dict[str, Any] = {"siret": siret, "_sources": []}

        for adapter in self._adapters.values():
            try:
                result = await adapter.get_by_id(siret)
                if result:
                    merged["_sources"].append(adapter.name)
                    # Merge non-None values
                    for key, value in result.items():
                        if value is not None and (
                            key not in merged or merged[key] is None
                        ):
                            merged[key] = value
            except Exception as e:
                logger.warning(f"get_by_id failed for {adapter.name}: {e}")

        return merged if merged["_sources"] else None

    async def status(self) -> dict[str, dict[str, Any]]:
        """Get status of all registered adapters.

        Returns:
            Dict mapping adapter name to status info
        """
        status = {}
        for name, adapter in self._adapters.items():
            try:
                healthy = await adapter.health_check()
                status[name] = {
                    "healthy": healthy,
                    "config": {
                        "rate_limit": adapter.config.rate_limit,
                        "cache_ttl": adapter.config.cache_ttl,
                        "enabled": adapter.config.enabled,
                    },
                }
            except Exception as e:
                status[name] = {
                    "healthy": False,
                    "error": str(e),
                }

        return status

    async def sync_all(self, since: datetime | None = None) -> list[SyncStatus]:
        """Sync all adapters that support it.

        Args:
            since: Only sync records updated after this time

        Returns:
            List of sync statuses
        """
        statuses = []
        for adapter in self._adapters.values():
            try:
                status = await adapter.sync(since)
                statuses.append(status)
            except Exception as e:
                statuses.append(
                    SyncStatus(
                        adapter_name=adapter.name,
                        last_sync=None,
                        records_synced=0,
                        status="failed",
                        error=str(e),
                    )
                )

        return statuses

    # Cache management methods

    @property
    def cache(self) -> CacheProtocol | None:
        """Get the cache instance."""
        return self._cache

    @property
    def cache_enabled(self) -> bool:
        """Check if cache is enabled."""
        return self._cache is not None

    async def cache_stats(self) -> CacheStats | None:
        """Get cache statistics.

        Returns:
            Cache stats or None if cache not enabled
        """
        if self._cache is None:
            return None
        return await self._cache.stats()

    async def invalidate_cache(self, source: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            source: Source name to invalidate (None = all)

        Returns:
            Number of entries cleared
        """
        if self._cache is None:
            return 0

        pattern = f"{source}:*" if source else None
        return await self._cache.clear(pattern)
