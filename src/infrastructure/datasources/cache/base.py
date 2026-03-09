"""Base protocol and utilities for cache implementations."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# Default TTL per data source (in seconds)
DEFAULT_TTL = {
    "bodacc": 86400,      # 24h - legal data, stable
    "boamp": 43200,       # 12h - public markets, updated 2x/day
    "sirene": 604800,     # 7 days - enterprise data, stable
    "rss": 3600,          # 1h - news, frequent updates
    "inpi": 86400,        # 24h - patents/trademarks, stable
    "default": 3600,      # 1h fallback
}


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""

    max_memory_items: int = 1000  # LRU cache size
    sqlite_path: str = ".cache/datasources.db"
    ttl_overrides: dict[str, int] = field(default_factory=dict)
    enabled: bool = True

    def get_ttl(self, source: str) -> int:
        """Get TTL for a specific source."""
        if source in self.ttl_overrides:
            return self.ttl_overrides[source]
        return DEFAULT_TTL.get(source, DEFAULT_TTL["default"])


@dataclass
class CacheStats:
    """Statistics for cache operations."""

    hits: int = 0
    misses: int = 0
    size: int = 0
    memory_items: int = 0
    sqlite_items: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache implementations.

    All cache backends must implement these methods.
    """

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = use default)
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete a specific key from cache.

        Args:
            key: Cache key to delete
        """
        ...

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Optional pattern to match keys (e.g., "bodacc:*")
                    If None, clears all entries.

        Returns:
            Number of entries cleared
        """
        ...

    async def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            Current cache statistics
        """
        ...


def cache_key(adapter: str, method: str, params: dict[str, Any]) -> str:
    """Generate a unique, readable cache key.

    Args:
        adapter: Adapter name (e.g., "bodacc")
        method: Method name (e.g., "search", "get_by_id")
        params: Query parameters

    Returns:
        Cache key string

    Example:
        >>> cache_key("bodacc", "search", {"siren": "123456789"})
        "bodacc:search:siren=123456789"

        >>> cache_key("bodacc", "search", {"nom": "ACME", "limit": 100})
        "bodacc:search:limit=100:nom=ACME"
    """
    # Sort params for consistent key generation
    param_parts = [f"{k}={v}" for k, v in sorted(params.items()) if v is not None]
    param_str = ":".join(param_parts) if param_parts else "_all"

    key = f"{adapter}:{method}:{param_str}"

    # If key is too long, hash the params part
    if len(key) > 200:
        params_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
        key = f"{adapter}:{method}:h_{params_hash}"

    return key


def serialize_value(value: Any) -> str:
    """Serialize a value for storage.

    Args:
        value: Value to serialize

    Returns:
        JSON string
    """
    return json.dumps(value, default=str, ensure_ascii=False)


def deserialize_value(data: str) -> Any:
    """Deserialize a stored value.

    Args:
        data: JSON string

    Returns:
        Deserialized value
    """
    return json.loads(data)
