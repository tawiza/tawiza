"""Base collector with rate limiting, retry, and logging."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx
from loguru import logger


@dataclass
class CollectorConfig:
    """Configuration for a collector."""

    name: str
    source_type: str  # 'api' or 'crawler'
    rate_limit: float = 1.0  # requests per second
    max_retries: int = 3
    timeout: int = 30
    batch_size: int = 100
    enabled: bool = True


@dataclass
class CollectedSignal:
    """A signal collected from a source."""

    source: str
    source_url: str | None = None
    event_date: date | None = None
    code_commune: str | None = None
    code_epci: str | None = None
    code_dept: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    metric_name: str = ""
    metric_value: float | None = None
    signal_type: str = "neutre"  # 'positif', 'negatif', 'neutre'
    confidence: float = 0.5
    raw_data: dict[str, Any] | None = None
    extracted_text: str | None = None
    entities: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return dict(self.__dict__)


class BaseCollector(ABC):
    """Abstract base class for all collectors.

    Features:
    - Rate limiting (token bucket)
    - Retry with exponential backoff
    - Structured logging
    - HTTP client with connection pooling
    """

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self._last_request_time = 0.0
        self._client: httpx.AsyncClient | None = None
        self._stats = {"collected": 0, "errors": 0, "started_at": None}

    @property
    def name(self) -> str:
        return self.config.name

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
                headers={"User-Agent": "Tawiza-Collector/0.1"},
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Apply rate limiting."""
        if self.config.rate_limit <= 0:
            return
        min_interval = 1.0 / self.config.rate_limit
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def _request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response | None:
        """HTTP request with retry and rate limiting."""
        client = await self._get_client()

        for attempt in range(self.config.max_retries):
            await self._rate_limit()
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503):
                    wait = 2**attempt
                    logger.warning(
                        f"[{self.name}] Rate limited ({e.response.status_code}), "
                        f"retry in {wait}s (attempt {attempt + 1}/{self.config.max_retries})"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"[{self.name}] HTTP {e.response.status_code}: {url}")
                    self._stats["errors"] += 1
                    return None
            except httpx.RequestError as e:
                wait = 2**attempt
                logger.warning(
                    f"[{self.name}] Request error: {e}, "
                    f"retry in {wait}s (attempt {attempt + 1}/{self.config.max_retries})"
                )
                await asyncio.sleep(wait)

        logger.error(f"[{self.name}] Max retries exceeded for {url}")
        self._stats["errors"] += 1
        return None

    @abstractmethod
    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect signals from this source.

        Args:
            code_dept: Optional department code to filter by.
            since: Optional date to collect from.

        Returns:
            List of collected signals.
        """
        ...

    async def run(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Run the collector with logging and stats."""
        if not self.config.enabled:
            logger.info(f"[{self.name}] Collector disabled, skipping")
            return []

        self._stats["started_at"] = datetime.now()
        logger.info(f"[{self.name}] Starting collection (dept={code_dept}, since={since})")

        try:
            signals = await self.collect(code_dept=code_dept, since=since)
            self._stats["collected"] += len(signals)
            logger.info(
                f"[{self.name}] Collected {len(signals)} signals "
                f"(total: {self._stats['collected']}, errors: {self._stats['errors']})"
            )
            return signals
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"[{self.name}] Collection failed: {e}")
            return []

    async def close(self) -> None:
        """Cleanup resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
