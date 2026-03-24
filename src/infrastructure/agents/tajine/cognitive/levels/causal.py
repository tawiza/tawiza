"""
CausalLevel - Level 2 of CognitiveEngine

Analyzes cause-effect relationships using temporal correlation and causal DAG.
"""

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.causal import (
    CausalChain,
    CausalHypothesis,
    CausalLink,
    DAGManager,
    compute_causal_confidence,
    compute_lagged_correlation,
)
from src.infrastructure.agents.tajine.cognitive.levels.discovery import BaseCognitiveLevel

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider
    from src.infrastructure.knowledge_graph.neo4j_client import Neo4jClient


# Confidence thresholds
MIN_LINK_CONFIDENCE = 0.5  # Minimum confidence to store a causal link
MIN_CORRELATION = 0.3  # Minimum |correlation| to consider meaningful
RULE_BASED_CONFIDENCE = 0.5  # Confidence for domain rule links
DEFAULT_CONFIDENCE = 0.4  # Fallback when no data available
DEFAULT_LAG_MONTHS = 3  # Default assumed lag for rules

# Domain knowledge: known causal relationships for territorial analysis
KNOWN_CAUSAL_RULES = [
    ("university_proximity", "tech_company_growth", 0.7),
    ("unemployment_rate", "company_creation", -0.5),
    ("infrastructure_quality", "business_attraction", 0.6),
    ("population_growth", "economic_activity", 0.5),
    ("tech_investment", "job_creation", 0.65),
    ("education_level", "innovation_index", 0.6),
]


class CausalLevel(BaseCognitiveLevel):
    """
    Level 2: Causal Analysis

    Identifies cause-effect relationships using:
    1. Temporal correlation analysis (lag correlation)
    2. Domain knowledge rules
    3. Neo4j DAG for persistence and chain discovery
    4. LLM for enhanced causal reasoning (when available)
    """

    def __init__(
        self,
        llm_provider: Optional["LLMProvider"] = None,
        neo4j_client: Optional["Neo4jClient"] = None,
    ):
        """
        Initialize CausalLevel.

        Args:
            llm_provider: Optional LLM for enhanced analysis
            neo4j_client: Optional Neo4j client for DAG persistence
        """
        super().__init__(llm_provider)
        self._dag_manager = DAGManager(neo4j_client)

    @property
    def level_number(self) -> int:
        return 2

    @property
    def level_name(self) -> str:
        return "causal"

    async def process(
        self, results: list[dict[str, Any]], previous: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Analyze causal relationships from discovery signals.

        Processing order:
        1. Try LLM-powered causal reasoning
        2. If LLM unavailable, use correlation + DAG analysis
        3. Fallback to rule-based analysis

        Args:
            results: Raw execution results
            previous: Previous level outputs (discovery signals)

        Returns:
            Dict with causes, effects, causal_chains, confidence
        """
        logger.debug("CausalLevel processing")

        # Try LLM-powered processing first
        llm_result = await self._process_with_llm(results, previous)
        if llm_result and llm_result.get("causes"):
            logger.info("CausalLevel: Using LLM-powered analysis")
            return llm_result

        # Try DAG-based causal analysis
        try:
            dag_result = await self._process_with_dag(results, previous)
            if dag_result and dag_result.get("causes"):
                logger.info("CausalLevel: Using DAG-based analysis")
                return dag_result
        except Exception as e:
            logger.warning(f"DAG analysis failed: {e}")

        # Fallback to rule-based processing
        logger.debug("CausalLevel: Using rule-based analysis")
        return self._process_rule_based(previous)

    async def _process_with_dag(
        self, results: list[dict[str, Any]], previous: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process using correlation analysis and DAG.

        Steps:
        1. Extract time series from results
        2. Generate causal hypotheses from signals
        3. Test hypotheses with lag correlation
        4. Store validated links in DAG
        5. Build causal chains
        """
        discovery = previous.get("discovery", {})
        signals = discovery.get("signals", [])
        territory = previous.get("territory", "default")

        # Extract time series data from results
        time_series = self._extract_time_series(results)

        # Generate hypotheses from signals
        hypotheses = self._generate_hypotheses(signals)

        # Test each hypothesis
        validated_links: list[CausalLink] = []
        for hypothesis in hypotheses:
            link = await self._test_hypothesis(hypothesis, time_series)
            if link and link.confidence >= MIN_LINK_CONFIDENCE:
                validated_links.append(link)
                await self._dag_manager.store_link(link, context=territory)

        # Add domain rules as baseline
        for cause, effect, strength in KNOWN_CAUSAL_RULES:
            if not any(l.cause == cause and l.effect == effect for l in validated_links):
                rule_link = CausalLink(
                    cause=cause,
                    effect=effect,
                    correlation=strength,
                    lag_months=DEFAULT_LAG_MONTHS,
                    confidence=RULE_BASED_CONFIDENCE,
                    evidence="Domain knowledge rule",
                )
                validated_links.append(rule_link)
                await self._dag_manager.store_link(rule_link, context=territory)

        # Build causal chains for key effects
        chains = await self._build_causal_chains(validated_links, territory)

        # Compute overall confidence (safe division)
        avg_confidence = (
            sum(l.confidence for l in validated_links) / len(validated_links)
            if validated_links
            else DEFAULT_CONFIDENCE
        )

        return {
            "causes": [self._format_cause(link) for link in validated_links],
            "effects": self._infer_effects(validated_links),
            "causal_chains": [chain.to_dict() for chain in chains],
            "confidence": round(avg_confidence, 2),
            "method": "dag_correlation",
        }

    def _extract_time_series(self, results: list[dict[str, Any]]) -> dict[str, list[float]]:
        """
        Extract time series data from execution results.

        Looks for monthly data in result payloads.
        """
        time_series = {}

        for r in results:
            result_data = r.get("result", {})
            if not isinstance(result_data, dict):
                continue

            data = result_data.get("data", result_data)
            if not isinstance(data, dict):
                continue

            # Look for monthly time series fields
            for key in [
                "creations_12_mois",
                "radiations_12_mois",
                "creation_monthly",
                "employment_monthly",
                "growth_monthly",
            ]:
                if key in data and isinstance(data[key], list):
                    time_series[key] = data[key]

            # Also extract single values as repeated series (for testing)
            for key in ["companies", "growth", "unemployment_rate"]:
                if key in data and isinstance(data[key], (int, float)):
                    # Convert single value to short series
                    time_series[key] = [float(data[key])] * 6

        return time_series

    def _generate_hypotheses(self, signals: list[dict[str, Any]]) -> list[CausalHypothesis]:
        """
        Generate causal hypotheses from discovery signals.
        """
        hypotheses = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue

            signal_type = signal.get("type", "")

            if signal_type == "growth":
                hypotheses.extend(
                    [
                        CausalHypothesis(
                            cause="economic_conditions",
                            effect="company_creation",
                            source="growth_signal",
                            priority=0.8,
                        ),
                        CausalHypothesis(
                            cause="tech_investment",
                            effect="growth",
                            source="growth_signal",
                            priority=0.7,
                        ),
                    ]
                )

            elif signal_type == "concentration":
                hypotheses.extend(
                    [
                        CausalHypothesis(
                            cause="university_proximity",
                            effect="tech_concentration",
                            source="concentration_signal",
                            priority=0.8,
                        ),
                        CausalHypothesis(
                            cause="infrastructure_quality",
                            effect="concentration",
                            source="concentration_signal",
                            priority=0.6,
                        ),
                    ]
                )

            elif signal_type == "decline":
                hypotheses.append(
                    CausalHypothesis(
                        cause="unemployment_rate",
                        effect="decline",
                        source="decline_signal",
                        priority=0.7,
                    )
                )

        # Sort by priority
        return sorted(hypotheses, key=lambda h: h.priority, reverse=True)

    async def _test_hypothesis(
        self, hypothesis: CausalHypothesis, time_series: dict[str, list[float]]
    ) -> CausalLink | None:
        """
        Test a causal hypothesis using lag correlation.
        """
        cause_series = time_series.get(hypothesis.cause)
        effect_series = time_series.get(hypothesis.effect)

        if not cause_series or not effect_series:
            # No data available - use domain knowledge default
            return CausalLink(
                cause=hypothesis.cause,
                effect=hypothesis.effect,
                correlation=RULE_BASED_CONFIDENCE,
                lag_months=DEFAULT_LAG_MONTHS,
                confidence=DEFAULT_CONFIDENCE,
                evidence=f"No time series data - using default (source: {hypothesis.source})",
            )

        # Compute lagged correlation
        correlation, lag = compute_lagged_correlation(cause_series, effect_series)

        # Compute confidence
        sample_size = min(len(cause_series), len(effect_series))
        confidence = compute_causal_confidence(correlation, lag, sample_size)

        if abs(correlation) < MIN_CORRELATION:
            return None  # Too weak correlation

        return CausalLink(
            cause=hypothesis.cause,
            effect=hypothesis.effect,
            correlation=correlation,
            lag_months=lag,
            confidence=confidence,
            evidence=f"Lag correlation: r={correlation:.2f}, lag={lag} months",
        )

    async def _build_causal_chains(
        self, links: list[CausalLink], context: str
    ) -> list[CausalChain]:
        """
        Build causal chains by traversing the DAG.
        """
        chains = []
        key_effects = ["company_creation", "job_creation", "growth", "tech_concentration"]

        for effect in key_effects:
            # Find chains leading to this effect
            for link in links:
                if link.effect != effect:
                    continue

                chain = await self._dag_manager.get_causal_chain(
                    root=link.cause, target=effect, context=context, max_depth=3
                )
                if chain and chain not in chains:
                    chains.append(chain)

        return chains[:5]  # Limit to top 5 chains

    def _format_cause(self, link: CausalLink) -> dict[str, Any]:
        """Format a causal link as a cause dict."""
        direction = "positive" if link.correlation > 0 else "negative"
        return {
            "factor": link.cause,
            "contribution": abs(link.correlation),
            "direction": direction,
            "lag_months": link.lag_months,
            "confidence": link.confidence,
            "evidence": link.evidence,
        }

    def _infer_effects(self, links: list[CausalLink]) -> list[dict[str, Any]]:
        """Infer effects from validated causal links."""
        effects = []
        effect_names = {l.effect for l in links}

        for effect_name in effect_names:
            relevant_links = [l for l in links if l.effect == effect_name]
            if not relevant_links:
                continue
            avg_confidence = sum(l.confidence for l in relevant_links) / len(relevant_links)

            effects.append(
                {
                    "outcome": effect_name,
                    "magnitude": "high" if avg_confidence > 0.7 else "medium",
                    "timeframe": "1-3 years",
                    "contributing_factors": [l.cause for l in relevant_links],
                }
            )

        return effects

    def _process_rule_based(self, previous: dict[str, Any]) -> dict[str, Any]:
        """
        Fallback rule-based processing (original implementation).
        """
        discovery = previous.get("discovery", {})
        signals = discovery.get("signals", [])

        causes = []
        effects = []

        for signal in signals:
            signal_type = signal.get("type", "") if isinstance(signal, dict) else ""
            if signal_type == "growth":
                causes.append(
                    {
                        "factor": "economic_conditions",
                        "contribution": 0.3,
                        "direction": "positive",
                        "evidence": "Correlation with regional GDP",
                    }
                )
                causes.append(
                    {
                        "factor": "education_infrastructure",
                        "contribution": 0.25,
                        "direction": "positive",
                        "evidence": "Proximity to universities",
                    }
                )

            if signal_type == "concentration":
                effects.append(
                    {"outcome": "job_creation", "magnitude": "high", "timeframe": "1-3 years"}
                )

        confidence = 0.6 if causes else 0.4

        return {
            "causes": causes,
            "effects": effects,
            "causal_chains": [],
            "confidence": confidence,
            "method": "rule_based",
        }
