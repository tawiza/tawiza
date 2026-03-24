"""Tests for base worker interface."""

from abc import ABC

import pytest

from src.infrastructure.crawler.workers.base_worker import BaseWorker, CrawlResult


class TestCrawlResult:
    """Test CrawlResult dataclass."""

    def test_create_success_result(self):
        """Create successful crawl result."""
        result = CrawlResult(
            source_id="test",
            url="https://example.com",
            success=True,
            content="<html>...</html>",
            content_hash="abc123",
        )
        assert result.success is True
        assert result.error is None

    def test_create_failure_result(self):
        """Create failed crawl result."""
        result = CrawlResult(
            source_id="test", url="https://example.com", success=False, error="Connection timeout"
        )
        assert result.success is False
        assert result.content is None

    def test_to_dict(self):
        """Convert to dictionary."""
        result = CrawlResult(source_id="test", url="https://example.com", success=True)
        d = result.to_dict()
        assert d["source_id"] == "test"
        assert d["success"] is True


class TestBaseWorker:
    """Test BaseWorker abstract class."""

    def test_is_abstract(self):
        """BaseWorker cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseWorker()

    def test_has_crawl_method(self):
        """BaseWorker defines crawl method."""
        assert hasattr(BaseWorker, "crawl")

    def test_has_close_method(self):
        """BaseWorker defines close method."""
        assert hasattr(BaseWorker, "close")
