"""Tests for CrawlerScheduler service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.crawler_scheduler import (
    FRENCH_DATA_SOURCES,
    CrawlerScheduler,
    get_crawler_scheduler,
)


class TestCrawlerSchedulerConfig:
    """Test crawler configuration."""

    def test_french_data_sources_not_empty(self):
        """Should have French data sources configured."""
        assert len(FRENCH_DATA_SOURCES) > 0

    def test_all_sources_have_required_fields(self):
        """All sources should have required fields."""
        required_fields = ["source_id", "url", "source_type", "priority"]
        for source in FRENCH_DATA_SOURCES:
            for field in required_fields:
                assert field in source, f"Source missing {field}: {source}"

    def test_sources_have_valid_priorities(self):
        """Sources should have valid priority values."""
        valid_priorities = ["high", "medium", "low"]
        for source in FRENCH_DATA_SOURCES:
            assert source["priority"] in valid_priorities

    def test_sources_have_valid_types(self):
        """Sources should have valid source types."""
        valid_types = ["api", "web", "rss"]
        for source in FRENCH_DATA_SOURCES:
            assert source["source_type"] in valid_types

    def test_high_priority_sources_exist(self):
        """Should have high priority sources."""
        high_priority = [s for s in FRENCH_DATA_SOURCES if s["priority"] == "high"]
        assert len(high_priority) >= 2


class TestCrawlerSchedulerSingleton:
    """Test singleton pattern."""

    def test_get_instance_returns_same_instance(self):
        """Should return the same instance."""
        instance1 = get_crawler_scheduler()
        instance2 = get_crawler_scheduler()
        assert instance1 is instance2


class TestCrawlerSchedulerLifecycle:
    """Test scheduler lifecycle."""

    @pytest.fixture
    def scheduler(self):
        """Create a fresh scheduler instance."""
        CrawlerScheduler._instance = None
        return CrawlerScheduler()

    @pytest.mark.asyncio
    async def test_start_initializes_crawler(self, scheduler):
        """Start should initialize the crawler."""
        with patch.object(scheduler, "_crawler", None):
            await scheduler.start()
            assert scheduler._is_running
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self, scheduler):
        """Stop should clean up resources."""
        await scheduler.start()
        await scheduler.stop()
        assert not scheduler._is_running

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, scheduler):
        """Starting twice should be safe."""
        await scheduler.start()
        await scheduler.start()  # Should not raise
        assert scheduler._is_running
        await scheduler.stop()


class TestCrawlerSchedulerStats:
    """Test stats methods."""

    @pytest.fixture
    def scheduler(self):
        """Create a scheduler."""
        CrawlerScheduler._instance = None
        return CrawlerScheduler()

    def test_get_source_stats_when_stopped(self, scheduler):
        """Should return empty stats when stopped."""
        stats = scheduler.get_source_stats()
        assert stats == {}

    def test_get_recent_results_empty(self, scheduler):
        """Should return empty list when no results."""
        results = scheduler.get_recent_results()
        assert results == []


class TestCrawlerSchedulerIntegration:
    """Integration tests with mocked crawler."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler with mocked crawler."""
        CrawlerScheduler._instance = None
        scheduler = CrawlerScheduler()
        scheduler._crawler = MagicMock()
        scheduler._crawler.crawl_source = AsyncMock(return_value={"success": True})
        scheduler._crawler.crawl_batch = AsyncMock(return_value=[])
        scheduler._crawler.close = AsyncMock()
        return scheduler

    @pytest.mark.asyncio
    async def test_crawl_now_specific_source(self, scheduler):
        """Should crawl specific source."""
        scheduler._is_running = True
        results = await scheduler.crawl_now("sirene_api")
        scheduler._crawler.crawl_source.assert_called_once_with("sirene_api")

    @pytest.mark.asyncio
    async def test_crawl_now_all_sources(self, scheduler):
        """Should crawl all sources when no source specified."""
        scheduler._is_running = True
        await scheduler.crawl_now()
        scheduler._crawler.crawl_batch.assert_called_once()

    def test_update_relevance(self, scheduler):
        """Should update relevance feedback."""
        scheduler.update_relevance("sirene_api", True)
        scheduler._crawler.update_relevance.assert_called_once_with("sirene_api", True)
