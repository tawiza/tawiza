"""Crawler - Crawl4AI wrapper for TAJINE data collection."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from loguru import logger

# Source configurations
SOURCE_CONFIGS = {
    "sirene": {
        "base_url": "https://recherche-entreprises.api.gouv.fr/search",
        "type": "api",
        "auth_required": False,  # Free API, no auth needed
    },
    "bodacc": {
        "base_url": "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records",
        "type": "api",
        "auth_required": False,
    },
    "boamp": {
        "base_url": "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records",
        "type": "api",
        "auth_required": False,
    },
    "rss_economie": {
        "base_url": "https://www.economie.gouv.fr/rss",
        "type": "rss",
        "auth_required": False,
    },
    "web": {
        "base_url": None,
        "type": "web",
        "auth_required": False,
    },
}


@dataclass
class CrawlResult:
    """Result of a crawl operation."""

    source: str
    url: str
    content: dict[str, Any]
    raw_html: str | None = None
    markdown: str | None = None
    fetched_at: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlerConfig:
    """Configuration for the Crawler."""

    timeout: int = 30
    max_retries: int = 3
    user_agent: str = "TAJINE-Crawler/1.0"
    respect_robots: bool = True
    extract_links: bool = True
    extract_images: bool = False
    headless: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour


class TAJINECrawler:
    """
    Crawl4AI wrapper for TAJINE data collection.

    Supports:
    - API sources (SIRENE, BODACC, BOAMP)
    - RSS feeds
    - Web pages (with LLM-friendly extraction)
    """

    def __init__(
        self,
        config: CrawlerConfig | None = None,
        api_keys: dict[str, str] | None = None,
    ):
        """Initialize crawler."""
        self.config = config or CrawlerConfig()
        self.api_keys = api_keys or {}
        self._crawler = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazy initialization of Crawl4AI."""
        if self._initialized:
            return

        try:
            from crawl4ai import AsyncWebCrawler

            self._crawler = AsyncWebCrawler(
                headless=self.config.headless,
                verbose=False,
            )
            await self._crawler.start()
            self._initialized = True
            logger.info("Crawl4AI initialized successfully")
        except ImportError:
            logger.warning("Crawl4AI not installed, using fallback HTTP client")
            self._crawler = None
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Crawl4AI: {e}")
            self._crawler = None
            self._initialized = True

    async def fetch(
        self,
        source: str,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch data from a source.

        Args:
            source: Source identifier (sirene, bodacc, boamp, web)
            query: Search query
            params: Additional parameters (territory, etc.)

        Returns:
            Dict with 'content', 'url', 'metadata'
        """
        await self._ensure_initialized()

        source_config = SOURCE_CONFIGS.get(source, SOURCE_CONFIGS["web"])

        if source_config["type"] == "api":
            return await self._fetch_api(source, query, params, source_config)
        elif source_config["type"] == "rss":
            return await self._fetch_rss(source, query, params, source_config)
        else:
            return await self._fetch_web(source, query, params)

    async def fetch_url(self, url: str) -> CrawlResult:
        """
        Fetch a specific URL using Crawl4AI.

        Returns LLM-friendly markdown content.
        """
        await self._ensure_initialized()

        if self._crawler:
            try:
                result = await self._crawler.arun(url=url)
                return CrawlResult(
                    source="web",
                    url=url,
                    content={"text": result.markdown or ""},
                    raw_html=result.html,
                    markdown=result.markdown,
                    metadata={
                        "title": result.metadata.get("title", ""),
                        "links": result.links if self.config.extract_links else [],
                    },
                )
            except Exception as e:
                logger.error(f"Crawl4AI error for {url}: {e}")
                return CrawlResult(
                    source="web",
                    url=url,
                    content={},
                    success=False,
                    error=str(e),
                )

        # Fallback to httpx
        return await self._fetch_with_httpx(url)

    async def fetch_all(
        self,
        targets: list[dict[str, Any]],
    ) -> list[CrawlResult]:
        """
        Fetch multiple targets concurrently.

        Args:
            targets: List of {"query": str, "sources": List[str]}

        Returns:
            List of CrawlResult
        """
        tasks = []
        for target in targets:
            query = target.get("query", "")
            sources = target.get("sources", ["web"])
            params = target.get("params", {})

            for source in sources:
                tasks.append(self.fetch(source, query, params))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        crawl_results = []
        for _i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Fetch error: {result}")
                crawl_results.append(
                    CrawlResult(
                        source="unknown",
                        url="",
                        content={},
                        success=False,
                        error=str(result),
                    )
                )
            elif isinstance(result, dict):
                crawl_results.append(
                    CrawlResult(
                        source=result.get("source", "unknown"),
                        url=result.get("url", ""),
                        content=result.get("content", {}),
                        metadata=result.get("metadata", {}),
                    )
                )
            else:
                crawl_results.append(result)

        return crawl_results

    async def _fetch_api(
        self,
        source: str,
        query: str,
        params: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch from API source."""
        import httpx

        base_url = config["base_url"]
        headers = {"User-Agent": self.config.user_agent}

        # Add auth if required
        if config.get("auth_required") and source in self.api_keys:
            headers["Authorization"] = f"Bearer {self.api_keys[source]}"

        # Build query params based on source type
        query_params = {}

        # Truncate query to avoid sending entire LLM prompts to APIs
        short_query = query.split("\n")[0][:100].strip() if query else ""

        if source == "sirene":
            # recherche-entreprises.api.gouv.fr format
            query_params["q"] = short_query
            query_params["per_page"] = params.get("limit", 25) if params else 25
            if params and "territory" in params:
                territory = params["territory"]
                # Support both department (2 digits) and commune (5 digits)
                if len(territory) == 2:
                    query_params["departement"] = territory
                elif len(territory) >= 5:
                    query_params["code_postal"] = territory[:5]
            if params and "naf" in params:
                naf = params["naf"]
                # NAF code needs dot format: 6201Z -> 62.01Z
                if len(naf) == 5 and "." not in naf:
                    naf = f"{naf[:2]}.{naf[2:]}"
                query_params["activite_principale"] = naf
        elif source in ("bodacc", "boamp"):
            # v2.1 API uses ODSQL where clause
            where_parts = []
            if short_query:
                if source == "bodacc":
                    where_parts.append(f'commercant like "%{short_query}%"')
                else:
                    where_parts.append(f'objet like "%{short_query}%"')
            if params and "territory" in params:
                dept = params["territory"][:2]
                if source == "bodacc":
                    where_parts.append(f'numerodepartement="{dept}"')
                else:
                    where_parts.append(f'code_departement like "{dept}"')
            if where_parts:
                query_params["where"] = " AND ".join(where_parts)
            query_params["limit"] = params.get("limit", 25) if params else 25
            query_params["order_by"] = "dateparution desc"
        else:
            query_params["q"] = short_query

        url = f"{base_url}?{urlencode(query_params)}"

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                return {
                    "source": source,
                    "url": url,
                    "content": data,
                    "metadata": {"status": response.status_code},
                }
            except Exception as e:
                logger.error(f"API fetch error for {source}: {e}")
                return {
                    "source": source,
                    "url": url,
                    "content": {},
                    "error": str(e),
                }

    async def _fetch_rss(
        self,
        source: str,
        query: str,
        params: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch from RSS feed."""
        import httpx

        url = config["base_url"]

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()

                # Parse RSS
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response.text)  # nosec B314

                items = []
                for item in root.findall(".//item"):
                    title = item.find("title")
                    description = item.find("description")
                    link = item.find("link")

                    items.append(
                        {
                            "title": title.text if title is not None else "",
                            "description": description.text if description is not None else "",
                            "link": link.text if link is not None else "",
                        }
                    )

                # Filter by query
                if query:
                    query_lower = query.lower()
                    items = [
                        i
                        for i in items
                        if query_lower in i.get("title", "").lower()
                        or query_lower in i.get("description", "").lower()
                    ]

                return {
                    "source": source,
                    "url": url,
                    "content": {"items": items[:10]},
                    "metadata": {"total_items": len(items)},
                }
            except Exception as e:
                logger.error(f"RSS fetch error for {source}: {e}")
                return {
                    "source": source,
                    "url": url,
                    "content": {},
                    "error": str(e),
                }

    async def _fetch_web(
        self,
        source: str,
        query: str,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Fetch from web using Crawl4AI."""
        # Build search URL
        search_url = f"https://www.google.com/search?q={query}"

        if self._crawler:
            try:
                result = await self._crawler.arun(url=search_url)
                return {
                    "source": "web",
                    "url": search_url,
                    "content": {"text": result.markdown or ""},
                    "metadata": {"title": result.metadata.get("title", "")},
                }
            except Exception as e:
                logger.error(f"Crawl4AI web fetch error: {e}")

        # Fallback
        return {
            "source": "web",
            "url": search_url,
            "content": {"query": query},
            "metadata": {},
        }

    async def _fetch_with_httpx(self, url: str) -> CrawlResult:
        """Fallback fetch using httpx."""
        import httpx

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()

                return CrawlResult(
                    source="web",
                    url=url,
                    content={"html": response.text[:10000]},
                    raw_html=response.text,
                )
            except Exception as e:
                return CrawlResult(
                    source="web",
                    url=url,
                    content={},
                    success=False,
                    error=str(e),
                )

    async def close(self):
        """Close the crawler."""
        if self._crawler:
            with contextlib.suppress(Exception):
                await self._crawler.close()
        self._initialized = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
