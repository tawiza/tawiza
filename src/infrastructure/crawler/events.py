"""Event system for crawler-to-TAJINE communication."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class CrawlerEvent(StrEnum):
    """Events emitted by AdaptiveCrawler."""

    SOURCE_CRAWLED = "crawler.source_crawled"
    SOURCE_CHANGED = "crawler.source_changed"
    SOURCE_ERROR = "crawler.source_error"
    NEW_SOURCE = "crawler.new_source"
    SIGNAL_DETECTED = "crawler.signal_detected"


@dataclass
class CrawlerCallback:
    """Callback data for crawler events."""

    event: CrawlerEvent
    source_id: str
    url: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for transmission."""
        return {
            "type": self.event.value,
            "source_id": self.source_id,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "signals": self.signals,
            "quality_score": self.quality_score,
            "error": self.error,
        }
