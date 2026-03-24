"""Tests for JSON parser."""

import pytest

from src.infrastructure.crawler.parsers.json_parser import JSONParser


class TestJSONParser:
    """Test JSON parser."""

    def test_can_parse_json(self):
        """Parses application/json content type."""
        parser = JSONParser()
        assert parser.can_parse("application/json", "https://api.example.com")
        assert parser.can_parse("application/json; charset=utf-8", "https://api.example.com")

    def test_cannot_parse_html(self):
        """Does not parse HTML."""
        parser = JSONParser()
        assert not parser.can_parse("text/html", "https://example.com")

    @pytest.mark.asyncio
    async def test_parse_simple_json(self):
        """Parse simple JSON object."""
        parser = JSONParser()
        content = '{"name": "Test", "value": 42}'
        result = await parser.parse(content, "https://api.example.com")
        assert result["name"] == "Test"
        assert result["value"] == 42

    @pytest.mark.asyncio
    async def test_parse_json_array(self):
        """Parse JSON array."""
        parser = JSONParser()
        content = '[{"id": 1}, {"id": 2}]'
        result = await parser.parse(content, "https://api.example.com")
        assert "items" in result
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        """Handle invalid JSON gracefully."""
        parser = JSONParser()
        content = "not valid json {"
        result = await parser.parse(content, "https://api.example.com")
        assert "error" in result
