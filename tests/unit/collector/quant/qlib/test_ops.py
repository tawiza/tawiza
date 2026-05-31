"""Tests for QLib-adapted alpha expression operators.

This module tests the pure operators in
``src.collector.quant.qlib.ops`` on known input series so that the
results are analytically verifiable:

- Temporal operators: Ref, Mean, Std, Max, Min, Delta, ROC, Slope
- Cross-sectional operators: Rank, CSZScore, CSRank
- Correlation: Corr (two perfectly correlated series -> 1.0)
- Territorial helpers: PerCapita, HealthRatio (incl. division by zero)
- Convenience factors: Momentum, Volatility
- The simplified ``evaluate_expression`` evaluator on a valid and an
  invalid expression (errors are handled gracefully).
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from src.collector.quant.qlib.ops import (
    Corr,
    CSRank,
    CSZScore,
    Delta,
    HealthRatio,
    Max,
    Mean,
    Min,
    Momentum,
    PerCapita,
    Rank,
    Ref,
    ROC,
    Slope,
    Std,
    Volatility,
    evaluate_expression,
)


@pytest.fixture
def linear_series():
    """A simple increasing series [1, 2, 3, 4, 5]."""
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])


class TestRef:
    """Tests for the Ref (lag) operator."""

    def test_ref_shifts_values_back(self, linear_series):
        """Ref(s, 2) should shift values back by two periods."""
        result = Ref(linear_series, 2)

        assert np.isnan(result.iloc[0])
        assert np.isnan(result.iloc[1])
        assert result.iloc[2] == 1.0
        assert result.iloc[3] == 2.0
        assert result.iloc[4] == 3.0

    def test_ref_n_one(self, linear_series):
        """Ref(s, 1) should be the previous value."""
        result = Ref(linear_series, 1)

        assert np.isnan(result.iloc[0])
        assert result.iloc[1] == 1.0
        assert result.iloc[4] == 4.0


class TestMean:
    """Tests for the rolling Mean operator."""

    def test_mean_rolling_window_3(self, linear_series):
        """Mean(s, 3) with min_periods=1 should match manual rolling means."""
        result = Mean(linear_series, 3)

        # min_periods=1: first values use available data only
        assert result.iloc[0] == 1.0  # mean([1])
        assert result.iloc[1] == 1.5  # mean([1, 2])
        assert result.iloc[2] == 2.0  # mean([1, 2, 3])
        assert result.iloc[3] == 3.0  # mean([2, 3, 4])
        assert result.iloc[4] == 4.0  # mean([3, 4, 5])

    def test_mean_window_1_is_identity(self, linear_series):
        """Mean(s, 1) should return the series unchanged."""
        result = Mean(linear_series, 1)

        pd.testing.assert_series_equal(result, linear_series)


class TestStd:
    """Tests for the rolling Std operator."""

    def test_std_window_3(self, linear_series):
        """Std(s, 3) should give the sample std of the trailing window."""
        result = Std(linear_series, 3)

        # First point has a single observation -> NaN (ddof=1)
        assert np.isnan(result.iloc[0])
        # Window [1, 2, 3] -> sample std = 1.0
        assert result.iloc[2] == pytest.approx(1.0)
        # Window [2, 3, 4] and [3, 4, 5] also have std 1.0
        assert result.iloc[3] == pytest.approx(1.0)
        assert result.iloc[4] == pytest.approx(1.0)

    def test_std_constant_series_is_zero(self):
        """Std of a constant window should be zero."""
        s = pd.Series([7.0, 7.0, 7.0, 7.0])
        result = Std(s, 3)

        assert result.iloc[2] == pytest.approx(0.0)
        assert result.iloc[3] == pytest.approx(0.0)


class TestMaxMin:
    """Tests for rolling Max and Min operators."""

    def test_max_window_3(self, linear_series):
        """Max(s, 3) over an increasing series equals the current value."""
        result = Max(linear_series, 3)

        assert result.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_min_window_3(self, linear_series):
        """Min(s, 3) tracks the minimum of the trailing window."""
        result = Min(linear_series, 3)

        assert result.iloc[0] == 1.0  # min([1])
        assert result.iloc[2] == 1.0  # min([1, 2, 3])
        assert result.iloc[3] == 2.0  # min([2, 3, 4])
        assert result.iloc[4] == 3.0  # min([3, 4, 5])


class TestDelta:
    """Tests for the Delta (absolute change) operator."""

    def test_delta_n_2(self, linear_series):
        """Delta(s, 2) = s - Ref(s, 2); constant step series -> 2.0."""
        result = Delta(linear_series, 2)

        assert np.isnan(result.iloc[0])
        assert np.isnan(result.iloc[1])
        assert result.iloc[2] == 2.0
        assert result.iloc[3] == 2.0
        assert result.iloc[4] == 2.0

    def test_delta_n_1(self, linear_series):
        """Delta(s, 1) of a +1 step series should be 1.0 everywhere defined."""
        result = Delta(linear_series, 1)

        assert np.isnan(result.iloc[0])
        assert result.iloc[1:].tolist() == [1.0, 1.0, 1.0, 1.0]


class TestROC:
    """Tests for the ROC (rate of change) operator."""

    def test_roc_n_2(self, linear_series):
        """ROC(s, 2) = (s - Ref(s,2)) / (Ref(s,2) + 1e-6)."""
        result = ROC(linear_series, 2)

        assert np.isnan(result.iloc[0])
        assert np.isnan(result.iloc[1])
        # (3 - 1) / (1 + 1e-6) ~= 2.0
        assert result.iloc[2] == pytest.approx(2.0, abs=1e-4)
        # (4 - 2) / (2 + 1e-6) ~= 1.0
        assert result.iloc[3] == pytest.approx(1.0, abs=1e-4)
        # (5 - 3) / (3 + 1e-6) ~= 0.6667
        assert result.iloc[4] == pytest.approx(2.0 / 3.0, abs=1e-4)

    def test_roc_handles_zero_reference(self):
        """ROC should not raise when the reference value is zero."""
        s = pd.Series([0.0, 5.0])
        result = ROC(s, 1)

        assert np.isnan(result.iloc[0])
        # (5 - 0) / (0 + 1e-6) is large but finite, not an exception
        assert np.isfinite(result.iloc[1])


class TestRank:
    """Tests for the cross-sectional Rank operator."""

    def test_rank_normalized_between_zero_and_one(self):
        """Rank should produce normalized ranks ending at 1.0."""
        s = pd.Series([10.0, 20.0, 30.0, 40.0])
        result = Rank(s)

        assert result.tolist() == [0.25, 0.5, 0.75, 1.0]

    def test_rank_unsorted_input(self):
        """Rank should reflect ordering, not position."""
        s = pd.Series([40.0, 10.0, 30.0, 20.0])
        result = Rank(s)

        # 40 is largest -> 1.0; 10 smallest -> 0.25
        assert result.iloc[0] == 1.0
        assert result.iloc[1] == 0.25
        assert result.iloc[2] == 0.75
        assert result.iloc[3] == 0.5


class TestCorr:
    """Tests for the rolling Corr operator."""

    def test_corr_perfectly_correlated(self):
        """Two linearly dependent series should correlate to 1.0."""
        a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        b = pd.Series([2.0, 4.0, 6.0, 8.0, 10.0])  # b = 2 * a

        result = Corr(a, b, 5)

        # min_periods=2: first value NaN, the rest ~1.0
        assert np.isnan(result.iloc[0])
        for value in result.iloc[1:]:
            assert value == pytest.approx(1.0)

    def test_corr_perfectly_anticorrelated(self):
        """A decreasing mirror series should correlate to -1.0."""
        a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        b = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0])

        result = Corr(a, b, 5)

        assert result.iloc[-1] == pytest.approx(-1.0)


class TestPerCapita:
    """Tests for the PerCapita normalization operator."""

    def test_per_capita_with_population_mapping(self):
        """PerCapita should divide by population and scale by per_n."""
        data = pd.Series([100.0, 200.0], index=["75", "13"])
        population = {"75": 1_000_000, "13": 2_000_000}

        result = PerCapita(data, population=population, per_n=10_000)

        # 100 / 1_000_000 * 10_000 = 1.0
        assert result.loc["75"] == pytest.approx(1.0)
        # 200 / 2_000_000 * 10_000 = 1.0
        assert result.loc["13"] == pytest.approx(1.0)

    def test_per_capita_missing_population_defaults_to_one(self):
        """Unknown territories fall back to a population of 1 (no division by zero)."""
        data = pd.Series([5.0], index=["99"])
        population = {"75": 1_000_000}

        result = PerCapita(data, population=population, per_n=1)

        # 5 / 1 * 1 = 5.0
        assert result.loc["99"] == pytest.approx(5.0)


class TestCSZScore:
    """Tests for the cross-sectional Z-score operator."""

    def test_cszscore_symmetric_series(self):
        """A symmetric series should z-score to [-1, 0, 1] (ddof=1)."""
        s = pd.Series([10.0, 20.0, 30.0])
        result = CSZScore(s)

        assert result.tolist() == [-1.0, 0.0, 1.0]

    def test_cszscore_mean_is_zero(self):
        """The z-scored series should have mean approximately zero."""
        s = pd.Series([5.0, 15.0, 25.0, 35.0])
        result = CSZScore(s)

        assert result.mean() == pytest.approx(0.0, abs=1e-9)


class TestCSRank:
    """Tests for CSRank (alias of Rank)."""

    def test_csrank_matches_rank(self):
        """CSRank should produce identical results to Rank."""
        s = pd.Series([10.0, 20.0, 30.0])

        pd.testing.assert_series_equal(CSRank(s), Rank(s))


class TestSlope:
    """Tests for the rolling Slope operator."""

    def test_slope_of_linear_series_is_one(self, linear_series):
        """A series increasing by 1 each step has a regression slope of 1.0."""
        result = Slope(linear_series, 5)

        # min_periods=2: first point NaN, the rest converge to slope 1.0
        assert np.isnan(result.iloc[0])
        assert result.iloc[-1] == pytest.approx(1.0)

    def test_slope_of_flat_series_is_zero(self):
        """A constant series should have a slope of 0.0."""
        s = pd.Series([3.0, 3.0, 3.0, 3.0])
        result = Slope(s, 4)

        assert result.iloc[-1] == pytest.approx(0.0)


class TestMomentum:
    """Tests for the Momentum convenience factor."""

    def test_momentum_short_over_long(self, linear_series):
        """Momentum should equal short_MA / (long_MA + 1e-6)."""
        result = Momentum(linear_series, short=1, long=3)

        expected = Mean(linear_series, 1) / (Mean(linear_series, 3) + 1e-6)
        pd.testing.assert_series_equal(result, expected)

    def test_momentum_above_one_for_rising_series(self, linear_series):
        """On an increasing series, the short MA exceeds the long MA -> > 1."""
        result = Momentum(linear_series, short=1, long=3)

        # Last point: short MA = 5, long MA = 4 -> ratio > 1
        assert result.iloc[-1] > 1.0


class TestVolatility:
    """Tests for the Volatility convenience factor."""

    def test_volatility_is_std_over_mean(self, linear_series):
        """Volatility should equal Std / (Mean + 1e-6)."""
        result = Volatility(linear_series, 3)

        expected = Std(linear_series, 3) / (Mean(linear_series, 3) + 1e-6)
        pd.testing.assert_series_equal(result, expected)

    def test_volatility_constant_series_is_zero(self):
        """A constant series has zero std, hence zero volatility."""
        s = pd.Series([8.0, 8.0, 8.0, 8.0])
        result = Volatility(s, 3)

        assert result.iloc[2] == pytest.approx(0.0)
        assert result.iloc[3] == pytest.approx(0.0)


class TestHealthRatio:
    """Tests for the HealthRatio operator."""

    def test_health_ratio_basic(self):
        """HealthRatio = liquidations / (creations + 1)."""
        liq = pd.Series([10.0, 0.0, 6.0])
        crea = pd.Series([1.0, 4.0, 2.0])

        result = HealthRatio(liq, crea)

        assert result.iloc[0] == pytest.approx(10.0 / 2.0)  # 5.0
        assert result.iloc[1] == pytest.approx(0.0 / 5.0)  # 0.0
        assert result.iloc[2] == pytest.approx(6.0 / 3.0)  # 2.0

    def test_health_ratio_zero_creations_no_division_error(self):
        """With zero creations the +1 denominator avoids division by zero."""
        liq = pd.Series([10.0])
        crea = pd.Series([0.0])

        result = HealthRatio(liq, crea)

        # 10 / (0 + 1) = 10.0, finite, no exception
        assert result.iloc[0] == pytest.approx(10.0)
        assert np.isfinite(result.iloc[0])


class TestEvaluateExpression:
    """Tests for the simplified expression evaluator."""

    def test_evaluate_valid_mean_expression(self):
        """A valid 'Mean($value, 3)' expression should match Mean()."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0]})

        result = evaluate_expression("Mean($value, 3)", df)
        expected = Mean(df["value"], 3)

        pd.testing.assert_series_equal(result, expected)

    def test_evaluate_arithmetic_expression(self):
        """A division expression with $variables should evaluate elementwise."""
        df = pd.DataFrame(
            {"liquidations": [10.0, 20.0], "creations": [4.0, 9.0]}
        )

        result = evaluate_expression("$liquidations / ($creations + 1)", df)

        assert result.iloc[0] == pytest.approx(10.0 / 5.0)
        assert result.iloc[1] == pytest.approx(20.0 / 10.0)

    def test_evaluate_invalid_expression_returns_nan(self):
        """An invalid expression should be handled and return an all-NaN series."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0]})

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = evaluate_expression("Mean($value, 3", df)  # missing ')'

        assert len(result) == len(df)
        assert result.isna().all()

    def test_evaluate_invalid_expression_emits_warning(self):
        """A failing expression should emit a warning rather than raise."""
        df = pd.DataFrame({"value": [1.0, 2.0, 3.0]})

        with pytest.warns(UserWarning):
            result = evaluate_expression("Mean($value, 3", df)

        assert result.isna().all()
