"""Episodic retriever for TAJINE agent.

Provides semantic retrieval of past episodes using:
- Vector similarity search
- Contextual filtering (territory, sector)
- Pattern matching
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from loguru import logger

from src.infrastructure.agents.tajine.memory.episodic_store import Episode, EpisodicStore


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...


@dataclass
class RetrievalResult:
    """Result from episode retrieval."""

    episode: Episode
    score: float  # Relevance score (0-1)
    match_type: str  # 'semantic', 'territory', 'sector', 'text'
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "episode_id": self.episode.id,
            "score": self.score,
            "match_type": self.match_type,
            "highlights": self.highlights,
            "query": self.episode.query,
            "territory": self.episode.territory,
            "sector": self.episode.sector,
            "timestamp": self.episode.timestamp.isoformat(),
        }


class OllamaEmbeddingProvider:
    """Embedding provider using Ollama."""

    def __init__(
        self,
        model: str = "nomic-embed-text:latest",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using Ollama."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text},
                )
                response.raise_for_status()
                data = response.json()
                embs = data.get("embeddings", [[]])
                return embs[0] if embs else []

        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch."""
        return [await self.embed(text) for text in texts]


class EpisodicRetriever:
    """Retriever for finding relevant episodes.

    Combines multiple retrieval strategies:
    - Semantic (vector similarity)
    - Contextual (territory/sector match)
    - Recency (time-weighted)
    - Text (keyword matching)
    """

    def __init__(
        self,
        store: EpisodicStore,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize the retriever.

        Args:
            store: Episode store instance
            embedding_provider: Provider for generating embeddings
        """
        self.store = store
        self.embedding_provider = embedding_provider or OllamaEmbeddingProvider()

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def retrieve_similar(
        self,
        query: str,
        k: int = 5,
        min_score: float = 0.5,
    ) -> list[RetrievalResult]:
        """Retrieve episodes semantically similar to query.

        Args:
            query: Search query
            k: Number of results
            min_score: Minimum similarity score

        Returns:
            List of similar episodes with scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed(query)
        if not query_embedding:
            # Fallback to text search
            return await self.retrieve_by_text(query, k)

        results = []
        for episode in self.store._episodes.values():
            if not episode.embedding:
                # Generate embedding if missing
                episode.embedding = await self.embedding_provider.embed(
                    episode.get_search_text()
                )
                self.store._save_episode(episode)

            if episode.embedding:
                score = self._cosine_similarity(query_embedding, episode.embedding)
                if score >= min_score:
                    results.append(RetrievalResult(
                        episode=episode,
                        score=score,
                        match_type="semantic",
                    ))

        # Sort by score and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def retrieve_by_territory(
        self,
        territory: str,
        k: int = 5,
        recent_days: int | None = 90,
    ) -> list[RetrievalResult]:
        """Retrieve episodes for a specific territory.

        Args:
            territory: Territory code
            k: Number of results
            recent_days: Only consider episodes from last N days

        Returns:
            List of matching episodes
        """
        cutoff = None
        if recent_days:
            cutoff = datetime.now(UTC) - timedelta(days=recent_days)

        results = []
        for episode in self.store._episodes.values():
            if episode.territory != territory:
                continue
            if cutoff and episode.timestamp < cutoff:
                continue

            # Score based on recency and feedback
            days_old = (datetime.now(UTC) - episode.timestamp).days
            recency_score = max(0, 1 - days_old / 365)  # Decay over year

            feedback_boost = 0
            if episode.feedback_score and episode.feedback_score > 0:
                feedback_boost = 0.2

            score = recency_score + feedback_boost

            results.append(RetrievalResult(
                episode=episode,
                score=min(score, 1.0),
                match_type="territory",
                highlights=[f"Territoire: {territory}"],
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def retrieve_by_sector(
        self,
        sector: str,
        k: int = 5,
    ) -> list[RetrievalResult]:
        """Retrieve episodes for a specific sector.

        Args:
            sector: Sector code or name
            k: Number of results

        Returns:
            List of matching episodes
        """
        sector_lower = sector.lower()
        results = []

        for episode in self.store._episodes.values():
            if not episode.sector:
                continue

            # Fuzzy sector matching
            if sector_lower in episode.sector.lower():
                days_old = (datetime.now(UTC) - episode.timestamp).days
                recency_score = max(0, 1 - days_old / 365)

                results.append(RetrievalResult(
                    episode=episode,
                    score=recency_score,
                    match_type="sector",
                    highlights=[f"Secteur: {episode.sector}"],
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def retrieve_by_pattern(
        self,
        pattern: str,
        k: int = 5,
    ) -> list[RetrievalResult]:
        """Retrieve episodes matching a reasoning pattern.

        Args:
            pattern: Pattern description (e.g., "growth analysis", "causal")
            k: Number of results

        Returns:
            Episodes with similar patterns
        """
        pattern_lower = pattern.lower()
        results = []

        # Map patterns to cognitive levels
        pattern_levels = {
            "discovery": ["découverte", "exploration", "données"],
            "causal": ["cause", "effet", "corrélation", "pourquoi"],
            "scenario": ["scénario", "projection", "prévision", "futur"],
            "strategy": ["stratégie", "recommandation", "action"],
            "theoretical": ["théorie", "modèle", "hypothèse"],
        }

        matching_levels = []
        for level, keywords in pattern_levels.items():
            if any(kw in pattern_lower for kw in keywords):
                matching_levels.append(level)

        for episode in self.store._episodes.values():
            score = 0.0
            highlights = []

            # Check cognitive levels
            for level in matching_levels:
                if level in episode.cognitive_levels:
                    level_score = episode.cognitive_levels[level]
                    if level_score > 0.5:
                        score += 0.3
                        highlights.append(f"{level}: {level_score:.2f}")

            # Check keywords in query
            if any(kw in episode.query.lower() for kw in pattern_lower.split()):
                score += 0.2

            if score > 0:
                results.append(RetrievalResult(
                    episode=episode,
                    score=min(score, 1.0),
                    match_type="pattern",
                    highlights=highlights,
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]

    async def retrieve_by_text(
        self,
        query: str,
        k: int = 5,
    ) -> list[RetrievalResult]:
        """Simple text search retrieval.

        Args:
            query: Search query
            k: Number of results

        Returns:
            Text-matching episodes
        """
        episodes = self.store.search_text(query, k)
        return [
            RetrievalResult(
                episode=ep,
                score=0.5,  # Default score for text match
                match_type="text",
            )
            for ep in episodes
        ]

    async def retrieve_for_context(
        self,
        query: str,
        territory: str | None = None,
        sector: str | None = None,
        k: int = 5,
    ) -> list[RetrievalResult]:
        """Retrieve episodes relevant to full context.

        Combines multiple retrieval strategies for best results.

        Args:
            query: Search query
            territory: Optional territory filter
            sector: Optional sector filter
            k: Number of results

        Returns:
            Most relevant episodes
        """
        all_results: dict[str, RetrievalResult] = {}

        # Semantic search (highest weight)
        semantic_results = await self.retrieve_similar(query, k * 2)
        for result in semantic_results:
            result.score *= 1.0  # Full weight
            all_results[result.episode.id] = result

        # Territory-specific
        if territory:
            territory_results = await self.retrieve_by_territory(territory, k)
            for result in territory_results:
                if result.episode.id in all_results:
                    all_results[result.episode.id].score += result.score * 0.5
                    all_results[result.episode.id].highlights.extend(result.highlights)
                else:
                    result.score *= 0.5
                    all_results[result.episode.id] = result

        # Sector-specific
        if sector:
            sector_results = await self.retrieve_by_sector(sector, k)
            for result in sector_results:
                if result.episode.id in all_results:
                    all_results[result.episode.id].score += result.score * 0.3
                    all_results[result.episode.id].highlights.extend(result.highlights)
                else:
                    result.score *= 0.3
                    all_results[result.episode.id] = result

        # Sort by combined score
        final_results = list(all_results.values())
        final_results.sort(key=lambda x: x.score, reverse=True)

        return final_results[:k]

    async def get_relevant_context(
        self,
        query: str,
        territory: str | None = None,
        sector: str | None = None,
        k: int = 3,
    ) -> str:
        """Get formatted context string from relevant episodes.

        Args:
            query: Search query
            territory: Optional territory
            sector: Optional sector
            k: Number of episodes to include

        Returns:
            Formatted context string for LLM prompt
        """
        results = await self.retrieve_for_context(query, territory, sector, k)

        if not results:
            return ""

        context_parts = ["## Analyses precedentes pertinentes:\n"]

        for i, result in enumerate(results, 1):
            ep = result.episode
            context_parts.append(f"### {i}. {ep.query}")
            context_parts.append(f"- Date: {ep.timestamp.strftime('%Y-%m-%d')}")
            if ep.territory:
                context_parts.append(f"- Territoire: {ep.territory}")
            if ep.sector:
                context_parts.append(f"- Secteur: {ep.sector}")
            if ep.confidence_score:
                context_parts.append(f"- Confiance: {ep.confidence_score:.0%}")

            # Add key findings from analysis result
            if ep.analysis_result.get("summary"):
                context_parts.append(f"- Resume: {ep.analysis_result['summary'][:200]}...")

            if ep.user_feedback:
                context_parts.append(f"- Feedback: {ep.user_feedback}")

            context_parts.append("")

        return "\n".join(context_parts)
