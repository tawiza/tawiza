"""Base classes for value objects."""

from abc import ABC
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValueObject(ABC):
    """Base class for value objects.

    A value object is an object that describes some characteristic or attribute
    but has no unique identity. They are immutable and should be compared by
    their values, not by identity.

    Use frozen=True in dataclass to make them immutable.
    """

    def __eq__(self, other: object) -> bool:
        """Two value objects are equal if all their attributes are equal."""
        if not isinstance(other, self.__class__):
            return False
        return all(
            getattr(self, attr) == getattr(other, attr)
            for attr in self.__dataclass_fields__
        )

    def __hash__(self) -> int:
        """Hash based on all attributes."""
        return hash(tuple(getattr(self, attr) for attr in self.__dataclass_fields__))

    def to_dict(self) -> dict[str, Any]:
        """Convert value object to dictionary."""
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }
