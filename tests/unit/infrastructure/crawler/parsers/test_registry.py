"""Tests for parser registry."""

import pytest

from src.infrastructure.crawler.parsers.registry import BaseParser, ParserRegistry


class MockParser(BaseParser):
    """Mock parser for testing."""

    def can_parse(self, content_type: str, url: str) -> bool:
        return "mock" in content_type

    async def parse(self, content: str, url: str) -> dict:
        return {"mock": True}


class TestParserRegistry:
    """Test parser registry."""

    def test_create_registry(self):
        """Create empty registry."""
        registry = ParserRegistry()
        assert len(registry.parsers) == 0

    def test_register_parser(self):
        """Register a parser."""
        registry = ParserRegistry()
        parser = MockParser()
        registry.register(parser)
        assert len(registry.parsers) == 1

    def test_get_parser_for_content_type(self):
        """Get appropriate parser for content type."""
        registry = ParserRegistry()
        parser = MockParser()
        registry.register(parser)

        found = registry.get_parser("application/mock", "https://example.com")
        assert found is parser

    def test_no_parser_found(self):
        """Returns None when no parser matches."""
        registry = ParserRegistry()
        parser = MockParser()
        registry.register(parser)

        found = registry.get_parser("text/html", "https://example.com")
        assert found is None
