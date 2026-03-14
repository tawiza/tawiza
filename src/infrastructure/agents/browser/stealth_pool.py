"""Stealth Browser Pool - Intelligent selection between nodriver and Camoufox.

This module provides:
- Automatic browser selection based on site characteristics
- Fallback chain: nodriver -> Camoufox -> standard Playwright
- Domain-specific browser preferences learned over time
- Parallel browser pool for concurrent stealth requests
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from src.infrastructure.agents.browser.camoufox_agent import (
    CAMOUFOX_AVAILABLE,
    CamoufoxBrowserAgent,
    CamoufoxResult,
    FingerprintConfig,
)

# Import both stealth browsers
from src.infrastructure.agents.browser.nodriver_agent import (
    NODRIVER_AVAILABLE,
    NodriverBrowserAgent,
)
from src.infrastructure.agents.browser.nodriver_agent import (
    StealthResult as NodriverResult,
)


class BrowserType(Enum):
    """Available stealth browser types."""

    NODRIVER = "nodriver"  # Chrome-based, CDP direct
    CAMOUFOX = "camoufox"  # Firefox-based, C++ hooks
    PLAYWRIGHT = "playwright"  # Standard fallback


@dataclass
class StealthFetchResult:
    """Unified result from stealth browser pool."""

    success: bool
    content: str | None = None
    screenshot_b64: str | None = None
    url: str | None = None
    browser_used: BrowserType | None = None
    error: str | None = None
    duration_ms: int = 0
    retries: int = 0


@dataclass
class DomainPreference:
    """Learned browser preference for a domain."""

    domain: str
    preferred_browser: BrowserType
    success_count: int = 0
    failure_count: int = 0
    last_success: datetime | None = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5


# Known domain preferences based on detection patterns
KNOWN_DOMAIN_PREFERENCES: dict[str, BrowserType] = {
    # Sites that work better with Firefox (Camoufox)
    "service-public.fr": BrowserType.CAMOUFOX,
    "impots.gouv.fr": BrowserType.CAMOUFOX,
    "ameli.fr": BrowserType.CAMOUFOX,
    "caf.fr": BrowserType.CAMOUFOX,
    "pole-emploi.fr": BrowserType.CAMOUFOX,
    "francetravail.fr": BrowserType.CAMOUFOX,
    # Sites that work better with Chrome (nodriver)
    "societe.com": BrowserType.NODRIVER,
    "pappers.fr": BrowserType.NODRIVER,
    "infogreffe.fr": BrowserType.NODRIVER,
    "verif.com": BrowserType.NODRIVER,
    # Cloudflare-protected (try nodriver first)
    "bodacc.fr": BrowserType.NODRIVER,
    "boamp.fr": BrowserType.NODRIVER,
}


class StealthBrowserPool:
    """Intelligent stealth browser pool with automatic selection.

    Manages both nodriver (Chrome) and Camoufox (Firefox) for maximum
    coverage against bot detection. Learns domain preferences over time.

    Features:
    - Automatic browser selection based on domain
    - Fallback chain on detection/failure
    - Parallel request support
    - Domain preference learning
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: str | None = None,
        territory: str | None = None,
        screenshot_callback: Callable[[str, str], None] | None = None,
        max_parallel: int = 3,
    ):
        """Initialize stealth browser pool.

        Args:
            headless: Run browsers in headless mode
            proxy: Proxy server URL
            territory: French department code for geolocation
            screenshot_callback: Callback for screenshots
            max_parallel: Maximum parallel browser instances
        """
        self.headless = headless
        self.proxy = proxy
        self.territory = territory
        self.screenshot_callback = screenshot_callback
        self.max_parallel = max_parallel

        # Domain preference tracking
        self.domain_preferences: dict[str, DomainPreference] = {}

        # Semaphore for parallel limiting
        self._semaphore = asyncio.Semaphore(max_parallel)

        # Active browser instances
        self._nodriver_agent: NodriverBrowserAgent | None = None
        self._camoufox_agent: CamoufoxBrowserAgent | None = None

        logger.info(
            f"StealthBrowserPool initialized: "
            f"nodriver={'available' if NODRIVER_AVAILABLE else 'unavailable'}, "
            f"camoufox={'available' if CAMOUFOX_AVAILABLE else 'unavailable'}"
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.lower()

    def _get_preferred_browser(self, url: str) -> BrowserType:
        """Get preferred browser for a URL based on domain.

        Priority:
        1. Learned preferences (if success rate > 70%)
        2. Known domain preferences
        3. Default: nodriver (Chrome) - wider compatibility
        """
        domain = self._extract_domain(url)

        # Check learned preferences
        if domain in self.domain_preferences:
            pref = self.domain_preferences[domain]
            if pref.success_rate > 0.7:
                return pref.preferred_browser

        # Check known preferences
        for known_domain, browser in KNOWN_DOMAIN_PREFERENCES.items():
            if known_domain in domain:
                return browser

        # Default to nodriver if available
        if NODRIVER_AVAILABLE:
            return BrowserType.NODRIVER
        elif CAMOUFOX_AVAILABLE:
            return BrowserType.CAMOUFOX
        else:
            return BrowserType.PLAYWRIGHT

    def _get_fallback_chain(self, primary: BrowserType) -> list[BrowserType]:
        """Get fallback chain starting from primary browser."""
        all_browsers = [BrowserType.NODRIVER, BrowserType.CAMOUFOX, BrowserType.PLAYWRIGHT]

        # Filter by availability
        available = []
        for b in all_browsers:
            if (
                b == BrowserType.NODRIVER
                and NODRIVER_AVAILABLE
                or b == BrowserType.CAMOUFOX
                and CAMOUFOX_AVAILABLE
            ):
                available.append(b)
            elif b == BrowserType.PLAYWRIGHT:
                available.append(b)  # Always available as last resort

        # Reorder to put primary first
        if primary in available:
            available.remove(primary)
            available.insert(0, primary)

        return available

    async def _get_nodriver_agent(self) -> NodriverBrowserAgent:
        """Get or create nodriver agent."""
        if not self._nodriver_agent:
            self._nodriver_agent = NodriverBrowserAgent(
                headless=self.headless,
                proxy=self.proxy,
                screenshot_callback=self.screenshot_callback,
            )
        return self._nodriver_agent

    async def _get_camoufox_agent(self) -> CamoufoxBrowserAgent:
        """Get or create Camoufox agent."""
        if not self._camoufox_agent:
            self._camoufox_agent = CamoufoxBrowserAgent(
                headless=self.headless,
                proxy=self.proxy,
                territory=self.territory,
                screenshot_callback=self.screenshot_callback,
            )
        return self._camoufox_agent

    async def _fetch_with_nodriver(self, url: str) -> StealthFetchResult:
        """Fetch using nodriver (Chrome)."""
        try:
            agent = await self._get_nodriver_agent()
            # Ensure browser is started
            if not agent._browser:
                started = await agent.start()
                if not started:
                    raise RuntimeError("Failed to start nodriver browser")
            result = await agent.navigate(url)

            return StealthFetchResult(
                success=result.success,
                content=result.content,
                screenshot_b64=result.screenshot_b64,
                url=result.url,
                browser_used=BrowserType.NODRIVER,
                error=result.error,
                duration_ms=result.duration_ms,
            )
        except Exception as e:
            logger.error(f"nodriver fetch failed: {e}")
            return StealthFetchResult(
                success=False,
                browser_used=BrowserType.NODRIVER,
                error=str(e),
                url=url,
            )

    async def _fetch_with_camoufox(self, url: str) -> StealthFetchResult:
        """Fetch using Camoufox (Firefox)."""
        try:
            agent = await self._get_camoufox_agent()
            result = await agent.navigate(url)

            return StealthFetchResult(
                success=result.success,
                content=result.content,
                screenshot_b64=result.screenshot_b64,
                url=result.url,
                browser_used=BrowserType.CAMOUFOX,
                error=result.error,
                duration_ms=result.duration_ms,
            )
        except Exception as e:
            logger.error(f"Camoufox fetch failed: {e}")
            return StealthFetchResult(
                success=False,
                browser_used=BrowserType.CAMOUFOX,
                error=str(e),
                url=url,
            )

    async def _fetch_with_playwright(self, url: str) -> StealthFetchResult:
        """Fetch using standard Playwright (fallback)."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()
                await page.goto(url)
                content = await page.content()
                await browser.close()

                return StealthFetchResult(
                    success=True,
                    content=content,
                    url=url,
                    browser_used=BrowserType.PLAYWRIGHT,
                )
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return StealthFetchResult(
                success=False,
                browser_used=BrowserType.PLAYWRIGHT,
                error=str(e),
                url=url,
            )

    async def fetch(
        self,
        url: str,
        preferred_browser: BrowserType | None = None,
        max_retries: int = 2,
    ) -> StealthFetchResult:
        """Fetch URL with automatic browser selection and fallback.

        Args:
            url: URL to fetch
            preferred_browser: Force specific browser (None for auto-select)
            max_retries: Maximum retry attempts with fallback browsers

        Returns:
            StealthFetchResult with content or error
        """
        async with self._semaphore:
            start_time = datetime.now()

            # Determine browser chain
            primary = preferred_browser or self._get_preferred_browser(url)
            browser_chain = self._get_fallback_chain(primary)

            domain = self._extract_domain(url)
            retries = 0

            for browser_type in browser_chain[: max_retries + 1]:
                logger.info(f"Attempting {browser_type.value} for {domain}")

                if browser_type == BrowserType.NODRIVER:
                    result = await self._fetch_with_nodriver(url)
                elif browser_type == BrowserType.CAMOUFOX:
                    result = await self._fetch_with_camoufox(url)
                else:
                    result = await self._fetch_with_playwright(url)

                # Update domain preferences
                self._update_preference(domain, browser_type, result.success)

                if result.success:
                    result.retries = retries
                    total_duration = int((datetime.now() - start_time).total_seconds() * 1000)
                    result.duration_ms = total_duration
                    logger.info(
                        f"Success with {browser_type.value} for {domain} "
                        f"({total_duration}ms, {retries} retries)"
                    )
                    return result

                retries += 1
                logger.warning(f"{browser_type.value} failed for {domain}: {result.error}")

            # All browsers failed
            total_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return StealthFetchResult(
                success=False,
                url=url,
                error=f"All browsers failed after {retries} attempts",
                duration_ms=total_duration,
                retries=retries,
            )

    def _update_preference(
        self,
        domain: str,
        browser: BrowserType,
        success: bool,
    ) -> None:
        """Update domain preference based on result."""
        if domain not in self.domain_preferences:
            self.domain_preferences[domain] = DomainPreference(
                domain=domain,
                preferred_browser=browser,
            )

        pref = self.domain_preferences[domain]

        if success:
            pref.success_count += 1
            pref.last_success = datetime.now()
            # Update preferred browser if this one works better
            if browser != pref.preferred_browser:
                current_rate = pref.success_rate
                # Simple heuristic: switch if current browser has <50% success
                if current_rate < 0.5:
                    pref.preferred_browser = browser
                    logger.info(f"Updated preference for {domain}: {browser.value}")
        else:
            pref.failure_count += 1

    async def fetch_batch(
        self,
        urls: list[str],
        max_parallel: int | None = None,
    ) -> list[StealthFetchResult]:
        """Fetch multiple URLs in parallel.

        Args:
            urls: List of URLs to fetch
            max_parallel: Override max parallel (default: pool setting)

        Returns:
            List of StealthFetchResult in same order as urls
        """
        if max_parallel:
            sem = asyncio.Semaphore(max_parallel)
        else:
            sem = self._semaphore

        async def fetch_with_sem(url: str) -> StealthFetchResult:
            async with sem:
                return await self.fetch(url)

        tasks = [fetch_with_sem(url) for url in urls]
        return await asyncio.gather(*tasks)

    async def close(self) -> None:
        """Close all browser instances."""
        if self._nodriver_agent:
            await self._nodriver_agent.stop()
            self._nodriver_agent = None

        if self._camoufox_agent:
            await self._camoufox_agent.stop()
            self._camoufox_agent = None

        logger.info("StealthBrowserPool closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        return {
            "nodriver_available": NODRIVER_AVAILABLE,
            "camoufox_available": CAMOUFOX_AVAILABLE,
            "domain_preferences": {
                domain: {
                    "browser": pref.preferred_browser.value,
                    "success_rate": pref.success_rate,
                    "total_requests": pref.success_count + pref.failure_count,
                }
                for domain, pref in self.domain_preferences.items()
            },
        }


# Convenience function
async def stealth_fetch(
    url: str,
    territory: str | None = None,
    headless: bool = True,
) -> str:
    """Quick stealth fetch with automatic browser selection.

    Args:
        url: URL to fetch
        territory: French department code
        headless: Run headless

    Returns:
        Page HTML content or empty string on failure
    """
    async with StealthBrowserPool(
        headless=headless,
        territory=territory,
    ) as pool:
        result = await pool.fetch(url)
        return result.content if result.success else ""
