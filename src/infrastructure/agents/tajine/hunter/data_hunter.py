"""DataHunter - Proactive information gathering orchestrator.

DataHunter v2 enhancements:
- LinUCB contextual bandit for territory-aware source selection
- DiscoveryEngine for automatic pattern learning
- DoclingParser for PDF/DOCX document parsing
- NodriverBrowserAgent for stealth browser access
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.infrastructure.agents.tajine.core.types import HuntContext, RawData
from src.infrastructure.agents.tajine.hunter.bandit import SourceBandit
from src.infrastructure.agents.tajine.hunter.graph_expander import (
    GraphExpander,
    KnowledgeGap,
)
from src.infrastructure.agents.tajine.hunter.hypothesis import (
    Hypothesis,
    HypothesisGenerator,
)
from src.infrastructure.datasources.manager import DataSourceManager

# v2 imports (optional, with fallbacks)
try:
    from src.infrastructure.crawler.scheduler import ContextFeatures, LinUCBScheduler

    LINUCB_AVAILABLE = True
except ImportError:
    LINUCB_AVAILABLE = False

try:
    from src.infrastructure.agents.tajine.hunter.discovery_engine import DiscoveryEngine

    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False

try:
    from src.infrastructure.parsers import DoclingParser

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class HuntResult:
    """Result of a hunt operation."""

    data: list[RawData]
    hypotheses_used: list[Hypothesis]
    gaps_addressed: list[KnowledgeGap]
    sources_queried: list[str]
    duration_ms: int
    # v2 additions
    patterns_learned: list[Any] = field(default_factory=list)
    documents_parsed: int = 0
    context_used: dict[str, Any] = field(default_factory=dict)


class DataHunter:
    """
    Proactive information gathering orchestrator.

    DataHunter v2 combines four strategies:
    - Hypothesis-driven: Generate hypotheses, search to validate
    - Bandit-optimized: Use LinUCB contextual bandit for territory-aware selection
    - Graph-expanding: Fill gaps in knowledge graph
    - Semantic: Use discovery engine for pattern learning (v2)

    Modes (4-tuple: hypothesis, bandit, graph, semantic):
    - normal: Bandit (60%) + Graph (30%) + Semantic (10%)
    - question: Hypotheses (40%) + Bandit (30%) + Graph (20%) + Semantic (10%)
    - combler: Graph (70%) + Bandit (20%) + Semantic (10%)
    - semantic: Semantic (70%) + Bandit (20%) + Graph (10%)
    - hybrid: Balanced mix for complex analysis
    """

    # v2: 4-tuple weights (hypothesis, bandit, graph, semantic)
    MODE_WEIGHTS = {
        "normal": (0.0, 0.6, 0.3, 0.1),
        "question": (0.4, 0.3, 0.2, 0.1),
        "combler": (0.0, 0.2, 0.7, 0.1),
        "semantic": (0.0, 0.2, 0.1, 0.7),
        "hybrid": (0.25, 0.25, 0.25, 0.25),
    }

    # Sources that can be served by DataSourceManager adapters
    ADAPTER_SOURCES = {
        "sirene",
        "bodacc",
        "boamp",
        "ban",
        "dvf",
        "ofgl",
        "france_travail",
        "insee_local",
        "gdelt",
        "google_news",
        "dbnomics",
        "subventions",
        "geo",
        "melodi",
        "rss",
        "wikipedia_pageviews",
        "pytrends",
        "commoncrawl",
    }

    def __init__(
        self,
        bandit: SourceBandit,
        hypothesis_generator: HypothesisGenerator,
        graph_expander: GraphExpander,
        crawler=None,
        datasource_manager: DataSourceManager | None = None,
        # v2 components
        linucb_scheduler: Any = None,
        discovery_engine: Any = None,
        document_parser: Any = None,
        ollama_url: str = "http://localhost:11434",
    ):
        """Initialize with components.

        Args:
            bandit: UCB1 source bandit (fallback)
            hypothesis_generator: Hypothesis generator
            graph_expander: Knowledge graph expander
            crawler: Web crawler
            datasource_manager: DataSourceManager for API sources
            linucb_scheduler: LinUCB contextual bandit (v2)
            discovery_engine: ScrapeGraphAI discovery engine (v2)
            document_parser: Docling document parser (v2)
            ollama_url: Ollama API URL for v2 components
        """
        self.bandit = bandit
        self.hypothesis_gen = hypothesis_generator
        self.graph_expander = graph_expander
        self.crawler = crawler
        self.datasource_manager = datasource_manager

        # v2 components (lazy init if not provided)
        self._linucb = linucb_scheduler
        self._discovery = discovery_engine
        self._parser = document_parser
        self.ollama_url = ollama_url

    @property
    def linucb_scheduler(self):
        """Lazy init LinUCB scheduler."""
        if self._linucb is None and LINUCB_AVAILABLE:
            self._linucb = LinUCBScheduler(alpha=0.5)
        return self._linucb

    @property
    def discovery_engine(self):
        """Lazy init discovery engine."""
        if self._discovery is None and DISCOVERY_AVAILABLE:
            self._discovery = DiscoveryEngine(ollama_url=self.ollama_url)
        return self._discovery

    @property
    def document_parser(self):
        """Lazy init document parser."""
        if self._parser is None and DOCLING_AVAILABLE:
            self._parser = DoclingParser()
        return self._parser

    async def hunt(self, context: HuntContext) -> HuntResult:
        """Execute a hunt for information using v2 strategies."""
        start_time = datetime.now()

        # v2: Get 4-tuple weights (hypothesis, bandit, graph, semantic)
        weights = self.MODE_WEIGHTS.get(context.mode, self.MODE_WEIGHTS["normal"])

        # Handle both old 3-tuple and new 4-tuple format
        if len(weights) == 3:
            w_hyp, w_bandit, w_graph = weights
            w_semantic = 0.0
        else:
            w_hyp, w_bandit, w_graph, w_semantic = weights

        targets = []
        hypotheses_used = []
        gaps_addressed = []
        patterns_learned = []
        documents_parsed = 0

        # Build context features for LinUCB (v2)
        context_features = None
        if LINUCB_AVAILABLE:
            context_features = ContextFeatures.from_query(
                query=context.query,
                territory=context.territory,
                domain=getattr(context, "domain", "general"),
            )

        # 1. Hypothesis-driven targets
        if w_hyp > 0:
            kg_gaps = await self._get_kg_gaps_dict(context.territory)
            hypotheses = await asyncio.to_thread(
                self.hypothesis_gen.generate,
                context=context.query,
                territory=context.territory,
                kg_gaps=kg_gaps,
                max_hypotheses=max(1, round(context.max_sources * w_hyp)),
            )
            for h in hypotheses:
                targets.extend([{"query": h.statement, "sources": h.sources_to_check}])
                hypotheses_used.append(h)

        # 2. Graph-driven targets
        if w_graph > 0:
            gaps = await self.graph_expander.find_gaps(context.territory)
            n_graph = max(1, round(context.max_sources * w_graph))
            for gap in gaps[:n_graph]:
                queries = self.graph_expander.gap_to_queries(gap)
                targets.extend(
                    [{"query": q, "sources": gap.suggested_sources} for q in queries[:1]]
                )
                gaps_addressed.append(gap)

        # 3. Bandit-driven targets (v2: use LinUCB if available)
        n_bandit = max(1, round(context.max_sources * w_bandit)) if w_bandit > 0 else 0
        if n_bandit > 0:
            selected_sources = []

            if self.linucb_scheduler and context_features:
                # v2: Try LinUCB contextual bandit
                selected_arms = self.linucb_scheduler.select_batch(
                    batch_size=n_bandit,
                    context=context_features,
                )
                selected_sources = [arm.source_id for arm in selected_arms]

            # Fallback to UCB1 if LinUCB returned nothing (e.g., no arms registered)
            if not selected_sources:
                selected_sources = self.bandit.select(n=n_bandit)

            if selected_sources:
                targets.append(
                    {
                        "query": context.query,
                        "sources": selected_sources,
                    }
                )

        # 4. Semantic/Discovery targets (v2)
        if w_semantic > 0 and self.discovery_engine:
            n_semantic = max(1, round(context.max_sources * w_semantic))
            discovery_results = await self._run_discovery(
                query=context.query,
                territory=context.territory,
                max_discoveries=n_semantic,
            )
            patterns_learned.extend(discovery_results.get("patterns", []))
            # Add discovered data to raw_data later

        # Fetch data from sources
        raw_data = []
        sources_queried = set()

        for target in targets:
            for source in target.get("sources", []):
                try:
                    data = await self._fetch_from_source(
                        source=source,
                        query=target["query"],
                        territory=context.territory,
                    )
                    if data:
                        raw_data.append(data)
                        sources_queried.add(source)

                        # v2: Update LinUCB if available
                        if self.linucb_scheduler and context_features:
                            self.linucb_scheduler.record_result(
                                source_id=source,
                                context=context_features,
                                success=True,
                                quality=data.quality_hint,
                            )
                        else:
                            self.bandit.update(source, reward=data.quality_hint)

                        # v2: Parse documents if PDF/DOCX
                        if self._should_parse_document(data.url):
                            parsed = await self._parse_document(data.url)
                            if parsed:
                                documents_parsed += 1
                                data.content = parsed

                except Exception as e:
                    logger.warning(f"Failed to fetch from {source}: {e}")
                    if self.linucb_scheduler and context_features:
                        self.linucb_scheduler.record_result(
                            source_id=source,
                            context=context_features,
                            success=False,
                        )
                    else:
                        self.bandit.update(source, reward=0.0)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Hunt completed: {len(raw_data)} items from {len(sources_queried)} sources "
            f"({documents_parsed} docs parsed, {len(patterns_learned)} patterns) "
            f"in {duration_ms}ms"
        )

        return HuntResult(
            data=raw_data,
            hypotheses_used=hypotheses_used,
            gaps_addressed=gaps_addressed,
            sources_queried=list(sources_queried),
            duration_ms=duration_ms,
            patterns_learned=patterns_learned,
            documents_parsed=documents_parsed,
            context_used=context_features.to_vector().tolist() if context_features else {},
        )

    async def _run_discovery(
        self,
        query: str,
        territory: str,
        max_discoveries: int = 3,
    ) -> dict:
        """Run discovery engine to find new patterns."""
        if not self.discovery_engine:
            return {"patterns": [], "data": []}

        try:
            # Try to find matching pattern first
            pattern = self.discovery_engine.find_matching_pattern(
                domain="entreprises",  # Default domain
            )

            if pattern:
                # Reuse existing pattern
                logger.debug(f"Reusing pattern {pattern.pattern_id} for discovery")
                # Apply pattern logic would go here

            return {"patterns": [], "data": []}
        except Exception as e:
            logger.warning(f"Discovery failed: {e}")
            return {"patterns": [], "data": []}

    def _should_parse_document(self, url: str) -> bool:
        """Check if URL points to a parseable document."""
        if not url:
            return False
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in [".pdf", ".docx", ".xlsx"])

    async def _parse_document(self, url: str) -> dict | None:
        """Parse a document from URL."""
        if not self.document_parser:
            return None

        try:
            result = await self.document_parser.parse(url)
            return {
                "text": result.text,
                "tables": [t.to_dict() if hasattr(t, "to_dict") else str(t) for t in result.tables],
                "metadata": result.metadata,
                "pages": result.pages,
            }
        except Exception as e:
            logger.warning(f"Document parsing failed for {url}: {e}")
            return None

    @staticmethod
    def _is_siren(s: str) -> bool:
        """Check if string looks like a SIREN number."""
        return len(s) == 9 and s.isdigit()

    @staticmethod
    def _is_siret(s: str) -> bool:
        """Check if string looks like a SIRET number."""
        return len(s) == 14 and s.isdigit()

    def _build_adapter_query(self, source: str, query: str, territory: str) -> dict:
        """Build adapter-specific query dict from generic parameters.

        Handles both entity queries (SIREN/SIRET/company name) and
        topic queries (economic analysis, sector keywords).
        """
        base = {"limit": 25}

        if source == "sirene":
            if self._is_siren(query) or self._is_siret(query):
                base["nom"] = query  # API will match by identifier
            else:
                base["nom"] = query
            if territory and len(territory) == 2:
                base["departement"] = territory
            elif territory and len(territory) >= 5:
                base["code_postal"] = territory[:5]

        elif source == "bodacc":
            if self._is_siren(query):
                base["siren"] = query
            elif self._is_siret(query):
                base["siren"] = query[:9]
            else:
                # For topic queries, just filter by territory to get recent data
                if territory:
                    base["departement"] = territory[:2]
                # Only add nom filter if it looks like a company name (short, no spaces > 3 words)
                words = query.split()
                if len(words) <= 3:
                    base["nom"] = query

        elif source == "boamp":
            base["keywords"] = query
            if territory:
                base["departement"] = territory[:2]

        elif source == "dvf":
            if territory and len(territory) >= 5:
                base["code_insee"] = territory
            elif territory and len(territory) == 2:
                base["code_departement"] = territory
            else:
                base["code_departement"] = "31"

        elif source == "france_travail":
            base["keywords"] = query
            if territory:
                base["departement"] = territory[:2]

        elif source == "insee_local":
            if territory and len(territory) >= 5:
                base["code_commune"] = territory
            elif territory:
                base["code_commune"] = ""
            base["type"] = "population"

        elif source == "dbnomics":
            base["type"] = "search"
            base["q"] = query
            if territory:
                base["region"] = territory[:2]

        elif source == "ban":
            base["address"] = query

        elif source in ("gdelt", "google_news", "rss", "subventions"):
            base["keywords"] = query

        elif source == "geo":
            base["code"] = territory if territory else ""

        else:
            base["keywords"] = query

        return base

    async def _fetch_from_source(
        self,
        source: str,
        query: str,
        territory: str,
    ) -> RawData | None:
        """Fetch data from a single source.

        Priority: DataSourceManager adapters > Crawler > None
        """
        # 1. Try DataSourceManager for known API sources
        if self.datasource_manager and source in self.ADAPTER_SOURCES:
            adapter = self.datasource_manager.adapters.get(source)
            if adapter:
                try:
                    adapter_query = self._build_adapter_query(source, query, territory)
                    raw_results = await adapter.search(adapter_query)

                    # Normalize: some adapters return dict with "results" key, some return list
                    if isinstance(raw_results, dict):
                        results = (
                            raw_results.get("results", [raw_results])
                            if "results" in raw_results
                            else [raw_results]
                        )
                    elif isinstance(raw_results, list):
                        results = raw_results
                    else:
                        results = []

                    if results:
                        n_items = len(results) if isinstance(results, list) else 1
                        return RawData(
                            source=source,
                            content=results,
                            url=getattr(adapter, "config", None)
                            and adapter.config.base_url
                            or f"adapter://{source}",
                            fetched_at=datetime.now(),
                            quality_hint=min(0.9, 0.5 + n_items * 0.02),
                        )
                except Exception as e:
                    logger.warning(f"Adapter {source} failed: {e}, trying crawler fallback")

        # 2. Try crawler for web/unknown sources or as fallback
        if self.crawler:
            try:
                result = await self.crawler.fetch(
                    source=source,
                    query=query,
                    params={"territory": territory},
                )
                content = result.get("content", {})
                if content and not result.get("error"):
                    # Extract actual data count for quality estimation
                    if isinstance(content, dict):
                        data_items = content.get("results", content.get("items", []))
                        n_items = len(data_items) if isinstance(data_items, list) else 1
                    else:
                        n_items = 1
                    return RawData(
                        source=source,
                        content=content,
                        url=result.get("url", ""),
                        fetched_at=datetime.now(),
                        quality_hint=min(0.85, 0.3 + n_items * 0.02),
                    )
            except Exception as e:
                logger.error(f"Crawler error for {source}: {e}")

        # 3. No data available
        logger.warning(f"No data fetched from {source} (no adapter or crawler available)")
        return None

    async def _get_kg_gaps_dict(self, territory: str) -> dict:
        """Get knowledge graph gaps as dict for hypothesis generator."""
        gaps = await self.graph_expander.find_gaps(territory)
        return self.graph_expander.to_kg_gaps_dict(gaps)

    def _estimate_quality(self, result: dict) -> float:
        """Estimate data quality from result."""
        if not result.get("content"):
            return 0.1

        content = result["content"]
        if isinstance(content, dict):
            n_fields = len(content)
            return min(0.9, 0.3 + n_fields * 0.05)

        return 0.5
