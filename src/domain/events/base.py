"""Base classes for domain events."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Domain events represent something that happened in the domain that
    domain experts care about.
    """

    event_id: UUID
    occurred_at: datetime
    aggregate_id: UUID

    def __init__(self, aggregate_id: UUID) -> None:
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, "event_id", uuid4())
        object.__setattr__(self, "occurred_at", utc_now())
        object.__setattr__(self, "aggregate_id", aggregate_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": str(self.aggregate_id),
        }
