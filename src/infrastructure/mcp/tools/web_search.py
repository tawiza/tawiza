"""Web search MCP tool using DuckDuckGo.

Provides free web search without API key.
"""

import json

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


def register_web_search_tools(mcp: FastMCP) -> None:
    """Register web search tools on the MCP server."""

    @mcp.tool()
    async def web_search(
        query: str,
        limit: int = 10,
        region: str = "fr-fr",
        search_type: str = "auto",
        ctx: Context = None,
    ) -> str:
        """Recherche web via DuckDuckGo (gratuit, sans API key).

        Args:
            query: Requête de recherche
            limit: Nombre maximum de résultats (défaut: 10)
            region: Région pour les résultats (défaut: fr-fr)
            search_type: Type de recherche - "text", "news", ou "auto" (défaut: auto)

        Returns:
            Résultats de recherche avec titre, URL et description
        """
        try:
            import warnings

            from duckduckgo_search import DDGS
            warnings.filterwarnings('ignore')

            if ctx:
                ctx.info(f"[WebSearch] Searching: {query}")
                ctx.report_progress(0, 100, f"Searching: {query}")

            results = []
            ddgs = DDGS()

            # Try text search first if requested
            if search_type in ("text", "auto"):
                try:
                    for r in ddgs.text(query, region=region, max_results=limit):
                        # Filter out non-French/English results for French queries
                        url = r.get("href", "")
                        if ".cn" not in url and "baidu" not in url:
                            results.append({
                                "title": r.get("title", ""),
                                "url": url,
                                "description": r.get("body", ""),
                                "type": "web",
                            })
                except Exception as e:
                    logger.debug(f"Text search failed: {e}")
                    pass

            # Fallback to news if text search returned poor results
            if (search_type == "auto" and len(results) < 3) or search_type == "news":
                try:
                    for r in ddgs.news(query, region=region, max_results=limit):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "description": r.get("body", ""),
                            "source": r.get("source", ""),
                            "date": r.get("date", ""),
                            "type": "news",
                        })
                except Exception as e:
                    logger.debug(f"News search failed: {e}")
                    pass

            # Deduplicate by URL
            seen_urls = set()
            unique_results = []
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    unique_results.append(r)

            results = unique_results[:limit]

            if ctx:
                ctx.info(f"[WebSearch] Found {len(results)} results")
                ctx.report_progress(100, 100, f"Found {len(results)} results")

            return json.dumps({
                "success": True,
                "query": query,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
            }, ensure_ascii=False)

    @mcp.tool()
    async def web_search_news(
        query: str,
        limit: int = 10,
        region: str = "fr-fr",
        ctx: Context = None,
    ) -> str:
        """Recherche d'actualités via DuckDuckGo (gratuit).

        Args:
            query: Requête de recherche
            limit: Nombre maximum de résultats (défaut: 10)
            region: Région pour les résultats (défaut: fr-fr)

        Returns:
            Articles d'actualité avec titre, URL, source et date
        """
        try:
            from duckduckgo_search import DDGS

            if ctx:
                ctx.info(f"[WebSearch] Searching news: {query}")

            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, region=region, max_results=limit):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", ""),
                        "date": r.get("date", ""),
                        "description": r.get("body", ""),
                        "image": r.get("image", ""),
                    })

            if ctx:
                ctx.info(f"[WebSearch] Found {len(results)} news articles")

            return json.dumps({
                "success": True,
                "query": query,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
            }, ensure_ascii=False)

    @mcp.tool()
    async def web_search_images(
        query: str,
        limit: int = 10,
        region: str = "fr-fr",
        ctx: Context = None,
    ) -> str:
        """Recherche d'images via DuckDuckGo (gratuit).

        Args:
            query: Requête de recherche
            limit: Nombre maximum de résultats (défaut: 10)
            region: Région pour les résultats (défaut: fr-fr)

        Returns:
            Images avec URL, titre et source
        """
        try:
            from duckduckgo_search import DDGS

            if ctx:
                ctx.info(f"[WebSearch] Searching images: {query}")

            results = []
            with DDGS() as ddgs:
                for r in ddgs.images(query, region=region, max_results=limit):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("image", ""),
                        "thumbnail": r.get("thumbnail", ""),
                        "source": r.get("source", ""),
                        "width": r.get("width"),
                        "height": r.get("height"),
                    })

            if ctx:
                ctx.info(f"[WebSearch] Found {len(results)} images")

            return json.dumps({
                "success": True,
                "query": query,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
            }, ensure_ascii=False)

    @mcp.tool()
    async def web_search_maps(
        query: str,
        place: str | None = None,
        limit: int = 10,
        ctx: Context = None,
    ) -> str:
        """Recherche de lieux/entreprises via DuckDuckGo Maps (gratuit).

        Args:
            query: Type de lieu (ex: "restaurant", "boulangerie")
            place: Ville ou adresse (ex: "Lille", "Paris 75001")
            limit: Nombre maximum de résultats (défaut: 10)

        Returns:
            Lieux avec nom, adresse, téléphone, horaires
        """
        try:
            from duckduckgo_search import DDGS

            search_query = f"{query} {place}" if place else query

            if ctx:
                ctx.info(f"[WebSearch] Searching maps: {search_query}")

            results = []
            with DDGS() as ddgs:
                for r in ddgs.maps(search_query, max_results=limit):
                    results.append({
                        "name": r.get("title", ""),
                        "address": r.get("address", ""),
                        "phone": r.get("phone", ""),
                        "url": r.get("url", ""),
                        "latitude": r.get("latitude"),
                        "longitude": r.get("longitude"),
                        "hours": r.get("hours", {}),
                        "rating": r.get("rating"),
                        "reviews": r.get("reviews"),
                        "category": r.get("category", ""),
                    })

            if ctx:
                ctx.info(f"[WebSearch] Found {len(results)} places")

            return json.dumps({
                "success": True,
                "query": search_query,
                "count": len(results),
                "results": results,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
            }, ensure_ascii=False)
