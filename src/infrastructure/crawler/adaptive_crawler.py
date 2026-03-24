"""AdaptiveCrawler - Intelligent web crawling with MAB optimization."""

from collections.abc import Callable
from typing import Any

from loguru import logger

from .events import CrawlerCallback, CrawlerEvent
from .parsers.html_parser import HTMLParser
from .parsers.json_parser import JSONParser
from .parsers.registry import ParserRegistry
from .scheduler.mab_scheduler import MABScheduler
from .scheduler.source_arm import SourceArm, SourceType
from .workers.base_worker import BaseWorker
from .workers.httpx_worker import HTTPXWorker
from .workers.playwright_worker import PlaywrightWorker
from .workers.rate_limiter import RateLimit, RateLimiter

# Known JS-heavy domains that require Playwright
JS_HEAVY_DOMAINS = {
    "app.sirene.fr",
    "annuaire-entreprises.data.gouv.fr",
    "societe.com",
    "pappers.fr",
    "infogreffe.fr",
    "verif.com",
}


class AdaptiveCrawler:
    """
    Intelligent web crawler with Multi-Armed Bandit optimization.

    Features:
    - MAB source selection (UCB algorithm)
    - Async worker pool with rate limiting
    - Content parsing and extraction
    - Event streaming to TAJINEAgent
    """

    def __init__(
        self,
        sources: list[dict[str, Any]] | None = None,
        exploration_param: float = 2.0,
        max_concurrent: int = 10,
        enable_playwright: bool = True,
    ):
        self.scheduler = MABScheduler(exploration_param=exploration_param)

        self.rate_limiter = RateLimiter()
        self.rate_limiter.set_limit("api.insee.fr", RateLimit(requests=100, period=60))
        self.rate_limiter.set_limit("data.gouv.fr", RateLimit(requests=50, period=60))

        # Primary worker for static content (fast, lightweight)
        self._httpx_worker = HTTPXWorker(rate_limiter=self.rate_limiter)

        # Secondary worker for JS-heavy sites (lazy-loaded)
        self._playwright_worker: PlaywrightWorker | None = None
        self._enable_playwright = enable_playwright

        self._parser_registry = ParserRegistry()
        self._parser_registry.register(JSONParser())
        self._parser_registry.register(HTMLParser())

        self._handlers: list[Callable] = []
        self.max_concurrent = max_concurrent

        if sources:
            for src in sources:
                self.add_source(
                    source_id=src["source_id"],
                    url=src["url"],
                    source_type=src.get("source_type", "web"),
                    requires_js=src.get("requires_js"),  # None = auto-detect
                )

        logger.info(
            f"AdaptiveCrawler initialized with {len(self.scheduler.arms)} sources (playwright={enable_playwright})"
        )

    def add_source(
        self,
        source_id: str,
        url: str,
        source_type: str = "web",
        requires_js: bool | None = None,
    ) -> None:
        """
        Add a source to crawl.

        Args:
            source_id: Unique identifier for the source
            url: URL to crawl
            source_type: Type of source (api, web, rss, js_heavy)
            requires_js: If True, use Playwright. If None, auto-detect from domain.
        """
        # Auto-detect JS requirement from domain
        from urllib.parse import urlparse

        if requires_js is None:
            domain = urlparse(url).netloc
            requires_js = domain in JS_HEAVY_DOMAINS or source_type == "js_heavy"

        arm = SourceArm(
            source_id=source_id,
            url=url,
            source_type=SourceType(source_type) if source_type != "js_heavy" else SourceType.WEB,
            requires_js=requires_js,
        )
        self.scheduler.add_arm(arm)
        logger.debug(f"Added source {source_id} (requires_js={requires_js})")

    def on_event(self, handler: Callable[[CrawlerCallback], None]) -> None:
        """Register event handler."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def _emit(self, callback: CrawlerCallback) -> None:
        """Emit event to all handlers."""
        for handler in self._handlers:
            try:
                handler(callback)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def _get_worker(self, arm: SourceArm) -> BaseWorker:
        """
        Get the appropriate worker for a source.

        Uses PlaywrightWorker for JS-heavy sites, HTTPXWorker otherwise.
        Playwright is lazy-loaded on first use to save resources.
        """
        if arm.requires_js and self._enable_playwright:
            if self._playwright_worker is None:
                logger.info("Initializing PlaywrightWorker for JS-heavy content")
                self._playwright_worker = PlaywrightWorker(
                    rate_limiter=self.rate_limiter,
                    headless=True,
                )
            return self._playwright_worker
        return self._httpx_worker

    async def crawl_source(self, source_id: str) -> dict[str, Any] | None:
        """Crawl a specific source using the appropriate worker."""
        arm = self.scheduler.get_arm(source_id)
        if not arm:
            return None

        # Select worker based on source requirements
        worker = await self._get_worker(arm)
        result = await worker.crawl(arm.url, source_id)

        if result.success:
            parser = self._parser_registry.get_parser(
                "application/json" if arm.source_type == SourceType.API else "text/html", arm.url
            )
            if parser and result.content:
                parsed = await parser.parse(result.content, arm.url)
                result.extracted_data = parsed

            content_changed = arm.content_hash != result.content_hash

            freshness = 1.0 if content_changed else 0.3
            quality = 0.8 if result.extracted_data else 0.4
            self.scheduler.record_result(source_id, True, freshness, quality)

            arm.content_hash = result.content_hash

            event_type = (
                CrawlerEvent.SOURCE_CHANGED if content_changed else CrawlerEvent.SOURCE_CRAWLED
            )
            self._emit(
                CrawlerCallback(
                    event=event_type,
                    source_id=source_id,
                    url=arm.url,
                    data=result.extracted_data,
                    quality_score=quality,
                )
            )
        else:
            self.scheduler.record_result(source_id, False)

            self._emit(
                CrawlerCallback(
                    event=CrawlerEvent.SOURCE_ERROR,
                    source_id=source_id,
                    url=arm.url,
                    error=result.error,
                )
            )

        return result.to_dict()

    async def crawl_batch(self, batch_size: int | None = None) -> list[dict[str, Any]]:
        """Crawl a batch of sources selected by MAB."""
        import asyncio

        size = batch_size or self.max_concurrent
        arms = self.scheduler.select_batch(size)

        tasks = [self.crawl_source(arm.source_id) for arm in arms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if r and not isinstance(r, Exception)]

    def update_relevance(self, source_id: str, was_useful: bool) -> None:
        """Update relevance score from TAJINE feedback."""
        self.scheduler.update_relevance(source_id, was_useful)

    async def close(self) -> None:
        """Clean up resources (close all workers)."""
        await self._httpx_worker.close()
        if self._playwright_worker:
            await self._playwright_worker.close()
            self._playwright_worker = None
        logger.info("AdaptiveCrawler closed")
