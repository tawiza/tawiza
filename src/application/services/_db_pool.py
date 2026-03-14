"""Shared asyncpg connection pool for relation services."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from loguru import logger

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql+asyncpg://localhost:5433/tawiza",
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it lazily if needed."""
    global _pool
    if _pool is None or _pool._closed:
        dsn = DB_DSN.replace("+asyncpg", "")
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
        logger.info("asyncpg pool created (min=2, max=10)")
    return _pool


@asynccontextmanager
async def acquire_conn() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the shared pool (context manager)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_pool() -> None:
    """Gracefully close the shared connection pool."""
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
