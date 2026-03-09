"""Stealth browser agent using Camoufox (anti-detect Firefox).

Camoufox provides:
- Firefox-based stealth (complements Chrome/nodriver)
- C++ level fingerprint spoofing (undetectable via JS)
- BrowserForge fingerprints mimicking real traffic
- Playwright-compatible API

Use this for:
- Sites blocking Chrome-based automation
- When nodriver gets detected
- French government portals needing diverse browser profiles
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

# Optional import with fallback
try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logger.warning("camoufox not installed. Firefox stealth browser not available.")


class CamoufoxAction(Enum):
    """Types of Camoufox browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    EXTRACT = "extract"
    WAIT_FOR_SELECTOR = "wait_for_selector"


@dataclass
class CamoufoxResult:
    """Result of a Camoufox browser action."""
    success: bool
    action: CamoufoxAction
    screenshot_b64: str | None = None
    content: str | None = None
    error: str | None = None
    duration_ms: int = 0
    url: str | None = None
    browser_type: str = "camoufox"


@dataclass
class FingerprintConfig:
    """Configuration for browser fingerprint spoofing.

    Camoufox uses BrowserForge to generate realistic fingerprints.
    Unset values are auto-populated from real-world distributions.
    """
    # Navigator
    user_agent: str | None = None
    platform: str | None = None  # "Win32", "MacIntel", "Linux x86_64"
    language: str = "fr-FR"

    # Screen
    screen_width: int | None = None
    screen_height: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None

    # Locale
    locale_language: str = "fr"
    locale_region: str = "FR"
    timezone: str = "Europe/Paris"

    # Geolocation (for French territory)
    latitude: float | None = None
    longitude: float | None = None

    # Behavior
    humanize: bool = True  # Human-like cursor movement

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to Camoufox config dictionary.

        Note: Most settings are now handled via Camoufox constructor params
        (locale, geoip, etc.) rather than config dict. Only screen/viewport
        remain in config dict.
        """
        config = {}

        # Only screen dimensions still use config dict
        if self.screen_width:
            config["screen.width"] = self.screen_width
        if self.screen_height:
            config["screen.height"] = self.screen_height
        if self.viewport_width:
            config["window.innerWidth"] = self.viewport_width
        if self.viewport_height:
            config["window.innerHeight"] = self.viewport_height

        return config

    def get_locale(self) -> str:
        """Get locale string for Camoufox."""
        return f"{self.locale_language}-{self.locale_region}"


# French city coordinates for geolocation spoofing
FRENCH_GEOLOCATIONS = {
    "75": (48.8566, 2.3522),     # Paris
    "69": (45.7640, 4.8357),     # Lyon
    "13": (43.2965, 5.3698),     # Marseille
    "31": (43.6047, 1.4442),     # Toulouse
    "33": (44.8378, -0.5792),    # Bordeaux
    "59": (50.6292, 3.0573),     # Lille
    "06": (43.7102, 7.2620),     # Nice
    "44": (47.2184, -1.5536),    # Nantes
    "67": (48.5734, 7.7521),     # Strasbourg
    "34": (43.6108, 3.8767),     # Montpellier
}


class CamoufoxBrowserAgent:
    """Stealth browser automation using Camoufox (Firefox-based).

    Complements NodriverBrowserAgent (Chrome-based) for maximum coverage:
    - Camoufox: Firefox with C++ fingerprint spoofing
    - nodriver: Chrome with CDP-based stealth

    Use CamoufoxBrowserAgent when:
    - Site blocks Chrome-based automation
    - Need Firefox-specific behavior
    - nodriver gets detected
    """

    def __init__(
        self,
        headless: bool = True,
        fingerprint: FingerprintConfig | None = None,
        proxy: str | None = None,
        territory: str | None = None,
        screenshot_callback: Callable[[str, str], None] | None = None,
        exclude_addons: list[str] | None = None,
    ):
        """Initialize Camoufox browser agent.

        Args:
            headless: Run browser in headless mode
            fingerprint: Custom fingerprint config (auto-generated if None)
            proxy: Proxy server URL
            territory: French department code for geolocation (e.g., "75")
            screenshot_callback: Callback for streaming screenshots
            exclude_addons: Addons to exclude (e.g., ["ubo"] for uBlock)
        """
        self.headless = headless
        self.proxy = proxy
        self.screenshot_callback = screenshot_callback
        self.exclude_addons = exclude_addons or []

        # Setup fingerprint with territory-based geolocation
        if fingerprint:
            self.fingerprint = fingerprint
        else:
            self.fingerprint = FingerprintConfig()

        # Add French geolocation if territory specified
        if territory and territory in FRENCH_GEOLOCATIONS:
            lat, lon = FRENCH_GEOLOCATIONS[territory]
            self.fingerprint.latitude = lat
            self.fingerprint.longitude = lon

        self._browser = None
        self._page = None
        self._started = False

    async def start(self) -> bool:
        """Start the Camoufox browser.

        Returns:
            True if browser started successfully
        """
        if not CAMOUFOX_AVAILABLE:
            logger.error("Camoufox not installed. Run: pip install camoufox && camoufox fetch")
            return False

        if self._started:
            return True

        try:
            # Build Camoufox options using modern API
            options = {
                "headless": self.headless,
                "locale": self.fingerprint.get_locale(),  # Use locale param
                "geoip": True,  # Let Camoufox auto-populate geolocation
                "humanize": self.fingerprint.humanize,
                "i_know_what_im_doing": True,  # Suppress warnings for screen config
            }

            # Only add config dict if we have screen/viewport settings
            config = self.fingerprint.to_config_dict()
            if config:
                options["config"] = config

            if self.proxy:
                options["proxy"] = {"server": self.proxy}

            if self.exclude_addons:
                options["exclude_addons"] = self.exclude_addons

            # Start browser
            self._browser_context = AsyncCamoufox(**options)
            self._browser = await self._browser_context.__aenter__()
            self._page = await self._browser.new_page()
            self._started = True

            logger.info("Camoufox browser started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Camoufox: {e}")
            return False

    async def stop(self) -> None:
        """Stop the Camoufox browser."""
        if self._browser_context and self._started:
            try:
                await self._browser_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error stopping Camoufox: {e}")
            finally:
                self._browser = None
                self._page = None
                self._started = False
                logger.info("Camoufox browser stopped")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> CamoufoxResult:
        """Navigate to a URL.

        Args:
            url: URL to navigate to
            wait_until: Wait condition ("load", "domcontentloaded", "networkidle")

        Returns:
            CamoufoxResult with page content
        """
        start_time = datetime.now()

        if not self._started:
            if not await self.start():
                return CamoufoxResult(
                    success=False,
                    action=CamoufoxAction.NAVIGATE,
                    error="Browser not started",
                )

        try:
            await self._page.goto(url, wait_until=wait_until)
            content = await self._page.content()

            # Take screenshot if callback provided
            # Callback signature: (action: str, screenshot_b64: str)
            screenshot_b64 = None
            if self.screenshot_callback:
                screenshot_b64 = await self._take_screenshot()
                if screenshot_b64:
                    self.screenshot_callback("navigate", screenshot_b64)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)

            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.NAVIGATE,
                content=content,
                screenshot_b64=screenshot_b64,
                url=url,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Navigation failed: {e}")
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.NAVIGATE,
                error=str(e),
                url=url,
                duration_ms=duration,
            )

    async def click(self, selector: str, timeout: int = 30000) -> CamoufoxResult:
        """Click an element.

        Args:
            selector: CSS selector or XPath
            timeout: Timeout in milliseconds

        Returns:
            CamoufoxResult
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.CLICK,
                error="Browser not started",
            )

        try:
            # Human-like click with Camoufox
            await self._page.click(selector, timeout=timeout)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.CLICK,
                duration_ms=duration,
                url=self._page.url,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.CLICK,
                error=str(e),
                duration_ms=duration,
            )

    async def type_text(
        self,
        selector: str,
        text: str,
        delay: int = 50,
        clear_first: bool = True,
    ) -> CamoufoxResult:
        """Type text into an element with human-like delay.

        Args:
            selector: CSS selector
            text: Text to type
            delay: Delay between keystrokes in ms
            clear_first: Clear field before typing

        Returns:
            CamoufoxResult
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.TYPE,
                error="Browser not started",
            )

        try:
            if clear_first:
                await self._page.fill(selector, "")

            # Human-like typing with delay
            await self._page.type(selector, text, delay=delay)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.TYPE,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.TYPE,
                error=str(e),
                duration_ms=duration,
            )

    async def extract_text(self, selector: str) -> CamoufoxResult:
        """Extract text content from elements.

        Args:
            selector: CSS selector

        Returns:
            CamoufoxResult with extracted text in content
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.EXTRACT,
                error="Browser not started",
            )

        try:
            elements = await self._page.query_selector_all(selector)
            texts = []
            for el in elements:
                text = await el.text_content()
                if text:
                    texts.append(text.strip())

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.EXTRACT,
                content="\n".join(texts),
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.EXTRACT,
                error=str(e),
                duration_ms=duration,
            )

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> CamoufoxResult:
        """Wait for an element to appear.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            CamoufoxResult
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.WAIT_FOR_SELECTOR,
                error="Browser not started",
            )

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.WAIT_FOR_SELECTOR,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.WAIT_FOR_SELECTOR,
                error=str(e),
                duration_ms=duration,
            )

    async def screenshot(self, full_page: bool = False) -> CamoufoxResult:
        """Take a screenshot.

        Args:
            full_page: Capture full scrollable page

        Returns:
            CamoufoxResult with screenshot_b64
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.SCREENSHOT,
                error="Browser not started",
            )

        try:
            screenshot_b64 = await self._take_screenshot(full_page)

            # Callback signature: (action: str, screenshot_b64: str)
            if self.screenshot_callback and screenshot_b64:
                self.screenshot_callback("screenshot", screenshot_b64)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.SCREENSHOT,
                screenshot_b64=screenshot_b64,
                url=self._page.url,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.SCREENSHOT,
                error=str(e),
                duration_ms=duration,
            )

    async def get_content(self) -> str:
        """Get current page HTML content."""
        if not self._page:
            return ""
        try:
            return await self._page.content()
        except Exception:
            return ""

    async def get_url(self) -> str:
        """Get current page URL."""
        if not self._page:
            return ""
        return self._page.url

    async def scroll(self, direction: str = "down", amount: int = 500) -> CamoufoxResult:
        """Scroll the page with human-like behavior.

        Args:
            direction: "up" or "down"
            amount: Scroll amount in pixels

        Returns:
            CamoufoxResult
        """
        start_time = datetime.now()

        if not self._page:
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.SCROLL,
                error="Browser not started",
            )

        try:
            scroll_amount = amount if direction == "down" else -amount
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")

            # Small delay for human-like behavior
            await asyncio.sleep(0.3)

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=True,
                action=CamoufoxAction.SCROLL,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return CamoufoxResult(
                success=False,
                action=CamoufoxAction.SCROLL,
                error=str(e),
                duration_ms=duration,
            )

    async def _take_screenshot(self, full_page: bool = False) -> str:
        """Take screenshot and return base64."""
        import base64

        screenshot_bytes = await self._page.screenshot(full_page=full_page)
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Convenience function for quick stealth navigation
async def stealth_fetch_firefox(
    url: str,
    territory: str | None = None,
    headless: bool = True,
) -> str:
    """Quick stealth fetch using Camoufox.

    Args:
        url: URL to fetch
        territory: French department code for geolocation
        headless: Run headless

    Returns:
        Page HTML content
    """
    async with CamoufoxBrowserAgent(
        headless=headless,
        territory=territory,
    ) as agent:
        result = await agent.navigate(url)
        return result.content if result.success else ""
