"""Base classes for output formatting."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OutputFormat(StrEnum):
    """Supported output formats."""

    AUTO = "auto"  # Auto-detect based on TTY
    JSON = "json"  # Machine-readable JSON
    TABLE = "table"  # Human-readable Rich table
    CSV = "csv"  # CSV export
    MARKDOWN = "md"  # Markdown report


@dataclass
class OutputOptions:
    """Options for output formatting."""

    title: str | None = None
    indent: int = 2
    sort_keys: bool = False
    show_header: bool = True
    max_width: int | None = None
    colors: bool = True


class OutputFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format(self, data: Any, options: OutputOptions | None = None) -> str:
        """Format data according to this formatter's rules.

        Args:
            data: The data to format (dict, list, or dataclass)
            options: Formatting options

        Returns:
            Formatted string representation
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this formatter supports streaming output."""
        pass

    def get_content_type(self) -> str:
        """Return the MIME content type for this format."""
        return "text/plain"
