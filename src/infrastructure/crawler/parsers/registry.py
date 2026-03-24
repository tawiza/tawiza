"""Parser registry for content extraction."""

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """Base class for content parsers."""

    @abstractmethod
    def can_parse(self, content_type: str, url: str) -> bool:
        """Check if this parser can handle the content."""
        pass

    @abstractmethod
    async def parse(self, content: str, url: str) -> dict[str, Any]:
        """Parse content and extract structured data."""
        pass


class ParserRegistry:
    """Registry of available parsers."""

    def __init__(self):
        """Initialize empty registry."""
        self.parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        """Register a parser."""
        self.parsers.append(parser)

    def get_parser(self, content_type: str, url: str) -> BaseParser | None:
        """Get first matching parser."""
        for parser in self.parsers:
            if parser.can_parse(content_type, url):
                return parser
        return None
