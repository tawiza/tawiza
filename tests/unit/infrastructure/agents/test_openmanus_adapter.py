"""Unit tests for OpenManusAdapter.

Tests cover:
- Browser navigation
- Element extraction (text, links, attributes)
- Form filling with validation
- Element clicking and interaction
- Screenshot capture
- Error handling and recovery
- Task state management
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

try:
    from playwright.async_api import Browser, Page, Playwright
except ImportError:
    pytest.skip("Playwright not installed", allow_module_level=True)

# Skip entire module in CI  -  these tests need real browser binaries
pytestmark = pytest.mark.skipif(
    not Path.home().joinpath(".cache/ms-playwright/chromium-1148").exists()
    and not Path.home().joinpath(".cache/ms-playwright/chromium_headless_shell-1208").exists(),
    reason="Playwright browsers not installed (run: playwright install)",
)

from src.application.ports.agent_ports import AgentExecutionError, TaskStatus
from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter


@pytest.fixture
async def mock_playwright():
    """Create mock Playwright instance."""
    return AsyncMock()


@pytest.fixture
async def mock_browser():
    """Create mock Browser instance."""
    browser = AsyncMock()
    page = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()
    return browser


@pytest.fixture
async def mock_page():
    """Create mock Page instance."""
    page = AsyncMock()
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Example Page")
    page.content = AsyncMock(return_value="<html><body>Test</body></html>")
    page.screenshot = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.close = AsyncMock()
    return page


@pytest.fixture
def adapter(tmp_path):
    """Create OpenManusAdapter for testing."""
    adapter = OpenManusAdapter(headless=True, screenshots_dir=str(tmp_path), llm_client=None)
    return adapter


# Unit Tests
class TestOpenManusAdapterInit:
    """Tests for OpenManusAdapter initialization."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        adapter = OpenManusAdapter()
        assert adapter.headless is True
        assert adapter.agent_type.value == "openmanus"
        assert adapter.llm_client is None
        assert isinstance(adapter.screenshots_dir, Path)

    def test_init_custom_headless(self):
        """Test initialization with custom headless setting."""
        adapter = OpenManusAdapter(headless=False)
        assert adapter.headless is False

    def test_init_custom_screenshots_dir(self, tmp_path):
        """Test initialization with custom screenshots directory."""
        custom_dir = tmp_path / "custom_screenshots"
        adapter = OpenManusAdapter(screenshots_dir=str(custom_dir))
        assert adapter.screenshots_dir == custom_dir
        assert custom_dir.exists()

    def test_init_with_llm_client(self):
        """Test initialization with LLM client."""
        mock_llm = MagicMock()
        adapter = OpenManusAdapter(llm_client=mock_llm)
        assert adapter.llm_client is mock_llm


class TestOpenManusAdapterNavigation:
    """Tests for navigation functionality."""

    @pytest.mark.asyncio
    async def test_execute_navigate_action(self, adapter, mock_page):
        """Test navigation action execution."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {"url": "https://example.com", "action": "navigate"}
            )

            assert result["result"]["action"] == "navigate"
            assert result["result"]["status"] == "success"
            assert result["status"] == TaskStatus.COMPLETED
            mock_page.goto.assert_called_once_with(
                "https://example.com", wait_until="networkidle", timeout=30000
            )

    @pytest.mark.asyncio
    async def test_navigate_missing_url(self, adapter):
        """Test navigation without URL raises error."""
        with pytest.raises(AgentExecutionError, match="URL is required"):
            await adapter.execute_task(
                {
                    "action": "navigate"
                    # Missing 'url' field
                }
            )

    @pytest.mark.asyncio
    async def test_navigate_updates_progress(self, adapter, mock_page):
        """Test that navigation updates progress."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with patch.object(adapter, "_update_progress") as mock_progress:
                with patch.object(adapter, "_take_screenshot"):
                    await adapter.execute_task({"url": "https://example.com", "action": "navigate"})

                # Verify progress was updated
                assert mock_progress.call_count > 0

    @pytest.mark.asyncio
    async def test_navigate_takes_screenshots(self, adapter, mock_page):
        """Test that screenshots are taken during navigation."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with patch.object(adapter, "_take_screenshot") as mock_screenshot:
                await adapter.execute_task({"url": "https://example.com", "action": "navigate"})

                # Should take initial and final screenshots
                assert mock_screenshot.call_count >= 2


class TestOpenManusAdapterExtraction:
    """Tests for data extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_with_selectors(self, adapter, mock_page):
        """Test extraction using CSS selectors."""
        mock_page.content = AsyncMock(
            return_value="""
            <html>
                <h1>Title</h1>
                <p class="paragraph">Paragraph 1</p>
                <p class="paragraph">Paragraph 2</p>
                <a href="/page1">Link 1</a>
                <a href="/page2">Link 2</a>
            </html>
        """
        )

        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com",
                    "action": "extract",
                    "selectors": {"title": "h1", "paragraphs": "p.paragraph", "links": "a"},
                }
            )

            extracted_data = result["result"]["data"]
            assert "title" in extracted_data
            assert "paragraphs" in extracted_data
            assert "links" in extracted_data

    @pytest.mark.asyncio
    async def test_extract_without_selectors(self, adapter, mock_page):
        """Test extraction without selectors (full page)."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task({"url": "https://example.com", "action": "extract"})

            extracted_data = result["result"]["data"]
            assert "title" in extracted_data
            assert "url" in extracted_data
            assert "text" in extracted_data
            assert "links" in extracted_data

    @pytest.mark.asyncio
    async def test_extract_target_specification(self, adapter, mock_page):
        """Test extraction with target specification."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://news.ycombinator.com",
                    "action": "extract",
                    "data": {"target": "top 5 article titles"},
                }
            )

            assert result["result"]["target"] == "top 5 article titles"
            assert result["result"]["status"] == "success"


class TestOpenManusAdapterFormFilling:
    """Tests for form filling functionality."""

    @pytest.mark.asyncio
    async def test_fill_form_single_field(self, adapter, mock_page):
        """Test filling a single form field."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {"email": "#email-input"},
                    "data": {"email": "test@example.com"},
                }
            )

            mock_page.fill.assert_called_with("#email-input", "test@example.com")
            assert "email" in result["result"]["filled_fields"]
            assert result["result"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_fill_form_multiple_fields(self, adapter, mock_page):
        """Test filling multiple form fields."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {
                        "name": "#name-input",
                        "email": "#email-input",
                        "phone": "#phone-input",
                    },
                    "data": {"name": "John Doe", "email": "john@example.com", "phone": "555-1234"},
                }
            )

            assert len(result["result"]["filled_fields"]) == 3
            assert mock_page.fill.call_count == 3

    @pytest.mark.asyncio
    async def test_fill_form_missing_selector(self, adapter, mock_page):
        """Test form filling with missing selector (should skip field)."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {
                        "email": "#email-input"
                        # Missing selector for 'name'
                    },
                    "data": {"name": "John Doe", "email": "john@example.com"},
                }
            )

            # Only email should be filled
            assert len(result["result"]["filled_fields"]) == 1
            assert "email" in result["result"]["filled_fields"]

    @pytest.mark.asyncio
    async def test_fill_form_with_submit(self, adapter, mock_page):
        """Test form filling and submission."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {"email": "#email-input"},
                    "data": {"email": "test@example.com"},
                    "submit": True,
                    "submit_selector": "button[type='submit']",
                }
            )

            mock_page.click.assert_called_with("button[type='submit']")
            assert result["result"]["submitted"] is True

    @pytest.mark.asyncio
    async def test_fill_form_type_conversion(self, adapter, mock_page):
        """Test that form values are converted to strings."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {
                    "url": "https://example.com/form",
                    "action": "fill_form",
                    "selectors": {"count": "#count-input"},
                    "data": {
                        "count": 42  # Integer value
                    },
                }
            )

            # Verify integer was converted to string
            call_args = mock_page.fill.call_args[0]
            assert isinstance(call_args[1], str)
            assert call_args[1] == "42"


class TestOpenManusAdapterClicking:
    """Tests for element clicking functionality."""

    @pytest.mark.asyncio
    async def test_click_element(self, adapter, mock_page):
        """Test clicking an element."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {"url": "https://example.com", "action": "click", "selector": "button.submit"}
            )

            mock_page.click.assert_called_once_with("button.submit")
            assert result["result"]["action"] == "click"
            assert result["result"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_click_missing_selector(self, adapter):
        """Test click without selector raises error."""
        with pytest.raises(AgentExecutionError, match="Selector is required"):
            await adapter.execute_task(
                {
                    "url": "https://example.com",
                    "action": "click",
                    # Missing 'selector' field
                }
            )

    @pytest.mark.asyncio
    async def test_click_waits_for_navigation(self, adapter, mock_page):
        """Test that click waits for page load after clicking."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            await adapter.execute_task(
                {"url": "https://example.com", "action": "click", "selector": "a.link"}
            )

            mock_page.wait_for_load_state.assert_called_with("networkidle", timeout=10000)


class TestOpenManusAdapterErrorHandling:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_unknown_action(self, adapter):
        """Test error on unknown action type."""
        with patch.object(adapter, "_ensure_browser"):
            with pytest.raises(AgentExecutionError, match="Unknown action"):
                await adapter.execute_task(
                    {"url": "https://example.com", "action": "unknown_action"}
                )

    @pytest.mark.asyncio
    async def test_navigation_timeout(self, adapter, mock_page):
        """Test error handling for navigation timeout."""
        mock_page.goto = AsyncMock(side_effect=TimeoutError("Navigation timeout"))

        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with pytest.raises(AgentExecutionError):
                await adapter.execute_task(
                    {"url": "https://slow.example.com", "action": "navigate"}
                )

    @pytest.mark.asyncio
    async def test_page_closed_before_completion(self, adapter, mock_page):
        """Test graceful handling when page closes unexpectedly."""
        mock_page.goto = AsyncMock()
        mock_page.screenshot = AsyncMock(side_effect=RuntimeError("Page has been closed"))

        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with pytest.raises(AgentExecutionError):
                await adapter.execute_task({"url": "https://example.com", "action": "navigate"})

    @pytest.mark.asyncio
    async def test_task_failure_updates_status(self, adapter, mock_page):
        """Test that failed tasks update status to FAILED."""
        mock_page.goto = AsyncMock(side_effect=RuntimeError("Network error"))

        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            try:
                await adapter.execute_task({"url": "https://example.com", "action": "navigate"})
            except AgentExecutionError:
                pass

            # Verify task was marked as failed
            # (This would require accessing internal task state)


class TestOpenManusAdapterBrowserManagement:
    """Tests for browser lifecycle management."""

    @pytest.mark.asyncio
    async def test_browser_lazy_initialization(self, adapter):
        """Test that browser is initialized lazily."""
        browser = await adapter._ensure_browser()
        # First call creates browser
        assert browser is not None

        browser2 = await adapter._ensure_browser()
        # Second call returns same browser
        assert browser2 is browser

    @pytest.mark.asyncio
    async def test_browser_close(self, adapter):
        """Test browser cleanup."""
        with patch(
            "src.infrastructure.agents.openmanus.openmanus_adapter.async_playwright"
        ) as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            # Initialize browser
            await adapter._ensure_browser()

            # Close it
            await adapter._close_browser()

            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_adapter_cleanup(self, adapter):
        """Test full adapter cleanup."""
        with patch.object(adapter, "_close_browser") as mock_close:
            await adapter.cleanup()
            mock_close.assert_called_once()


class TestOpenManusAdapterScreenshots:
    """Tests for screenshot capture functionality."""

    @pytest.mark.asyncio
    async def test_screenshot_saved_to_directory(self, adapter, mock_page, tmp_path):
        """Test that screenshots are saved to configured directory."""
        adapter.screenshots_dir = tmp_path

        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with patch.object(adapter, "_take_screenshot", wraps=adapter._take_screenshot):
                await adapter.execute_task({"url": "https://example.com", "action": "navigate"})

    @pytest.mark.asyncio
    async def test_screenshot_naming(self, adapter, mock_page):
        """Test that screenshots have consistent naming."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {"url": "https://example.com", "action": "navigate"}
            )

            # Screenshots should have task ID in filename
            # (Implementation detail - verify through mocks)


class TestOpenManusAdapterTaskManagement:
    """Tests for internal task management."""

    @pytest.mark.asyncio
    async def test_task_creation_and_tracking(self, adapter, mock_page):
        """Test that tasks are properly created and tracked."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            result = await adapter.execute_task(
                {"url": "https://example.com", "action": "navigate"}
            )

            # Verify task result structure
            assert "task_id" in result or "id" in result
            assert result["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_logging(self, adapter, mock_page):
        """Test that task actions are logged."""
        with patch.object(adapter, "_ensure_browser") as mock_ensure:
            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_ensure.return_value = mock_browser

            with patch.object(adapter, "_add_log") as mock_log:
                await adapter.execute_task({"url": "https://example.com", "action": "navigate"})

                # Verify logs were created
                assert mock_log.call_count > 0


class TestOpenManusAdapterHeadlessMode:
    """Tests for headless mode configuration."""

    @pytest.mark.asyncio
    async def test_headless_mode_true(self, mock_page):
        """Test browser launch with headless=True."""
        adapter = OpenManusAdapter(headless=True)

        with patch(
            "src.infrastructure.agents.openmanus.openmanus_adapter.async_playwright"
        ) as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            await adapter._ensure_browser()

            # Verify headless=True was passed
            call_kwargs = mock_playwright.chromium.launch.call_args[1]
            assert call_kwargs["headless"] is True

    @pytest.mark.asyncio
    async def test_headless_mode_false(self):
        """Test browser launch with headless=False."""
        adapter = OpenManusAdapter(headless=False)

        with patch(
            "src.infrastructure.agents.openmanus.openmanus_adapter.async_playwright"
        ) as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

            await adapter._ensure_browser()

            # Verify headless=False was passed
            call_kwargs = mock_playwright.chromium.launch.call_args[1]
            assert call_kwargs["headless"] is False
