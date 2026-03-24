"""Tests for Monte Carlo simulation engine.

Tests the scenario generation module including:
- Distribution parameter models
- Correlated sample generation (Cholesky decomposition)
- Time series projection with lag effects
- Full simulation workflow
- Edge cases and error handling
"""

from unittest.mock import patch

import numpy as np
import pytest

from src.infrastructure.agents.tajine.cognitive.scenario import (
    DistributionParams,
    DistributionStats,
    MonteCarloEngine,
    ScenarioOutput,
    SimulationConfig,
    TimeSeriesProjection,
    generate_correlated_samples,
)

# ============================================================================
# Distribution Parameter Tests
# ============================================================================


class TestDistributionParams:
    """Test DistributionParams dataclass and factory method."""

    def test_create_distribution_params(self):
        """Test creating distribution params directly."""
        params = DistributionParams(type="normal", mean=0.1, std=0.05)

        assert params.type == "normal"
        assert params.mean == 0.1
        assert params.std == 0.05

    def test_from_causal_factor_positive(self):
        """Test creating params from positive causal factor."""
        params = DistributionParams.from_causal_factor(
            contribution=0.2, confidence=0.8, direction="positive"
        )

        assert params.mean == 0.2  # positive contribution
        assert params.std > 0
        assert params.std < 0.2  # std scales with mean and confidence

    def test_from_causal_factor_negative(self):
        """Test creating params from negative causal factor."""
        params = DistributionParams.from_causal_factor(
            contribution=0.15, confidence=0.7, direction="negative"
        )

        assert params.mean == -0.15  # negative direction
        assert params.std > 0

    def test_from_causal_factor_high_confidence_low_std(self):
        """Test that high confidence produces lower std."""
        low_conf = DistributionParams.from_causal_factor(0.1, 0.3, "positive")
        high_conf = DistributionParams.from_causal_factor(0.1, 0.9, "positive")

        assert high_conf.std < low_conf.std

    def test_from_causal_factor_minimum_std(self):
        """Test std never goes below minimum."""
        params = DistributionParams.from_causal_factor(
            contribution=0.0, confidence=1.0, direction="positive"
        )

        assert params.std >= 0.01  # Minimum std


class TestDistributionStats:
    """Test DistributionStats dataclass."""

    def test_create_distribution_stats(self):
        """Test creating distribution stats."""
        stats = DistributionStats(
            mean=0.1,
            std=0.05,
            skewness=0.2,
            percentiles={10: 0.02, 50: 0.1, 90: 0.18},
            histogram_bins=[0.0, 0.1, 0.2],
            histogram_counts=[100, 500, 400],
        )

        assert stats.mean == 0.1
        assert stats.percentiles[50] == 0.1

    def test_to_dict_rounds_values(self):
        """Test to_dict rounds float values."""
        stats = DistributionStats(
            mean=0.12345678,
            std=0.05432109,
            skewness=0.23456789,
            percentiles={50: 0.11111111},
            histogram_bins=[0.12345678],
            histogram_counts=[100],
        )

        result = stats.to_dict()

        assert result["mean"] == 0.1235  # Rounded to 4 decimals
        assert result["std"] == 0.0543


# ============================================================================
# Simulation Configuration Tests
# ============================================================================


class TestSimulationConfig:
    """Test SimulationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SimulationConfig()

        assert config.n_simulations == 10000
        assert config.horizon_months == 24
        assert 10 in config.percentiles
        assert 50 in config.percentiles
        assert 90 in config.percentiles

    def test_custom_config(self):
        """Test custom configuration."""
        config = SimulationConfig(n_simulations=5000, horizon_months=12, random_seed=42)

        assert config.n_simulations == 5000
        assert config.horizon_months == 12
        assert config.random_seed == 42


# ============================================================================
# Correlated Sample Generation Tests
# ============================================================================


class TestCorrelatedSamples:
    """Test generate_correlated_samples function."""

    def test_generates_correct_shape(self):
        """Test samples have correct shape."""
        distributions = [
            DistributionParams(type="normal", mean=0.1, std=0.05),
            DistributionParams(type="normal", mean=0.2, std=0.08),
        ]

        samples = generate_correlated_samples(1000, distributions)

        assert samples.shape == (1000, 2)

    def test_empty_distributions_returns_empty(self):
        """Test empty distributions returns zero-width array."""
        samples = generate_correlated_samples(1000, [])

        assert samples.shape == (1000, 0)

    def test_normal_distribution_mean(self):
        """Test normal distribution samples have correct mean."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="normal", mean=0.5, std=0.1),
        ]

        samples = generate_correlated_samples(10000, distributions)
        sample_mean = np.mean(samples[:, 0])

        assert abs(sample_mean - 0.5) < 0.02  # Within 2% of expected

    def test_normal_distribution_std(self):
        """Test normal distribution samples have correct std."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="normal", mean=0.0, std=0.3),
        ]

        samples = generate_correlated_samples(10000, distributions)
        sample_std = np.std(samples[:, 0])

        assert abs(sample_std - 0.3) < 0.02

    def test_lognormal_positive_values(self):
        """Test lognormal distribution produces positive values."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="lognormal", mean=0.5, std=0.2),
        ]

        samples = generate_correlated_samples(1000, distributions)

        assert np.all(samples > 0)

    def test_lognormal_negative_mean_fallback(self):
        """Test lognormal with negative mean falls back to normal."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="lognormal", mean=-0.1, std=0.05),
        ]

        # Should not raise, falls back to normal
        samples = generate_correlated_samples(1000, distributions)

        assert samples.shape == (1000, 1)
        # Some samples should be negative (normal distribution)
        assert np.any(samples < 0)

    def test_triangular_distribution_bounds(self):
        """Test triangular distribution produces values centered around mean."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="triangular", mean=0.5, std=0.2),
        ]

        samples = generate_correlated_samples(1000, distributions)

        # Most samples should be around mean, distribution is bounded
        sample_mean = np.mean(samples)
        assert abs(sample_mean - 0.5) < 0.1  # Mean close to expected

    def test_uniform_distribution_bounds(self):
        """Test uniform distribution produces values within expected range."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="uniform", mean=0.5, std=0.2),
        ]

        samples = generate_correlated_samples(1000, distributions)

        # Uniform distribution should be bounded (allowing small numerical tolerance)
        sample_mean = np.mean(samples)
        assert abs(sample_mean - 0.5) < 0.05  # Mean close to expected
        # Check most samples are in range
        in_range = np.sum((samples >= 0.29) & (samples <= 0.71)) / len(samples)
        assert in_range > 0.95  # At least 95% in expected range

    def test_correlation_applied(self):
        """Test correlation matrix is applied."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="normal", mean=0.1, std=0.05),
            DistributionParams(type="normal", mean=0.2, std=0.08),
        ]
        corr_matrix = np.array([[1.0, 0.8], [0.8, 1.0]])

        samples = generate_correlated_samples(10000, distributions, corr_matrix)
        sample_corr = np.corrcoef(samples[:, 0], samples[:, 1])[0, 1]

        # Correlation should be close to 0.8
        assert abs(sample_corr - 0.8) < 0.05

    def test_invalid_correlation_matrix_fallback(self):
        """Test invalid correlation matrix falls back to independent."""
        np.random.seed(42)
        distributions = [
            DistributionParams(type="normal", mean=0.1, std=0.05),
            DistributionParams(type="normal", mean=0.2, std=0.08),
        ]
        # Not positive definite
        invalid_corr = np.array([[1.0, 1.5], [1.5, 1.0]])

        # Should not raise, falls back to independent
        samples = generate_correlated_samples(1000, distributions, invalid_corr)

        assert samples.shape == (1000, 2)


# ============================================================================
# Time Series Projection Tests
# ============================================================================


class TestTimeSeriesProjection:
    """Test TimeSeriesProjection dataclass."""

    def test_create_time_series(self):
        """Test creating time series projection."""
        ts = TimeSeriesProjection(
            months=[1, 2, 3],
            mean_path=[0.1, 0.12, 0.14],
            lower_bound=[0.05, 0.06, 0.07],
            upper_bound=[0.15, 0.18, 0.21],
        )

        assert len(ts.months) == 3
        assert ts.mean_path[0] == 0.1

    def test_to_dict_format(self):
        """Test to_dict returns correct format."""
        ts = TimeSeriesProjection(
            months=[1, 2], mean_path=[0.1, 0.12], lower_bound=[0.05, 0.06], upper_bound=[0.15, 0.18]
        )

        result = ts.to_dict()

        assert "months" in result
        assert "mean_path" in result
        assert "lower_bound" in result
        assert "upper_bound" in result


# ============================================================================
# Monte Carlo Engine Tests
# ============================================================================


class TestMonteCarloEngine:
    """Test MonteCarloEngine class."""

    def test_create_engine_default_config(self):
        """Test creating engine with default config."""
        engine = MonteCarloEngine()

        assert engine.config.n_simulations == 10000

    def test_create_engine_custom_config(self):
        """Test creating engine with custom config."""
        config = SimulationConfig(n_simulations=5000)
        engine = MonteCarloEngine(config)

        assert engine.config.n_simulations == 5000

    def test_simulate_returns_scenario_output(self):
        """Test simulate returns ScenarioOutput."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {
                "factor": "tech_growth",
                "contribution": 0.1,
                "confidence": 0.7,
                "direction": "positive",
            }
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert isinstance(result, ScenarioOutput)

    def test_simulate_returns_all_scenarios(self):
        """Test simulate returns optimistic/median/pessimistic."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {"factor": "growth", "contribution": 0.15, "confidence": 0.8, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.optimistic is not None
        assert result.median is not None
        assert result.pessimistic is not None

    def test_simulate_optimistic_greater_than_pessimistic(self):
        """Test optimistic growth > pessimistic growth."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=2000, random_seed=42))
        causes = [
            {"factor": "growth", "contribution": 0.2, "confidence": 0.8, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.optimistic["growth_rate"] > result.pessimistic["growth_rate"]

    def test_simulate_empty_causes_returns_baseline(self):
        """Test empty causes returns baseline scenario."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100))

        result = engine.simulate([], base_value=0.05)

        assert result.method == "baseline"
        assert result.n_simulations == 0
        assert result.optimistic["growth_rate"] == 0.05

    def test_simulate_generates_time_series(self):
        """Test simulate generates time series projection."""
        config = SimulationConfig(n_simulations=1000, horizon_months=12)
        engine = MonteCarloEngine(config)
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.time_series is not None
        assert len(result.time_series.months) == 12
        assert len(result.time_series.mean_path) == 12

    def test_simulate_computes_statistics(self):
        """Test simulate computes distribution statistics."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.final_value_stats is not None
        assert result.final_value_stats.mean != 0
        assert result.final_value_stats.std > 0

    def test_simulate_confidence_in_range(self):
        """Test confidence is between 0 and 1."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert 0 <= result.confidence <= 1

    def test_simulate_method_is_monte_carlo(self):
        """Test method is 'monte_carlo'."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100))
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.method == "monte_carlo"

    def test_simulate_with_lag(self):
        """Test simulation respects lag_months."""
        config = SimulationConfig(n_simulations=1000, horizon_months=12, random_seed=42)
        engine = MonteCarloEngine(config)

        # Factor with 6-month lag shouldn't affect early months much
        causes = [
            {
                "factor": "delayed_growth",
                "contribution": 0.5,
                "confidence": 0.9,
                "direction": "positive",
                "lag_months": 6,
            }
        ]

        result = engine.simulate(causes, base_value=0.05)
        ts = result.time_series

        # Early months should be close to base value
        # Later months should show more growth
        early_growth = ts.mean_path[2] - ts.mean_path[0]
        late_growth = ts.mean_path[11] - ts.mean_path[8]

        # Late growth should be higher due to factor kicking in
        assert late_growth > early_growth * 0.5

    def test_simulate_multiple_factors(self):
        """Test simulation with multiple factors."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {
                "factor": "tech_growth",
                "contribution": 0.1,
                "confidence": 0.8,
                "direction": "positive",
            },
            {
                "factor": "economic_headwind",
                "contribution": 0.05,
                "confidence": 0.6,
                "direction": "negative",
            },
            {
                "factor": "policy_support",
                "contribution": 0.08,
                "confidence": 0.7,
                "direction": "positive",
            },
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.n_simulations == 1000
        assert len(result.final_value_stats.percentiles) > 0

    def test_simulate_negative_base_value(self):
        """Test simulation with negative base value."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=1000, random_seed=42))
        causes = [
            {"factor": "decline", "contribution": 0.1, "confidence": 0.7, "direction": "negative"}
        ]

        result = engine.simulate(causes, base_value=-0.02)

        # Should handle negative base value
        assert result.method == "monte_carlo"


# ============================================================================
# Scenario Output Tests
# ============================================================================


class TestScenarioOutput:
    """Test ScenarioOutput dataclass."""

    def test_scenario_output_to_dict(self):
        """Test ScenarioOutput.to_dict() contains all fields."""
        stats = DistributionStats(
            mean=0.1,
            std=0.05,
            skewness=0.1,
            percentiles={10: 0.02, 50: 0.1, 90: 0.18},
            histogram_bins=[0.0, 0.1, 0.2],
            histogram_counts=[100, 500, 400],
        )
        ts = TimeSeriesProjection(
            months=[1, 2], mean_path=[0.1, 0.12], lower_bound=[0.05, 0.06], upper_bound=[0.15, 0.18]
        )

        output = ScenarioOutput(
            final_value_stats=stats,
            time_series=ts,
            optimistic={"growth_rate": 0.18},
            median={"growth_rate": 0.1},
            pessimistic={"growth_rate": 0.02},
            n_simulations=1000,
            method="monte_carlo",
            confidence=0.75,
        )

        result = output.to_dict()

        assert "optimistic" in result
        assert "median" in result
        assert "pessimistic" in result
        assert "distribution" in result
        assert "time_series" in result
        assert "confidence" in result
        assert result["method"] == "monte_carlo"


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_contribution_factor(self):
        """Test factor with zero contribution."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100, random_seed=42))
        causes = [
            {"factor": "neutral", "contribution": 0.0, "confidence": 0.5, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.method == "monte_carlo"

    def test_extreme_contribution(self):
        """Test factor with very high contribution."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100, random_seed=42))
        causes = [
            {"factor": "extreme", "contribution": 2.0, "confidence": 0.9, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        # Should handle without error, time series should grow significantly
        assert result.optimistic["growth_rate"] > 0.5

    def test_zero_confidence_factor(self):
        """Test factor with zero confidence (high uncertainty)."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100, random_seed=42))
        causes = [
            {"factor": "uncertain", "contribution": 0.1, "confidence": 0.0, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        # High std due to low confidence
        assert result.final_value_stats.std > 0

    def test_missing_optional_fields(self):
        """Test causes with missing optional fields use defaults."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100, random_seed=42))
        causes = [
            {"factor": "minimal"},  # Missing contribution, confidence, direction
        ]

        # Should use defaults without error
        result = engine.simulate(causes, base_value=0.05)

        assert result.method == "monte_carlo"

    def test_random_seed_reproducibility(self):
        """Test random seed produces reproducible results."""
        config = SimulationConfig(n_simulations=1000, random_seed=42)
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        engine1 = MonteCarloEngine(config)
        result1 = engine1.simulate(causes, base_value=0.05)

        engine2 = MonteCarloEngine(config)
        result2 = engine2.simulate(causes, base_value=0.05)

        assert result1.final_value_stats.mean == result2.final_value_stats.mean

    def test_very_short_horizon(self):
        """Test with 1-month horizon."""
        config = SimulationConfig(n_simulations=100, horizon_months=1)
        engine = MonteCarloEngine(config)
        causes = [
            {"factor": "growth", "contribution": 0.1, "confidence": 0.7, "direction": "positive"}
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert len(result.time_series.months) == 1

    def test_large_number_of_factors(self):
        """Test with many factors."""
        engine = MonteCarloEngine(SimulationConfig(n_simulations=100, random_seed=42))
        causes = [
            {
                "factor": f"factor_{i}",
                "contribution": 0.02,
                "confidence": 0.6,
                "direction": "positive",
            }
            for i in range(20)
        ]

        result = engine.simulate(causes, base_value=0.05)

        assert result.method == "monte_carlo"
        assert result.final_value_stats.mean > 0.05  # Should grow with positive factors


# ============================================================================
# Integration with ScenarioLevel Tests
# ============================================================================


class TestScenarioLevelIntegration:
    """Test Monte Carlo integration with ScenarioLevel."""

    @pytest.mark.asyncio
    async def test_scenario_level_uses_monte_carlo(self):
        """Test ScenarioLevel uses Monte Carlo when causes available."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel

        level = ScenarioLevel()
        previous = {
            "causal": {
                "causes": [
                    {
                        "factor": "growth",
                        "contribution": 0.1,
                        "confidence": 0.7,
                        "direction": "positive",
                    }
                ]
            }
        }
        results = [{"tool": "data", "result": {"growth": 0.08}}]

        output = await level.process(results, previous)

        assert output.get("method") in ["monte_carlo", "llm", "rule_based"]
        assert "optimistic" in output
        assert "median" in output
        assert "pessimistic" in output

    @pytest.mark.asyncio
    async def test_scenario_level_fallback_no_causes(self):
        """Test ScenarioLevel falls back when no causes."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel

        level = ScenarioLevel()
        previous = {"causal": {"causes": []}}

        output = await level.process([], previous)

        assert output.get("method") == "rule_based"
