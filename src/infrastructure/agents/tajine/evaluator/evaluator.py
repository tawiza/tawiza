"""Evaluator - 3D data scoring orchestrator."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.infrastructure.agents.tajine.core.types import (
    EvaluationResult,
    RawData,
    ScoredData,
)
from src.infrastructure.agents.tajine.evaluator.alpha_tester import AlphaTester
from src.infrastructure.agents.tajine.evaluator.kg_validator import KGValidator
from src.infrastructure.agents.tajine.evaluator.semantic_scorer import (
    SemanticCoherenceScorer,
)
from src.infrastructure.agents.tajine.evaluator.source_credibility import (
    SourceCredibilityScorer,
)

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.semantic import SemanticSearchService

logger = logging.getLogger(__name__)


class Evaluator:
    """
    Evaluates data on 3 dimensions:

    1. Reliability: Source credibility (Bayesian)
    2. Coherence: Consistency with Knowledge Graph
    3. Alpha: Predictive power (new information value)

    Composite Score = Reliability^0.4 × Coherence^0.3 × Alpha^0.3
    """

    def __init__(
        self,
        source_scorer: SourceCredibilityScorer | None = None,
        kg_validator: KGValidator | None = None,
        alpha_tester: AlphaTester | None = None,
        semantic_scorer: SemanticCoherenceScorer | None = None,
        weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
        neo4j_client=None,
        semantic_service: SemanticSearchService | None = None,
        use_semantic_coherence: bool = False,
    ):
        """
        Initialize evaluator.

        Args:
            source_scorer: Bayesian source credibility scorer
            kg_validator: Knowledge graph coherence checker
            alpha_tester: Predictive power tester
            semantic_scorer: Semantic coherence scorer (vector-based)
            weights: (reliability, coherence, alpha) weights for composite
            neo4j_client: Optional Neo4j client for KG validation
            semantic_service: Optional SemanticSearchService for semantic coherence
            use_semantic_coherence: Enable blended coherence (KG + semantic)
        """
        self.source_scorer = source_scorer or SourceCredibilityScorer()
        self.kg_validator = kg_validator or KGValidator(neo4j_client=neo4j_client)
        self.alpha_tester = alpha_tester or AlphaTester()
        self.semantic_scorer = semantic_scorer or (
            SemanticCoherenceScorer(semantic_service=semantic_service)
            if semantic_service else None
        )
        self.use_semantic_coherence = use_semantic_coherence and self.semantic_scorer is not None
        self.w_rel, self.w_coh, self.w_alpha = weights

    async def evaluate(self, data: RawData) -> EvaluationResult:
        """
        Evaluate a piece of raw data.

        Args:
            data: Raw data to evaluate

        Returns:
            EvaluationResult with 3D scores and decision
        """
        # 1. Reliability from source credibility
        reliability = self.source_scorer.score(data.source)

        # 2. Coherence from KG validation
        kg_coherence = await self.kg_validator.check(data)

        # 2b. Optional: Blend with semantic coherence
        if self.use_semantic_coherence and self.semantic_scorer:
            semantic_coherence = await self.semantic_scorer.score(data)
            # Blend: 60% KG + 40% semantic, clamped to [0, 1]
            coherence = max(0.0, min(1.0, 0.6 * kg_coherence + 0.4 * semantic_coherence))
        else:
            coherence = kg_coherence

        # 3. Alpha from predictive testing
        alpha = await self.alpha_tester.test(data)

        # Create result (composite and decision computed in __post_init__)
        return EvaluationResult(
            reliability=reliability,
            coherence=coherence,
            alpha=alpha,
        )

    async def evaluate_batch(
        self,
        data_list: list[RawData],
    ) -> list[ScoredData]:
        """
        Evaluate multiple data items.

        Args:
            data_list: List of raw data to evaluate

        Returns:
            List of ScoredData with evaluations attached
        """
        scored = []

        for data in data_list:
            try:
                evaluation = await self.evaluate(data)
                scored.append(ScoredData(raw=data, evaluation=evaluation))
            except Exception as e:
                logger.error(f"Failed to evaluate data from {data.source}: {e}")

        return scored

    def update_source_credibility(self, source: str, was_correct: bool):
        """
        Update source credibility after validation.

        Args:
            source: Source identifier
            was_correct: Whether the data was validated as correct
        """
        self.source_scorer.update(source, was_correct)
