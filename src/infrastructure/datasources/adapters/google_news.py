"""Google News RSS adapter - Free unlimited news via RSS."""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import feedparser
import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class GoogleNewsAdapter(BaseAdapter):
    """Adapter for Google News RSS feeds.

    Uses Google News RSS feeds which are free and unlimited.
    Supports keyword search and topic-based feeds.
    """

    # Google News RSS URL patterns
    SEARCH_URL = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"
    TOPIC_URLS = {
        "business": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtWnlHZ0pHVWlnQVAB?hl=fr&gl=FR&ceid=FR:fr",
        "technology": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtWnlHZ0pHVWlnQVAB?hl=fr&gl=FR&ceid=FR:fr",
        "science": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtWnlHZ0pHVWlnQVAB?hl=fr&gl=FR&ceid=FR:fr",
    }

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                name="google_news",
                base_url="https://news.google.com",
                rate_limit=30,
                cache_ttl=1800,  # 30 min - news updates frequently
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search Google News.

        Args:
            query: Search parameters
                - keywords: Search terms
                - topic: Topic name (business, technology, science)
                - limit: Max results (default 20)

        Returns:
            List of news articles
        """
        limit = query.get("limit", 20)

        # Determine URL
        if topic := query.get("topic"):
            url = self.TOPIC_URLS.get(topic.lower())
            if not url:
                logger.warning(f"Unknown topic: {topic}")
                return []
        elif keywords := query.get("keywords"):
            url = self.SEARCH_URL.format(query=quote(keywords))
        else:
            url = self.TOPIC_URLS["business"]  # Default to business news

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                logger.warning(f"Feed parse error: {feed.bozo_exception}")
                return []

            return [
                self._transform_entry(entry)
                for entry in feed.entries[:limit]
            ]

        except httpx.HTTPError as e:
            logger.error(f"Google News search failed: {e}")
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get article by URL (not directly supported)."""
        return None

    async def health_check(self) -> bool:
        """Check if Google News RSS is available."""
        try:
            response = await self._client.get(self.TOPIC_URLS["business"])
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync recent news."""
        try:
            results = await self.search({"topic": "business", "limit": 50})
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

    def _transform_entry(self, entry: Any) -> dict[str, Any]:
        """Transform RSS entry to standard format."""
        # Parse date
        published_dt = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_dt = datetime(*entry.published_parsed[:6])
            except Exception as e:
                logger.debug(f"Failed to parse published date: {e}")

        # Extract source from title (Google News format: "Title - Source")
        title = entry.title
        source_name = None
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            if len(parts) == 2:
                title = parts[0]
                source_name = parts[1]

        return {
            "source": "google_news",
            "id": entry.link,
            "url": entry.link,
            "title": title,
            "source_name": source_name,
            "summary": getattr(entry, "summary", ""),
            "published": getattr(entry, "published", None),
            "published_dt": published_dt,
            "raw": dict(entry) if hasattr(entry, "keys") else {},
        }
