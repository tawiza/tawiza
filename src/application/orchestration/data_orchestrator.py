"""Data orchestrator for multi-source parallel queries."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from src.domain.matching.entity_matcher import EntityMatcher
from src.infrastructure.datasources.manager import DataSourceManager


@dataclass
class QueryResult:
    """Result from a single data source query."""

    source: str
    query: dict[str, Any]
    results: list[dict[str, Any]]
    duration_ms: float
    error: str | None = None


@dataclass
class OrchestratedResult:
    """Combined result from all data sources."""

    query: str
    timestamp: datetime
    source_results: list[QueryResult] = field(default_factory=list)
    correlated_entities: list[list[dict[str, Any]]] = field(default_factory=list)
    total_results: int = 0
    total_duration_ms: float = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "total_results": self.total_results,
            "total_duration_ms": self.total_duration_ms,
            "sources": [
                {
                    "source": r.source,
                    "count": len(r.results),
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in self.source_results
            ],
            "correlated_groups": len(self.correlated_entities),
        }


class DataOrchestrator:
    """Orchestrates parallel queries across multiple data sources.

    Features:
    - Parallel async queries to all registered adapters
    - Automatic rate limiting per source
    - Entity correlation using fuzzy matching
    - Configurable query strategies

    Example:
        orchestrator = DataOrchestrator()
        result = await orchestrator.search("startup IA Lille")
        for group in result.correlated_entities:
            logger.info(f"Entity group: {len(group)} sources")
    """

    def __init__(
        self,
        manager: DataSourceManager | None = None,
        matcher: EntityMatcher | None = None,
    ):
        """Initialize orchestrator.

        Args:
            manager: DataSourceManager with registered adapters
            matcher: EntityMatcher for correlation
        """
        self.manager = manager or self._create_default_manager()
        self.matcher = matcher or EntityMatcher()

    def _create_default_manager(self) -> DataSourceManager:
        """Create manager with all registered adapters."""
        from src.infrastructure.datasources.adapters import (
            BanAdapter,
            BoampAdapter,
            BodaccAdapter,
            GdeltAdapter,
            GoogleNewsAdapter,
            RssAdapter,
            RssEnhancedAdapter,
            SireneAdapter,
            SubventionsAdapter,
        )
        from src.infrastructure.datasources.adapters.commoncrawl import CommonCrawlAdapter

        manager = DataSourceManager()
        manager.register(BodaccAdapter())
        manager.register(BoampAdapter())
        manager.register(SireneAdapter())
        manager.register(BanAdapter())
        manager.register(RssAdapter())
        manager.register(RssEnhancedAdapter())
        manager.register(GdeltAdapter())
        manager.register(GoogleNewsAdapter())
        manager.register(SubventionsAdapter())
        manager.register(CommonCrawlAdapter())
        return manager

    async def search(
        self,
        query: str,
        sources: list[str] | None = None,
        limit_per_source: int = 20,
        correlate: bool = True,
    ) -> OrchestratedResult:
        """Search across multiple data sources in parallel.

        Args:
            query: Search query string
            sources: Specific sources to query (default: all)
            limit_per_source: Max results per source
            correlate: Whether to correlate entities across sources

        Returns:
            OrchestratedResult with all data and correlations
        """
        start_time = datetime.utcnow()

        # Determine which sources to query
        adapters = self.manager.adapters
        if sources:
            adapters = {k: v for k, v in adapters.items() if k in sources}

        # Build queries for each source type
        queries = self._build_source_queries(query, limit_per_source)

        # Execute queries in parallel
        tasks = []
        for name, adapter in adapters.items():
            source_query = queries.get(name, {"keywords": query, "limit": limit_per_source})
            tasks.append(self._query_source(name, adapter, source_query))

        source_results = await asyncio.gather(*tasks)

        # Aggregate all results
        all_entities = []
        for result in source_results:
            for item in result.results:
                all_entities.append(item)

        # Correlate entities if requested
        correlated = []
        if correlate and all_entities:
            correlated = self.matcher.deduplicate(all_entities)

        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return OrchestratedResult(
            query=query,
            timestamp=start_time,
            source_results=source_results,
            correlated_entities=correlated,
            total_results=len(all_entities),
            total_duration_ms=duration_ms,
        )

    async def search_entity(
        self,
        siret: str | None = None,
        name: str | None = None,
        address: str | None = None,
    ) -> OrchestratedResult:
        """Search for a specific entity across all sources.

        Args:
            siret: SIRET number
            name: Company name
            address: Address for geocoding

        Returns:
            OrchestratedResult with entity data from all sources
        """
        start_time = datetime.utcnow()
        source_results = []

        # 1. If SIRET provided, query Sirene first
        if siret:
            sirene_result = await self._query_source(
                "sirene",
                self.manager.adapters.get("sirene"),
                {"siret": siret},
            )
            source_results.append(sirene_result)

            # Extract company info from Sirene
            if sirene_result.results:
                company = sirene_result.results[0]
                name = name or company.get("name")
                address = address or company.get("address")

        # 2. If address provided, geocode it
        if address and "ban" in self.manager.adapters:
            ban_result = await self._query_source(
                "ban",
                self.manager.adapters["ban"],
                {"address": address, "limit": 1},
            )
            source_results.append(ban_result)

        # 3. Search news sources for mentions
        if name:
            news_tasks = []
            for source in ["gdelt", "google_news"]:
                if source in self.manager.adapters:
                    news_tasks.append(
                        self._query_source(
                            source,
                            self.manager.adapters[source],
                            {"keywords": name, "limit": 10},
                        )
                    )
            if news_tasks:
                news_results = await asyncio.gather(*news_tasks)
                source_results.extend(news_results)

        # 4. Search legal sources
        legal_tasks = []
        for source in ["bodacc", "boamp"]:
            if source in self.manager.adapters:
                query = {"siret": siret} if siret else {"keywords": name, "limit": 10}
                legal_tasks.append(self._query_source(source, self.manager.adapters[source], query))
        if legal_tasks:
            legal_results = await asyncio.gather(*legal_tasks)
            source_results.extend(legal_results)

        # 5. Search subventions
        if "subventions" in self.manager.adapters and name:
            subv_result = await self._query_source(
                "subventions",
                self.manager.adapters["subventions"],
                {"keywords": name, "limit": 10},
            )
            source_results.append(subv_result)

        # Aggregate and correlate
        all_entities = []
        for result in source_results:
            if result:
                all_entities.extend(result.results)

        correlated = self.matcher.deduplicate(all_entities) if all_entities else []

        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return OrchestratedResult(
            query=f"entity:{siret or name}",
            timestamp=start_time,
            source_results=[r for r in source_results if r],
            correlated_entities=correlated,
            total_results=len(all_entities),
            total_duration_ms=duration_ms,
        )

    async def _query_source(
        self,
        name: str,
        adapter: Any,
        query: dict[str, Any],
    ) -> QueryResult:
        """Query a single data source with error handling."""
        if not adapter:
            return QueryResult(
                source=name,
                query=query,
                results=[],
                duration_ms=0,
                error="Adapter not found",
            )

        start = datetime.utcnow()
        try:
            results = await adapter.search(query)
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            logger.debug(f"{name}: {len(results)} results in {duration:.0f}ms")
            return QueryResult(
                source=name,
                query=query,
                results=results,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            logger.error(f"{name} query failed: {e}")
            return QueryResult(
                source=name,
                query=query,
                results=[],
                duration_ms=duration,
                error=str(e),
            )

    def _build_source_queries(
        self,
        query: str,
        limit: int,
    ) -> dict[str, dict[str, Any]]:
        """Build optimized queries for each source type.

        Maps the generic query to source-specific parameters.
        """
        # Parse location from query (e.g., "startup Lille" -> nom="startup", location="Lille")
        sirene_query = self._parse_sirene_query(query, limit)

        return {
            # Sirene needs special handling for location
            "sirene": sirene_query,
            # Legal sources use 'keywords'
            "bodacc": {"keywords": query, "limit": limit},
            "boamp": {"keywords": query, "limit": limit},
            # BAN uses 'address' for geocoding
            "ban": {"address": query, "limit": limit},
            # News sources use 'keywords'
            "rss": {"keywords": query, "limit": limit},
            # GDELT: Don't filter by country - returns more results
            "gdelt": {"keywords": query, "limit": limit},
            "google_news": {"keywords": query, "limit": limit},
            # Subventions uses 'keywords'
            "subventions": {"keywords": query, "limit": limit},
        }

    def _parse_sirene_query(self, query: str, limit: int) -> dict[str, Any]:
        """Parse query for Sirene API, extracting location if present."""
        # Common French city names and their department codes
        city_departments = {
            "paris": "75",
            "lyon": "69",
            "marseille": "13",
            "toulouse": "31",
            "nice": "06",
            "nantes": "44",
            "strasbourg": "67",
            "montpellier": "34",
            "bordeaux": "33",
            "lille": "59",
            "rennes": "35",
            "reims": "51",
            "le havre": "76",
            "saint-etienne": "42",
            "toulon": "83",
            "grenoble": "38",
            "dijon": "21",
            "angers": "49",
            "nimes": "30",
            "villeurbanne": "69",
        }

        words = query.lower().split()
        nom_parts = []
        departement = None

        for word in words:
            if word in city_departments:
                departement = city_departments[word]
            else:
                nom_parts.append(word)

        result = {"limit": limit}
        if nom_parts:
            result["nom"] = " ".join(nom_parts)
        if departement:
            result["departement"] = departement

        # If no nom, use original query
        if "nom" not in result:
            result["nom"] = query

        return result
