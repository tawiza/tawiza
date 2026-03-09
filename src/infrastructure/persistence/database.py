"""Database configuration and session management.

This module provides:
- Async database engine with connection pooling
- Session management with automatic commit/rollback
- Slow query logging and monitoring
- Health checks and pool statistics
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import Pool

from src.infrastructure.config.settings import Settings, get_settings

# Declarative base for SQLAlchemy models
Base = declarative_base()

# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Slow query threshold (in seconds)
SLOW_QUERY_THRESHOLD = 1.0

# Query statistics
_query_stats = {
    "total_queries": 0,
    "slow_queries": 0,
    "total_time": 0.0,
    "errors": 0,
}


def _setup_query_logging(sync_engine: Engine) -> None:
    """Setup SQLAlchemy event listeners for query logging.

    Args:
        sync_engine: Synchronous engine (underlying the async engine)
    """

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query start time."""
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log slow queries and update statistics."""
        global _query_stats

        start_time = conn.info["query_start_time"].pop()
        duration = time.time() - start_time

        _query_stats["total_queries"] += 1
        _query_stats["total_time"] += duration

        # Log slow queries
        if duration >= SLOW_QUERY_THRESHOLD:
            _query_stats["slow_queries"] += 1

            # Truncate long statements
            stmt_preview = statement[:500] + "..." if len(statement) > 500 else statement

            logger.warning(
                f"Slow query detected ({duration:.3f}s)",
                extra={
                    "duration_seconds": duration,
                    "statement": stmt_preview,
                    "parameters": str(parameters)[:200] if parameters else None,
                },
            )

    @event.listens_for(sync_engine, "handle_error")
    def handle_error(exception_context):
        """Log database errors."""
        global _query_stats
        _query_stats["errors"] += 1

        logger.error(
            f"Database error: {exception_context.original_exception}",
            extra={
                "statement": str(exception_context.statement)[:500]
                if exception_context.statement
                else None,
            },
        )


def _setup_pool_logging(pool: Pool) -> None:
    """Setup connection pool event listeners.

    Args:
        pool: SQLAlchemy connection pool
    """

    @event.listens_for(pool, "checkout")
    def on_checkout(dbapi_conn, connection_record, connection_proxy):
        """Log connection checkout from pool."""
        logger.debug(
            "Connection checked out from pool",
            extra={"pool_size": pool.size(), "checked_out": pool.checkedout()},
        )

    @event.listens_for(pool, "checkin")
    def on_checkin(dbapi_conn, connection_record):
        """Log connection return to pool."""
        logger.debug(
            "Connection returned to pool",
            extra={"pool_size": pool.size(), "checked_out": pool.checkedout()},
        )

    @event.listens_for(pool, "connect")
    def on_connect(dbapi_conn, connection_record):
        """Log new connection creation."""
        logger.info("New database connection created")

    @event.listens_for(pool, "invalidate")
    def on_invalidate(dbapi_conn, connection_record, exception):
        """Log connection invalidation."""
        logger.warning(
            f"Connection invalidated: {exception}",
            extra={"exception": str(exception)},
        )


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Get or create the database engine.

    Args:
        settings: Application settings (uses default if not provided)

    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    global _engine

    if _engine is None:
        if settings is None:
            settings = get_settings()

        # Create async engine with optimized settings
        _engine = create_async_engine(
            str(settings.database.url),
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_timeout=30,  # Wait max 30s for connection
            echo=settings.database.echo,
            future=True,
        )

        # Setup logging on the underlying sync engine
        sync_engine = _engine.sync_engine
        _setup_query_logging(sync_engine)
        _setup_pool_logging(sync_engine.pool)

        logger.info(
            "Database engine created",
            extra={
                "url": str(settings.database.url).split("@")[-1],  # Hide credentials
                "pool_size": settings.database.pool_size,
                "max_overflow": settings.database.max_overflow,
            },
        )

    return _engine


def get_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory.

    Args:
        settings: Application settings (uses default if not provided)

    Returns:
        Session factory for creating database sessions
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Session factory created")

    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get a database session.

    Yields:
        AsyncSession: Database session

    Example:
        >>> async with get_session() as session:
        ...     result = await session.execute(query)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for context manager
get_async_session = get_session


async def init_db(settings: Settings | None = None) -> None:
    """Initialize the database.

    Creates all tables if they don't exist.

    Args:
        settings: Application settings (uses default if not provided)
    """
    engine = get_engine(settings)

    # Import all models to register them with Base
    # This must be done before create_all()
    from src.infrastructure.persistence.models import (  # noqa: F401
        conversation_model,
        dataset_model,
        decision_models,
        ml_model,
        scheduled_analysis_model,
        training_job_model,
        user_model,
        web_snapshot_model,
    )

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close the database connection.

    Should be called during application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

        logger.info("Database connection closed")


# Alias for backward compatibility
close_engine = close_db


async def health_check() -> dict:
    """Perform database health check.

    Returns:
        Dictionary with health status and pool statistics
    """
    try:
        engine = get_engine()

        # Test connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Get pool statistics
        pool = engine.sync_engine.pool
        pool_stats = {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalidatedcount if hasattr(pool, "invalidatedcount") else 0,
        }

        return {
            "status": "healthy",
            "pool": pool_stats,
            "query_stats": get_query_stats(),
        }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


def get_query_stats() -> dict:
    """Get query execution statistics.

    Returns:
        Dictionary with query statistics
    """
    global _query_stats

    avg_time = (
        _query_stats["total_time"] / _query_stats["total_queries"]
        if _query_stats["total_queries"] > 0
        else 0.0
    )

    return {
        **_query_stats,
        "avg_query_time": avg_time,
        "slow_query_threshold": SLOW_QUERY_THRESHOLD,
    }


def reset_query_stats() -> None:
    """Reset query statistics (useful for testing)."""
    global _query_stats
    _query_stats = {
        "total_queries": 0,
        "slow_queries": 0,
        "total_time": 0.0,
        "errors": 0,
    }


def get_pool_status() -> dict:
    """Get connection pool status.

    Returns:
        Dictionary with pool status or None if engine not initialized
    """
    global _engine

    if _engine is None:
        return {"status": "not_initialized"}

    pool = _engine.sync_engine.pool

    return {
        "size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session

    Example:
        >>> @router.get("/models")
        >>> async def list_models(session: AsyncSession = Depends(get_db_session)):
        ...     result = await session.execute(select(MLModelDB))
        ...     return result.scalars().all()
    """
    async with get_session() as session:
        yield session
