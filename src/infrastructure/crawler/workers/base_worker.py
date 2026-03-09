"""Base worker interface for all crawlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CrawlResult:
    """Result from a crawl operation."""
    source_id: str
    url: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    content: str | None = None
    content_hash: str | None = None
    extracted_data: dict[str, Any] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    error: str | None = None
    status_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "url": self.url,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "content_hash": self.content_hash,
            "extracted_data": self.extracted_data,
            "signals": self.signals,
            "error": self.error,
            "status_code": self.status_code,
        }


class BaseWorker(ABC):
    """
    Abstract base class for crawl workers.

    All worker types (HTTPX, Playwright, API) must implement this interface.
    """

    @abstractmethod
    async def crawl(self, url: str, source_id: str) -> CrawlResult:
        """
        Crawl a URL and return the result.

        Args:
            url: URL to crawl
            source_id: Identifier for the source

        Returns:
            CrawlResult with content or error
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass
