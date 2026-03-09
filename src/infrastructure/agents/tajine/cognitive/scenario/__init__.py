"""
Scenario generation module with Monte Carlo simulation.

Provides probabilistic scenario projections using:
- Correlated factor sampling (Cholesky decomposition)
- Time series projection with lag effects
- Full distribution statistics (mean, std, skew, percentiles)
"""

from src.infrastructure.agents.tajine.cognitive.scenario.models import (
    DistributionParams,
    DistributionStats,
    ScenarioOutput,
    SimulationConfig,
    TimeSeriesProjection,
)
from src.infrastructure.agents.tajine.cognitive.scenario.monte_carlo import (
    MonteCarloEngine,
    generate_correlated_samples,
)

__all__ = [
    # Models
    "DistributionParams",
    "DistributionStats",
    "ScenarioOutput",
    "SimulationConfig",
    "TimeSeriesProjection",
    # Engine
    "MonteCarloEngine",
    "generate_correlated_samples",
]
