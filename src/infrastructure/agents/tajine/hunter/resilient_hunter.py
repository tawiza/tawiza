"""ResilientDataHunter - Enhanced data hunting for rare data scenarios.

Extends DataHunter with:
- Retry and circuit breaker for all fetches
- Automatic fallback to alternative sources
- Caching to avoid redundant fetches
- Data augmentation when sources are sparse
- Persistent bandit learning
- Semantic search via vector stores (pgvector/Qdrant)
- **Web crawling reinforcement** when APIs are insufficient
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.infrastructure.agents.tajine.core.types import HuntContext, RawData

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.semantic import SemanticSearchService
from src.infrastructure.agents.tajine.hunter.bandit import SourceBandit
from src.infrastructure.agents.tajine.hunter.data_hunter import HuntResult
from src.infrastructure.agents.tajine.hunter.graph_expander import (
    GraphExpander,
)
from src.infrastructure.agents.tajine.hunter.hypothesis import (
    HypothesisGenerator,
)
from src.infrastructure.agents.tajine.hunter.resilient import (
    AugmentedData,
    DataCache,
    FallbackSourceChain,
    FetchResult,
    PersistentBanditMixin,
    RareDataAugmenter,
    ResilientFetcher,
)
from src.infrastructure.agents.tajine.telemetry import (
    record_bandit_pull,
    set_circuit_breaker,
    trace_hunt,
    track_cache,
    track_fallback,
    update_bandit_ucb,
)

logger = logging.getLogger(__name__)


@dataclass
class ResilientHuntResult(HuntResult):
    """Extended result with resilience metrics."""

    cache_hits: int = 0
    fallbacks_used: int = 0
    augmentations: int = 0
    circuit_breaker_trips: int = 0
    retry_count: int = 0
    web_crawls_used: int = 0  # Number of web pages crawled for reinforcement


class PersistentSourceBandit(SourceBandit, PersistentBanditMixin):
    """SourceBandit with persistence support."""

    pass


class ResilientDataHunter:
    """
    Enhanced DataHunter with resilience features for rare data.

    Features:
    1. Retry with exponential backoff on failures
    2. Circuit breaker to avoid hammering failing sources
    3. Automatic fallback to alternative sources
    4. Caching to reduce redundant API calls
    5. Data augmentation when primary sources fail
    6. Persistent bandit learning across sessions

    Usage:
        hunter = ResilientDataHunter(
            sources=["sirene", "bodacc", "boamp"],
            cache_path=Path(".cache/data_hunt"),
            bandit_state_path=Path(".state/bandit.json"),
        )

        result = await hunter.hunt(context)
    """

    # Mode weights: (hypothesis, bandit, graph, semantic)
    MODE_WEIGHTS = {
        "normal": (0.0, 0.7, 0.3, 0.0),
        "question": (0.5, 0.3, 0.2, 0.0),
        "combler": (0.0, 0.2, 0.8, 0.0),
        "rare": (0.3, 0.3, 0.4, 0.0),
        "semantic": (0.0, 0.0, 0.0, 1.0),  # 100% semantic search
        "hybrid": (0.2, 0.2, 0.3, 0.3),  # Mixed with semantic
    }

    # Web sources for crawling reinforcement
    # Audit 2026-02-21: removed bpifrance.fr/recherche (persistent 403),
    # added data.gouv.fr and geo.api alternatives.
    WEB_REINFORCEMENT_SOURCES = [
        "https://www.insee.fr/fr/recherche?q={query}&zone={territory}",
        "https://www.economie.gouv.fr/recherche?q={query}",
        "https://www.entreprises.gouv.fr/fr/search?keys={query}",
        "https://www.data.gouv.fr/api/1/datasets/?q={query}&page_size=10",
    ]

    def __init__(
        self,
        sources: list[str],
        hypothesis_generator: HypothesisGenerator | None = None,
        graph_expander: GraphExpander | None = None,
        crawler=None,
        # Semantic search
        semantic_service: SemanticSearchService | None = None,
        # Persistence
        cache_path: Path | None = None,
        bandit_state_path: Path | None = None,
        # Resilience config
        retry_attempts: int = 3,
        circuit_failure_threshold: int = 5,
        max_fallbacks: int = 2,
        # Augmentation
        llm_client=None,
        augment_on_sparse: bool = True,
        sparse_threshold: int = 2,  # Below this, try augmentation
        # Web crawling reinforcement
        web_crawl_on_sparse: bool = True,
        max_web_crawls: int = 3,
    ):
        # Core components
        self.bandit = PersistentSourceBandit(sources=sources)
        self.hypothesis_gen = hypothesis_generator or HypothesisGenerator()
        self.graph_expander = graph_expander or GraphExpander()
        self.crawler = crawler
        self.semantic_service = semantic_service

        # Resilience
        self.fetcher = ResilientFetcher(
            retry_attempts=retry_attempts,
            circuit_failure_threshold=circuit_failure_threshold,
        )
        self.fallback_chain = FallbackSourceChain(fetcher=self.fetcher)
        self.cache = DataCache(persist_path=cache_path / "cache.json" if cache_path else None)
        self.augmenter = RareDataAugmenter(llm_client=llm_client)

        # Config
        self.max_fallbacks = max_fallbacks
        self.augment_on_sparse = augment_on_sparse
        self.sparse_threshold = sparse_threshold
        self.web_crawl_on_sparse = web_crawl_on_sparse
        self.max_web_crawls = max_web_crawls

        # Persistence
        self.bandit_state_path = bandit_state_path
        if bandit_state_path:
            self.bandit.load_state(bandit_state_path)

    # -----------------------------------------------------------------------
    # Plan-Execute-Reflect loop
    # -----------------------------------------------------------------------
    MAX_REFLECT_ITERATIONS = 3
    REFLECT_QUALITY_THRESHOLD = 0.6  # avg quality_hint above which we stop
    REFLECT_DIVERSITY_MIN = 2  # unique sources below which we continue

    @trace_hunt(mode="resilient")
    async def hunt(self, context: HuntContext) -> ResilientHuntResult:
        """Execute a resilient hunt with Plan-Execute-Reflect loop.

        Each iteration:
        1. **Plan** — select targets (strategies, sources, gaps)
        2. **Execute** — fetch data with retry / fallback / cache
        3. **Reflect** — evaluate quality & diversity; re-plan if needed

        The loop runs up to ``MAX_REFLECT_ITERATIONS`` times (default 3).
        It exits early when data quality and source diversity thresholds are met.
        """
        start_time = datetime.now(UTC)

        # Use "rare" mode if explicitly sparse context
        mode = context.mode
        if mode == "normal" and await self._detect_sparse_territory(context.territory):
            mode = "rare"
            logger.info("Detected sparse territory, switching to 'rare' mode")

        weights = self.MODE_WEIGHTS.get(mode, self.MODE_WEIGHTS["normal"])
        w_hyp, w_bandit, w_graph, w_semantic = weights

        # Accumulators across iterations
        raw_data: list[RawData] = []
        sources_queried: set[str] = set()
        hypotheses_used: list = []
        gaps_addressed: list = []
        cache_hits = 0
        fallbacks_used = 0
        retry_count = 0
        iterations_run = 0

        for iteration in range(self.MAX_REFLECT_ITERATIONS):
            iterations_run = iteration + 1

            # ---- PLAN ----
            targets = await self._collect_targets(
                context,
                w_hyp,
                w_bandit,
                w_graph,
                w_semantic,
            )
            # On subsequent iterations, only keep targets for sources we haven't queried yet
            if iteration > 0:
                targets = self._filter_new_targets(targets, sources_queried)
                if not targets:
                    logger.debug("Reflect iter %d: no new targets, stopping", iteration)
                    break

            for t in targets:
                if "hypothesis" in t:
                    hypotheses_used.append(t["hypothesis"])
                if "gap" in t:
                    gaps_addressed.append(t["gap"])

            # ---- EXECUTE ----
            iter_data, iter_stats = await self._execute_targets(
                targets,
                context.territory,
            )
            raw_data.extend(iter_data)
            sources_queried.update(iter_stats["sources"])
            cache_hits += iter_stats["cache_hits"]
            fallbacks_used += iter_stats["fallbacks"]
            retry_count += iter_stats["retries"]

            # ---- REFLECT ----
            quality, diversity = self._reflect(raw_data, sources_queried)
            logger.info(
                "Hunt iter %d: %d items, quality=%.2f, diversity=%d sources",
                iteration + 1,
                len(raw_data),
                quality,
                diversity,
            )

            if (
                quality >= self.REFLECT_QUALITY_THRESHOLD
                and diversity >= self.REFLECT_DIVERSITY_MIN
            ):
                break  # Good enough

            # Shift weights toward graph gaps on subsequent iterations
            w_graph = min(0.8, w_graph + 0.2)
            w_bandit = max(0.1, w_bandit - 0.1)

        # Augment if still sparse
        augmentations = 0
        web_crawls_used = 0
        if self.augment_on_sparse and len(raw_data) < self.sparse_threshold:
            augmented = await self._augment_sparse_results(raw_data, context)
            if augmented and augmented.confidence > 0.5:
                raw_data = [augmented.primary] + augmented.supplements
                augmentations = len(augmented.supplements)
                web_crawls_used = sum(1 for s in augmented.supplements if s.source == "web_crawl")
                logger.info(
                    f"Augmented sparse data: {augmentations} supplements added "
                    f"({web_crawls_used} from web crawling)"
                )

        duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        # Save bandit state
        if self.bandit_state_path:
            self.bandit.save_state(self.bandit_state_path)

        logger.info(
            f"Resilient hunt: {len(raw_data)} items in {iterations_run} iterations, "
            f"{cache_hits} cache hits, {fallbacks_used} fallbacks, "
            f"{web_crawls_used} web crawls, {retry_count} retries in {duration_ms}ms"
        )

        return ResilientHuntResult(
            data=raw_data,
            hypotheses_used=hypotheses_used,
            gaps_addressed=gaps_addressed,
            sources_queried=list(sources_queried),
            duration_ms=duration_ms,
            cache_hits=cache_hits,
            fallbacks_used=fallbacks_used,
            augmentations=augmentations,
            retry_count=retry_count,
            web_crawls_used=web_crawls_used,
        )

    # -----------------------------------------------------------------------
    # Execute & Reflect helpers
    # -----------------------------------------------------------------------

    async def _execute_targets(
        self,
        targets: list[dict],
        territory: str,
    ) -> tuple[list[RawData], dict]:
        """Execute a batch of targets and return data + stats."""
        data: list[RawData] = []
        stats = {"sources": set(), "cache_hits": 0, "fallbacks": 0, "retries": 0}

        for target in targets:
            if "semantic_data" in target:
                data.append(target["semantic_data"])
                stats["sources"].add("semantic")
                continue

            for source in target.get("sources", []):
                cached = self.cache.get(source, target["query"], territory)
                if cached:
                    with track_cache(source=source, hit=True):
                        data.append(cached)
                        stats["sources"].add(f"{source}[cached]")
                        stats["cache_hits"] += 1
                    continue

                with track_cache(source=source, hit=False):
                    result = await self._resilient_fetch(
                        source=source,
                        query=target["query"],
                        territory=territory,
                    )

                health = self.fetcher.get_source_health(source)
                is_circuit_open = health.get("status") == "open"
                set_circuit_breaker(source=source, is_open=is_circuit_open)

                if result.success and result.data:
                    data.append(result.data)
                    stats["sources"].add(result.source_used)
                    self.cache.put(result.data, target["query"], territory)

                    reward = result.data.quality_hint
                    self.bandit.update(source, reward=reward)
                    record_bandit_pull(source=source, reward=reward)

                    source_idx = (
                        self.bandit.sources.index(source) if source in self.bandit.sources else None
                    )
                    if source_idx is not None:
                        ucb = self.bandit.get_ucb_score(source_idx)
                        update_bandit_ucb(source=source, ucb_score=ucb)

                    if result.fallbacks_tried:
                        stats["fallbacks"] += len(result.fallbacks_tried)
                        for fallback in result.fallbacks_tried:
                            with track_fallback(from_source=source, to_source=fallback):
                                pass
                else:
                    self.bandit.update(source, reward=0.0)
                    record_bandit_pull(source=source, reward=0.0)

                stats["retries"] += max(0, result.attempts - 1)

        return data, stats

    @staticmethod
    def _reflect(
        raw_data: list[RawData],
        sources: set[str],
    ) -> tuple[float, int]:
        """Evaluate data quality and source diversity.

        Returns (avg_quality, n_unique_sources).
        """
        if not raw_data:
            return 0.0, 0
        avg_q = sum(d.quality_hint for d in raw_data) / len(raw_data)
        # Strip '[cached]' suffix for true diversity count
        unique = {s.split("[")[0] for s in sources}
        return avg_q, len(unique)

    @staticmethod
    def _filter_new_targets(targets: list[dict], already_queried: set[str]) -> list[dict]:
        """Keep only targets whose sources haven't been queried yet."""
        stripped = {s.split("[")[0] for s in already_queried}
        filtered = []
        for t in targets:
            new_sources = [s for s in t.get("sources", []) if s not in stripped]
            if new_sources or "semantic_data" in t:
                t = {**t, "sources": new_sources}
                filtered.append(t)
        return filtered

    async def _collect_targets(
        self,
        context: HuntContext,
        w_hyp: float,
        w_bandit: float,
        w_graph: float,
        w_semantic: float = 0.0,
    ) -> list[dict]:
        """Collect all fetch targets based on strategies."""
        targets = []

        # Semantic search targets (priority: search indexed knowledge)
        if w_semantic > 0 and self.semantic_service:
            try:
                n_semantic = max(1, round(context.max_sources * w_semantic))
                semantic_results = await self.semantic_service.search_for_hunt(
                    query=context.query,
                    territory=context.territory,
                    limit=n_semantic,
                )
                for raw_data in semantic_results:
                    targets.append(
                        {
                            "query": context.query,
                            "sources": ["semantic"],
                            "semantic_data": raw_data,  # Pre-fetched data
                        }
                    )
                logger.info(f"Semantic search found {len(semantic_results)} results")
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")

        # Hypothesis-driven targets
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
                targets.append(
                    {
                        "query": h.statement,
                        "sources": h.sources_to_check,
                        "hypothesis": h,
                    }
                )

        # Graph-driven targets
        if w_graph > 0:
            gaps = await self.graph_expander.find_gaps(context.territory)
            n_graph = max(1, round(context.max_sources * w_graph))
            for gap in gaps[:n_graph]:
                queries = self.graph_expander.gap_to_queries(gap)
                for q in queries[:1]:
                    targets.append(
                        {
                            "query": q,
                            "sources": gap.suggested_sources,
                            "gap": gap,
                        }
                    )

        # Bandit-selected sources
        if w_bandit > 0:
            n_bandit = max(1, round(context.max_sources * w_bandit))
            selected = self.bandit.select(n=n_bandit)
            if selected:
                targets.append(
                    {
                        "query": context.query,
                        "sources": selected,
                    }
                )

        return targets

    async def _resilient_fetch(
        self,
        source: str,
        query: str,
        territory: str,
    ) -> FetchResult:
        """Fetch with retry, circuit breaker, and fallback."""

        async def do_fetch(source: str) -> RawData:
            if not self.crawler:
                # Mock for testing
                return RawData(
                    source=source,
                    content={"query": query, "territory": territory},
                    url=f"https://{source}.example.com/api",
                    fetched_at=datetime.now(UTC),
                    quality_hint=0.7,
                )

            result = await self.crawler.fetch(
                source=source,
                query=query,
                params={"territory": territory},
            )
            return RawData(
                source=source,
                content=result.get("content", {}),
                url=result.get("url", ""),
                fetched_at=datetime.now(UTC),
                quality_hint=self._estimate_quality(result),
            )

        return await self.fallback_chain.fetch_with_fallback(
            do_fetch,
            source=source,
            max_fallbacks=self.max_fallbacks,
        )

    async def _detect_sparse_territory(self, territory: str) -> bool:
        """Detect if territory has sparse data."""
        if not self.graph_expander.neo4j:
            return False

        try:
            # Check entity count for territory
            gaps = await self.graph_expander.find_gaps(territory)
            # If many gaps, territory is sparse
            return len(gaps) > 30
        except Exception:
            return False

    async def _augment_sparse_results(
        self,
        raw_data: list[RawData],
        context: HuntContext,
    ) -> AugmentedData | None:
        """Try to augment sparse results, including web crawling if enabled."""
        supplements = []

        if not raw_data:
            # Try to fetch from all sources as supplement
            for source in self.bandit.sources[:3]:
                result = await self._resilient_fetch(
                    source=source,
                    query=context.query,
                    territory=context.territory,
                )
                if result.success and result.data:
                    supplements.append(result.data)

        # If still sparse and web crawling is enabled, try web reinforcement
        total_data = len(raw_data) + len(supplements)
        if self.web_crawl_on_sparse and total_data < self.sparse_threshold:
            logger.info(
                f"API data insufficient ({total_data} items), triggering web crawling reinforcement"
            )
            web_results = await self._crawl_web_reinforcement(
                query=context.query,
                territory=context.territory,
            )
            supplements.extend(web_results)
            logger.info(f"Web crawling added {len(web_results)} supplementary items")

        if not raw_data and not supplements:
            return await self.augmenter.augment(
                primary=None,
                supplementary=[],
            )

        if not raw_data:
            return await self.augmenter.augment(
                primary=None,
                supplementary=supplements,
            )

        # Augment existing data
        primary = raw_data[0]
        existing_supplements = raw_data[1:] if len(raw_data) > 1 else []
        all_supplements = existing_supplements + supplements

        return await self.augmenter.augment(
            primary=primary,
            supplementary=all_supplements,
        )

    async def _crawl_web_reinforcement(
        self,
        query: str,
        territory: str,
    ) -> list[RawData]:
        """
        Crawl web sources to reinforce insufficient API data.

        Uses TAJINECrawler (Crawl4AI) to fetch contextual information
        from government and institutional websites.

        Args:
            query: Search query
            territory: Territory code (department)

        Returns:
            List of RawData from web crawling
        """
        if not self.crawler:
            logger.warning("No crawler available for web reinforcement")
            return []

        results = []
        urls_to_crawl = []

        # Build URLs from templates
        for template in self.WEB_REINFORCEMENT_SOURCES[: self.max_web_crawls]:
            url = template.format(
                query=query.replace(" ", "+"),
                territory=territory,
            )
            urls_to_crawl.append(url)

        # Crawl URLs concurrently
        async def safe_crawl(url: str) -> RawData | None:
            try:
                if hasattr(self.crawler, "fetch_url"):
                    crawl_result = await self.crawler.fetch_url(url)
                    if crawl_result.success and crawl_result.content:
                        return RawData(
                            source="web_crawl",
                            content={
                                "text": crawl_result.markdown
                                or crawl_result.content.get("text", ""),
                                "url": url,
                                "title": crawl_result.metadata.get("title", ""),
                            },
                            url=url,
                            fetched_at=datetime.now(UTC),
                            quality_hint=0.6,  # Web data is less reliable than APIs
                        )
                else:
                    # Fallback: use fetch with "web" source
                    result = await self.crawler.fetch(
                        source="web",
                        query=query,
                        params={"territory": territory, "url": url},
                    )
                    if result.get("content"):
                        return RawData(
                            source="web_crawl",
                            content=result.get("content", {}),
                            url=url,
                            fetched_at=datetime.now(UTC),
                            quality_hint=0.5,
                        )
            except Exception as e:
                logger.warning(f"Web crawl failed for {url}: {e}")
            return None

        # Execute crawls concurrently with timeout
        try:
            crawl_tasks = [safe_crawl(url) for url in urls_to_crawl]
            crawl_results = await asyncio.wait_for(
                asyncio.gather(*crawl_tasks, return_exceptions=True),
                timeout=30.0,  # 30 second timeout for all crawls
            )

            for result in crawl_results:
                if isinstance(result, RawData):
                    results.append(result)

        except TimeoutError:
            logger.warning("Web crawling timed out after 30 seconds")

        return results

    async def _get_kg_gaps_dict(self, territory: str) -> dict:
        """Get knowledge graph gaps as dict."""
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

    def get_health_report(self) -> dict:
        """Get health report for all sources."""
        return {source: self.fetcher.get_source_health(source) for source in self.bandit.sources}

    @property
    def cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.stats

    @property
    def bandit_stats(self) -> dict:
        """Get bandit learning statistics."""
        return {
            "total_pulls": self.bandit.total_pulls,
            "sources": {
                source: {
                    "pulls": self.bandit.arm_counts[i],
                    "mean_reward": self.bandit.get_arm_mean(source),
                    "ucb_score": self.bandit.get_ucb_score(i),
                }
                for i, source in enumerate(self.bandit.sources)
            },
        }
