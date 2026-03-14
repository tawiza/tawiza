"""RSS/Atom feed adapter for startup news and tech content."""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class RssAdapter(BaseAdapter):
    """Adapter for RSS/Atom feeds.

    Supports multiple feed sources with configurable URLs.
    Useful for monitoring startup news, tech blogs, and industry updates.
    """

    # Pre-configured French startup/tech feeds
    DEFAULT_FEEDS = {
        "maddyness": "https://www.maddyness.com/feed/",
        "frenchweb": "https://www.frenchweb.fr/feed",
        "usine_digitale": "https://www.usine-digitale.fr/rss",
        "journaldunet": "https://www.journaldunet.com/rss/",
        "lesechos_startups": "https://www.lesechos.fr/rss/start-up.xml",
    }

    def __init__(
        self,
        config: AdapterConfig | None = None,
        feeds: dict[str, str] | None = None,
    ):
        """Initialize RSS adapter.

        Args:
            config: Adapter configuration
            feeds: Dict of feed_name -> feed_url (defaults to DEFAULT_FEEDS)
        """
        if config is None:
            config = AdapterConfig(
                name="rss",
                base_url="",  # Multiple URLs
                rate_limit=60,
                cache_ttl=3600,  # 1h - news updates frequently
            )
        super().__init__(config)
        self._feeds = feeds or self.DEFAULT_FEEDS
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    @property
    def feeds(self) -> dict[str, str]:
        """Get configured feeds."""
        return self._feeds

    def add_feed(self, name: str, url: str) -> None:
        """Add a custom feed.

        Args:
            name: Feed identifier
            url: Feed URL
        """
        self._feeds[name] = url

    def remove_feed(self, name: str) -> bool:
        """Remove a feed.

        Args:
            name: Feed identifier

        Returns:
            True if removed, False if not found
        """
        if name in self._feeds:
            del self._feeds[name]
            return True
        return False

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search RSS feeds.

        Args:
            query: Search parameters
                - keywords: Search in title/description
                - feeds: List of feed names to search (None = all)
                - limit: Max results per feed (default 10)
                - since: Only entries after this datetime

        Returns:
            List of feed entries
        """
        keywords = query.get("keywords", "").lower()
        feed_names = query.get("feeds") or list(self._feeds.keys())
        limit = query.get("limit", 10)
        since = query.get("since")

        all_results = []

        for feed_name in feed_names:
            if feed_name not in self._feeds:
                logger.warning(f"Feed not found: {feed_name}")
                continue

            try:
                entries = await self._fetch_feed(
                    feed_name,
                    self._feeds[feed_name],
                    limit=limit,
                )

                # Filter by keywords
                if keywords:
                    entries = [
                        e
                        for e in entries
                        if keywords in e.get("title", "").lower()
                        or keywords in e.get("summary", "").lower()
                    ]

                # Filter by date
                if since:
                    entries = [
                        e for e in entries if e.get("published_dt") and e["published_dt"] > since
                    ]

                all_results.extend(entries[:limit])

            except Exception as e:
                logger.error(f"Failed to fetch feed {feed_name}: {e}")

        # Sort by publication date (newest first)
        all_results.sort(
            key=lambda x: x.get("published_dt") or datetime.min,
            reverse=True,
        )

        return all_results

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get entry by URL (used as ID).

        Args:
            id: Entry URL

        Returns:
            Entry details or None
        """
        # RSS entries don't have persistent IDs, search by URL
        for feed_name, feed_url in self._feeds.items():
            entries = await self._fetch_feed(feed_name, feed_url, limit=50)
            for entry in entries:
                if entry.get("url") == id or entry.get("id") == id:
                    return entry
        return None

    async def health_check(self) -> bool:
        """Check if at least one feed is accessible."""
        for feed_name, feed_url in list(self._feeds.items())[:2]:
            try:
                response = await self._client.head(feed_url)
                if response.status_code < 400:
                    return True
            except Exception as e:
                logger.debug(f"RSS health check failed for {feed_name}: {e}")
                continue
        return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync all feeds.

        Args:
            since: Only sync entries after this date

        Returns:
            Sync status
        """
        try:
            results = await self.search({"since": since, "limit": 100})
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

    async def _fetch_feed(
        self,
        name: str,
        url: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch and parse a single feed.

        Args:
            name: Feed identifier
            url: Feed URL
            limit: Max entries to return

        Returns:
            List of parsed entries
        """
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            content = response.text

            # Parse with feedparser
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                logger.warning(f"Feed parse error for {name}: {feed.bozo_exception}")
                return []

            return [self._transform_entry(entry, name, url) for entry in feed.entries[:limit]]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {name}: {e}")
            return []

    def _transform_entry(
        self,
        entry: Any,
        feed_name: str,
        feed_url: str,
    ) -> dict[str, Any]:
        """Transform feedparser entry to standard format.

        Args:
            entry: Feedparser entry object
            feed_name: Source feed name
            feed_url: Source feed URL

        Returns:
            Normalized entry dict
        """
        # Parse publication date
        published_dt = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_dt = datetime(*entry.published_parsed[:6])
            except Exception as e:
                logger.debug(f"Failed to parse RSS published date for {feed_name}: {e}")
                pass
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                published_dt = datetime(*entry.updated_parsed[:6])
            except Exception as e:
                logger.debug(f"Failed to parse RSS updated date for {feed_name}: {e}")
                pass

        # Extract domain for source identification
        domain = urlparse(feed_url).netloc.replace("www.", "")

        # Get summary/description
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description

        # Clean HTML from summary (basic)
        if summary:
            import re

            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:500]  # Truncate

        return {
            "source": "rss",
            "feed": feed_name,
            "domain": domain,
            "id": getattr(entry, "id", None) or entry.link,
            "url": entry.link,
            "title": entry.title,
            "summary": summary,
            "author": getattr(entry, "author", None),
            "published": getattr(entry, "published", None),
            "published_dt": published_dt,
            "updated": getattr(entry, "updated", None),
            "tags": [t.term for t in getattr(entry, "tags", [])],
            "raw": dict(entry) if hasattr(entry, "keys") else {},
        }

    async def get_latest(
        self,
        feed_names: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get latest entries across feeds (convenience method).

        Args:
            feed_names: Feeds to query (None = all)
            limit: Max total results

        Returns:
            Latest entries sorted by date
        """
        return await self.search({"feeds": feed_names, "limit": limit})

    async def search_by_keywords(
        self,
        keywords: str,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search recent entries by keywords (convenience method).

        Args:
            keywords: Search terms
            days: Look back N days
            limit: Max results

        Returns:
            Matching entries
        """
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(days=days)
        return await self.search(
            {
                "keywords": keywords,
                "since": since,
                "limit": limit,
            }
        )
