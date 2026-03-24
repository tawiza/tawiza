"""
Monte Carlo simulation data models.

Dataclasses for scenario generation with probabilistic projections.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

DistributionType = Literal["normal", "lognormal", "triangular", "uniform"]


@dataclass
class DistributionParams:
    """Parameters for a probability distribution."""

    type: DistributionType = "normal"
    mean: float = 0.0
    std: float = 1.0
    # For triangular: left=mean-std, mode=mean, right=mean+std
    # For uniform: low=mean-std, high=mean+std

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "mean": self.mean, "std": self.std}

    @classmethod
    def from_causal_factor(
        cls, contribution: float, confidence: float, direction: str = "positive"
    ) -> "DistributionParams":
        """Create distribution from causal factor.

        Args:
            contribution: Factor contribution (0-1), becomes mean
            confidence: Factor confidence (0-1), inversely affects std
            direction: "positive" or "negative"

        Returns:
            DistributionParams with appropriate mean and std
        """
        # Direction affects sign
        sign = 1.0 if direction == "positive" else -1.0
        mean = contribution * sign

        # Higher confidence = narrower distribution (lower std)
        # At confidence=1.0: std=0.1*mean, at confidence=0.5: std=0.5*mean
        base_std = abs(mean) * 0.3 if mean != 0 else 0.1
        std = base_std * (1.5 - confidence)

        return cls(type="normal", mean=mean, std=max(std, 0.01))


@dataclass
class SimulationConfig:
    """Configuration for Monte Carlo simulation."""

    n_simulations: int = 10000
    horizon_months: int = 24
    random_seed: int | None = None
    use_correlation: bool = True
    percentiles: list[float] = field(default_factory=lambda: [10, 25, 50, 75, 90])

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_simulations": self.n_simulations,
            "horizon_months": self.horizon_months,
            "random_seed": self.random_seed,
            "use_correlation": self.use_correlation,
            "percentiles": self.percentiles,
        }


@dataclass
class DistributionStats:
    """Statistical summary of a simulation output."""

    mean: float
    std: float
    skewness: float
    percentiles: dict[float, float]  # {10: value, 25: value, ...}
    histogram_bins: list[float] = field(default_factory=list)
    histogram_counts: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "skewness": round(self.skewness, 4),
            "percentiles": {k: round(v, 4) for k, v in self.percentiles.items()},
            "histogram_bins": [round(b, 4) for b in self.histogram_bins],
            "histogram_counts": self.histogram_counts,
        }


@dataclass
class TimeSeriesProjection:
    """Projected time series with uncertainty bands."""

    months: list[int]  # [1, 2, 3, ..., horizon]
    mean_path: list[float]  # Mean trajectory
    lower_bound: list[float]  # e.g., 10th percentile
    upper_bound: list[float]  # e.g., 90th percentile

    def to_dict(self) -> dict[str, Any]:
        return {
            "months": self.months,
            "mean_path": [round(v, 4) for v in self.mean_path],
            "lower_bound": [round(v, 4) for v in self.lower_bound],
            "upper_bound": [round(v, 4) for v in self.upper_bound],
        }


@dataclass
class ScenarioOutput:
    """Complete Monte Carlo scenario output."""

    # Final value distributions
    final_value_stats: DistributionStats

    # Time series projection
    time_series: TimeSeriesProjection

    # Scenario summaries (compatible with existing format)
    optimistic: dict[str, Any]  # 90th percentile scenario
    median: dict[str, Any]  # 50th percentile scenario
    pessimistic: dict[str, Any]  # 10th percentile scenario

    # Metadata
    n_simulations: int
    method: str = "monte_carlo"
    confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimistic": self.optimistic,
            "median": self.median,
            "pessimistic": self.pessimistic,
            "distribution": self.final_value_stats.to_dict(),
            "time_series": self.time_series.to_dict(),
            "n_simulations": self.n_simulations,
            "method": self.method,
            "confidence": self.confidence,
        }
