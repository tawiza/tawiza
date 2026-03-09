"""Circuit Breaker pattern for resilient data source access.

Inspired by World Monitor's circuit breaker implementation.
Provides per-source failure tracking, cooldown periods,
and stale-while-revalidate caching.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


class BreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures exceeded, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class BreakerConfig:
    """Configuration for a circuit breaker."""

    name: str
    max_failures: int = 2  # Failures before opening
    cooldown_seconds: float = 300  # 5 minutes cooldown
    cache_ttl_seconds: float = 600  # 10 minutes cache
    timeout_seconds: float = 30.0  # Request timeout


@dataclass
class BreakerStats:
    """Statistics for a circuit breaker."""

    name: str
    state: BreakerState
    failure_count: int
    last_failure_at: float | None
    last_success_at: float | None
    cooldown_remaining: float
    total_requests: int = 0
    total_failures: int = 0
    total_cache_hits: int = 0


@dataclass
class CacheEntry:
    """Cached data with timestamp."""

    data: Any
    timestamp: float
    is_fresh: bool = True


class CircuitBreaker:
    """Async circuit breaker with stale-while-revalidate.

    Usage:
        breaker = CircuitBreaker(BreakerConfig(name="rss_lemonde"))

        result = await breaker.execute(
            fn=lambda: fetch_feed("https://lemonde.fr/rss"),
            default=[],
        )

    States:
        CLOSED → OPEN (after max_failures consecutive failures)
        OPEN → HALF_OPEN (after cooldown_seconds)
        HALF_OPEN → CLOSED (on success) or OPEN (on failure)
    """

    def __init__(self, config: BreakerConfig):
        self.config = config
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_at: float | None = None
        self._last_success_at: float | None = None
        self._cooldown_until: float = 0
        self._cache: CacheEntry | None = None
        self._total_requests = 0
        self._total_failures = 0
        self._total_cache_hits = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> BreakerState:
        """Current state, auto-transitioning from OPEN to HALF_OPEN."""
        if self._state == BreakerState.OPEN:
            if time.monotonic() >= self._cooldown_until:
                self._state = BreakerState.HALF_OPEN
        return self._state

    @property
    def is_available(self) -> bool:
        """Whether the breaker allows requests."""
        return self.state != BreakerState.OPEN

    @property
    def cooldown_remaining(self) -> float:
        """Seconds remaining in cooldown (0 if not in cooldown)."""
        if self._state != BreakerState.OPEN:
            return 0
        return max(0, self._cooldown_until - time.monotonic())

    def _record_success(self, data: Any) -> None:
        """Record a successful call."""
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_success_at = time.monotonic()
        self._cache = CacheEntry(data=data, timestamp=time.monotonic())

    def _record_failure(self, error: str | None = None) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_at = time.monotonic()

        if self._failure_count >= self.config.max_failures:
            self._state = BreakerState.OPEN
            self._cooldown_until = time.monotonic() + self.config.cooldown_seconds
            logger.warning(
                f"[CircuitBreaker:{self.config.name}] OPEN — "
                f"{self._failure_count} failures, "
                f"cooldown {self.config.cooldown_seconds}s"
                f"{f' — {error}' if error else ''}"
            )

    def _get_cached(self) -> Any | None:
        """Get cached data if fresh."""
        if self._cache is None:
            return None
        age = time.monotonic() - self._cache.timestamp
        if age < self.config.cache_ttl_seconds:
            return self._cache.data
        return None

    def _get_stale(self) -> Any | None:
        """Get stale cached data (expired TTL but still available)."""
        if self._cache is None:
            return None
        return self._cache.data

    async def execute(
        self,
        fn: Callable[[], Any],
        default: T = None,
    ) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            fn: Async callable to execute
            default: Default value if all fallbacks fail

        Returns:
            Result from fn, cache, or default
        """
        async with self._lock:
            self._total_requests += 1

            # 1. Check fresh cache first
            cached = self._get_cached()
            if cached is not None:
                self._total_cache_hits += 1
                return cached

            # 2. If breaker is OPEN, return stale or default
            if not self.is_available:
                stale = self._get_stale()
                if stale is not None:
                    logger.debug(
                        f"[CircuitBreaker:{self.config.name}] "
                        f"Serving stale cache ({self.cooldown_remaining:.0f}s remaining)"
                    )
                    self._total_cache_hits += 1
                    return stale
                return default

            # 3. If we have stale cache, use stale-while-revalidate
            stale = self._get_stale()
            if stale is not None:
                # Return stale immediately, refresh in background
                asyncio.create_task(self._background_refresh(fn))
                self._total_cache_hits += 1
                return stale

        # 4. No cache at all — must fetch (blocking)
        try:
            result = await asyncio.wait_for(
                fn() if asyncio.iscoroutinefunction(fn) else asyncio.to_thread(fn),
                timeout=self.config.timeout_seconds,
            )
            async with self._lock:
                self._record_success(result)
            return result
        except Exception as e:
            async with self._lock:
                self._record_failure(str(e))
            logger.error(f"[CircuitBreaker:{self.config.name}] Failed: {e}")
            return default

    async def _background_refresh(self, fn: Callable[[], Any]) -> None:
        """Refresh cache in background (fire-and-forget)."""
        try:
            result = await asyncio.wait_for(
                fn() if asyncio.iscoroutinefunction(fn) else asyncio.to_thread(fn),
                timeout=self.config.timeout_seconds,
            )
            async with self._lock:
                self._record_success(result)
        except Exception as e:
            async with self._lock:
                self._record_failure(str(e))
            logger.debug(f"[CircuitBreaker:{self.config.name}] Background refresh failed: {e}")

    def stats(self) -> BreakerStats:
        """Get current statistics."""
        return BreakerStats(
            name=self.config.name,
            state=self.state,
            failure_count=self._failure_count,
            last_failure_at=self._last_failure_at,
            last_success_at=self._last_success_at,
            cooldown_remaining=self.cooldown_remaining,
            total_requests=self._total_requests,
            total_failures=self._total_failures,
            total_cache_hits=self._total_cache_hits,
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._cooldown_until = 0
        logger.info(f"[CircuitBreaker:{self.config.name}] Manually reset")


class CircuitBreakerRegistry:
    """Global registry for all circuit breakers.

    Usage:
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("lemonde", BreakerConfig(...))
        all_stats = registry.all_stats()
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(self, name: str, config: BreakerConfig | None = None) -> CircuitBreaker:
        """Get existing breaker or create a new one."""
        if name not in self._breakers:
            if config is None:
                config = BreakerConfig(name=name)
            self._breakers[name] = CircuitBreaker(config)
        return self._breakers[name]

    def all_stats(self) -> list[BreakerStats]:
        """Get stats for all breakers."""
        return [b.stats() for b in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all breakers."""
        for b in self._breakers.values():
            b.reset()

    @property
    def open_breakers(self) -> list[str]:
        """Get names of all open breakers."""
        return [name for name, b in self._breakers.items() if b.state == BreakerState.OPEN]


# Global singleton
breaker_registry = CircuitBreakerRegistry()
