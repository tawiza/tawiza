"""
StrategyLevel - Level 4 of CognitiveEngine

Generates strategic recommendations based on scenario analysis.
Uses Monte Carlo distribution for risk-adjusted decision making.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.levels.discovery import BaseCognitiveLevel

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider


@dataclass
class StrategicRecommendation:
    """A strategic recommendation with risk assessment."""

    type: str  # investment, monitoring, caution, diversification, exit
    priority: str  # critical, high, medium, low
    description: str
    rationale: str
    risk_score: float  # 0-1, higher = more risky
    confidence: float  # 0-1
    contributing_factors: list[str] = field(default_factory=list)
    time_horizon: str = "medium_term"  # immediate, short_term, medium_term, long_term

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "priority": self.priority,
            "description": self.description,
            "rationale": self.rationale,
            "risk_score": round(self.risk_score, 2),
            "confidence": round(self.confidence, 2),
            "contributing_factors": self.contributing_factors,
            "time_horizon": self.time_horizon,
        }


@dataclass
class ActionItem:
    """A concrete action to implement a strategy."""

    action: str
    priority: int  # 1 = highest priority
    category: str  # immediate, short_term, medium_term
    dependencies: list[str] = field(default_factory=list)
    estimated_months: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "priority": self.priority,
            "category": self.category,
            "dependencies": self.dependencies,
            "estimated_months": self.estimated_months,
        }


# Strategy thresholds
HIGH_GROWTH_THRESHOLD = 0.15  # 15% growth
MODERATE_GROWTH_THRESHOLD = 0.05  # 5% growth
HIGH_UNCERTAINTY_THRESHOLD = 0.3  # P90-P10 spread > 30% of median
HIGH_RISK_THRESHOLD = 0.6


class StrategyLevel(BaseCognitiveLevel):
    """
    Level 4: Strategy Recommendations

    Generates risk-adjusted strategic recommendations using:
    - Full scenario distribution (not just median)
    - Uncertainty quantification (P10-P90 spread)
    - Causal factor attribution
    - Time-phased action planning

    Output includes:
    - Recommendations with risk scores
    - Prioritized action items
    - Risk mitigation strategies
    """

    def __init__(self, llm_provider: Optional["LLMProvider"] = None):
        """Initialize StrategyLevel."""
        super().__init__(llm_provider)

    @property
    def level_number(self) -> int:
        return 4

    @property
    def level_name(self) -> str:
        return "strategy"

    async def process(
        self, results: list[dict[str, Any]], previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate strategic recommendations.

        Args:
            results: Raw execution results
            previous: Previous level outputs (scenario analysis)

        Returns:
            Dict with recommendations, actions, risk_assessment, confidence
        """
        logger.debug("StrategyLevel processing")

        # Try LLM-powered processing first
        llm_result = await self._process_with_llm(results, previous)
        if llm_result and llm_result.get("recommendations"):
            logger.info("StrategyLevel: Using LLM-powered analysis")
            return llm_result

        # Try risk-adjusted strategy generation
        strategy_result = await self._process_with_risk_analysis(previous)
        if strategy_result and strategy_result.get("recommendations"):
            logger.info("StrategyLevel: Using risk-adjusted analysis")
            return strategy_result

        # Fallback to rule-based processing
        logger.debug("StrategyLevel: Using rule-based analysis")
        return self._process_rule_based(previous)

    async def _process_with_risk_analysis(self, previous: dict[str, Any]) -> dict[str, Any]:
        """Generate risk-adjusted recommendations using Monte Carlo output."""
        scenario = previous.get("scenario", {})
        causal = previous.get("causal", {})

        # Check if we have Monte Carlo output
        if scenario.get("method") != "monte_carlo":
            return {}

        try:
            # Extract scenario data
            optimistic = scenario.get("optimistic", {})
            median = scenario.get("median", {})
            pessimistic = scenario.get("pessimistic", {})
            scenario.get("distribution", {})
            causes = causal.get("causes", [])

            # Calculate key metrics
            median_growth = median.get("growth_rate", 0)
            optimistic_growth = optimistic.get("growth_rate", median_growth)
            pessimistic_growth = pessimistic.get("growth_rate", median_growth)

            # Uncertainty spread (normalized)
            spread = optimistic_growth - pessimistic_growth
            uncertainty = spread / max(abs(median_growth), 0.01)

            # Risk score based on downside and uncertainty
            downside_risk = max(0, -pessimistic_growth)
            risk_score = min(1.0, downside_risk + uncertainty * 0.3)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                median_growth=median_growth,
                optimistic_growth=optimistic_growth,
                pessimistic_growth=pessimistic_growth,
                uncertainty=uncertainty,
                risk_score=risk_score,
                causes=causes,
            )

            # Generate action items
            actions = self._generate_actions(recommendations, causes)

            # Generate risk mitigation strategies
            risk_mitigations = self._generate_risk_mitigations(
                risk_score=risk_score, pessimistic_growth=pessimistic_growth, causes=causes
            )

            # Overall confidence
            scenario_confidence = scenario.get("confidence", 0.5)
            causal_confidence = causal.get("confidence", 0.5)
            confidence = (scenario_confidence + causal_confidence) / 2

            return {
                "recommendations": [r.to_dict() for r in recommendations],
                "actions": [a.to_dict() for a in actions],
                "risk_assessment": {
                    "overall_risk": round(risk_score, 2),
                    "uncertainty_level": "high"
                    if uncertainty > HIGH_UNCERTAINTY_THRESHOLD
                    else "moderate",
                    "downside_exposure": round(pessimistic_growth, 4),
                    "upside_potential": round(optimistic_growth, 4),
                    "mitigations": risk_mitigations,
                },
                "confidence": round(confidence, 2),
                "method": "risk_adjusted",
            }

        except Exception as e:
            logger.warning(f"Risk-adjusted analysis failed: {e}")
            return {}

    def _generate_recommendations(
        self,
        median_growth: float,
        optimistic_growth: float,
        pessimistic_growth: float,
        uncertainty: float,
        risk_score: float,
        causes: list[dict[str, Any]],
    ) -> list[StrategicRecommendation]:
        """Generate strategic recommendations based on scenario analysis."""
        recommendations = []
        contributing_factors = [c.get("factor", "") for c in causes[:3]]

        # High growth, low uncertainty → Strong investment
        if median_growth > HIGH_GROWTH_THRESHOLD and uncertainty < HIGH_UNCERTAINTY_THRESHOLD:
            recommendations.append(
                StrategicRecommendation(
                    type="investment",
                    priority="critical",
                    description="Aggressive expansion recommended",
                    rationale=f"Strong growth ({median_growth:.1%}) with low uncertainty",
                    risk_score=risk_score,
                    confidence=0.85,
                    contributing_factors=contributing_factors,
                    time_horizon="immediate",
                )
            )

        # High growth, high uncertainty → Cautious investment
        elif median_growth > HIGH_GROWTH_THRESHOLD and uncertainty >= HIGH_UNCERTAINTY_THRESHOLD:
            recommendations.append(
                StrategicRecommendation(
                    type="investment",
                    priority="high",
                    description="Phased investment with hedging",
                    rationale=f"High growth potential ({median_growth:.1%}) but significant uncertainty (±{uncertainty:.0%})",
                    risk_score=risk_score,
                    confidence=0.7,
                    contributing_factors=contributing_factors,
                    time_horizon="short_term",
                )
            )
            recommendations.append(
                StrategicRecommendation(
                    type="diversification",
                    priority="medium",
                    description="Diversify across related sectors",
                    rationale="Reduce concentration risk given uncertainty",
                    risk_score=risk_score * 0.8,
                    confidence=0.65,
                    contributing_factors=contributing_factors,
                    time_horizon="medium_term",
                )
            )

        # Moderate growth → Selective investment
        elif median_growth > MODERATE_GROWTH_THRESHOLD:
            recommendations.append(
                StrategicRecommendation(
                    type="monitoring",
                    priority="medium",
                    description="Selective opportunities in high-confidence segments",
                    rationale=f"Moderate growth ({median_growth:.1%}), focus on proven factors",
                    risk_score=risk_score,
                    confidence=0.6,
                    contributing_factors=contributing_factors,
                    time_horizon="medium_term",
                )
            )

        # Low/negative growth, high risk → Exit or defensive
        elif median_growth <= 0 or risk_score > HIGH_RISK_THRESHOLD:
            recommendations.append(
                StrategicRecommendation(
                    type="caution",
                    priority="high",
                    description="Defensive positioning recommended",
                    rationale=f"Limited growth ({median_growth:.1%}) with elevated risk ({risk_score:.0%})",
                    risk_score=risk_score,
                    confidence=0.75,
                    contributing_factors=contributing_factors,
                    time_horizon="immediate",
                )
            )
            if pessimistic_growth < -0.1:
                recommendations.append(
                    StrategicRecommendation(
                        type="exit",
                        priority="medium",
                        description="Consider reducing exposure",
                        rationale=f"Significant downside risk (P10: {pessimistic_growth:.1%})",
                        risk_score=risk_score,
                        confidence=0.6,
                        contributing_factors=contributing_factors,
                        time_horizon="short_term",
                    )
                )

        # Stable/neutral → Monitor
        else:
            recommendations.append(
                StrategicRecommendation(
                    type="monitoring",
                    priority="low",
                    description="Maintain current position, monitor developments",
                    rationale="Stable conditions, no urgent action required",
                    risk_score=risk_score,
                    confidence=0.5,
                    contributing_factors=contributing_factors,
                    time_horizon="long_term",
                )
            )

        return recommendations

    def _generate_actions(
        self, recommendations: list[StrategicRecommendation], causes: list[dict[str, Any]]
    ) -> list[ActionItem]:
        """Generate prioritized action items from recommendations."""
        actions = []
        priority_counter = 1

        # Extract lag information for timing
        max_lag = max((c.get("lag_months", 3) for c in causes), default=3)

        for rec in recommendations:
            if rec.type == "investment" and rec.priority in ["critical", "high"]:
                actions.extend(
                    [
                        ActionItem(
                            action="Conduct detailed market analysis",
                            priority=priority_counter,
                            category="immediate",
                            estimated_months=1,
                        ),
                        ActionItem(
                            action="Identify strategic partners or acquisition targets",
                            priority=priority_counter + 1,
                            category="short_term",
                            dependencies=["Conduct detailed market analysis"],
                            estimated_months=3,
                        ),
                        ActionItem(
                            action="Develop implementation roadmap",
                            priority=priority_counter + 2,
                            category="short_term",
                            dependencies=["Identify strategic partners or acquisition targets"],
                            estimated_months=2,
                        ),
                    ]
                )
                priority_counter += 3

            elif rec.type == "diversification":
                actions.append(
                    ActionItem(
                        action="Map adjacent sectors for diversification opportunities",
                        priority=priority_counter,
                        category="short_term",
                        estimated_months=2,
                    )
                )
                priority_counter += 1

            elif rec.type == "monitoring":
                actions.append(
                    ActionItem(
                        action="Establish monitoring dashboard with key indicators",
                        priority=priority_counter,
                        category="immediate",
                        estimated_months=1,
                    )
                )
                actions.append(
                    ActionItem(
                        action=f"Set review cadence (recommended: every {max_lag} months)",
                        priority=priority_counter + 1,
                        category="short_term",
                        estimated_months=max_lag,
                    )
                )
                priority_counter += 2

            elif rec.type == "caution":
                actions.append(
                    ActionItem(
                        action="Review current exposure and risk thresholds",
                        priority=priority_counter,
                        category="immediate",
                        estimated_months=1,
                    )
                )
                priority_counter += 1

            elif rec.type == "exit":
                actions.append(
                    ActionItem(
                        action="Develop exit timeline and transition plan",
                        priority=priority_counter,
                        category="short_term",
                        estimated_months=3,
                    )
                )
                priority_counter += 1

        return sorted(actions, key=lambda a: a.priority)

    def _generate_risk_mitigations(
        self, risk_score: float, pessimistic_growth: float, causes: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Generate risk mitigation strategies."""
        mitigations = []

        if risk_score > 0.5:
            mitigations.append(
                {
                    "risk": "High overall risk",
                    "mitigation": "Implement stop-loss thresholds and regular risk reviews",
                }
            )

        if pessimistic_growth < -0.05:
            mitigations.append(
                {
                    "risk": f"Downside exposure ({pessimistic_growth:.1%})",
                    "mitigation": "Hedge through diversification or options strategies",
                }
            )

        # Factor-specific mitigations
        for cause in causes:
            if cause.get("direction") == "negative" and cause.get("contribution", 0) > 0.1:
                factor = cause.get("factor", "Unknown factor")
                mitigations.append(
                    {
                        "risk": f"Negative factor: {factor}",
                        "mitigation": f"Monitor {factor} closely, prepare contingency plans",
                    }
                )

        return mitigations[:5]  # Limit to top 5

    def _process_rule_based(self, previous: dict[str, Any]) -> dict[str, Any]:
        """Fallback rule-based processing."""
        scenario = previous.get("scenario", {})
        median = scenario.get("median", {})

        recommendations = []
        actions = []

        growth_rate = median.get("growth_rate", 0)

        if growth_rate > 0.2:
            recommendations.append(
                {
                    "type": "investment",
                    "priority": "high",
                    "description": "Increase presence in growing sector",
                    "rationale": f"Expected growth rate: {growth_rate:.1%}",
                }
            )
            actions.append("Identify acquisition targets")
            actions.append("Expand local partnerships")
        elif growth_rate > 0:
            recommendations.append(
                {
                    "type": "monitoring",
                    "priority": "medium",
                    "description": "Monitor sector for opportunities",
                    "rationale": "Moderate growth expected",
                }
            )
            actions.append("Set up market watch")
        else:
            recommendations.append(
                {
                    "type": "caution",
                    "priority": "low",
                    "description": "Exercise caution, focus elsewhere",
                    "rationale": "Limited growth potential",
                }
            )

        return {
            "recommendations": recommendations,
            "actions": actions,
            "confidence": 0.5,
            "method": "rule_based",
        }
