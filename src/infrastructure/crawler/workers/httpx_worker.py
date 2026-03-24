"""HTTPX-based worker for lightweight crawling."""

import hashlib
from urllib.parse import urlparse

import httpx
from loguru import logger

from .base_worker import BaseWorker, CrawlResult
from .rate_limiter import RateLimiter

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


class HTTPXWorker(BaseWorker):
    """
    Async HTTP worker using httpx.

    Best for: APIs, static HTML pages, RSS/Atom feeds.
    Not suitable for: JavaScript-heavy sites (use PlaywrightWorker).
    """

    def __init__(
        self, rate_limiter: RateLimiter | None = None, timeout: int = 30, max_retries: int = 3
    ):
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self._ua_index = 0
        self._client: httpx.AsyncClient | None = None

    def _get_user_agent(self) -> str:
        """Get next User-Agent from rotation."""
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=100),
            )
        return self._client

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    def _compute_hash(self, content: str) -> str:
        """Compute content hash for change detection."""
        return hashlib.md5(content.encode()).hexdigest()

    async def crawl(self, url: str, source_id: str) -> CrawlResult:
        """Crawl a URL using httpx."""
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

        client = await self._ensure_client()

        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }

        for attempt in range(self.max_retries):
            try:
                response = await client.get(url, headers=headers)

                if response.status_code in (429, 503):
                    if self.rate_limiter:
                        block_time = 300 * (2**attempt)
                        self.rate_limiter.block_domain(domain, block_time)

                    if attempt < self.max_retries - 1:
                        continue

                    return CrawlResult(
                        source_id=source_id,
                        url=url,
                        success=False,
                        status_code=response.status_code,
                        error=f"Rate limited: {response.status_code}",
                    )

                if response.status_code >= 400:
                    return CrawlResult(
                        source_id=source_id,
                        url=url,
                        success=False,
                        status_code=response.status_code,
                        error=f"HTTP {response.status_code}",
                    )

                content = response.text
                return CrawlResult(
                    source_id=source_id,
                    url=url,
                    success=True,
                    content=content,
                    content_hash=self._compute_hash(content),
                    status_code=response.status_code,
                )

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout crawling {url}: {e}")
                if attempt == self.max_retries - 1:
                    return CrawlResult(
                        source_id=source_id,
                        url=url,
                        success=False,
                        error=f"Timeout after {self.max_retries} attempts",
                    )

            except httpx.RequestError as e:
                logger.warning(f"Request error crawling {url}: {e}")
                if attempt == self.max_retries - 1:
                    return CrawlResult(source_id=source_id, url=url, success=False, error=str(e))

        return CrawlResult(
            source_id=source_id, url=url, success=False, error="Max retries exceeded"
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
