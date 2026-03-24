"""Tests for AdaptiveCrawler main class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.crawler.adaptive_crawler import AdaptiveCrawler
from src.infrastructure.crawler.scheduler.source_arm import SourceArm, SourceType


class TestAdaptiveCrawlerCreation:
    """Test AdaptiveCrawler initialization."""

    def test_create_crawler(self):
        """Create crawler with defaults."""
        crawler = AdaptiveCrawler()
        assert crawler is not None
        assert crawler.scheduler is not None

    def test_create_with_sources(self):
        """Create crawler with initial sources."""
        sources = [{"source_id": "test", "url": "https://example.com", "source_type": "api"}]
        crawler = AdaptiveCrawler(sources=sources)
        assert len(crawler.scheduler.arms) == 1


class TestAdaptiveCrawlerOperations:
    """Test crawler operations."""

    def test_add_source(self):
        """Add source to crawler."""
        crawler = AdaptiveCrawler()
        crawler.add_source(source_id="new", url="https://new.example.com", source_type="web")
        assert "new" in crawler.scheduler.arms

    def test_on_event(self):
        """Register event handler."""
        crawler = AdaptiveCrawler()
        handler = MagicMock()
        crawler.on_event(handler)
        assert handler in crawler._handlers

    def test_update_relevance(self):
        """Update relevance from TAJINE feedback."""
        crawler = AdaptiveCrawler()
        crawler.add_source("test", "https://example.com", "api")

        arm = crawler.scheduler.get_arm("test")
        initial = arm.relevance_score

        crawler.update_relevance("test", was_useful=True)

        assert arm.relevance_score > initial


class TestCrawlerEventEmission:
    """Test event emission."""

    def test_emit_calls_handlers(self):
        """Emit event calls registered handlers."""
        from src.infrastructure.crawler.events import CrawlerCallback, CrawlerEvent

        crawler = AdaptiveCrawler()
        received = []

        def handler(cb):
            received.append(cb)

        crawler.on_event(handler)
        crawler._emit(
            CrawlerCallback(
                event=CrawlerEvent.SOURCE_CRAWLED, source_id="test", url="https://example.com"
            )
        )

        assert len(received) == 1
        assert received[0].source_id == "test"
