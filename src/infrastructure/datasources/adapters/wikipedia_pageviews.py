"""Wikipedia Pageviews adapter - Measure public interest via article views.

API Documentation: https://wikimedia.org/api/rest_v1/
Free access, no authentication required.

Use cases for territorial analysis:
- Measure public interest in companies/sectors
- Detect trending topics before they hit news
- Compare visibility of territorial entities
"""

from datetime import date, datetime, timedelta
from typing import Any

import httpx

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class WikipediaPageviewsAdapter(BaseAdapter):
    """Adapter for Wikipedia Pageviews API.

    Tracks article views to measure public interest.
    Can detect weak signals before they become trends.
    """

    BASE_URL = "https://wikimedia.org/api/rest_v1"

    # Common article mappings for French territorial analysis
    TERRITORIAL_ARTICLES = {
        # Regions
        "idf": "Île-de-France",
        "paca": "Provence-Alpes-Côte_d'Azur",
        "aura": "Auvergne-Rhône-Alpes",
        "occitanie": "Occitanie_(région_administrative)",
        # Major cities
        "paris": "Paris",
        "lyon": "Lyon",
        "marseille": "Marseille",
        "toulouse": "Toulouse",
        "bordeaux": "Bordeaux",
        # Economic topics
        "france_2030": "France_2030",
        "plan_relance": "Plan_de_relance_économique_de_la_France_de_2020-2022",
    }

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialize Wikipedia Pageviews adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
        """
        if config is None:
            config = AdapterConfig(
                name="wikipedia_pageviews",
                base_url=self.BASE_URL,
                rate_limit=100,  # 100 req/sec allowed
                cache_ttl=21600,  # 6h cache
            )
        super().__init__(config)

    def _format_date(self, d: date) -> str:
        """Format date for Wikimedia API (YYYYMMDD)."""
        return d.strftime("%Y%m%d")

    def _normalize_article(self, article: str) -> str:
        """Normalize article title for URL.

        Args:
            article: Article title

        Returns:
            URL-safe article title
        """
        # Check mappings first
        if article.lower() in self.TERRITORIAL_ARTICLES:
            return self.TERRITORIAL_ARTICLES[article.lower()]

        # Replace spaces with underscores
        return article.replace(" ", "_")

    async def get_pageviews(
        self,
        article: str,
        start: date | None = None,
        end: date | None = None,
        project: str = "fr.wikipedia",
        granularity: str = "daily",
    ) -> dict[str, Any]:
        """Get pageview counts for an article.

        Args:
            article: Wikipedia article title
            start: Start date (default: 30 days ago)
            end: End date (default: today)
            project: Wikimedia project (default: French Wikipedia)
            granularity: 'daily' or 'monthly'

        Returns:
            Pageview data with time series
        """
        if start is None:
            start = date.today() - timedelta(days=30)
        if end is None:
            end = date.today()

        article_normalized = self._normalize_article(article)

        try:
            url = (
                f"{self.BASE_URL}/metrics/pageviews/per-article/"
                f"{project}/all-access/all-agents/"
                f"{article_normalized}/{granularity}/"
                f"{self._format_date(start)}/{self._format_date(end)}"
            )

            response = await self._client.get(
                url,
                headers={"User-Agent": "Tawiza-TerritorialAnalysis/1.0"},
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])

            # Calculate statistics
            views = [item.get("views", 0) for item in items]
            total_views = sum(views)
            avg_views = total_views / len(views) if views else 0
            max_views = max(views) if views else 0
            min_views = min(views) if views else 0

            return {
                "source": "wikipedia_pageviews",
                "article": article,
                "article_normalized": article_normalized,
                "project": project,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "granularity": granularity,
                "total_views": total_views,
                "avg_daily_views": round(avg_views, 1),
                "max_views": max_views,
                "min_views": min_views,
                "data_points": len(items),
                "time_series": [
                    {
                        "date": item.get("timestamp", "")[:8],
                        "views": item.get("views", 0),
                    }
                    for item in items
                ],
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "source": "wikipedia_pageviews",
                    "article": article,
                    "error": "Article not found",
                    "suggestion": "Check article title spelling or try French title",
                }
            self._log_error(f"get_pageviews:{article}", e)
            return {"source": "wikipedia_pageviews", "error": str(e)}

        except httpx.HTTPError as e:
            self._log_error(f"get_pageviews:{article}", e)
            return {"source": "wikipedia_pageviews", "error": str(e)}

    async def get_top_articles(
        self,
        target_date: date | None = None,
        project: str = "fr.wikipedia",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get most viewed articles for a day.

        Args:
            target_date: Date to query (default: yesterday)
            project: Wikimedia project
            limit: Number of top articles

        Returns:
            List of top articles with view counts
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        try:
            url = (
                f"{self.BASE_URL}/metrics/pageviews/top/"
                f"{project}/all-access/{target_date.year}/"
                f"{target_date.month:02d}/{target_date.day:02d}"
            )

            response = await self._client.get(
                url,
                headers={"User-Agent": "Tawiza-TerritorialAnalysis/1.0"},
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [{}])[0].get("articles", [])

            return [
                {
                    "rank": i + 1,
                    "article": item.get("article", "").replace("_", " "),
                    "views": item.get("views", 0),
                }
                for i, item in enumerate(items[:limit])
            ]

        except httpx.HTTPError as e:
            self._log_error(f"get_top_articles:{target_date}", e)
            return []

    async def get_trend(
        self,
        article: str,
        period_days: int = 30,
        compare_previous: bool = True,
    ) -> dict[str, Any]:
        """Analyze trend for an article.

        Args:
            article: Article title
            period_days: Analysis period
            compare_previous: Compare with previous period

        Returns:
            Trend analysis with growth indicators
        """
        end = date.today()
        start = end - timedelta(days=period_days)

        current_data = await self.get_pageviews(article, start, end)

        if "error" in current_data:
            return current_data

        result = {
            "source": "wikipedia_pageviews",
            "article": article,
            "period_days": period_days,
            "current_period": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "total_views": current_data.get("total_views", 0),
                "avg_daily": current_data.get("avg_daily_views", 0),
            },
            "trend": "stable",
            "trend_score": 0.0,
        }

        if compare_previous:
            prev_end = start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days)
            prev_data = await self.get_pageviews(article, prev_start, prev_end)

            if "error" not in prev_data:
                prev_views = prev_data.get("total_views", 0)
                curr_views = current_data.get("total_views", 0)

                if prev_views > 0:
                    growth = (curr_views - prev_views) / prev_views * 100
                    result["previous_period"] = {
                        "start": prev_start.isoformat(),
                        "end": prev_end.isoformat(),
                        "total_views": prev_views,
                    }
                    result["growth_percent"] = round(growth, 2)

                    # Determine trend
                    if growth > 20:
                        result["trend"] = "rising"
                        result["trend_score"] = min(1.0, growth / 100)
                    elif growth < -20:
                        result["trend"] = "declining"
                        result["trend_score"] = max(-1.0, growth / 100)
                    else:
                        result["trend"] = "stable"
                        result["trend_score"] = growth / 100

        return result

    async def compare_articles(
        self,
        articles: list[str],
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Compare pageviews across multiple articles.

        Args:
            articles: List of article titles
            period_days: Comparison period

        Returns:
            Comparison data for all articles
        """
        end = date.today()
        start = end - timedelta(days=period_days)

        results = []
        for article in articles:
            data = await self.get_pageviews(article, start, end)
            if "error" not in data:
                results.append(
                    {
                        "article": article,
                        "total_views": data.get("total_views", 0),
                        "avg_daily": data.get("avg_daily_views", 0),
                        "max_views": data.get("max_views", 0),
                    }
                )

        # Sort by total views
        results.sort(key=lambda x: x["total_views"], reverse=True)

        # Calculate relative popularity
        max_views = results[0]["total_views"] if results else 1
        for r in results:
            r["relative_popularity"] = round(r["total_views"] / max_views * 100, 1)

        return {
            "source": "wikipedia_pageviews",
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "articles_count": len(results),
            "comparison": results,
        }

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search Wikipedia pageviews data.

        Args:
            query: Search parameters
                - type: 'pageviews', 'top', 'trend', 'compare'
                - article: Article title (for pageviews/trend)
                - articles: List of articles (for compare)
                - date: Target date (for top)
                - days: Period in days

        Returns:
            List of results
        """
        query_type = query.get("type", "pageviews")
        days = query.get("days", 30)

        if query_type == "top":
            target_date = query.get("date")
            if target_date and isinstance(target_date, str):
                target_date = date.fromisoformat(target_date)
            articles = await self.get_top_articles(target_date)
            return articles

        elif query_type == "trend":
            article = query.get("article", query.get("q", ""))
            if article:
                result = await self.get_trend(article, days)
                return [result]
            return []

        elif query_type == "compare":
            articles = query.get("articles", [])
            if articles:
                result = await self.compare_articles(articles, days)
                return [result]
            return []

        else:
            # Default: get pageviews for article
            article = query.get("article", query.get("q", ""))
            if article:
                end = date.today()
                start = end - timedelta(days=days)
                result = await self.get_pageviews(article, start, end)
                return [result]
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get pageviews by article title."""
        return await self.get_pageviews(id)

    async def health_check(self) -> bool:
        """Check if Wikipedia Pageviews API is available."""
        try:
            # Check with a known article
            yesterday = date.today() - timedelta(days=1)
            url = (
                f"{self.BASE_URL}/metrics/pageviews/top/"
                f"fr.wikipedia/all-access/{yesterday.year}/"
                f"{yesterday.month:02d}/{yesterday.day:02d}"
            )
            response = await self._client.get(
                url,
                headers={"User-Agent": "Tawiza-TerritorialAnalysis/1.0"},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Pageviews are fetched on-demand."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="Pageviews are fetched on-demand, no sync needed",
        )
