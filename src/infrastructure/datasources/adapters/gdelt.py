"""GDELT adapter - Global news and events database."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class GdeltAdapter(BaseAdapter):
    """Adapter for GDELT Project API.

    API Documentation: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

    GDELT indexes news from around the world in near real-time.
    The DOC 2.0 API provides free, unlimited access to article search.
    """

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                name="gdelt",
                base_url="https://api.gdeltproject.org/api/v2/doc/doc",
                rate_limit=60,
                cache_ttl=3600,  # 1 hour - news updates frequently
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search GDELT news articles.

        Args:
            query: Search parameters
                - keywords: Search terms
                - domain: Filter by domain (e.g., "lemonde.fr")
                - country: Country code (e.g., "FR")
                - language: Language code (e.g., "French")
                - days: Look back N days (default 7)
                - limit: Max results (default 25, max 250)
                - tone: Filter by tone (positive/negative)

        Returns:
            List of news articles
        """
        # Build GDELT query
        terms = []

        if keywords := query.get("keywords"):
            # GDELT requires keywords >= 3 characters
            # Filter out short words and keep only valid ones
            words = keywords.split()
            valid_words = [w for w in words if len(w) >= 3]
            if valid_words:
                terms.append(" ".join(valid_words))
            elif words:
                # If all words are short, quote them together
                terms.append(f'"{keywords}"')
        if domain := query.get("domain"):
            terms.append(f"domain:{domain}")
        if country := query.get("country"):
            terms.append(f"sourcecountry:{country}")
        if language := query.get("language"):
            terms.append(f"sourcelang:{language}")

        if not terms:
            terms = ["France"]  # Default to France news

        # Calculate time range
        days = query.get("days", 7)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        params = {
            "query": " ".join(terms),
            "mode": "artlist",
            "maxrecords": min(query.get("limit", 25), 250),
            "format": "json",
            "startdatetime": start_date.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end_date.strftime("%Y%m%d%H%M%S"),
            "sort": "datedesc",
        }

        # Add tone filter if specified
        if tone := query.get("tone"):
            if tone == "positive":
                params["query"] += " tone>5"
            elif tone == "negative":
                params["query"] += " tone<-5"

        try:
            response = await self._client.get(
                self.config.base_url,
                params=params,
            )
            response.raise_for_status()

            # Check if response is JSON (GDELT returns text errors for invalid queries)
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type and "text/json" not in content_type:
                error_msg = response.text.strip()
                logger.warning(f"GDELT returned non-JSON: {error_msg[:100]}")
                return []

            data = response.json()

            articles = data.get("articles", [])
            return [self._transform_article(a) for a in articles]

        except httpx.HTTPError as e:
            logger.error(f"GDELT search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"GDELT parsing error: {e}")
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get article by URL.

        Args:
            id: Article URL

        Returns:
            Article data or None
        """
        # GDELT doesn't have a get-by-id API
        # Search by exact URL
        results = await self.search({"keywords": f'"{id}"', "limit": 1})
        return results[0] if results else None

    async def health_check(self) -> bool:
        """Check if GDELT API is available."""
        try:
            response = await self._client.get(
                self.config.base_url,
                params={
                    "query": "test",
                    "mode": "artlist",
                    "maxrecords": 1,
                    "format": "json",
                },
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"GDELT health check failed: {e}")
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync recent news articles."""
        days = 1 if since is None else (datetime.utcnow() - since).days

        try:
            results = await self.search({
                "country": "FR",
                "days": min(days, 7),
                "limit": 100,
            })

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

    def _transform_article(self, article: dict) -> dict[str, Any]:
        """Transform GDELT article to standard format."""
        # Parse date
        date_str = article.get("seendate", "")
        published_dt = None
        if date_str:
            try:
                published_dt = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ")
            except ValueError as e:
                logger.debug(f"Failed to parse GDELT date '{date_str}': {e}")
                pass

        return {
            "source": "gdelt",
            "id": article.get("url"),
            "url": article.get("url"),
            "title": article.get("title"),
            "domain": article.get("domain"),
            "language": article.get("language"),
            "country": article.get("sourcecountry"),
            "published_dt": published_dt,
            "seendate": article.get("seendate"),
            "tone": article.get("tone"),
            "socialimage": article.get("socialimage"),
            "raw": article,
        }

    async def search_company_mentions(
        self,
        company_name: str,
        days: int = 30,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for mentions of a company (convenience method).

        Args:
            company_name: Company name to search
            days: Look back N days
            limit: Max results

        Returns:
            List of articles mentioning the company
        """
        return await self.search({
            "keywords": f'"{company_name}"',
            "country": "FR",
            "days": days,
            "limit": limit,
        })
