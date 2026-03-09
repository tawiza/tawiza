"""Tests for HTTPX worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.crawler.workers.httpx_worker import HTTPXWorker
from src.infrastructure.crawler.workers.rate_limiter import RateLimiter


class TestHTTPXWorkerCreation:
    """Test HTTPXWorker initialization."""

    def test_create_worker(self):
        """Create HTTPX worker."""
        worker = HTTPXWorker()
        assert worker is not None

    def test_create_with_rate_limiter(self):
        """Create worker with rate limiter."""
        limiter = RateLimiter()
        worker = HTTPXWorker(rate_limiter=limiter)
        assert worker.rate_limiter is limiter

    def test_create_with_timeout(self):
        """Create worker with custom timeout."""
        worker = HTTPXWorker(timeout=60)
        assert worker.timeout == 60


class TestHTTPXWorkerCrawl:
    """Test HTTPX crawling."""

    @pytest.mark.asyncio
    async def test_crawl_success(self):
        """Successful crawl returns content."""
        worker = HTTPXWorker()
        worker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.headers = {"content-type": "text/html"}

        worker._client.get = AsyncMock(return_value=mock_response)

        result = await worker.crawl("https://example.com", "test-source")

        assert result.success is True
        assert result.content is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_crawl_404(self):
        """404 response is a failure."""
        worker = HTTPXWorker()
        worker._client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        worker._client.get = AsyncMock(return_value=mock_response)

        result = await worker.crawl("https://example.com/missing", "test-source")

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_crawl_timeout(self):
        """Timeout is handled gracefully."""
        import httpx

        worker = HTTPXWorker(max_retries=1)
        worker._client = MagicMock()
        worker._client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await worker.crawl("https://slow.example.com", "test-source")

        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_close(self):
        """Close cleans up client."""
        worker = HTTPXWorker()
        await worker.close()


class TestUserAgentRotation:
    """Test User-Agent rotation."""

    def test_user_agent_rotation(self):
        """User agents rotate."""
        worker = HTTPXWorker()
        ua1 = worker._get_user_agent()
        ua2 = worker._get_user_agent()
        # Different calls should advance the rotation
        assert worker._ua_index == 2
