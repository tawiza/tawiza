"""Tests for TAJINE-Crawler integration."""

from unittest.mock import MagicMock

import pytest

from src.infrastructure.crawler.adaptive_crawler import AdaptiveCrawler
from src.infrastructure.crawler.events import CrawlerCallback, CrawlerEvent


class TestTAJINECrawlerBridge:
    """Test TAJINE-Crawler integration."""

    def test_crawler_emits_to_tajine_handler(self):
        """Crawler events reach TAJINE handler."""
        crawler = AdaptiveCrawler()
        received_events = []

        def handler(cb: CrawlerCallback):
            received_events.append(cb)

        crawler.on_event(handler)

        crawler._emit(
            CrawlerCallback(
                event=CrawlerEvent.SOURCE_CRAWLED,
                source_id="test",
                url="https://example.com",
                data={"key": "value"},
            )
        )

        assert len(received_events) == 1
        assert received_events[0].source_id == "test"

    def test_relevance_feedback_loop(self):
        """TAJINE can send relevance feedback."""
        crawler = AdaptiveCrawler()
        crawler.add_source("test", "https://example.com", "api")

        arm = crawler.scheduler.get_arm("test")
        initial = arm.relevance_score

        crawler.update_relevance("test", was_useful=True)

        assert arm.relevance_score > initial

    def test_multiple_handlers(self):
        """Multiple handlers receive events."""
        crawler = AdaptiveCrawler()
        handler1_calls = []
        handler2_calls = []

        crawler.on_event(lambda cb: handler1_calls.append(cb))
        crawler.on_event(lambda cb: handler2_calls.append(cb))

        crawler._emit(
            CrawlerCallback(
                event=CrawlerEvent.SOURCE_CRAWLED, source_id="test", url="https://example.com"
            )
        )

        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1
