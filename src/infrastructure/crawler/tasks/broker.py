"""Dramatiq broker configuration for distributed crawling.

Uses Redis as the message broker for reliable task distribution.
Includes middleware for:
- Rate limiting
- Prometheus metrics
- Retry handling
- Age limiting
"""

import os
from typing import Any

from loguru import logger

# Lazy imports to avoid startup issues if dramatiq not installed
_dramatiq = None
_broker = None


def _get_dramatiq():
    """Lazy load dramatiq."""
    global _dramatiq
    if _dramatiq is None:
        try:
            import dramatiq

            _dramatiq = dramatiq
        except ImportError:
            logger.warning("dramatiq not installed. Run: pip install dramatiq[redis]")
    return _dramatiq


def _create_broker():
    """Create and configure the Dramatiq broker."""
    dramatiq = _get_dramatiq()
    if dramatiq is None:
        return None

    try:
        from dramatiq.brokers.redis import RedisBroker
        from dramatiq.middleware import (
            AgeLimit,
            Callbacks,
            Pipelines,
            Retries,
            TimeLimit,
        )
    except ImportError as e:
        logger.error(f"Failed to import dramatiq components: {e}")
        return None

    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Strip password from URL for logging
    log_url = redis_url
    if "@" in redis_url:
        parts = redis_url.split("@")
        log_url = f"redis://***@{parts[-1]}"

    logger.info(f"Initializing Dramatiq broker with Redis: {log_url}")

    try:
        # Create broker with middleware
        broker = RedisBroker(url=redis_url)

        # Add middleware
        broker.add_middleware(AgeLimit())
        broker.add_middleware(TimeLimit())
        broker.add_middleware(Callbacks())
        broker.add_middleware(Pipelines())
        broker.add_middleware(Retries(max_retries=3, min_backoff=1000, max_backoff=60000))

        # Try to add Prometheus middleware if available
        try:
            from dramatiq.middleware.prometheus import Prometheus

            broker.add_middleware(Prometheus())
            logger.debug("Prometheus middleware enabled for Dramatiq")
        except ImportError:
            pass

        # Set as default broker
        dramatiq.set_broker(broker)

        logger.info("Dramatiq broker initialized successfully")
        return broker

    except Exception as e:
        logger.error(f"Failed to create Dramatiq broker: {e}")
        return None


def init_broker() -> Any:
    """Initialize and return the Dramatiq broker.

    Returns:
        Configured RedisBroker instance or None if unavailable
    """
    global _broker
    if _broker is None:
        _broker = _create_broker()
    return _broker


def get_broker() -> Any:
    """Get the current broker instance.

    Returns:
        Current broker or None if not initialized
    """
    global _broker
    return _broker


# Alias for import convenience
dramatiq_broker = init_broker


# Rate limiter for crawling tasks
_rate_limiter = None


def get_rate_limiter(limit: int = 10, key: str = "crawl-limiter"):
    """Get or create a rate limiter for crawling.

    Args:
        limit: Maximum concurrent requests
        key: Limiter key name

    Returns:
        ConcurrentRateLimiter or None if dramatiq unavailable
    """
    global _rate_limiter

    if _rate_limiter is not None:
        return _rate_limiter

    dramatiq = _get_dramatiq()
    if dramatiq is None:
        return None

    try:
        from dramatiq.rate_limits import ConcurrentRateLimiter
        from dramatiq.rate_limits.backends import RedisBackend

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        backend = RedisBackend(url=redis_url)

        _rate_limiter = ConcurrentRateLimiter(backend, key, limit=limit)
        logger.debug(f"Created rate limiter: {key} (limit={limit})")
        return _rate_limiter

    except Exception as e:
        logger.warning(f"Failed to create rate limiter: {e}")
        return None


class MockBroker:
    """Mock broker for when Dramatiq is not available.

    Executes tasks synchronously for development/testing.
    """

    def __init__(self):
        self.actors = {}

    def actor(self, fn=None, **options):
        """Decorator to register an actor."""

        def decorator(func):
            self.actors[func.__name__] = func
            # Make it callable as sync
            func.send = lambda *args, **kwargs: func(*args, **kwargs)
            func.send_with_options = lambda *args, **kwargs: func(*args, **kwargs.get("args", ()))
            return func

        if fn is not None:
            return decorator(fn)
        return decorator


def get_mock_broker() -> MockBroker:
    """Get a mock broker for sync execution."""
    return MockBroker()


# Initialize on module load if Redis is available
try:
    init_broker()
except Exception as e:
    logger.warning(f"Broker init deferred: {e}")
