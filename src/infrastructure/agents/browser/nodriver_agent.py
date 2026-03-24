"""Stealth browser agent using nodriver (undetected-chromedriver).

nodriver provides:
- Undetected Chrome automation (bypasses bot detection)
- CDP-based control (no webdriver fingerprint)
- Anti-bot evasion built-in

Use this for:
- Sites with advanced bot detection (Cloudflare, DataDome)
- French government portals with strict security
- When Playwright gets blocked
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from loguru import logger

# Optional import with fallback
try:
    import nodriver as uc
    from nodriver import Browser, Tab

    NODRIVER_AVAILABLE = True
except ImportError:
    NODRIVER_AVAILABLE = False
    logger.warning("nodriver not installed. Stealth browser not available.")


class StealthAction(Enum):
    """Types of stealth browser actions."""

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    EXTRACT = "extract"
    WAIT_FOR_ELEMENT = "wait_for_element"
    WAIT_FOR_NETWORK = "wait_for_network"


@dataclass
class StealthActionRequest:
    """A stealth browser action to execute."""

    action: StealthAction
    selector: str | None = None
    value: str | None = None
    timeout: int = 30
    wait_for: str | None = None  # CSS selector to wait for after action


@dataclass
class StealthResult:
    """Result of a stealth browser action."""

    success: bool
    action: StealthAction
    screenshot_b64: str | None = None
    content: str | None = None
    error: str | None = None
    duration_ms: int = 0
    url: str | None = None


class NodriverBrowserAgent:
    """Stealth browser automation using nodriver.

    This agent is designed for sites that block standard automation:
    - French government portals (service-public.fr, impots.gouv.fr)
    - Sites with Cloudflare protection
    - APIs requiring browser-like access
    """

    def __init__(
        self,
        headless: bool = True,
        user_data_dir: str | None = None,
        proxy: str | None = None,
        screenshot_callback: Callable[[str, str], None] | None = None,
    ):
        """Initialize stealth browser agent.

        Args:
            headless: Run browser in headless mode
            user_data_dir: Chrome user data directory (for persistent sessions)
            proxy: Proxy server URL (e.g., "http://proxy:8080")
            screenshot_callback: Callback for streaming screenshots (b64, url)
        """
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.proxy = proxy
        self.screenshot_callback = screenshot_callback
        self._browser: Browser | None = None
        self._tab: Tab | None = None

    async def start(self) -> bool:
        """Start the stealth browser."""
        if not NODRIVER_AVAILABLE:
            logger.error("nodriver not available. Install with: pip install nodriver")
            return False

        try:
            # Configure browser options
            options = {}

            if self.headless:
                options["headless"] = True

            if self.user_data_dir:
                options["user_data_dir"] = self.user_data_dir

            if self.proxy:
                options["browser_args"] = [f"--proxy-server={self.proxy}"]

            # Start browser
            self._browser = await uc.start(**options)
            self._tab = await self._browser.get("about:blank")

            logger.info("Stealth browser started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start stealth browser: {e}")
            return False

    async def stop(self) -> None:
        """Stop the stealth browser."""
        if self._browser:
            try:
                # browser.stop() is not awaitable in nodriver
                self._browser.stop()
            except Exception as e:
                logger.warning(f"Error stopping browser: {e}")
            finally:
                self._browser = None
                self._tab = None
            logger.info("Stealth browser stopped")

    async def navigate(self, url: str, wait_idle: bool = True) -> StealthResult:
        """Navigate to a URL with stealth."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.NAVIGATE,
                    error="Browser not started",
                )

            await self._tab.get(url)

            if wait_idle:
                # nodriver doesn't have wait_for_idle, use a small delay instead
                await asyncio.sleep(0.5)

            # Get page content
            content = await self.get_content()

            # Take screenshot for streaming
            screenshot_b64 = await self._take_screenshot()

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=True,
                action=StealthAction.NAVIGATE,
                screenshot_b64=screenshot_b64,
                content=content,
                url=url,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=False,
                action=StealthAction.NAVIGATE,
                error=str(e),
                url=url,
                duration_ms=duration,
            )

    async def get_content(self) -> str:
        """Get page HTML content."""
        if not self._tab:
            return ""

        try:
            content = await self._tab.get_content()
            return content or ""
        except Exception as e:
            logger.error(f"Failed to get content: {e}")
            return ""

    async def get_text(self) -> str:
        """Get page text content (without HTML tags)."""
        if not self._tab:
            return ""

        try:
            # Execute JavaScript to get text content
            result = await self._tab.evaluate("document.body.innerText")
            return result or ""
        except Exception as e:
            logger.error(f"Failed to get text: {e}")
            return ""

    async def click(self, selector: str) -> StealthResult:
        """Click an element by CSS selector."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.CLICK,
                    error="Browser not started",
                )

            # Find and click element
            element = await self._tab.select(selector)
            if element:
                await element.click()
                await self._tab.wait_for_idle()

                screenshot_b64 = await self._take_screenshot()
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                return StealthResult(
                    success=True,
                    action=StealthAction.CLICK,
                    screenshot_b64=screenshot_b64,
                    duration_ms=duration,
                )
            else:
                return StealthResult(
                    success=False,
                    action=StealthAction.CLICK,
                    error=f"Element not found: {selector}",
                )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=False,
                action=StealthAction.CLICK,
                error=str(e),
                duration_ms=duration,
            )

    async def type_text(self, selector: str, text: str) -> StealthResult:
        """Type text into an input element."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.TYPE,
                    error="Browser not started",
                )

            element = await self._tab.select(selector)
            if element:
                await element.send_keys(text)
                await self._tab.wait_for_idle()

                screenshot_b64 = await self._take_screenshot()
                duration = int((datetime.now() - start_time).total_seconds() * 1000)
                return StealthResult(
                    success=True,
                    action=StealthAction.TYPE,
                    screenshot_b64=screenshot_b64,
                    duration_ms=duration,
                )
            else:
                return StealthResult(
                    success=False,
                    action=StealthAction.TYPE,
                    error=f"Element not found: {selector}",
                )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=False,
                action=StealthAction.TYPE,
                error=str(e),
                duration_ms=duration,
            )

    async def wait_for_selector(self, selector: str, timeout: int = 30) -> StealthResult:
        """Wait for an element to appear."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.WAIT_FOR_ELEMENT,
                    error="Browser not started",
                )

            # Poll for element
            for _ in range(timeout * 10):  # 100ms intervals
                element = await self._tab.select(selector)
                if element:
                    duration = int((datetime.now() - start_time).total_seconds() * 1000)
                    return StealthResult(
                        success=True,
                        action=StealthAction.WAIT_FOR_ELEMENT,
                        duration_ms=duration,
                    )
                await asyncio.sleep(0.1)

            return StealthResult(
                success=False,
                action=StealthAction.WAIT_FOR_ELEMENT,
                error=f"Timeout waiting for: {selector}",
            )

        except Exception as e:
            return StealthResult(
                success=False,
                action=StealthAction.WAIT_FOR_ELEMENT,
                error=str(e),
            )

    async def extract_data(self, selector: str) -> StealthResult:
        """Extract text content from elements matching selector."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.EXTRACT,
                    error="Browser not started",
                )

            # Get all matching elements
            js_code = f"""
            Array.from(document.querySelectorAll('{selector}'))
                .map(el => el.innerText || el.textContent)
                .filter(text => text.trim())
            """
            result = await self._tab.evaluate(js_code)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=True,
                action=StealthAction.EXTRACT,
                content=str(result) if result else "",
                duration_ms=duration,
            )

        except Exception as e:
            return StealthResult(
                success=False,
                action=StealthAction.EXTRACT,
                error=str(e),
            )

    async def scroll_to_bottom(self) -> StealthResult:
        """Scroll to the bottom of the page."""
        start_time = datetime.now()
        try:
            if not self._tab:
                return StealthResult(
                    success=False,
                    action=StealthAction.SCROLL,
                    error="Browser not started",
                )

            await self._tab.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)
            await self._tab.wait_for_idle()

            screenshot_b64 = await self._take_screenshot()
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthResult(
                success=True,
                action=StealthAction.SCROLL,
                screenshot_b64=screenshot_b64,
                duration_ms=duration,
            )

        except Exception as e:
            return StealthResult(
                success=False,
                action=StealthAction.SCROLL,
                error=str(e),
            )

    async def _take_screenshot(self) -> str | None:
        """Take a screenshot and optionally stream it."""
        try:
            if not self._tab:
                return None

            # Take screenshot
            screenshot_bytes = await self._tab.screenshot()
            if screenshot_bytes:
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                # Stream to callback if available
                # Callback signature: (action: str, screenshot_b64: str)
                if self.screenshot_callback:
                    self.screenshot_callback("screenshot", screenshot_b64)

                return screenshot_b64
            return None

        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")
            return None

    async def execute_action(self, request: StealthActionRequest) -> StealthResult:
        """Execute a stealth action request."""
        match request.action:
            case StealthAction.NAVIGATE:
                return await self.navigate(request.value or "")
            case StealthAction.CLICK:
                return await self.click(request.selector or "")
            case StealthAction.TYPE:
                return await self.type_text(request.selector or "", request.value or "")
            case StealthAction.SCROLL:
                return await self.scroll_to_bottom()
            case StealthAction.EXTRACT:
                return await self.extract_data(request.selector or "*")
            case StealthAction.WAIT_FOR_ELEMENT:
                return await self.wait_for_selector(request.selector or "", request.timeout)
            case _:
                return StealthResult(
                    success=False,
                    action=request.action,
                    error=f"Unknown action: {request.action}",
                )

    async def __aenter__(self) -> NodriverBrowserAgent:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


# Convenience function for quick scraping
async def stealth_scrape(url: str, extract_selector: str | None = None) -> str:
    """Quick stealth scraping of a URL.

    Args:
        url: URL to scrape
        extract_selector: Optional CSS selector for specific content

    Returns:
        Page content (HTML or extracted text)
    """
    if not NODRIVER_AVAILABLE:
        raise ImportError("nodriver not available. Install with: pip install nodriver")

    async with NodriverBrowserAgent(headless=True) as agent:
        result = await agent.navigate(url)
        if not result.success:
            raise RuntimeError(f"Navigation failed: {result.error}")

        if extract_selector:
            extract_result = await agent.extract_data(extract_selector)
            return extract_result.content or ""
        else:
            return await agent.get_content()
