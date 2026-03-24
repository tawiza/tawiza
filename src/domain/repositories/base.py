"""Base repository interfaces."""

from abc import ABC, abstractmethod
from typing import TypeVar
from uuid import UUID

from src.domain.entities.base import AggregateRoot

# Type variable for aggregate root
T = TypeVar("T", bound=AggregateRoot)


class IRepository[T: AggregateRoot](ABC):
    """Base repository interface.

    Defines the contract that all repositories must implement.
    This is a port in the hexagonal architecture.
    """

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save an entity.

        Args:
            entity: The entity to save

        Returns:
            The saved entity
        """
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> T | None:
        """Get an entity by its ID.

        Args:
            entity_id: The entity ID

        Returns:
            The entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """Get all entities with pagination.

        Args:
            skip: Number of entities to skip
            limit: Maximum number of entities to return

        Returns:
            List of entities
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity.

        Args:
            entity_id: The entity ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, entity_id: UUID) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The entity ID

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total number of entities.

        Returns:
            Total count
        """
        pass
