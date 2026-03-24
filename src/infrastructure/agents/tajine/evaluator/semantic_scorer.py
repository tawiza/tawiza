"""Semantic Coherence Scorer - Vector-based coherence checking for Evaluator.

Complements KGValidator by using semantic similarity to detect:
- Consistency with indexed knowledge (high similarity = coherent)
- Novelty vs contradiction (very low similarity to related docs)
- Semantic anomalies (outliers in embedding space)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.infrastructure.agents.tajine.core.types import RawData

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.semantic import SemanticSearchService

logger = logging.getLogger(__name__)


@dataclass
class SemanticCoherenceResult:
    """Result of semantic coherence check."""

    score: float  # 0.0 - 1.0
    similarity_to_indexed: float  # Max similarity to existing docs
    is_novel: bool  # Low similarity but plausible
    is_outlier: bool  # Very low similarity, potential anomaly
    similar_docs_count: int
    details: dict


class SemanticCoherenceScorer:
    """
    Scores data coherence using semantic similarity.

    Logic:
    - High similarity (>0.7) to indexed docs → coherent, score ~0.8
    - Medium similarity (0.4-0.7) → novel but plausible, score ~0.6
    - Low similarity (<0.4) with semantic source → anomaly, score ~0.3
    - No indexed docs yet → neutral, score 0.5

    Unlike KGValidator which checks structural contradictions,
    SemanticCoherenceScorer checks semantic proximity in vector space.
    """

    def __init__(
        self,
        semantic_service: SemanticSearchService | None = None,
        high_similarity_threshold: float = 0.7,
        low_similarity_threshold: float = 0.4,
        outlier_threshold: float = 0.2,
    ):
        """
        Initialize semantic coherence scorer.

        Args:
            semantic_service: SemanticSearchService for vector search
            high_similarity_threshold: Above this = clearly coherent
            low_similarity_threshold: Below this = potentially anomalous
            outlier_threshold: Below this = likely outlier/anomaly

        Raises:
            ValueError: If thresholds don't satisfy 0 < outlier < low < high < 1
        """
        # Validate threshold ordering to prevent division by zero and logic errors
        if not (0 < outlier_threshold < low_similarity_threshold < high_similarity_threshold < 1.0):
            raise ValueError(
                f"Thresholds must satisfy 0 < outlier ({outlier_threshold}) "
                f"< low ({low_similarity_threshold}) < high ({high_similarity_threshold}) < 1.0"
            )

        self.semantic_service = semantic_service
        self.high_threshold = high_similarity_threshold
        self.low_threshold = low_similarity_threshold
        self.outlier_threshold = outlier_threshold

    async def score(self, data: RawData) -> float:
        """
        Score data coherence and return a value.

        Args:
            data: Raw data to check

        Returns:
            Coherence score between 0.0 and 1.0
        """
        result = await self.check(data)
        return result.score

    async def check(self, data: RawData) -> SemanticCoherenceResult:
        """
        Full coherence check with detailed results.

        Args:
            data: Raw data to check

        Returns:
            SemanticCoherenceResult with score and details
        """
        if not self.semantic_service:
            return SemanticCoherenceResult(
                score=0.5,  # Neutral if no service
                similarity_to_indexed=0.0,
                is_novel=False,
                is_outlier=False,
                similar_docs_count=0,
                details={"reason": "no_semantic_service"},
            )

        # Extract text from RawData
        text = self._extract_text(data)
        if not text or len(text) < 10:
            return SemanticCoherenceResult(
                score=0.5,
                similarity_to_indexed=0.0,
                is_novel=False,
                is_outlier=False,
                similar_docs_count=0,
                details={"reason": "insufficient_text"},
            )

        # Get territory hint from data if available
        territory = None
        if isinstance(data.content, dict):
            territory = data.content.get("territory") or data.content.get("department") or None

        # Search for similar indexed documents
        try:
            results = await self.semantic_service.search(
                query=text[:500],  # Limit query length
                limit=5,
                territory=territory,
                score_threshold=0.1,  # Low threshold to see distribution
            )
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return SemanticCoherenceResult(
                score=0.5,
                similarity_to_indexed=0.0,
                is_novel=False,
                is_outlier=False,
                similar_docs_count=0,
                details={"reason": "search_failed", "error": str(e)},
            )

        if not results:
            # No indexed docs yet - treat as novel
            return SemanticCoherenceResult(
                score=0.6,  # Slightly positive for fresh data
                similarity_to_indexed=0.0,
                is_novel=True,
                is_outlier=False,
                similar_docs_count=0,
                details={"reason": "no_indexed_docs"},
            )

        # Analyze similarity distribution
        max_similarity = max(r.score for r in results)
        avg_similarity = sum(r.score for r in results) / len(results)

        # Determine coherence score
        is_outlier = max_similarity < self.outlier_threshold
        is_novel = self.low_threshold <= max_similarity < self.high_threshold
        is_coherent = max_similarity >= self.high_threshold

        if is_coherent:
            # High similarity = coherent with existing knowledge
            score = 0.7 + (max_similarity - self.high_threshold) * 0.3 / (1.0 - self.high_threshold)
        elif is_novel:
            # Medium similarity = novel but plausible
            range_size = self.high_threshold - self.low_threshold
            normalized = (max_similarity - self.low_threshold) / range_size
            score = 0.5 + normalized * 0.2
        elif is_outlier:
            # Very low similarity = potential anomaly
            score = 0.2 + max_similarity * 0.5  # 0.2 - 0.3
        else:
            # Low similarity but not extreme
            score = 0.4

        # Bonus for multiple similar docs (cross-validation)
        coherent_docs = sum(1 for r in results if r.score >= self.low_threshold)
        if coherent_docs >= 3:
            score += 0.05

        # Clamp score to valid range [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        return SemanticCoherenceResult(
            score=round(score, 3),
            similarity_to_indexed=round(max_similarity, 3),
            is_novel=is_novel,
            is_outlier=is_outlier,
            similar_docs_count=len(results),
            details={
                "max_similarity": max_similarity,
                "avg_similarity": avg_similarity,
                "coherent_docs": coherent_docs,
                "territory_filter": territory,
            },
        )

    def _extract_text(self, data: RawData) -> str:
        """Extract text content from RawData."""
        if isinstance(data.content, str):
            return data.content
        elif isinstance(data.content, dict):
            # Prioritize 'text' field, then flatten
            if "text" in data.content:
                return str(data.content["text"])

            parts = []
            for _key, value in data.content.items():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, (list, tuple)):
                    parts.extend(str(v) for v in value if v)
            return " ".join(parts)

        return str(data.content) if data.content else ""
