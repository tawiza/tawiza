"""
ScenarioLevel - Level 3 of CognitiveEngine

Generates future scenarios using Monte Carlo simulation with probabilistic projections.
"""

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.levels.discovery import BaseCognitiveLevel
from src.infrastructure.agents.tajine.cognitive.scenario import (
    MonteCarloEngine,
    SimulationConfig,
)

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider


class ScenarioLevel(BaseCognitiveLevel):
    """
    Level 3: Scenario Generation with Monte Carlo Simulation

    Generates probabilistic scenarios:
    - Optimistic: 90th percentile outcome
    - Median: 50th percentile outcome
    - Pessimistic: 10th percentile outcome

    Processing order:
    1. Try LLM-powered scenario generation
    2. Run Monte Carlo simulation from causal factors
    3. Fallback to rule-based multipliers

    The Monte Carlo simulation:
    - Samples from factor distributions (correlated via Cholesky)
    - Projects time series with lag effects (sigmoid ramp)
    - Computes full distribution statistics
    """

    def __init__(
        self,
        llm_provider: Optional["LLMProvider"] = None,
        simulation_config: SimulationConfig | None = None
    ):
        """Initialize ScenarioLevel.

        Args:
            llm_provider: Optional LLM for enhanced analysis
            simulation_config: Monte Carlo configuration (uses defaults if None)
        """
        super().__init__(llm_provider)
        self._simulation_config = simulation_config or SimulationConfig()

    @property
    def level_number(self) -> int:
        return 3

    @property
    def level_name(self) -> str:
        return "scenario"

    async def process(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate scenarios based on causal analysis.

        Args:
            results: Raw execution results
            previous: Previous level outputs (causal analysis)

        Returns:
            Dict with optimistic, median, pessimistic scenarios,
            plus full distribution and time series data
        """
        logger.debug("ScenarioLevel processing")

        # Try LLM-powered processing first
        llm_result = await self._process_with_llm(results, previous)
        if llm_result and llm_result.get('optimistic'):
            logger.info("ScenarioLevel: Using LLM-powered analysis")
            return llm_result

        # Try Monte Carlo simulation
        monte_carlo_result = await self._process_with_monte_carlo(results, previous)
        if monte_carlo_result and monte_carlo_result.get('method') == 'monte_carlo':
            logger.info("ScenarioLevel: Using Monte Carlo simulation")
            return monte_carlo_result

        # Fallback to rule-based processing
        logger.debug("ScenarioLevel: Using rule-based analysis")
        return self._process_rule_based(previous)

    async def _process_with_monte_carlo(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Run Monte Carlo simulation from causal factors.

        Extracts causes from CausalLevel output and runs simulation.
        """
        causal = previous.get('causal', {})
        causes = causal.get('causes', [])

        if not causes:
            logger.debug("No causal factors, skipping Monte Carlo")
            return {}

        try:
            # Extract base value from results
            base_value = self._extract_base_value(results)

            # Run simulation
            engine = MonteCarloEngine(self._simulation_config)
            output = engine.simulate(causes, base_value)

            return output.to_dict()
        except Exception as e:
            logger.warning(f"Monte Carlo simulation failed: {e}")
            return {}

    def _extract_base_value(self, results: list[dict[str, Any]]) -> float:
        """Extract base growth rate from execution results.

        Looks for growth indicators or computes from company data.
        """
        for r in results:
            result_data = r.get('result', {})
            if not isinstance(result_data, dict):
                continue

            data = result_data.get('data', result_data)
            if not isinstance(data, dict):
                continue

            # Check for explicit growth rate
            if 'growth' in data:
                val = data['growth']
                if isinstance(val, (int, float)):
                    return float(val)

            # Compute from year-over-year
            current = data.get('companies', data.get('count'))
            previous = data.get('companies_last_year', data.get('count_last_year'))
            if current and previous and previous > 0:
                return (current - previous) / previous

        # Default baseline
        return 0.05  # 5% baseline growth

    def _process_rule_based(self, previous: dict[str, Any]) -> dict[str, Any]:
        """Fallback rule-based processing (simple multipliers).

        IMPORTANT: This returns synthetic projections, not real data.
        The result is flagged with data_source='synthetic' for transparency.
        """
        causal = previous.get('causal', {})
        causes = causal.get('causes', [])

        # Check if we have real causal factors
        has_real_causes = len(causes) > 0 and any(
            c.get('source') or c.get('evidence') for c in causes
        )

        # Base growth rate from causes (or conservative default)
        if causes:
            base_rate = sum(c.get('contribution', 0) for c in causes)
        else:
            # No causes = very conservative estimate
            base_rate = 0.02  # 2% baseline, not 10%

        # Flag if this is synthetic data
        if not has_real_causes:
            logger.warning("ScenarioLevel: Using rule-based fallback without real causal data")

        return {
            'optimistic': {
                'growth_rate': base_rate * 1.3,  # Conservative multiplier (was 1.5)
                'probability': 0.2,
                'percentile': 90,
                'key_assumptions': ['Favorable policy', 'Strong investment']
            },
            'median': {
                'growth_rate': base_rate,
                'probability': 0.6,
                'percentile': 50,
                'key_assumptions': ['Current trends continue']
            },
            'pessimistic': {
                'growth_rate': base_rate * 0.7,  # Conservative multiplier (was 0.5)
                'probability': 0.2,
                'percentile': 10,
                'key_assumptions': ['Economic downturn', 'Policy changes']
            },
            'confidence': 0.3 if not has_real_causes else 0.5,  # Lower confidence without data
            'method': 'rule_based',
            'data_source': 'synthetic' if not has_real_causes else 'causal_derived',
            'warning': 'Projections basées sur des hypothèses théoriques, pas sur des données réelles' if not has_real_causes else None,
        }
