"""Tests for crawler events."""

import pytest

from src.infrastructure.crawler.events import CrawlerCallback, CrawlerEvent


class TestCrawlerEvents:
    """Test crawler event types."""

    def test_event_types_exist(self):
        """All event types are defined."""
        assert CrawlerEvent.SOURCE_CRAWLED
        assert CrawlerEvent.SOURCE_CHANGED
        assert CrawlerEvent.SOURCE_ERROR
        assert CrawlerEvent.NEW_SOURCE
        assert CrawlerEvent.SIGNAL_DETECTED


class TestCrawlerCallback:
    """Test crawler callback data."""

    def test_create_callback(self):
        """Create crawler callback."""
        cb = CrawlerCallback(
            event=CrawlerEvent.SOURCE_CRAWLED, source_id="test-source", url="https://example.com"
        )
        assert cb.event == CrawlerEvent.SOURCE_CRAWLED

    def test_to_dict(self):
        """Convert callback to dict."""
        cb = CrawlerCallback(
            event=CrawlerEvent.SOURCE_CRAWLED,
            source_id="test",
            url="https://example.com",
            data={"key": "value"},
        )
        d = cb.to_dict()
        assert d["type"] == "crawler.source_crawled"
        assert d["source_id"] == "test"

    def test_callback_with_signals(self):
        """Callback can include signals."""
        cb = CrawlerCallback(
            event=CrawlerEvent.SIGNAL_DETECTED,
            source_id="test",
            url="https://example.com",
            signals=["growth", "concentration"],
        )
        assert len(cb.signals) == 2
