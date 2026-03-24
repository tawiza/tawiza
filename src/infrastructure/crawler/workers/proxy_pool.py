"""Proxy Pool Manager for rotating proxies in crawling operations.

Provides:
- Round-robin proxy rotation
- Failed proxy tracking and exclusion
- Health checking
- Automatic recovery of failed proxies
"""

import asyncio
import contextlib
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger


@dataclass
class ProxyStats:
    """Statistics for a single proxy."""

    url: str
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    last_failure: float = 0.0
    avg_response_time_ms: float = 0.0
    is_healthy: bool = True

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def record_success(self, response_time_ms: float) -> None:
        """Record a successful request."""
        self.success_count += 1
        self.last_used = time.time()
        # Exponential moving average for response time
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = response_time_ms
        else:
            self.avg_response_time_ms = 0.9 * self.avg_response_time_ms + 0.1 * response_time_ms
        self.is_healthy = True

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure = time.time()
        # Mark unhealthy if too many consecutive failures
        if self.failure_count > 3 and self.success_rate < 0.5:
            self.is_healthy = False


@dataclass
class ProxyPoolConfig:
    """Configuration for proxy pool."""

    # Rotation strategy: 'round_robin', 'random', 'weighted'
    strategy: str = "round_robin"

    # Maximum failures before marking proxy as unhealthy
    max_failures: int = 5

    # Time in seconds to wait before retrying unhealthy proxy
    recovery_time: float = 300.0  # 5 minutes

    # Health check interval in seconds
    health_check_interval: float = 60.0

    # Test URL for health checks
    health_check_url: str = "https://httpbin.org/ip"

    # Timeout for health checks in seconds
    health_check_timeout: float = 10.0


class ProxyPoolManager:
    """Manages a pool of proxies with rotation and health tracking.

    Features:
    - Multiple rotation strategies
    - Automatic failure detection
    - Health checking with recovery
    - Performance metrics per proxy
    """

    def __init__(
        self,
        proxies: list[str] | None = None,
        config: ProxyPoolConfig | None = None,
    ) -> None:
        """Initialize the proxy pool.

        Args:
            proxies: List of proxy URLs (http://user:pass@host:port or http://host:port)
            config: Pool configuration
        """
        self.config = config or ProxyPoolConfig()
        self._proxies: dict[str, ProxyStats] = {}
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None

        if proxies:
            for proxy in proxies:
                self.add_proxy(proxy)

    def add_proxy(self, proxy_url: str) -> None:
        """Add a proxy to the pool.

        Args:
            proxy_url: Proxy URL (http://host:port or http://user:pass@host:port)
        """
        if proxy_url not in self._proxies:
            self._proxies[proxy_url] = ProxyStats(url=proxy_url)
            logger.debug(f"Added proxy to pool: {self._mask_proxy(proxy_url)}")

    def remove_proxy(self, proxy_url: str) -> None:
        """Remove a proxy from the pool."""
        if proxy_url in self._proxies:
            del self._proxies[proxy_url]
            logger.debug(f"Removed proxy from pool: {self._mask_proxy(proxy_url)}")

    def _mask_proxy(self, proxy_url: str) -> str:
        """Mask proxy credentials for logging."""
        if "@" in proxy_url:
            parts = proxy_url.split("@")
            return f"***@{parts[-1]}"
        return proxy_url

    @property
    def healthy_proxies(self) -> list[str]:
        """Get list of healthy proxies."""
        now = time.time()
        healthy = []
        for url, stats in self._proxies.items():
            if stats.is_healthy:
                healthy.append(url)
            elif now - stats.last_failure > self.config.recovery_time:
                # Allow retry after recovery time
                healthy.append(url)
        return healthy

    @property
    def pool_size(self) -> int:
        """Total number of proxies in pool."""
        return len(self._proxies)

    @property
    def healthy_count(self) -> int:
        """Number of healthy proxies."""
        return len(self.healthy_proxies)

    async def get_next(self) -> str | None:
        """Get next proxy based on rotation strategy.

        Returns:
            Proxy URL or None if no healthy proxies available
        """
        async with self._lock:
            healthy = self.healthy_proxies

            if not healthy:
                logger.warning("No healthy proxies available")
                return None

            if self.config.strategy == "random":
                return random.choice(healthy)

            elif self.config.strategy == "weighted":
                # Weight by success rate and response time
                weights = []
                for url in healthy:
                    stats = self._proxies[url]
                    # Higher weight = better proxy
                    weight = stats.success_rate * 100
                    if stats.avg_response_time_ms > 0:
                        weight /= stats.avg_response_time_ms / 1000  # Penalize slow proxies
                    weights.append(max(weight, 0.1))

                return random.choices(healthy, weights=weights, k=1)[0]

            else:
                # Round-robin (default)
                self._current_index = self._current_index % len(healthy)
                proxy = healthy[self._current_index]
                self._current_index += 1
                return proxy

    def mark_success(self, proxy_url: str, response_time_ms: float) -> None:
        """Mark a proxy request as successful.

        Args:
            proxy_url: The proxy URL
            response_time_ms: Response time in milliseconds
        """
        if proxy_url in self._proxies:
            self._proxies[proxy_url].record_success(response_time_ms)

    def mark_failed(self, proxy_url: str) -> None:
        """Mark a proxy request as failed.

        Args:
            proxy_url: The proxy URL
        """
        if proxy_url in self._proxies:
            stats = self._proxies[proxy_url]
            stats.record_failure()

            if stats.failure_count >= self.config.max_failures:
                logger.warning(
                    f"Proxy marked unhealthy after {stats.failure_count} failures: "
                    f"{self._mask_proxy(proxy_url)}"
                )

    async def health_check(self, proxy_url: str | None = None) -> dict[str, bool]:
        """Check health of proxy(ies).

        Args:
            proxy_url: Specific proxy to check, or None for all

        Returns:
            Dict mapping proxy URLs to health status
        """
        proxies_to_check = [proxy_url] if proxy_url else list(self._proxies.keys())
        results = {}

        async with httpx.AsyncClient(timeout=self.config.health_check_timeout) as client:
            for proxy in proxies_to_check:
                try:
                    start = time.time()
                    response = await client.get(
                        self.config.health_check_url,
                        proxies={"http://": proxy, "https://": proxy},
                    )
                    elapsed_ms = (time.time() - start) * 1000

                    if response.status_code == 200:
                        self.mark_success(proxy, elapsed_ms)
                        results[proxy] = True
                    else:
                        self.mark_failed(proxy)
                        results[proxy] = False

                except Exception as e:
                    logger.debug(f"Health check failed for {self._mask_proxy(proxy)}: {e}")
                    self.mark_failed(proxy)
                    results[proxy] = False

        return results

    async def start_health_checks(self) -> None:
        """Start periodic health check task."""
        if self._health_check_task is not None:
            return

        async def _health_loop():
            while True:
                await asyncio.sleep(self.config.health_check_interval)
                try:
                    await self.health_check()
                except Exception as e:
                    logger.error(f"Health check error: {e}")

        self._health_check_task = asyncio.create_task(_health_loop())
        logger.info("Started proxy health check task")

    async def stop_health_checks(self) -> None:
        """Stop periodic health check task."""
        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task
            self._health_check_task = None

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Pool statistics including per-proxy metrics
        """
        return {
            "total_proxies": self.pool_size,
            "healthy_proxies": self.healthy_count,
            "strategy": self.config.strategy,
            "proxies": [
                {
                    "url": self._mask_proxy(url),
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "success_rate": round(stats.success_rate * 100, 1),
                    "avg_response_ms": round(stats.avg_response_time_ms, 1),
                    "is_healthy": stats.is_healthy,
                }
                for url, stats in self._proxies.items()
            ],
        }

    def get_proxy_for_httpx(self, proxy_url: str) -> dict[str, str]:
        """Get proxy config formatted for httpx.

        Args:
            proxy_url: Proxy URL

        Returns:
            Dict suitable for httpx proxies parameter
        """
        return {
            "http://": proxy_url,
            "https://": proxy_url,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_health_checks()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_health_checks()


# Singleton instance for global access
_global_proxy_pool: ProxyPoolManager | None = None


def get_proxy_pool() -> ProxyPoolManager:
    """Get or create the global proxy pool instance."""
    global _global_proxy_pool
    if _global_proxy_pool is None:
        _global_proxy_pool = ProxyPoolManager()
    return _global_proxy_pool


def configure_proxy_pool(
    proxies: list[str],
    config: ProxyPoolConfig | None = None,
) -> ProxyPoolManager:
    """Configure the global proxy pool.

    Args:
        proxies: List of proxy URLs
        config: Pool configuration

    Returns:
        Configured ProxyPoolManager instance
    """
    global _global_proxy_pool
    _global_proxy_pool = ProxyPoolManager(proxies, config)
    return _global_proxy_pool
