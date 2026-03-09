"""Playwright-based worker for JavaScript-heavy sites."""
import asyncio
import hashlib
from urllib.parse import urlparse

from loguru import logger

from .base_worker import BaseWorker, CrawlResult
from .rate_limiter import RateLimiter

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Anti-detection stealth script
STEALTH_SCRIPT = """
    // Hide webdriver flag
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // Mock plugins array
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // Mock languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['fr-FR', 'fr', 'en-US', 'en']
    });

    // Mock chrome runtime
    window.chrome = {
        runtime: {}
    };

    // Override permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
"""


class PlaywrightWorker(BaseWorker):
    """
    Browser-based worker using Playwright.

    Best for: JavaScript-heavy sites, SPAs, sites requiring interaction.
    Not suitable for: Simple APIs or static HTML (use HTTPXWorker - faster).

    Features:
    - Anti-detection stealth scripts
    - JavaScript rendering
    - User-Agent rotation
    - Rate limiting support
    - Automatic retry with exponential backoff
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        timeout: int = 30000,
        max_retries: int = 3,
        headless: bool = True,
        wait_until: str = "networkidle",
    ):
        """
        Initialize PlaywrightWorker.

        Args:
            rate_limiter: Optional rate limiter for domain throttling
            timeout: Page load timeout in milliseconds
            max_retries: Maximum retry attempts per URL
            headless: Run browser in headless mode
            wait_until: Navigation wait strategy (load, domcontentloaded, networkidle)
        """
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.headless = headless
        self.wait_until = wait_until
        self._ua_index = 0

        self._playwright = None
        self._browser = None
        self._context = None

    def _get_user_agent(self) -> str:
        """Get next User-Agent from rotation."""
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    def _compute_hash(self, content: str) -> str:
        """Compute content hash for change detection."""
        return hashlib.md5(content.encode()).hexdigest()

    async def _ensure_browser(self) -> None:
        """Ensure browser is initialized."""
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise ImportError(
                "playwright not installed. Run: pip install playwright && playwright install chromium"
            ) from e

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu" if self.headless else "--enable-gpu",
            ],
        )

        logger.info(f"Playwright browser started (headless={self.headless})")

    async def _create_context(self, user_agent: str):
        """Create a new browser context with stealth settings."""
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=user_agent,
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )

        # Inject stealth scripts
        await context.add_init_script(STEALTH_SCRIPT)

        return context

    async def crawl(self, url: str, source_id: str) -> CrawlResult:
        """Crawl a URL using Playwright browser."""
        domain = self._extract_domain(url)

        # Check rate limiting
        if self.rate_limiter:
            if self.rate_limiter.is_blocked(domain):
                return CrawlResult(
                    source_id=source_id,
                    url=url,
                    success=False,
                    error=f"Domain {domain} is temporarily blocked",
                )
            await self.rate_limiter.acquire(domain)

        await self._ensure_browser()

        user_agent = self._get_user_agent()
        context = await self._create_context(user_agent)
        page = await context.new_page()

        try:
            for attempt in range(self.max_retries):
                try:
                    response = await page.goto(
                        url, wait_until=self.wait_until, timeout=self.timeout
                    )

                    if response is None:
                        return CrawlResult(
                            source_id=source_id,
                            url=url,
                            success=False,
                            error="No response received",
                        )

                    status_code = response.status

                    # Handle rate limiting
                    if status_code in (429, 503):
                        if self.rate_limiter:
                            block_time = 300 * (2**attempt)
                            self.rate_limiter.block_domain(domain, block_time)

                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2**attempt)
                            continue

                        return CrawlResult(
                            source_id=source_id,
                            url=url,
                            success=False,
                            status_code=status_code,
                            error=f"Rate limited: {status_code}",
                        )

                    if status_code >= 400:
                        return CrawlResult(
                            source_id=source_id,
                            url=url,
                            success=False,
                            status_code=status_code,
                            error=f"HTTP {status_code}",
                        )

                    # Wait a bit for dynamic content to load
                    await asyncio.sleep(0.5)

                    # Extract rendered content
                    content = await page.content()

                    return CrawlResult(
                        source_id=source_id,
                        url=url,
                        success=True,
                        content=content,
                        content_hash=self._compute_hash(content),
                        status_code=status_code,
                    )

                except Exception as e:
                    error_msg = str(e)
                    logger.warning(
                        f"Playwright error crawling {url} (attempt {attempt + 1}): {error_msg}"
                    )

                    if "Timeout" in error_msg:
                        if attempt == self.max_retries - 1:
                            return CrawlResult(
                                source_id=source_id,
                                url=url,
                                success=False,
                                error=f"Timeout after {self.max_retries} attempts",
                            )
                        await asyncio.sleep(2**attempt)
                        continue

                    if attempt == self.max_retries - 1:
                        return CrawlResult(
                            source_id=source_id,
                            url=url,
                            success=False,
                            error=error_msg,
                        )

            return CrawlResult(
                source_id=source_id,
                url=url,
                success=False,
                error="Max retries exceeded",
            )

        finally:
            await page.close()
            await context.close()

    async def crawl_with_interaction(
        self,
        url: str,
        source_id: str,
        actions: list[dict] | None = None,
    ) -> CrawlResult:
        """
        Crawl a URL with optional interactions before extraction.

        Args:
            url: URL to crawl
            source_id: Identifier for the source
            actions: List of actions to perform, e.g.:
                [
                    {"type": "click", "selector": ".load-more"},
                    {"type": "wait", "selector": ".results"},
                    {"type": "scroll", "distance": 500},
                ]

        Returns:
            CrawlResult with rendered content after interactions
        """
        domain = self._extract_domain(url)

        if self.rate_limiter:
            if self.rate_limiter.is_blocked(domain):
                return CrawlResult(
                    source_id=source_id,
                    url=url,
                    success=False,
                    error=f"Domain {domain} is temporarily blocked",
                )
            await self.rate_limiter.acquire(domain)

        await self._ensure_browser()

        user_agent = self._get_user_agent()
        context = await self._create_context(user_agent)
        page = await context.new_page()

        try:
            response = await page.goto(
                url, wait_until=self.wait_until, timeout=self.timeout
            )

            if response is None or response.status >= 400:
                status = response.status if response else None
                return CrawlResult(
                    source_id=source_id,
                    url=url,
                    success=False,
                    status_code=status,
                    error=f"HTTP {status}" if status else "No response",
                )

            # Execute interactions
            if actions:
                for action in actions:
                    await self._execute_action(page, action)

            # Extract rendered content
            content = await page.content()

            return CrawlResult(
                source_id=source_id,
                url=url,
                success=True,
                content=content,
                content_hash=self._compute_hash(content),
                status_code=response.status,
            )

        except Exception as e:
            logger.error(f"Crawl with interaction failed for {url}: {e}")
            return CrawlResult(
                source_id=source_id,
                url=url,
                success=False,
                error=str(e),
            )

        finally:
            await page.close()
            await context.close()

    async def _execute_action(self, page, action: dict) -> None:
        """Execute a single browser action."""
        action_type = action.get("type")
        selector = action.get("selector")
        timeout = action.get("timeout", 10000)

        if action_type == "click":
            await page.click(selector, timeout=timeout)
            await asyncio.sleep(0.3)

        elif action_type == "type":
            value = action.get("value", "")
            await page.fill(selector, value, timeout=timeout)

        elif action_type == "wait":
            if selector:
                await page.wait_for_selector(selector, timeout=timeout)
            else:
                await asyncio.sleep(action.get("duration", 1))

        elif action_type == "scroll":
            distance = action.get("distance", 500)
            await page.mouse.wheel(0, distance)
            await asyncio.sleep(0.5)

        elif action_type == "press":
            key = action.get("key", "Enter")
            await page.keyboard.press(key)

        else:
            logger.warning(f"Unknown action type: {action_type}")

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        self._context = None
        logger.info("PlaywrightWorker closed")
