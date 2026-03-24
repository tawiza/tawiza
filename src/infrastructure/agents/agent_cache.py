"""
Agent Result Cache - Caching for agent execution results.

Provides caching mechanisms for agent results to avoid redundant executions:
- Task-based caching (same task config = same result)
- Time-based expiration
- Result validation before caching
- Integration with MultiLevelCache

Usage:
    cache = AgentResultCache()

    # Check cache before executing
    cache_key = cache.make_key(agent_name, task_config)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Execute agent
    result = await agent.execute_task(task_config)

    # Cache result
    if cache.is_cacheable(result):
        await cache.set(cache_key, result)
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from loguru import logger

from src.infrastructure.caching import MultiLevelCache

T = TypeVar("T")


@dataclass
class CachedAgentResult:
    """Wrapper for cached agent results."""

    result: Any
    agent_name: str
    task_hash: str
    cached_at: datetime
    expires_at: datetime | None
    execution_time_ms: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "result": self.result,
            "agent_name": self.agent_name,
            "task_hash": self.task_hash,
            "cached_at": self.cached_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CachedAgentResult":
        """Create from dictionary."""
        return CachedAgentResult(
            result=data["result"],
            agent_name=data["agent_name"],
            task_hash=data["task_hash"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            expires_at=(datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None),
            execution_time_ms=data["execution_time_ms"],
            metadata=data.get("metadata", {}),
        )


# Default cache configuration per agent type
DEFAULT_AGENT_CACHE_CONFIG = {
    # Data agents - cache for 1 hour (data doesn't change frequently)
    "data": {"ttl": 3600, "cacheable": True},
    # Analysis agents - cache for 30 minutes
    "analysis": {"ttl": 1800, "cacheable": True},
    # Browser agents - don't cache (dynamic web content)
    "browser": {"ttl": 0, "cacheable": False},
    # Chat agents - short cache (conversation context matters)
    "chat": {"ttl": 300, "cacheable": True},
    # Search agents - cache for 15 minutes
    "search": {"ttl": 900, "cacheable": True},
    # Default - 10 minute cache
    "default": {"ttl": 600, "cacheable": True},
}


class AgentResultCache:
    """
    Cache for agent execution results.

    Features:
    - Per-agent-type TTL configuration
    - Task config hashing for cache keys
    - Result validation before caching
    - Multi-level cache backend (L1/L2/L3)
    - Statistics and monitoring

    Usage:
        cache = AgentResultCache()
        await cache.connect()

        # With cache decorator
        @cache.cached("data_agent")
        async def analyze_data(config):
            return await agent.execute(config)

        # Manual caching
        key = cache.make_key("data_agent", config)
        cached = await cache.get(key)
        if not cached:
            result = await agent.execute(config)
            await cache.set(key, result, agent_type="data")
    """

    def __init__(
        self,
        l1_capacity: int = 100,
        l2_capacity: int = 500,
        enable_redis: bool = False,
        redis_url: str = "redis://localhost:6379/0",
        config: dict[str, dict[str, Any]] | None = None,
        result_validator: Callable[[Any], bool] | None = None,
    ):
        """
        Initialize agent result cache.

        Args:
            l1_capacity: L1 cache capacity
            l2_capacity: L2 cache capacity
            enable_redis: Enable Redis L3
            redis_url: Redis connection URL
            config: Per-agent-type cache configuration
            result_validator: Function to validate if result should be cached
        """
        self._config = config or DEFAULT_AGENT_CACHE_CONFIG
        self._result_validator = result_validator or self._default_validator

        self._cache = MultiLevelCache(
            l1_capacity=l1_capacity,
            l2_capacity=l2_capacity,
            l1_ttl=300,
            l2_ttl=900,
            l3_ttl=3600,
            enable_l3=enable_redis,
            redis_url=redis_url,
            redis_key_prefix="tawiza:agent_cache:",
        )

        # Statistics
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_skipped": 0,
            "invalid_results": 0,
            "time_saved_ms": 0.0,
        }

        logger.info(
            f"AgentResultCache initialized: L1={l1_capacity}, L2={l2_capacity}, "
            f"Redis={'enabled' if enable_redis else 'disabled'}"
        )

    async def connect(self) -> bool:
        """Connect to Redis if enabled."""
        return await self._cache.connect_l3()

    async def close(self) -> None:
        """Close cache connections."""
        await self._cache.close_l3()

    def _default_validator(self, result: Any) -> bool:
        """
        Default validator for cacheable results.

        Args:
            result: Agent result to validate

        Returns:
            True if result should be cached
        """
        # Don't cache None results
        if result is None:
            return False

        # Don't cache error results
        if isinstance(result, dict):
            if result.get("error") or result.get("status") == "failed":
                return False

        # Don't cache empty results
        return not (isinstance(result, (list, dict, str)) and len(result) == 0)

    def _get_agent_type(self, agent_name: str) -> str:
        """
        Determine agent type from agent name.

        Args:
            agent_name: Agent name

        Returns:
            Agent type for config lookup
        """
        name_lower = agent_name.lower()

        if "data" in name_lower or "collect" in name_lower or "fetch" in name_lower:
            return "data"
        elif "analy" in name_lower or "process" in name_lower:
            return "analysis"
        elif "browser" in name_lower or "web" in name_lower or "scrape" in name_lower:
            return "browser"
        elif "chat" in name_lower or "converse" in name_lower:
            return "chat"
        elif "search" in name_lower or "find" in name_lower or "query" in name_lower:
            return "search"
        else:
            return "default"

    def _get_ttl(self, agent_name: str) -> int:
        """Get TTL for agent type."""
        agent_type = self._get_agent_type(agent_name)
        config = self._config.get(agent_type, self._config["default"])
        return config.get("ttl", 600)

    def is_cacheable(self, agent_name: str, result: Any = None) -> bool:
        """
        Check if agent results should be cached.

        Args:
            agent_name: Agent name
            result: Optional result to validate

        Returns:
            True if cacheable
        """
        agent_type = self._get_agent_type(agent_name)
        config = self._config.get(agent_type, self._config["default"])

        if not config.get("cacheable", True):
            return False

        return not (result is not None and not self._result_validator(result))

    def make_key(
        self,
        agent_name: str,
        task_config: dict[str, Any],
    ) -> str:
        """
        Generate cache key from agent name and task config.

        Args:
            agent_name: Agent name
            task_config: Task configuration

        Returns:
            Cache key string
        """
        # Create deterministic hash of task config
        config_str = json.dumps(task_config, sort_keys=True, default=str)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]

        return f"{agent_name}:{config_hash}"

    async def get(self, key: str) -> CachedAgentResult | None:
        """
        Get cached result.

        Args:
            key: Cache key

        Returns:
            CachedAgentResult or None
        """
        data = await self._cache.get_async(key)

        if data is not None:
            self._stats["cache_hits"] += 1

            # Reconstruct CachedAgentResult
            if isinstance(data, dict) and "cached_at" in data:
                cached = CachedAgentResult.from_dict(data)
                self._stats["time_saved_ms"] += cached.execution_time_ms
                logger.debug(f"Agent cache hit: {key}")
                return cached
            else:
                # Raw result (backwards compatibility)
                return CachedAgentResult(
                    result=data,
                    agent_name=key.split(":")[0],
                    task_hash=key,
                    cached_at=datetime.utcnow(),
                    expires_at=None,
                    execution_time_ms=0,
                    metadata={},
                )

        self._stats["cache_misses"] += 1
        return None

    async def set(
        self,
        key: str,
        result: Any,
        agent_name: str | None = None,
        execution_time_ms: float = 0,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Cache agent result.

        Args:
            key: Cache key
            result: Result to cache
            agent_name: Agent name (extracted from key if not provided)
            execution_time_ms: Execution time for statistics
            metadata: Additional metadata

        Returns:
            True if cached successfully
        """
        agent_name = agent_name or key.split(":")[0]

        # Validate result
        if not self.is_cacheable(agent_name, result):
            self._stats["invalid_results"] += 1
            return False

        # Check if agent type allows caching
        if not self.is_cacheable(agent_name):
            self._stats["cache_skipped"] += 1
            return False

        ttl = self._get_ttl(agent_name)

        # Wrap result with metadata
        cached = CachedAgentResult(
            result=result,
            agent_name=agent_name,
            task_hash=key,
            cached_at=datetime.utcnow(),
            expires_at=None,  # Handled by cache TTL
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )

        await self._cache.put_async(key, cached.to_dict(), l3_ttl=ttl)
        logger.debug(f"Agent result cached: {key} (TTL: {ttl}s)")
        return True

    async def invalidate(self, key: str) -> bool:
        """Invalidate cached result."""
        return await self._cache.delete_async(key)

    async def invalidate_agent(self, agent_name: str) -> None:
        """Invalidate all cached results for an agent."""
        # Note: This is a simplified version
        # Full implementation would need pattern-based deletion
        logger.info(f"Invalidating cache for agent: {agent_name}")

    async def clear(self) -> None:
        """Clear all cached results."""
        await self._cache.clear_async()
        logger.info("Agent cache cleared")

    def cached(
        self,
        agent_name: str,
        key_func: Callable[..., str] | None = None,
    ):
        """
        Decorator for caching agent method results.

        Args:
            agent_name: Agent name for cache key
            key_func: Custom key function

        Usage:
            @cache.cached("data_agent")
            async def fetch_data(self, config):
                return await self._do_fetch(config)
        """

        def decorator(func):
            import functools
            import time

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Build cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Use first dict arg as task config
                    task_config = None
                    for arg in args[1:]:  # Skip self
                        if isinstance(arg, dict):
                            task_config = arg
                            break
                    if task_config is None:
                        task_config = kwargs

                    cache_key = self.make_key(agent_name, task_config)

                # Try cache
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached.result

                # Execute
                start = time.time()
                result = await func(*args, **kwargs)
                execution_time_ms = (time.time() - start) * 1000

                # Cache result
                await self.set(
                    cache_key,
                    result,
                    agent_name=agent_name,
                    execution_time_ms=execution_time_ms,
                )

                return result

            return wrapper

        return decorator

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = (self._stats["cache_hits"] / total * 100) if total > 0 else 0.0

        return {
            **self._stats,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total,
            "multi_level_stats": self._cache.get_stats(),
        }

    async def health_check(self) -> dict[str, Any]:
        """Health check for cache."""
        return await self._cache.health_check()

    async def __aenter__(self) -> "AgentResultCache":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Global agent cache instance
_agent_cache: AgentResultCache | None = None


async def get_agent_cache(
    enable_redis: bool = False,
    redis_url: str = "redis://localhost:6379/0",
    **kwargs,
) -> AgentResultCache:
    """Get or create global agent cache instance."""
    global _agent_cache

    if _agent_cache is None:
        _agent_cache = AgentResultCache(
            enable_redis=enable_redis,
            redis_url=redis_url,
            **kwargs,
        )
        await _agent_cache.connect()

    return _agent_cache


async def close_agent_cache() -> None:
    """Close global agent cache instance."""
    global _agent_cache

    if _agent_cache is not None:
        await _agent_cache.close()
        _agent_cache = None
