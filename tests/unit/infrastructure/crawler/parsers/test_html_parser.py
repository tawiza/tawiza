"""Tests for HTML parser."""

import pytest

from src.infrastructure.crawler.parsers.html_parser import HTMLParser


class TestHTMLParser:
    """Test HTML parser."""

    def test_can_parse_html(self):
        """Parses text/html content type."""
        parser = HTMLParser()
        assert parser.can_parse("text/html", "https://example.com")
        assert parser.can_parse("text/html; charset=utf-8", "https://example.com")

    @pytest.mark.asyncio
    async def test_extract_title(self):
        """Extract page title."""
        parser = HTMLParser()
        content = "<html><head><title>Test Page</title></head><body></body></html>"
        result = await parser.parse(content, "https://example.com")
        assert result["title"] == "Test Page"

    @pytest.mark.asyncio
    async def test_extract_text(self):
        """Extract text content."""
        parser = HTMLParser()
        content = "<html><body><p>Hello World</p></body></html>"
        result = await parser.parse(content, "https://example.com")
        assert "Hello World" in result["text"]

    @pytest.mark.asyncio
    async def test_extract_links(self):
        """Extract links from page."""
        parser = HTMLParser()
        content = '<html><body><a href="https://example.com/page">Link</a></body></html>'
        result = await parser.parse(content, "https://example.com")
        assert len(result["links"]) == 1
