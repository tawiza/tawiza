"""Base classes for domain entities."""

from abc import ABC
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class Entity(ABC):
    """Base class for all domain entities.

    An entity is an object that has a unique identity that runs through time and
    different representations. You can change its attributes but it's still the same entity.
    """

    def __init__(self, id: UUID | None = None) -> None:
        self._id = id or uuid4()
        self._created_at = utc_now()
        self._updated_at = utc_now()

    @property
    def id(self) -> UUID:
        """Get the entity's unique identifier."""
        return self._id

    @property
    def created_at(self) -> datetime:
        """Get the creation timestamp."""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """Get the last update timestamp."""
        return self._updated_at

    def _touch(self) -> None:
        """Update the updated_at timestamp."""
        self._updated_at = utc_now()

    def __eq__(self, other: object) -> bool:
        """Two entities are equal if they have the same ID."""
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on the entity's ID."""
        return hash(self.id)

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AggregateRoot(Entity):
    """Base class for aggregate roots.

    An aggregate root is an entity that is the entry point to an aggregate.
    It maintains consistency boundaries for all entities within the aggregate.
    """

    def __init__(self, id: UUID | None = None) -> None:
        super().__init__(id)
        self._domain_events: list[Any] = []

    @property
    def domain_events(self) -> list[Any]:
        """Get the list of domain events."""
        return self._domain_events.copy()

    def add_domain_event(self, event: Any) -> None:
        """Add a domain event to the entity."""
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        """Clear all domain events."""
        self._domain_events.clear()
