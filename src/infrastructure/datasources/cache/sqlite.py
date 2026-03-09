"""SQLite-based persistent cache implementation."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

from src.infrastructure.datasources.cache.base import (
    CacheConfig,
    CacheStats,
    deserialize_value,
    serialize_value,
)


class SQLiteCache:
    """SQLite-based persistent cache with TTL support.

    Features:
    - Persistent storage across restarts
    - Per-entry TTL expiration
    - Async operations with aiosqlite
    - Automatic cleanup of expired entries
    - Pattern-based deletion

    Usage:
        cache = SQLiteCache(config)
        await cache.initialize()  # Create tables
        await cache.set("key", {"data": "value"}, ttl=3600)
        result = await cache.get("key")
    """

    def __init__(self, config: CacheConfig | None = None):
        self._config = config or CacheConfig()
        self._db_path = Path(self._config.sqlite_path)
        self._db: aiosqlite.Connection | None = None
        self._hits = 0
        self._misses = 0

    async def initialize(self) -> None:
        """Initialize database and create tables."""
        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(str(self._db_path))

        # Create cache table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                source TEXT
            )
        """)

        # Index for expiration cleanup
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_expires
            ON cache(expires_at)
        """)

        # Index for source-based queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_source
            ON cache(source)
        """)

        await self._db.commit()
        logger.info(f"SQLite cache initialized: {self._db_path}")

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def _ensure_connected(self) -> None:
        """Ensure database is connected."""
        if self._db is None:
            await self.initialize()

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        await self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()

        if row is None:
            self._misses += 1
            return None

        value, expires_at_str = row
        expires_at = datetime.fromisoformat(expires_at_str)

        # Check expiration
        if datetime.utcnow() > expires_at:
            await self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
            await self._db.commit()
            self._misses += 1
            logger.debug(f"SQLite cache expired: {key}")
            return None

        self._hits += 1
        return deserialize_value(value)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        await self._ensure_connected()

        # Determine TTL
        if ttl is None:
            source = key.split(":")[0] if ":" in key else "default"
            ttl = self._config.get_ttl(source)

        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl)
        source = key.split(":")[0] if ":" in key else None

        # Upsert (SQLite 3.24+)
        await self._db.execute("""
            INSERT INTO cache (key, value, expires_at, created_at, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                expires_at = excluded.expires_at,
                created_at = excluded.created_at
        """, (
            key,
            serialize_value(value),
            expires_at.isoformat(),
            now.isoformat(),
            source,
        ))
        await self._db.commit()
        logger.debug(f"SQLite cache set: {key} (TTL: {ttl}s)")

    async def delete(self, key: str) -> None:
        """Delete a specific key from cache.

        Args:
            key: Cache key to delete
        """
        await self._ensure_connected()
        await self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self._db.commit()
        logger.debug(f"SQLite cache deleted: {key}")

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Optional pattern to match (e.g., "bodacc:*")

        Returns:
            Number of entries cleared
        """
        await self._ensure_connected()

        if pattern is None:
            cursor = await self._db.execute("SELECT COUNT(*) FROM cache")
            count = (await cursor.fetchone())[0]
            await self._db.execute("DELETE FROM cache")
            await self._db.commit()
            logger.info(f"SQLite cache cleared: {count} entries")
            return count

        # Pattern matching
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM cache WHERE key LIKE ?",
                (f"{prefix}%",)
            )
            count = (await cursor.fetchone())[0]
            await self._db.execute(
                "DELETE FROM cache WHERE key LIKE ?",
                (f"{prefix}%",)
            )
        else:
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM cache WHERE key = ?",
                (pattern,)
            )
            count = (await cursor.fetchone())[0]
            await self._db.execute(
                "DELETE FROM cache WHERE key = ?",
                (pattern,)
            )

        await self._db.commit()
        logger.info(f"SQLite cache cleared pattern '{pattern}': {count} entries")
        return count

    async def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            Current cache statistics
        """
        await self._ensure_connected()

        # Count non-expired entries
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
            (datetime.utcnow().isoformat(),)
        )
        count = (await cursor.fetchone())[0]

        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            size=count,
            memory_items=0,
            sqlite_items=count,
        )

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        await self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at <= ?",
            (datetime.utcnow().isoformat(),)
        )
        count = (await cursor.fetchone())[0]

        await self._db.execute(
            "DELETE FROM cache WHERE expires_at <= ?",
            (datetime.utcnow().isoformat(),)
        )
        await self._db.commit()

        if count > 0:
            logger.info(f"SQLite cache cleanup: {count} expired entries removed")

        return count

    async def clear_source(self, source: str) -> int:
        """Clear all entries for a specific source.

        Args:
            source: Source name (e.g., "bodacc")

        Returns:
            Number of entries cleared
        """
        await self._ensure_connected()

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM cache WHERE source = ?",
            (source,)
        )
        count = (await cursor.fetchone())[0]

        await self._db.execute(
            "DELETE FROM cache WHERE source = ?",
            (source,)
        )
        await self._db.commit()

        logger.info(f"SQLite cache cleared source '{source}': {count} entries")
        return count
