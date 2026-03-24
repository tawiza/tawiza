"""Tests for RSS/Atom feed parser."""

import pytest

from src.infrastructure.crawler.parsers.feed_parser import FeedParser


class TestFeedParser:
    """Test feed parser."""

    def test_can_parse_rss(self):
        """Parses RSS feeds."""
        parser = FeedParser()
        assert parser.can_parse("application/rss+xml", "https://example.com/feed")
        assert parser.can_parse("text/xml", "https://example.com/feed.rss")

    def test_can_parse_atom(self):
        """Parses Atom feeds."""
        parser = FeedParser()
        assert parser.can_parse("application/atom+xml", "https://example.com/feed")

    @pytest.mark.asyncio
    async def test_parse_rss_feed(self):
        """Parse RSS feed content."""
        parser = FeedParser()
        content = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Article 1</title>
                    <link>https://example.com/1</link>
                </item>
            </channel>
        </rss>"""
        result = await parser.parse(content, "https://example.com/feed")
        assert result["title"] == "Test Feed"
        assert len(result["entries"]) == 1
