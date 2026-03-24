"""Base classes and protocols for data source adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

import httpx
from loguru import logger


@dataclass
class AdapterConfig:
    """Configuration for a data source adapter."""

    name: str
    base_url: str
    rate_limit: int = 60  # requests per minute
    cache_ttl: int = 3600  # seconds (1 hour default)
    timeout: float = 30.0  # seconds
    enabled: bool = True


@dataclass
class SyncStatus:
    """Status of a sync operation."""

    adapter_name: str
    last_sync: datetime | None
    records_synced: int
    status: str  # 'success', 'failed', 'running', 'never'
    error: str | None = None


@runtime_checkable
class DataSourceAdapter(Protocol):
    """Protocol for all data source adapters.

    Each adapter must implement these methods to be used
    by the DataSourceManager.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this adapter."""
        ...

    @property
    def config(self) -> AdapterConfig:
        """Adapter configuration."""
        ...

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search for records matching the query.

        Args:
            query: Search parameters (adapter-specific)

        Returns:
            List of matching records
        """
        ...

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get a single record by its ID.

        Args:
            id: Record identifier (e.g., SIRET for enterprises)

        Returns:
            Record data or None if not found
        """
        ...

    async def health_check(self) -> bool:
        """Check if the data source is available.

        Returns:
            True if healthy, False otherwise
        """
        ...


class BaseAdapter(ABC):
    """Abstract base class for adapters with common functionality.

    Provides:
    - HTTP client with connection pooling
    - Default health check implementation
    - Logging utilities
    """

    def __init__(self, config: AdapterConfig):
        self._config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout,
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def config(self) -> AdapterConfig:
        return self._config

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the shared HTTP client."""
        return self._client

    async def close(self) -> None:
        """Close the HTTP client. Call when done using the adapter."""
        await self._client.aclose()

    @abstractmethod
    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search implementation."""
        pass

    @abstractmethod
    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get by ID implementation."""
        pass

    async def health_check(self) -> bool:
        """Default health check - verify base URL is reachable.

        Override in subclass for custom health checks.
        """
        try:
            response = await self._client.head(
                self.config.base_url,
                timeout=5.0,
            )
            return response.status_code < 500
        except Exception as e:
            logger.debug(f"{self.name} health check failed: {e}")
            return False

    def _log_error(self, operation: str, error: Exception) -> None:
        """Log an error with adapter context."""
        logger.error(f"{self.name} {operation} failed: {error}")

    def _log_debug(self, message: str) -> None:
        """Log a debug message with adapter context."""
        logger.debug(f"[{self.name}] {message}")

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync data from source (optional, for batch sources).

        Override in adapters that support incremental sync.

        Args:
            since: Only sync records updated after this time

        Returns:
            Sync status
        """
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_implemented",
            error="This adapter does not support sync",
        )
