"""Base classes for autocompletion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionResult:
    """A single completion suggestion."""

    value: str
    description: str | None = None
    score: float = 1.0  # Higher = more relevant
    source: str = "static"  # static, dynamic, history, intelligent


class CompletionProvider(ABC):
    """Abstract base class for completion providers."""

    @abstractmethod
    def get_completions(
        self, incomplete: str, context: dict | None = None
    ) -> list[CompletionResult]:
        """Get completion suggestions.

        Args:
            incomplete: Partial input to complete
            context: Optional context (previous args, command, etc.)

        Returns:
            List of CompletionResult objects sorted by relevance
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    def priority(self) -> int:
        """Provider priority (higher = checked first)."""
        return 0

    def supports_caching(self) -> bool:
        """Whether results can be cached."""
        return False

    def cache_ttl(self) -> int:
        """Cache TTL in seconds."""
        return 0
