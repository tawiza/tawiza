"""Enhanced RSS Adapter with circuit breaker, dedup, and multi-category feeds.

Replaces the basic RssAdapter with a production-grade implementation
inspired by World Monitor's feed architecture.

Features:
- 65+ pre-configured French & international feeds
- Per-feed circuit breaker (2 failures → 5min cooldown)
- Jaccard similarity deduplication (>0.6 threshold)
- Category-based filtering (eco, regional, startups, etc.)
- Stale-while-revalidate caching
- Priority-based fetch ordering
"""

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus
from src.infrastructure.datasources.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
    CircuitBreakerRegistry,
    breaker_registry,
)
from src.infrastructure.datasources.dedup import (
    deduplicate_by_url,
    deduplicate_headlines,
)
from src.infrastructure.datasources.feeds_config import (
    FEEDS,
    FeedCategory,
    FeedConfig,
    FeedPriority,
)


class RssEnhancedAdapter(BaseAdapter):
    """Production-grade RSS adapter with circuit breakers and dedup.

    Usage:
        adapter = RssEnhancedAdapter()

        # Fetch all feeds
        results = await adapter.search({"limit": 50})

        # Fetch by category
        results = await adapter.search({
            "categories": ["eco_national", "eco_regional"],
            "limit": 30,
        })

        # Fetch by region (department code)
        results = await adapter.search({
            "region": "13",
            "limit": 20,
        })

        # Search with keywords
        results = await adapter.search({
            "keywords": "intelligence artificielle",
            "categories": ["tech", "startups"],
            "limit": 20,
        })
    """

    # Concurrency limit for parallel feed fetching
    MAX_CONCURRENT_FETCHES = 10

    def __init__(
        self,
        config: AdapterConfig | None = None,
        feeds: list[FeedConfig] | None = None,
        registry: CircuitBreakerRegistry | None = None,
    ):
        if config is None:
            config = AdapterConfig(
                name="rss_enhanced",
                base_url="",
                rate_limit=120,
                cache_ttl=300,  # 5min global cache
                timeout=15.0,  # 15s per feed
            )
        super().__init__(config)
        self._feeds = feeds or FEEDS
        self._registry = registry or breaker_registry
        self._client = httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Tawiza-V2/1.0 (RSS Aggregator; +https://tawiza.fr)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_FETCHES)

    @property
    def feeds(self) -> list[FeedConfig]:
        """All configured feeds."""
        return self._feeds

    @property
    def feed_count(self) -> int:
        """Number of enabled feeds."""
        return sum(1 for f in self._feeds if f.enabled)

    def _get_breaker(self, feed: FeedConfig) -> CircuitBreaker:
        """Get or create a circuit breaker for a feed."""
        return self._registry.get_or_create(
            f"rss_{feed.name}",
            BreakerConfig(
                name=f"rss_{feed.name}",
                max_failures=2,
                cooldown_seconds=300,  # 5 minutes
                cache_ttl_seconds=feed.refresh_interval,
                timeout_seconds=self.config.timeout,
            ),
        )

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search RSS feeds with filtering and dedup.

        Args:
            query: Search parameters
                - keywords: str — Filter by title/summary content
                - categories: list[str] — Filter by FeedCategory values
                - region: str — Filter by department/region code
                - priority: int — Max priority level (1=critical only, 4=all)
                - feeds: list[str] — Specific feed names
                - limit: int — Max results (default 50)
                - since: datetime — Only entries after this date
                - deduplicate: bool — Apply Jaccard dedup (default True)

        Returns:
            Deduplicated, sorted list of feed entries
        """
        keywords = query.get("keywords", "").lower()
        categories = query.get("categories")
        region = query.get("region")
        priority = query.get("priority", FeedPriority.LOW.value)
        feed_names = query.get("feeds")
        limit = query.get("limit", 50)
        since = query.get("since")
        do_dedup = query.get("deduplicate", True)

        # Select feeds based on filters
        selected_feeds = self._select_feeds(
            categories=categories,
            region=region,
            priority=priority,
            feed_names=feed_names,
        )

        if not selected_feeds:
            logger.warning("No feeds matched the query filters")
            return []

        logger.info(
            f"Fetching {len(selected_feeds)} feeds (categories={categories}, region={region})"
        )

        # Fetch all selected feeds in parallel with semaphore
        tasks = [self._fetch_feed_with_breaker(feed) for feed in selected_feeds]
        results_per_feed = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_results: list[dict[str, Any]] = []
        for i, result in enumerate(results_per_feed):
            if isinstance(result, Exception):
                logger.error(f"Feed {selected_feeds[i].name} raised: {result}")
                continue
            if isinstance(result, list):
                all_results.extend(result)

        # Filter by keywords
        if keywords:
            all_results = [
                e
                for e in all_results
                if keywords in e.get("title", "").lower()
                or keywords in e.get("summary", "").lower()
            ]

        # Filter by date
        if since:
            all_results = [
                e for e in all_results if e.get("published_dt") and e["published_dt"] > since
            ]

        # Deduplication pipeline
        if do_dedup:
            before = len(all_results)
            all_results = deduplicate_by_url(all_results)
            all_results = deduplicate_headlines(all_results)
            deduped = before - len(all_results)
            if deduped > 0:
                logger.debug(f"Deduplicated {deduped} entries ({before} → {len(all_results)})")

        # Sort by priority then date
        all_results.sort(
            key=lambda x: (
                x.get("_priority", 4),
                -(x.get("published_dt") or datetime.min).timestamp(),
            ),
        )

        return all_results[:limit]

    def _select_feeds(
        self,
        categories: list[str] | None = None,
        region: str | None = None,
        priority: int = 4,
        feed_names: list[str] | None = None,
    ) -> list[FeedConfig]:
        """Select feeds based on filters."""
        feeds = [f for f in self._feeds if f.enabled]

        if feed_names:
            name_set = set(feed_names)
            feeds = [f for f in feeds if f.name in name_set]

        if categories:
            cat_set = {
                FeedCategory(c) for c in categories if c in FeedCategory.__members__.values()
            }
            if not cat_set:
                # Try matching by value
                cat_set = set()
                for c in categories:
                    try:
                        cat_set.add(FeedCategory(c))
                    except ValueError:
                        pass
            if cat_set:
                feeds = [f for f in feeds if f.category in cat_set]

        if region:
            feeds = [f for f in feeds if f.region is None or f.region == region]

        feeds = [f for f in feeds if f.priority.value <= priority]

        # Sort by priority (critical first)
        feeds.sort(key=lambda f: f.priority.value)

        return feeds

    async def _fetch_feed_with_breaker(
        self,
        feed: FeedConfig,
    ) -> list[dict[str, Any]]:
        """Fetch a single feed with circuit breaker protection."""
        breaker = self._get_breaker(feed)

        async def _do_fetch() -> list[dict[str, Any]]:
            async with self._semaphore:
                return await self._fetch_feed(feed)

        result = await breaker.execute(fn=_do_fetch, default=[])
        return result if isinstance(result, list) else []

    async def _fetch_feed(self, feed: FeedConfig) -> list[dict[str, Any]]:
        """Fetch and parse a single feed."""
        try:
            response = await self._client.get(feed.url)
            response.raise_for_status()
            content = response.text

            parsed = feedparser.parse(content)

            if parsed.bozo and not parsed.entries:
                logger.warning(f"Feed parse error for {feed.name}: {parsed.bozo_exception}")
                return []

            entries = [
                self._transform_entry(entry, feed) for entry in parsed.entries[: feed.max_items]
            ]

            logger.debug(f"Fetched {len(entries)} entries from {feed.name}")
            return entries

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {feed.name}: {e}")
            raise  # Let circuit breaker handle it
        except Exception as e:
            logger.error(f"Error fetching {feed.name}: {e}")
            raise

    def _transform_entry(
        self,
        entry: Any,
        feed: FeedConfig,
    ) -> dict[str, Any]:
        """Transform feedparser entry to standard format."""
        import re

        # Parse publication date
        published_dt = None
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    published_dt = datetime(*parsed[:6])
                    break
                except Exception:
                    pass

        # Extract domain
        domain = urlparse(feed.url).netloc.replace("www.", "")

        # Clean summary
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        if summary:
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = re.sub(r"\s+", " ", summary).strip()[:500]

        return {
            "source": "rss",
            "feed": feed.name,
            "feed_category": feed.category.value,
            "domain": domain,
            "language": feed.language,
            "id": getattr(entry, "id", None) or getattr(entry, "link", ""),
            "url": getattr(entry, "link", ""),
            "title": getattr(entry, "title", ""),
            "summary": summary,
            "author": getattr(entry, "author", None),
            "published": getattr(entry, "published", None),
            "published_dt": published_dt,
            "tags": [t.term for t in getattr(entry, "tags", [])],
            "_priority": feed.priority.value,
            "_region": feed.region,
            "_feed_tags": feed.tags,
        }

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get entry by URL."""
        # RSS doesn't support ID lookups efficiently
        return None

    async def health_check(self) -> bool:
        """Check if critical feeds are accessible."""
        critical = [f for f in self._feeds if f.priority == FeedPriority.CRITICAL and f.enabled]
        if not critical:
            critical = self._feeds[:3]

        for feed in critical[:2]:
            try:
                response = await self._client.head(feed.url, timeout=5.0)
                if response.status_code < 400:
                    return True
            except Exception:
                continue
        return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync all feeds."""
        try:
            results = await self.search({"since": since, "limit": 500})
            return SyncStatus(
                adapter_name=self.name,
                last_sync=datetime.utcnow(),
                records_synced=len(results),
                status="success",
            )
        except Exception as e:
            return SyncStatus(
                adapter_name=self.name,
                last_sync=None,
                records_synced=0,
                status="failed",
                error=str(e),
            )

    def breaker_stats(self) -> list[dict[str, Any]]:
        """Get circuit breaker stats for all feeds."""
        stats = self._registry.all_stats()
        return [
            {
                "name": s.name,
                "state": s.state.value,
                "failures": s.failure_count,
                "cooldown_remaining": round(s.cooldown_remaining, 1),
                "total_requests": s.total_requests,
                "total_failures": s.total_failures,
                "cache_hits": s.total_cache_hits,
            }
            for s in stats
            if s.name.startswith("rss_")
        ]

    # Convenience methods

    async def get_regional_news(
        self,
        department: str = "13",
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get news for a specific department."""
        return await self.search(
            {
                "categories": ["eco_regional"],
                "region": department,
                "limit": limit,
            }
        )

    async def get_economic_briefing(
        self,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Get economic briefing (national + institutional)."""
        return await self.search(
            {
                "categories": ["eco_national", "institutions", "think_tanks"],
                "priority": FeedPriority.HIGH.value,
                "limit": limit,
            }
        )

    async def get_startup_pulse(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get startup/innovation news."""
        return await self.search(
            {
                "categories": ["startups", "tech"],
                "limit": limit,
            }
        )

    async def get_security_alerts(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get security alerts (ANSSI, CERT)."""
        return await self.search(
            {
                "categories": ["security"],
                "limit": limit,
            }
        )
