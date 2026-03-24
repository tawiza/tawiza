"""PyTrends adapter - Google Trends data for territorial analysis.

Uses pytrends library to access Google Trends data.
Includes anti-blocking measures: proxy rotation, random delays, retries.

Use cases:
- Detect rising search interest in sectors/regions
- Compare territorial economic topics
- Identify seasonal patterns
"""

import asyncio
import random
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus

# Lazy import to avoid startup delay
_pytrends = None


def _get_pytrends():
    """Lazy load pytrends to avoid import issues."""
    global _pytrends
    if _pytrends is None:
        try:
            from pytrends.request import TrendReq

            _pytrends = TrendReq
        except ImportError:
            logger.warning("pytrends not installed. Run: pip install pytrends")
            return None
    return _pytrends


class PyTrendsAdapter(BaseAdapter):
    """Adapter for Google Trends via pytrends.

    Provides search trend data with anti-blocking measures.
    Essential for detecting weak signals and public interest.
    """

    # French regions for geo targeting
    FRENCH_REGIONS = {
        "FR": "France",
        "FR-IDF": "Ile-de-France",
        "FR-ARA": "Auvergne-Rhone-Alpes",
        "FR-PAC": "Provence-Alpes-Cote d'Azur",
        "FR-OCC": "Occitanie",
        "FR-NAQ": "Nouvelle-Aquitaine",
        "FR-HDF": "Hauts-de-France",
        "FR-GES": "Grand Est",
        "FR-NOR": "Normandie",
        "FR-PDL": "Pays de la Loire",
        "FR-BRE": "Bretagne",
        "FR-CVL": "Centre-Val de Loire",
        "FR-BFC": "Bourgogne-Franche-Comte",
        "FR-COR": "Corse",
    }

    # Territorial analysis keywords
    TERRITORIAL_KEYWORDS = {
        "immobilier": ["immobilier", "achat maison", "prix m2", "location appartement"],
        "emploi": ["offre emploi", "recrutement", "pole emploi", "chomage"],
        "entreprise": ["creation entreprise", "auto entrepreneur", "startup"],
        "economie": ["croissance economique", "inflation", "crise economique"],
    }

    def __init__(
        self,
        config: AdapterConfig | None = None,
        proxies: list[str] | None = None,
    ) -> None:
        """Initialize PyTrends adapter.

        Args:
            config: Adapter configuration
            proxies: List of proxy URLs for rotation
        """
        if config is None:
            config = AdapterConfig(
                name="pytrends",
                base_url="https://trends.google.com",
                rate_limit=5,  # Very conservative to avoid blocks
                cache_ttl=3600,  # 1h cache
            )
        super().__init__(config)

        self._proxies = proxies or []
        self._proxy_index = 0
        self._pytrends_client = None
        self._min_delay = 2.0  # Minimum delay between requests
        self._max_delay = 5.0  # Maximum delay

    def _get_next_proxy(self) -> str | None:
        """Get next proxy from pool (round-robin)."""
        if not self._proxies:
            return None
        proxy = self._proxies[self._proxy_index]
        self._proxy_index = (self._proxy_index + 1) % len(self._proxies)
        return proxy

    def _create_client(self) -> Any:
        """Create pytrends client with optional proxy."""
        TrendReq = _get_pytrends()
        if TrendReq is None:
            return None

        proxy = self._get_next_proxy()
        requests_args = {}

        if proxy:
            requests_args["proxies"] = {
                "http": proxy,
                "https": proxy,
            }
            logger.debug(f"Using proxy: {proxy}")

        return TrendReq(
            hl="fr-FR",
            tz=60,  # GMT+1 (France)
            retries=3,
            backoff_factor=0.5,
            requests_args=requests_args,
        )

    async def _rate_limit_delay(self) -> None:
        """Add random delay to avoid rate limiting."""
        delay = random.uniform(self._min_delay, self._max_delay)
        await asyncio.sleep(delay)

    async def get_interest_over_time(
        self,
        keywords: list[str],
        geo: str = "FR",
        timeframe: str = "today 3-m",
    ) -> dict[str, Any]:
        """Get search interest over time for keywords.

        Args:
            keywords: List of search terms (max 5)
            geo: Geographic region code
            timeframe: Time period (e.g., 'today 3-m', 'today 12-m')

        Returns:
            Interest data with time series
        """
        await self._rate_limit_delay()

        client = self._create_client()
        if client is None:
            return {
                "source": "pytrends",
                "error": "pytrends library not available",
            }

        try:
            # Limit to 5 keywords (Google Trends limit)
            keywords = keywords[:5]

            client.build_payload(
                kw_list=keywords,
                geo=geo,
                timeframe=timeframe,
            )

            df = client.interest_over_time()

            if df.empty:
                return {
                    "source": "pytrends",
                    "keywords": keywords,
                    "geo": geo,
                    "data": [],
                    "message": "No data available for these keywords",
                }

            # Convert to serializable format
            data = []
            for idx, row in df.iterrows():
                point = {"date": idx.strftime("%Y-%m-%d")}
                for kw in keywords:
                    if kw in df.columns:
                        point[kw] = int(row[kw])
                data.append(point)

            # Calculate summary stats
            summary = {}
            for kw in keywords:
                if kw in df.columns:
                    values = df[kw].tolist()
                    summary[kw] = {
                        "avg": round(sum(values) / len(values), 1),
                        "max": max(values),
                        "min": min(values),
                        "latest": values[-1] if values else 0,
                    }

            return {
                "source": "pytrends",
                "keywords": keywords,
                "geo": geo,
                "geo_name": self.FRENCH_REGIONS.get(geo, geo),
                "timeframe": timeframe,
                "data_points": len(data),
                "summary": summary,
                "time_series": data,
            }

        except Exception as e:
            self._log_error(f"get_interest_over_time:{keywords}", e)
            return {"source": "pytrends", "error": str(e)}

    async def get_related_queries(
        self,
        keyword: str,
        geo: str = "FR",
    ) -> dict[str, Any]:
        """Get related search queries for a keyword.

        Args:
            keyword: Search term
            geo: Geographic region

        Returns:
            Top and rising related queries
        """
        await self._rate_limit_delay()

        client = self._create_client()
        if client is None:
            return {"source": "pytrends", "error": "pytrends not available"}

        try:
            client.build_payload([keyword], geo=geo, timeframe="today 3-m")
            related = client.related_queries()

            result = {
                "source": "pytrends",
                "keyword": keyword,
                "geo": geo,
                "top_queries": [],
                "rising_queries": [],
            }

            if keyword in related:
                kw_data = related[keyword]

                # Top queries
                if kw_data.get("top") is not None and not kw_data["top"].empty:
                    result["top_queries"] = kw_data["top"].to_dict("records")[:10]

                # Rising queries
                if kw_data.get("rising") is not None and not kw_data["rising"].empty:
                    result["rising_queries"] = kw_data["rising"].to_dict("records")[:10]

            return result

        except Exception as e:
            self._log_error(f"get_related_queries:{keyword}", e)
            return {"source": "pytrends", "error": str(e)}

    async def get_regional_interest(
        self,
        keyword: str,
        resolution: str = "REGION",
    ) -> dict[str, Any]:
        """Get interest by French region.

        Args:
            keyword: Search term
            resolution: 'COUNTRY', 'REGION', or 'CITY'

        Returns:
            Interest scores by region
        """
        await self._rate_limit_delay()

        client = self._create_client()
        if client is None:
            return {"source": "pytrends", "error": "pytrends not available"}

        try:
            client.build_payload([keyword], geo="FR", timeframe="today 12-m")
            df = client.interest_by_region(resolution=resolution)

            if df.empty:
                return {
                    "source": "pytrends",
                    "keyword": keyword,
                    "regions": [],
                }

            # Convert and sort by interest
            regions = []
            for region_name, row in df.iterrows():
                interest = int(row[keyword]) if keyword in df.columns else 0
                if interest > 0:
                    regions.append(
                        {
                            "region": region_name,
                            "interest": interest,
                        }
                    )

            regions.sort(key=lambda x: x["interest"], reverse=True)

            return {
                "source": "pytrends",
                "keyword": keyword,
                "resolution": resolution,
                "regions_count": len(regions),
                "regions": regions,
            }

        except Exception as e:
            self._log_error(f"get_regional_interest:{keyword}", e)
            return {"source": "pytrends", "error": str(e)}

    async def get_trending_searches(
        self,
        country: str = "france",
    ) -> list[dict[str, Any]]:
        """Get real-time trending searches.

        Args:
            country: Country name (lowercase)

        Returns:
            List of trending search topics
        """
        await self._rate_limit_delay()

        client = self._create_client()
        if client is None:
            return []

        try:
            df = client.trending_searches(pn=country)

            if df.empty:
                return []

            return [{"rank": i + 1, "query": row[0]} for i, row in df.iterrows()][:20]

        except Exception as e:
            self._log_error("get_trending_searches", e)
            return []

    async def compare_territories(
        self,
        keyword: str,
        territories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compare search interest across French territories.

        Args:
            keyword: Search term
            territories: List of geo codes (default: main regions)

        Returns:
            Comparison data across territories
        """
        if territories is None:
            territories = ["FR-IDF", "FR-ARA", "FR-PAC", "FR-OCC", "FR-NAQ"]

        results = []
        for geo in territories:
            await self._rate_limit_delay()

            client = self._create_client()
            if client is None:
                continue

            try:
                client.build_payload([keyword], geo=geo, timeframe="today 3-m")
                df = client.interest_over_time()

                if not df.empty and keyword in df.columns:
                    values = df[keyword].tolist()
                    avg_interest = sum(values) / len(values) if values else 0

                    results.append(
                        {
                            "geo": geo,
                            "name": self.FRENCH_REGIONS.get(geo, geo),
                            "avg_interest": round(avg_interest, 1),
                            "latest": values[-1] if values else 0,
                        }
                    )

            except Exception as e:
                logger.warning(f"Error fetching {geo}: {e}")
                continue

        # Sort by average interest
        results.sort(key=lambda x: x["avg_interest"], reverse=True)

        return {
            "source": "pytrends",
            "keyword": keyword,
            "territories_count": len(results),
            "comparison": results,
        }

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search Google Trends data.

        Args:
            query: Search parameters
                - type: 'interest', 'related', 'regional', 'trending', 'compare'
                - keywords: List of keywords
                - keyword: Single keyword
                - geo: Geographic region
                - timeframe: Time period

        Returns:
            List of results
        """
        query_type = query.get("type", "interest")
        geo = query.get("geo", "FR")

        if query_type == "trending":
            country = query.get("country", "france")
            return await self.get_trending_searches(country)

        elif query_type == "related":
            keyword = query.get("keyword", query.get("q", ""))
            if keyword:
                result = await self.get_related_queries(keyword, geo)
                return [result]
            return []

        elif query_type == "regional":
            keyword = query.get("keyword", query.get("q", ""))
            if keyword:
                result = await self.get_regional_interest(keyword)
                return [result]
            return []

        elif query_type == "compare":
            keyword = query.get("keyword", query.get("q", ""))
            territories = query.get("territories")
            if keyword:
                result = await self.compare_territories(keyword, territories)
                return [result]
            return []

        else:
            # Default: interest over time
            keywords = query.get("keywords", [])
            if not keywords:
                kw = query.get("keyword", query.get("q", ""))
                keywords = [kw] if kw else []

            if keywords:
                timeframe = query.get("timeframe", "today 3-m")
                result = await self.get_interest_over_time(keywords, geo, timeframe)
                return [result]
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get trend data for a keyword."""
        result = await self.get_interest_over_time([id])
        if "error" not in result:
            return result
        return None

    async def health_check(self) -> bool:
        """Check if Google Trends is accessible."""
        try:
            client = self._create_client()
            if client is None:
                return False

            # Try a simple query
            client.build_payload(["test"], geo="FR", timeframe="now 1-d")
            client.interest_over_time()
            return True

        except Exception as e:
            logger.warning(f"PyTrends health check failed: {e}")
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Trends are fetched on-demand."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="Google Trends data is fetched on-demand",
        )
