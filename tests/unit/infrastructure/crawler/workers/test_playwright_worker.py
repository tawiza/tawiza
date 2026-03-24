"""Tests for Playwright worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.crawler.workers.playwright_worker import PlaywrightWorker
from src.infrastructure.crawler.workers.rate_limiter import RateLimiter


class TestPlaywrightWorkerCreation:
    """Test PlaywrightWorker initialization."""

    def test_create_worker(self):
        """Create Playwright worker."""
        worker = PlaywrightWorker()
        assert worker is not None

    def test_create_with_rate_limiter(self):
        """Create worker with rate limiter."""
        limiter = RateLimiter()
        worker = PlaywrightWorker(rate_limiter=limiter)
        assert worker.rate_limiter is limiter

    def test_create_with_timeout(self):
        """Create worker with custom timeout."""
        worker = PlaywrightWorker(timeout=60000)
        assert worker.timeout == 60000

    def test_create_headless_mode(self):
        """Create worker in headless mode (default)."""
        worker = PlaywrightWorker()
        assert worker.headless is True

    def test_create_visible_mode(self):
        """Create worker with visible browser."""
        worker = PlaywrightWorker(headless=False)
        assert worker.headless is False

    def test_default_wait_strategy(self):
        """Default wait strategy is networkidle."""
        worker = PlaywrightWorker()
        assert worker.wait_until == "networkidle"


class TestPlaywrightWorkerHelpers:
    """Test helper methods."""

    def test_user_agent_rotation(self):
        """User agents rotate."""
        worker = PlaywrightWorker()
        ua1 = worker._get_user_agent()
        ua2 = worker._get_user_agent()
        # Different calls should advance the rotation
        assert worker._ua_index == 2

    def test_extract_domain(self):
        """Extract domain from URL."""
        worker = PlaywrightWorker()
        assert worker._extract_domain("https://example.com/path") == "example.com"
        assert worker._extract_domain("https://sub.example.com:8080/path") == "sub.example.com:8080"

    def test_compute_hash(self):
        """Compute content hash."""
        worker = PlaywrightWorker()
        hash1 = worker._compute_hash("test content")
        hash2 = worker._compute_hash("test content")
        hash3 = worker._compute_hash("different content")
        assert hash1 == hash2
        assert hash1 != hash3


class TestPlaywrightWorkerCrawl:
    """Test Playwright crawling with mocked browser."""

    @pytest.mark.asyncio
    async def test_crawl_blocked_domain(self):
        """Crawl returns error for blocked domain."""
        limiter = RateLimiter()
        limiter.block_domain("example.com", 1000)
        worker = PlaywrightWorker(rate_limiter=limiter)

        result = await worker.crawl("https://example.com/test", "test-source")

        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_crawl_success(self):
        """Successful crawl returns content."""
        worker = PlaywrightWorker()

        # Mock the entire Playwright chain
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        result = await worker.crawl("https://example.com", "test-source")

        assert result.success is True
        assert result.content is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_crawl_404(self):
        """404 response is a failure."""
        worker = PlaywrightWorker()

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=404))
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        result = await worker.crawl("https://example.com/missing", "test-source")

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_crawl_no_response(self):
        """No response is handled."""
        worker = PlaywrightWorker()

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        result = await worker.crawl("https://example.com/no-response", "test-source")

        assert result.success is False
        assert "response" in result.error.lower()

    @pytest.mark.asyncio
    async def test_close_without_browser(self):
        """Close without browser doesn't crash."""
        worker = PlaywrightWorker()
        await worker.close()

    @pytest.mark.asyncio
    async def test_close_with_browser(self):
        """Close cleans up browser resources."""
        worker = PlaywrightWorker()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        worker._browser = mock_browser
        worker._playwright = mock_playwright

        await worker.close()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert worker._browser is None
        assert worker._playwright is None


class TestPlaywrightWorkerInteraction:
    """Test crawl_with_interaction method."""

    @pytest.mark.asyncio
    async def test_crawl_with_click_action(self):
        """Crawl with click action."""
        worker = PlaywrightWorker()

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.content = AsyncMock(return_value="<html><body>After click</body></html>")
        mock_page.click = AsyncMock()
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        actions = [{"type": "click", "selector": ".load-more"}]
        result = await worker.crawl_with_interaction(
            "https://example.com", "test-source", actions=actions
        )

        assert result.success is True
        mock_page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_with_type_action(self):
        """Crawl with type action."""
        worker = PlaywrightWorker()

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.content = AsyncMock(return_value="<html><body>Search result</body></html>")
        mock_page.fill = AsyncMock()
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        actions = [{"type": "type", "selector": "#search", "value": "test query"}]
        result = await worker.crawl_with_interaction(
            "https://example.com", "test-source", actions=actions
        )

        assert result.success is True
        mock_page.fill.assert_called_once()


class TestRateLimitingIntegration:
    """Test rate limiting integration."""

    @pytest.mark.asyncio
    async def test_rate_limiting_applied(self):
        """Rate limiter acquire is called."""
        limiter = RateLimiter()
        worker = PlaywrightWorker(rate_limiter=limiter)

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.content = AsyncMock(return_value="<html></html>")
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_context.add_init_script = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        worker._browser = mock_browser

        with patch.object(limiter, "acquire", new_callable=AsyncMock) as mock_acquire:
            await worker.crawl("https://example.com", "test-source")
            mock_acquire.assert_called_once_with("example.com")
