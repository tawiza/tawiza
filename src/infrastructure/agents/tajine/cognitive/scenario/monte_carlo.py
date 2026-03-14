"""
Monte Carlo simulation engine for scenario generation.

Uses numpy for vectorized operations to achieve <1s for 10K simulations.
"""

from typing import Any

import numpy as np
from loguru import logger
from scipy import special

from src.infrastructure.agents.tajine.cognitive.scenario.models import (
    DistributionParams,
    DistributionStats,
    ScenarioOutput,
    SimulationConfig,
    TimeSeriesProjection,
)


def generate_correlated_samples(
    n_samples: int,
    distributions: list[DistributionParams],
    correlation_matrix: np.ndarray | None = None,
) -> np.ndarray:
    """Generate correlated samples using Cholesky decomposition.

    Args:
        n_samples: Number of samples to generate
        distributions: List of distribution parameters
        correlation_matrix: Correlation matrix (identity if None)

    Returns:
        Array of shape (n_samples, n_factors) with correlated samples
    """
    n_factors = len(distributions)
    if n_factors == 0:
        return np.zeros((n_samples, 0))

    # Generate independent standard normal samples
    z = np.random.standard_normal((n_samples, n_factors))

    # Apply correlation if provided
    if correlation_matrix is not None and n_factors > 1:
        try:
            # Cholesky decomposition: L @ L.T = correlation_matrix
            L = np.linalg.cholesky(correlation_matrix)
            z = z @ L.T
        except np.linalg.LinAlgError:
            logger.warning("Correlation matrix not positive definite, using independent samples")

    # Transform to target distributions
    samples = np.zeros((n_samples, n_factors))
    for i, dist in enumerate(distributions):
        samples[:, i] = _transform_to_distribution(z[:, i], dist)

    return samples


def _transform_to_distribution(z: np.ndarray, dist: DistributionParams) -> np.ndarray:
    """Transform standard normal samples to target distribution.

    Args:
        z: Standard normal samples
        dist: Target distribution parameters

    Returns:
        Transformed samples
    """
    if dist.type == "normal":
        return dist.mean + dist.std * z

    elif dist.type == "lognormal":
        # Lognormal: exp(normal) - only valid for positive means
        if dist.mean <= 0:
            logger.debug("Lognormal invalid for non-positive mean, using normal")
            return dist.mean + dist.std * z
        # Adjust parameters so E[X] = mean, Var[X] matches std
        sigma = np.sqrt(np.log(1 + (dist.std / dist.mean) ** 2))
        mu = np.log(dist.mean) - sigma**2 / 2
        return np.exp(mu + sigma * z)

    elif dist.type == "triangular":
        # Map normal to uniform [0,1] via CDF, then to triangular
        u = _normal_cdf(z)
        left = dist.mean - dist.std
        mode = dist.mean
        right = dist.mean + dist.std
        return _triangular_ppf(u, left, mode, right)

    elif dist.type == "uniform":
        # Map normal to uniform [mean-std, mean+std]
        u = _normal_cdf(z)
        low = dist.mean - dist.std
        high = dist.mean + dist.std
        return low + (high - low) * u

    else:
        # Default to normal
        return dist.mean + dist.std * z


def _normal_cdf(z: np.ndarray) -> np.ndarray:
    """Standard normal CDF."""
    return 0.5 * (1 + special.erf(z / np.sqrt(2)))


def _triangular_ppf(u: np.ndarray, left: float, mode: float, right: float) -> np.ndarray:
    """Triangular distribution inverse CDF (percent point function)."""
    fc = (mode - left) / (right - left) if right != left else 0.5
    result = np.where(
        u < fc,
        left + np.sqrt(u * (right - left) * (mode - left)),
        right - np.sqrt((1 - u) * (right - left) * (right - mode)),
    )
    return result


class MonteCarloEngine:
    """Monte Carlo simulation engine for scenario generation.

    Simulates future outcomes by:
    1. Sampling from factor distributions (optionally correlated)
    2. Projecting over time with lag effects
    3. Computing statistics and percentile scenarios
    """

    def __init__(self, config: SimulationConfig | None = None):
        """Initialize engine with configuration.

        Args:
            config: Simulation configuration (uses defaults if None)
        """
        self.config = config or SimulationConfig()
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

    def simulate(self, causes: list[dict[str, Any]], base_value: float = 0.0) -> ScenarioOutput:
        """Run Monte Carlo simulation from causal factors.

        Args:
            causes: List of causal factors from CausalLevel output
                   Each with: factor, contribution, direction, confidence, lag_months
            base_value: Starting value for projections

        Returns:
            ScenarioOutput with full distribution and scenarios
        """
        n_sim = self.config.n_simulations
        horizon = self.config.horizon_months

        logger.info(f"Running Monte Carlo: {n_sim} simulations, {horizon} months")

        # Convert causes to distributions
        distributions = []
        lags = []
        for cause in causes:
            dist = DistributionParams.from_causal_factor(
                contribution=cause.get("contribution", 0.1),
                confidence=cause.get("confidence", 0.5),
                direction=cause.get("direction", "positive"),
            )
            distributions.append(dist)
            lags.append(cause.get("lag_months", 0))

        if not distributions:
            # No causes - return baseline scenario
            return self._baseline_scenario(base_value)

        # Generate correlated samples
        correlation_matrix = self._build_correlation_matrix(causes)
        factor_samples = generate_correlated_samples(n_sim, distributions, correlation_matrix)

        # Project time series with lag effects
        paths = self._project_time_series(factor_samples, lags, horizon, base_value)

        # Compute statistics on final values
        final_values = paths[:, -1]
        final_stats = self._compute_statistics(final_values)

        # Build time series projection (mean and percentile bands)
        time_series = self._build_time_series_projection(paths)

        # Build scenario summaries for backward compatibility
        optimistic = self._build_scenario(90, final_stats, causes)
        median = self._build_scenario(50, final_stats, causes)
        pessimistic = self._build_scenario(10, final_stats, causes)

        # Compute confidence based on sample size and convergence
        confidence = self._compute_confidence(final_stats)

        return ScenarioOutput(
            final_value_stats=final_stats,
            time_series=time_series,
            optimistic=optimistic,
            median=median,
            pessimistic=pessimistic,
            n_simulations=n_sim,
            method="monte_carlo",
            confidence=confidence,
        )

    def _build_correlation_matrix(self, causes: list[dict[str, Any]]) -> np.ndarray | None:
        """Build correlation matrix from causal factors.

        Uses simple heuristic: factors from same source are correlated.
        """
        if not self.config.use_correlation:
            return None

        n = len(causes)
        if n <= 1:
            return None

        # Simple correlation structure based on evidence similarity
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                # Same evidence source = higher correlation
                ev_i = causes[i].get("evidence", "")
                ev_j = causes[j].get("evidence", "")
                if ev_i and ev_j and ev_i == ev_j:
                    corr[i, j] = corr[j, i] = 0.5
                else:
                    corr[i, j] = corr[j, i] = 0.2  # Default weak correlation

        return corr

    def _project_time_series(
        self, factor_samples: np.ndarray, lags: list[int], horizon: int, base_value: float
    ) -> np.ndarray:
        """Project factor effects over time with lag ramp-up.

        Uses sigmoid ramp to model gradual effect onset after lag period.

        Args:
            factor_samples: (n_sim, n_factors) sampled factor effects
            lags: Lag months for each factor
            horizon: Projection horizon in months
            base_value: Starting value

        Returns:
            (n_sim, horizon) time series paths
        """
        n_sim, n_factors = factor_samples.shape
        paths = np.zeros((n_sim, horizon))

        # Initialize with base value
        paths[:, 0] = base_value

        # Precompute effect weights over time for each factor
        # Effect ramps up using sigmoid after lag period
        time_weights = np.zeros((n_factors, horizon))
        for i, lag in enumerate(lags):
            # Use minimum ramp period of 3 months to avoid division issues
            ramp_period = max(lag, 3)
            for t in range(horizon):
                if t < lag:
                    # Before lag: no effect
                    time_weights[i, t] = 0.0
                else:
                    # After lag: sigmoid ramp to full effect over ramp_period
                    x = (t - lag) / ramp_period
                    time_weights[i, t] = 1 / (1 + np.exp(-4 * (x - 0.5)))

        # Accumulate effects over time
        for t in range(1, horizon):
            # Monthly increment = sum of weighted factor effects
            monthly_effect = np.zeros(n_sim)
            for i in range(n_factors):
                monthly_effect += factor_samples[:, i] * time_weights[i, t]

            # Compound the effect (multiplicative growth model)
            growth_factor = 1 + monthly_effect / 12  # Annualized to monthly
            # Clip to prevent negative or zero values
            growth_factor = np.maximum(growth_factor, 0.01)
            paths[:, t] = paths[:, t - 1] * growth_factor

        return paths

    def _compute_statistics(self, values: np.ndarray) -> DistributionStats:
        """Compute distribution statistics from simulated values."""
        mean = float(np.mean(values))
        std = float(np.std(values))

        # Skewness: (E[(X-mu)^3]) / sigma^3
        skewness = float(np.mean(((values - mean) / std) ** 3)) if std > 0 else 0.0

        # Percentiles
        percentiles = {p: float(np.percentile(values, p)) for p in self.config.percentiles}

        # Histogram (30 bins for visualization)
        counts, bins = np.histogram(values, bins=30)
        histogram_bins = bins[:-1].tolist()  # Left edges
        histogram_counts = counts.tolist()

        return DistributionStats(
            mean=mean,
            std=std,
            skewness=skewness,
            percentiles=percentiles,
            histogram_bins=histogram_bins,
            histogram_counts=histogram_counts,
        )

    def _build_time_series_projection(self, paths: np.ndarray) -> TimeSeriesProjection:
        """Build time series projection from simulation paths."""
        horizon = paths.shape[1]

        mean_path = np.mean(paths, axis=0).tolist()
        lower_bound = np.percentile(paths, 10, axis=0).tolist()
        upper_bound = np.percentile(paths, 90, axis=0).tolist()

        return TimeSeriesProjection(
            months=list(range(1, horizon + 1)),
            mean_path=mean_path,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    def _build_scenario(
        self, percentile: int, stats: DistributionStats, causes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build scenario dict for backward compatibility."""
        value = stats.percentiles.get(percentile, stats.mean)

        # Map percentile to probability and assumptions
        if percentile >= 75:
            probability = 0.2
            assumptions = ["Favorable conditions", "Strong market response"]
        elif percentile <= 25:
            probability = 0.2
            assumptions = ["Adverse conditions", "Market challenges"]
        else:
            probability = 0.6
            assumptions = ["Current trends continue"]

        return {
            "growth_rate": value,
            "probability": probability,
            "percentile": percentile,
            "key_assumptions": assumptions,
            "contributing_factors": [c.get("factor", "unknown") for c in causes],
        }

    def _compute_confidence(self, stats: DistributionStats) -> float:
        """Compute confidence based on simulation quality.

        Higher confidence when:
        - Distribution is well-behaved (low skewness)
        - Percentiles are stable (narrow relative to mean)
        """
        # Skewness penalty: extreme skew reduces confidence
        skew_factor = 1 / (1 + abs(stats.skewness) / 2)

        # Stability: ratio of IQR to median
        p25 = stats.percentiles.get(25, stats.mean)
        p75 = stats.percentiles.get(75, stats.mean)
        p50 = stats.percentiles.get(50, stats.mean)

        if p50 != 0:
            iqr_ratio = (p75 - p25) / abs(p50)
            stability_factor = 1 / (1 + iqr_ratio)
        else:
            stability_factor = 0.5

        # Combined confidence
        confidence = 0.5 + 0.3 * skew_factor + 0.2 * stability_factor
        return round(min(confidence, 0.95), 2)

    def _baseline_scenario(self, base_value: float) -> ScenarioOutput:
        """Return baseline scenario when no causes provided."""
        stats = DistributionStats(
            mean=base_value,
            std=0.0,
            skewness=0.0,
            percentiles=dict.fromkeys(self.config.percentiles, base_value),
            histogram_bins=[base_value],
            histogram_counts=[self.config.n_simulations],
        )

        ts = TimeSeriesProjection(
            months=list(range(1, self.config.horizon_months + 1)),
            mean_path=[base_value] * self.config.horizon_months,
            lower_bound=[base_value] * self.config.horizon_months,
            upper_bound=[base_value] * self.config.horizon_months,
        )

        scenario_base = {
            "growth_rate": base_value,
            "probability": 1.0,
            "percentile": 50,
            "key_assumptions": ["No causal factors identified"],
            "contributing_factors": [],
        }

        return ScenarioOutput(
            final_value_stats=stats,
            time_series=ts,
            optimistic=scenario_base,
            median=scenario_base,
            pessimistic=scenario_base,
            n_simulations=0,
            method="baseline",
            confidence=0.3,
        )
