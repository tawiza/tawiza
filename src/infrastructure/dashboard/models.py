"""Data models for the dashboard.

Provides type-safe dataclasses for dashboard entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AlertSource(StrEnum):
    """Sources that can generate alerts."""

    BODACC = "bodacc"
    BOAMP = "boamp"
    GDELT = "gdelt"


class AlertType(StrEnum):
    """Types of alerts."""

    # BODACC types
    CREATION = "creation"
    RADIATION = "radiation"
    MODIFICATION = "modification"
    VENTE = "vente"
    # BOAMP types
    MARCHE = "marche"
    ATTRIBUTION = "attribution"
    # GDELT types
    NEWS = "news"


class SourceStatus(StrEnum):
    """Status of a data source."""

    OK = "ok"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class Alert:
    """An alert from the watcher system."""

    id: int | None = None
    source: AlertSource = AlertSource.BODACC
    type: AlertType = AlertType.CREATION
    title: str = ""
    content: str | None = None
    url: str | None = None
    detected_at: datetime | None = None
    read: bool = False
    data: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "source": self.source.value if isinstance(self.source, AlertSource) else self.source,
            "type": self.type.value if isinstance(self.type, AlertType) else self.type,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "read": self.read,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            source=AlertSource(data["source"]) if data.get("source") else AlertSource.BODACC,
            type=AlertType(data["type"]) if data.get("type") else AlertType.CREATION,
            title=data.get("title", ""),
            content=data.get("content"),
            url=data.get("url"),
            detected_at=datetime.fromisoformat(data["detected_at"])
            if data.get("detected_at")
            else None,
            read=data.get("read", False),
            data=data.get("data"),
        )


@dataclass
class Analysis:
    """A recorded analysis."""

    id: int | None = None
    query: str = ""
    timestamp: datetime | None = None
    sources_used: list[str] = field(default_factory=list)
    results_count: int = 0
    confidence: float | None = None
    duration_ms: int | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "query": self.query,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "sources_used": self.sources_used,
            "results_count": self.results_count,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Analysis":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            query=data.get("query", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            sources_used=data.get("sources_used", []),
            results_count=data.get("results_count", 0),
            confidence=data.get("confidence"),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata"),
        )

    @property
    def time_ago(self) -> str:
        """Human-readable time since analysis."""
        if not self.timestamp:
            return "unknown"

        now = datetime.now()
        if isinstance(self.timestamp, str):
            ts = datetime.fromisoformat(self.timestamp)
        else:
            ts = self.timestamp

        diff = now - ts
        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}min ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}d ago"
        else:
            return ts.strftime("%Y-%m-%d")


@dataclass
class WatchItem:
    """A watchlist item for monitoring."""

    id: int | None = None
    keywords: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=lambda: ["bodacc", "boamp", "gdelt"])
    active: bool = True
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "keywords": self.keywords,
            "sources": self.sources,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WatchItem":
        """Create from dictionary."""
        return cls(
            id=data.get("id"),
            keywords=data.get("keywords", []),
            sources=data.get("sources", ["bodacc", "boamp", "gdelt"]),
            active=data.get("active", True),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
        )


@dataclass
class PollStatus:
    """Status of a poller for a source."""

    source: str = ""
    last_poll: datetime | None = None
    next_poll: datetime | None = None
    last_error: str | None = None
    polls_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "next_poll": self.next_poll.isoformat() if self.next_poll else None,
            "last_error": self.last_error,
            "polls_count": self.polls_count,
        }

    @property
    def time_until_next(self) -> str:
        """Human-readable time until next poll."""
        if not self.next_poll:
            return "unknown"

        now = datetime.now()
        if isinstance(self.next_poll, str):
            np = datetime.fromisoformat(self.next_poll)
        else:
            np = self.next_poll

        diff = np - now
        seconds = diff.total_seconds()

        if seconds <= 0:
            return "now"
        elif seconds < 60:
            return f"in {int(seconds)}s"
        elif seconds < 3600:
            return f"in {int(seconds / 60)}min"
        else:
            return f"in {int(seconds / 3600)}h"


@dataclass
class DashboardStatus:
    """Complete dashboard status."""

    sources: dict = field(default_factory=dict)
    watcher: dict = field(default_factory=dict)
    database: dict = field(default_factory=dict)
    alerts_unread: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP resource."""
        return {
            "sources": self.sources,
            "watcher": self.watcher,
            "database": self.database,
            "alerts_unread": self.alerts_unread,
        }


@dataclass
class DashboardStats:
    """Dashboard statistics."""

    period: str = "last_7_days"
    analyses_count: int = 0
    companies_found: int = 0
    sources_usage: dict = field(default_factory=dict)
    top_queries: list[str] = field(default_factory=list)
    avg_confidence: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP resource."""
        return {
            "period": self.period,
            "analyses_count": self.analyses_count,
            "companies_found": self.companies_found,
            "sources_usage": self.sources_usage,
            "top_queries": self.top_queries,
            "avg_confidence": self.avg_confidence,
        }
