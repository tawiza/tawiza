"""Tests for QLib-adapted data processors.

This module tests the chainable data transformers used for territorial
intelligence time series, covering each Processor implementation, the
ProcessorChain composition, the convenience factory functions, and a set
of edge cases (empty DataFrame, constant column, all-NaN column).

Asserted behaviors were validated against the real implementation in
``src/collector/quant/qlib/processor.py`` (the code is the source of truth):
- ZScore (global) yields mean ~0 and population/sample std ~1
- MinMax maps values into the [0, 1] range
- Dropna removes rows containing NaN
- Fillna replaces NaN with the configured value / method
- A constant column (std == 0 / mad == 0) collapses to 0
- An all-NaN column collapses to 0 (NaN > 0 is False)
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from src.collector.quant.qlib.processor import (
    DropnaProcessor,
    FillnaProcessor,
    MinMaxProcessor,
    PopulationNormalizer,
    Processor,
    ProcessorChain,
    RobustZScoreProcessor,
    SeasonalDecompProcessor,
    ZScoreProcessor,
    create_inference_chain,
    create_standard_chain,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def simple_df():
    """Small clean DataFrame with a known linear distribution."""
    return pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})


@pytest.fixture
def df_with_nan():
    """DataFrame containing NaN values across two columns."""
    return pd.DataFrame(
        {
            "a": [1.0, np.nan, 3.0, np.nan, 5.0],
            "b": [10.0, 20.0, np.nan, 40.0, 50.0],
        }
    )


@pytest.fixture
def df_with_outlier():
    """DataFrame with a clear outlier for robust statistics testing."""
    return pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 100.0]})


@pytest.fixture
def constant_df():
    """DataFrame with a single constant column (std == 0)."""
    return pd.DataFrame({"a": [5.0, 5.0, 5.0]})


@pytest.fixture
def all_nan_df():
    """DataFrame whose only column is entirely NaN."""
    return pd.DataFrame({"a": [np.nan, np.nan, np.nan]})


@pytest.fixture
def empty_df():
    """Empty (zero-row) DataFrame with a float column."""
    return pd.DataFrame({"a": pd.Series([], dtype=float)})


# ═══════════════════════════════════════════════════════════════════════════════
# DropnaProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestDropnaProcessor:
    """Tests for DropnaProcessor."""

    def test_is_processor_subclass(self):
        """DropnaProcessor should be a Processor."""
        assert issubclass(DropnaProcessor, Processor)

    def test_fit_returns_self(self, df_with_nan):
        """fit() should return the processor instance."""
        proc = DropnaProcessor()
        assert proc.fit(df_with_nan) is proc

    def test_drops_rows_with_any_nan(self, df_with_nan):
        """Without fields, rows with any NaN should be removed."""
        result = DropnaProcessor().transform(df_with_nan)

        # Only rows 0 and 4 have no NaN in any column.
        assert len(result) == 2
        assert result["a"].isna().sum() == 0
        assert result["b"].isna().sum() == 0

    def test_drops_only_on_specified_fields(self, df_with_nan):
        """With fields, only NaN in those fields trigger a drop."""
        result = DropnaProcessor(fields=["a"]).transform(df_with_nan)

        # Column 'a' has NaN at rows 1 and 3 -> 3 rows remain.
        assert len(result) == 3
        assert result["a"].isna().sum() == 0

    def test_missing_field_falls_back_to_full_dropna(self, df_with_nan):
        """A field not present falls back to dropping any-NaN rows."""
        result = DropnaProcessor(fields=["does_not_exist"]).transform(df_with_nan)

        assert len(result) == 2

    def test_no_nan_keeps_all_rows(self, simple_df):
        """A clean DataFrame should be returned unchanged in length."""
        result = DropnaProcessor().transform(simple_df)

        assert len(result) == len(simple_df)

    def test_fit_transform(self, df_with_nan):
        """fit_transform should behave like fit then transform."""
        result = DropnaProcessor().fit_transform(df_with_nan)

        assert len(result) == 2

    def test_callable_interface(self, df_with_nan):
        """A processor should be callable and equivalent to transform."""
        proc = DropnaProcessor()
        assert len(proc(df_with_nan)) == len(proc.transform(df_with_nan))


# ═══════════════════════════════════════════════════════════════════════════════
# FillnaProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestFillnaProcessor:
    """Tests for FillnaProcessor."""

    def test_fill_with_value(self, df_with_nan):
        """Default 'value' method should fill NaN with fill_value."""
        result = FillnaProcessor(fill_value=99).transform(df_with_nan)

        assert result["a"].isna().sum() == 0
        assert result["b"].isna().sum() == 0
        assert result.loc[1, "a"] == 99
        assert result.loc[2, "b"] == 99

    def test_fill_with_zero_default(self, df_with_nan):
        """Default fill_value is 0."""
        result = FillnaProcessor().transform(df_with_nan)

        assert result.loc[1, "a"] == 0
        assert result.loc[3, "a"] == 0

    def test_fill_does_not_alter_present_values(self, df_with_nan):
        """Existing (non-NaN) values must be preserved."""
        result = FillnaProcessor(fill_value=0).transform(df_with_nan)

        assert result.loc[0, "a"] == 1.0
        assert result.loc[4, "a"] == 5.0

    def test_ffill_method(self):
        """'ffill' should forward-fill NaN values."""
        df = pd.DataFrame({"a": [1.0, np.nan, np.nan, 4.0]})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            result = FillnaProcessor(method="ffill").transform(df)

        assert result["a"].tolist() == [1.0, 1.0, 1.0, 4.0]

    def test_bfill_method(self):
        """'bfill' should backward-fill NaN values."""
        df = pd.DataFrame({"a": [1.0, np.nan, np.nan, 4.0]})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            result = FillnaProcessor(method="bfill").transform(df)

        assert result["a"].tolist() == [1.0, 4.0, 4.0, 4.0]

    def test_fields_subset(self, df_with_nan):
        """Only the listed fields should be filled."""
        result = FillnaProcessor(fill_value=0, fields=["a"]).transform(df_with_nan)

        assert result["a"].isna().sum() == 0
        # 'b' still has its NaN since it was not in the fields list.
        assert result["b"].isna().sum() == 1

    def test_does_not_mutate_input(self, df_with_nan):
        """transform should not mutate the original DataFrame."""
        original = df_with_nan.copy()
        FillnaProcessor(fill_value=0).transform(df_with_nan)

        pd.testing.assert_frame_equal(df_with_nan, original)

    def test_no_numeric_fields_returns_copy(self):
        """A DataFrame with no numeric columns returns an unchanged copy."""
        df = pd.DataFrame({"label": ["x", "y", None]})
        result = FillnaProcessor(fill_value=0).transform(df)

        assert result["label"].tolist() == ["x", "y", None]

    def test_multiindex_ffill_per_territory(self):
        """MultiIndex ffill should forward-fill within each territory group."""
        idx = pd.MultiIndex.from_tuples(
            [
                ("2024-01", "75"),
                ("2024-02", "75"),
                ("2024-01", "59"),
                ("2024-02", "59"),
            ],
            names=["date", "territory"],
        )
        df = pd.DataFrame({"a": [1.0, np.nan, np.nan, 4.0]}, index=idx)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            result = FillnaProcessor(method="ffill").transform(df)

        # Territory 75: 1.0 forward-filled to row 2.
        # Territory 59: first value is NaN with nothing to fill from -> stays NaN.
        values = result["a"].tolist()
        assert values[0] == 1.0
        assert values[1] == 1.0
        assert np.isnan(values[2])
        assert values[3] == 4.0


# ═══════════════════════════════════════════════════════════════════════════════
# ZScoreProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestZScoreProcessor:
    """Tests for ZScoreProcessor (global method)."""

    def test_zscore_mean_zero_std_one(self, simple_df):
        """Global z-score output should have mean ~0 and std ~1."""
        result = ZScoreProcessor().fit_transform(simple_df)

        assert result["a"].mean() == pytest.approx(0.0, abs=1e-9)
        # pandas std uses ddof=1, and the processor divides by the same std,
        # so the resulting sample std is exactly 1.
        assert result["a"].std() == pytest.approx(1.0, abs=1e-9)

    def test_fit_stores_statistics(self, simple_df):
        """fit() should populate stats_ with mean and std per field."""
        proc = ZScoreProcessor().fit(simple_df)

        assert "a" in proc.stats_
        assert proc.stats_["a"]["mean"] == pytest.approx(3.0)
        assert proc.stats_["a"]["std"] > 0

    def test_constant_column_collapses_to_zero(self, constant_df):
        """A constant column (std == 0) should be set to 0."""
        proc = ZScoreProcessor().fit(constant_df)
        result = proc.transform(constant_df)

        assert proc.stats_["a"]["std"] == 0
        assert (result["a"] == 0).all()

    def test_all_nan_column_collapses_to_zero(self, all_nan_df):
        """An all-NaN column has NaN std (not > 0) and collapses to 0."""
        proc = ZScoreProcessor().fit(all_nan_df)
        result = proc.transform(all_nan_df)

        assert (result["a"] == 0).all()

    def test_empty_dataframe(self, empty_df):
        """An empty DataFrame should be handled without error."""
        result = ZScoreProcessor().fit_transform(empty_df)

        assert len(result) == 0

    def test_specific_fields_only(self):
        """Only the listed numeric fields should be normalized."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [10.0, 20.0, 30.0]})
        result = ZScoreProcessor(fields=["a"]).fit_transform(df)

        assert result["a"].mean() == pytest.approx(0.0, abs=1e-9)
        # 'b' was excluded -> left untouched.
        assert result["b"].tolist() == [10.0, 20.0, 30.0]

    def test_does_not_mutate_input(self, simple_df):
        """transform should not mutate the original DataFrame."""
        original = simple_df.copy()
        ZScoreProcessor().fit_transform(simple_df)

        pd.testing.assert_frame_equal(simple_df, original)

    def test_rolling_method_runs(self):
        """Rolling z-score should run and return a same-length frame."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
        result = ZScoreProcessor(method="rolling", window=3).fit_transform(df)

        assert len(result) == len(df)
        assert "a" in result.columns


# ═══════════════════════════════════════════════════════════════════════════════
# RobustZScoreProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestRobustZScoreProcessor:
    """Tests for RobustZScoreProcessor (median / MAD based)."""

    def test_robust_centers_on_median(self, df_with_outlier):
        """Robust z-score output should be centered on the median (~0)."""
        result = RobustZScoreProcessor().fit_transform(df_with_outlier)

        assert result["a"].median() == pytest.approx(0.0, abs=1e-9)

    def test_fit_stores_median_and_mad(self, df_with_outlier):
        """fit() should compute median and MAD per field."""
        proc = RobustZScoreProcessor().fit(df_with_outlier)

        assert "a" in proc.stats_
        assert proc.stats_["a"]["median"] == pytest.approx(3.0)
        assert proc.stats_["a"]["mad"] > 0

    def test_constant_column_collapses_to_zero(self, constant_df):
        """A constant column (MAD == 0) should be set to 0."""
        proc = RobustZScoreProcessor().fit(constant_df)
        result = proc.transform(constant_df)

        assert proc.stats_["a"]["mad"] == 0
        assert (result["a"] == 0).all()

    def test_resistant_to_outlier(self):
        """Robust scaling should keep the bulk of the data on a small scale."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0, 1000.0]})
        result = RobustZScoreProcessor().fit_transform(df)

        # The five normal values stay within a modest range; only the
        # outlier is pushed far out.
        bulk = result["a"].iloc[:5].abs()
        assert (bulk < 5).all()
        assert result["a"].iloc[5] > 100

    def test_empty_dataframe(self, empty_df):
        """An empty DataFrame should be handled without error."""
        result = RobustZScoreProcessor().fit_transform(empty_df)

        assert len(result) == 0

    def test_rolling_method_runs(self):
        """Rolling robust z-score should run and return a same-length frame."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]})
        result = RobustZScoreProcessor(method="rolling", window=3).fit_transform(df)

        assert len(result) == len(df)


# ═══════════════════════════════════════════════════════════════════════════════
# MinMaxProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestMinMaxProcessor:
    """Tests for MinMaxProcessor."""

    def test_scales_to_zero_one(self):
        """Output should span exactly [0, 1] for a varied column."""
        df = pd.DataFrame({"a": [10.0, 20.0, 30.0, 40.0]})
        result = MinMaxProcessor().fit_transform(df)

        assert result["a"].min() == pytest.approx(0.0)
        assert result["a"].max() == pytest.approx(1.0)

    def test_within_bounds(self):
        """All scaled values should fall inside [0, 1]."""
        df = pd.DataFrame({"a": [3.0, 7.0, 1.0, 9.0, 5.0]})
        result = MinMaxProcessor().fit_transform(df)

        assert (result["a"] >= 0).all()
        assert (result["a"] <= 1).all()

    def test_custom_feature_range(self):
        """A custom feature_range should be respected."""
        df = pd.DataFrame({"a": [0.0, 5.0, 10.0]})
        result = MinMaxProcessor(feature_range=(-1, 1)).fit_transform(df)

        assert result["a"].min() == pytest.approx(-1.0)
        assert result["a"].max() == pytest.approx(1.0)

    def test_preserves_nan(self):
        """NaN values should remain NaN after scaling."""
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 5.0]})
        result = MinMaxProcessor().fit_transform(df)

        assert np.isnan(result.loc[1, "a"])
        assert result["a"].dropna().min() == pytest.approx(0.0)
        assert result["a"].dropna().max() == pytest.approx(1.0)

    def test_empty_dataframe_no_scaler(self, empty_df):
        """An empty column produces no fitted scaler and transforms cleanly."""
        proc = MinMaxProcessor().fit(empty_df)

        assert "a" not in proc.scalers_
        result = proc.transform(empty_df)
        assert len(result) == 0

    def test_specific_fields(self):
        """Only listed fields should be scaled."""
        df = pd.DataFrame({"a": [10.0, 20.0, 30.0], "b": [1.0, 2.0, 3.0]})
        result = MinMaxProcessor(fields=["a"]).fit_transform(df)

        assert result["a"].max() == pytest.approx(1.0)
        assert result["b"].tolist() == [1.0, 2.0, 3.0]


# ═══════════════════════════════════════════════════════════════════════════════
# PopulationNormalizer
# ═══════════════════════════════════════════════════════════════════════════════


class TestPopulationNormalizer:
    """Tests for PopulationNormalizer."""

    def test_dict_population_simple_index(self):
        """Counts should be scaled per per_n inhabitants using a dict."""
        df = pd.DataFrame({"liquidations": [10.0, 20.0]}, index=["75", "59"])
        proc = PopulationNormalizer(
            {"75": 100000, "59": 200000}, per_n=10000
        )
        result = proc.transform(df)

        # 10 / 100000 * 10000 = 1.0 ; 20 / 200000 * 10000 = 1.0
        assert result["liquidations"].tolist() == [1.0, 1.0]

    def test_dataframe_with_code_dept_and_population(self):
        """A DataFrame with code_dept/population columns builds pop_dict."""
        pop_df = pd.DataFrame(
            {"code_dept": ["75", "59"], "population": [100000, 50000]}
        )
        proc = PopulationNormalizer(pop_df)

        assert proc.pop_dict == {"75": 100000, "59": 50000}

    def test_dataframe_fallback_first_column(self):
        """A DataFrame without the expected columns uses the first column."""
        pop_df = pd.DataFrame({"pop": [100000, 50000]}, index=["75", "59"])
        proc = PopulationNormalizer(pop_df)

        assert proc.pop_dict == {"75": 100000, "59": 50000}

    def test_explicit_fields(self):
        """Explicit fields override the default count-based detection."""
        df = pd.DataFrame({"foo": [50.0]}, index=["75"])
        proc = PopulationNormalizer({"75": 50000}, per_n=10000, fields=["foo"])
        result = proc.transform(df)

        # 50 / 50000 * 10000 = 10
        assert result["foo"].tolist() == [10.0]

    def test_missing_territory_defaults_population_to_one(self):
        """An unknown territory falls back to population 1 (fillna(1))."""
        df = pd.DataFrame({"liquidations": [5.0]}, index=["99"])
        proc = PopulationNormalizer({"75": 100000}, per_n=10000)
        result = proc.transform(df)

        # 5 / 1 * 10000 = 50000
        assert result["liquidations"].tolist() == [50000.0]

    def test_default_count_fields_detected(self):
        """Count-based field names should be auto-detected by substring."""
        df = pd.DataFrame(
            {"creation_entreprise": [100.0], "autre_metric": [5.0]},
            index=["75"],
        )
        proc = PopulationNormalizer({"75": 100000}, per_n=10000)
        result = proc.transform(df)

        # creation_entreprise normalized: 100 / 100000 * 10000 = 10
        assert result["creation_entreprise"].tolist() == [10.0]
        # Non-count field untouched.
        assert result["autre_metric"].tolist() == [5.0]

    def test_multiindex_uses_level_one(self):
        """With a MultiIndex, the territory is taken from level 1."""
        idx = pd.MultiIndex.from_tuples(
            [("2024-01", "75"), ("2024-01", "59")], names=["date", "territory"]
        )
        df = pd.DataFrame({"liquidations": [10.0, 30.0]}, index=idx)
        proc = PopulationNormalizer({"75": 100000, "59": 300000}, per_n=10000)
        result = proc.transform(df)

        assert result["liquidations"].tolist() == [1.0, 1.0]

    def test_fit_returns_self(self):
        """fit() should return the processor instance."""
        proc = PopulationNormalizer({"75": 100000})
        df = pd.DataFrame({"liquidations": [10.0]}, index=["75"])

        assert proc.fit(df) is proc


# ═══════════════════════════════════════════════════════════════════════════════
# SeasonalDecompProcessor
# ═══════════════════════════════════════════════════════════════════════════════


class TestSeasonalDecompProcessor:
    """Tests for SeasonalDecompProcessor.

    statsmodels is not installed in this environment, so the processor
    follows its graceful-degradation path: warn and return data unchanged.
    """

    def test_missing_statsmodels_warns_and_returns_copy(self):
        """Without statsmodels, transform should warn and return data as-is."""
        df = pd.DataFrame({"a": list(range(30))})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = SeasonalDecompProcessor().transform(df)
            messages = [str(w.message) for w in caught]

        assert list(result.columns) == ["a"]
        assert result["a"].tolist() == list(range(30))
        assert any("statsmodels" in m for m in messages)

    def test_fit_returns_self(self):
        """fit() should return the processor instance."""
        proc = SeasonalDecompProcessor()
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})

        assert proc.fit(df) is proc

    def test_does_not_mutate_input(self):
        """transform should not mutate the original DataFrame."""
        df = pd.DataFrame({"a": list(range(10))})
        original = df.copy()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            SeasonalDecompProcessor().transform(df)

        pd.testing.assert_frame_equal(df, original)


# ═══════════════════════════════════════════════════════════════════════════════
# ProcessorChain
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessorChain:
    """Tests for ProcessorChain composition."""

    def test_len_and_getitem(self):
        """Chain should expose its length and indexable processors."""
        fill = FillnaProcessor(fill_value=0)
        zscore = ZScoreProcessor()
        chain = ProcessorChain([fill, zscore])

        assert len(chain) == 2
        assert chain[0] is fill
        assert chain[1] is zscore

    def test_ordered_composition(self):
        """Processors should be applied in order: Fillna then ZScore."""
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 5.0]})
        chain = ProcessorChain([FillnaProcessor(fill_value=0), ZScoreProcessor()])
        result = chain.fit_transform(df)

        # After fill the NaN became 0, then everything was z-scored:
        # no NaN remains and the mean is ~0.
        assert result["a"].isna().sum() == 0
        assert result["a"].mean() == pytest.approx(0.0, abs=1e-9)

    def test_fit_returns_self(self):
        """fit() should return the chain instance."""
        chain = ProcessorChain([FillnaProcessor(fill_value=0)])
        df = pd.DataFrame({"a": [1.0, np.nan]})

        assert chain.fit(df) is chain

    def test_add_processor(self):
        """add_processor should append to the chain."""
        chain = ProcessorChain([FillnaProcessor(fill_value=0)])
        chain.add_processor(MinMaxProcessor())

        assert len(chain) == 2
        assert isinstance(chain[1], MinMaxProcessor)

    def test_transform_without_explicit_fit(self):
        """transform should work even when fit was not called first.

        MinMax requires fit (it builds scalers), but Fillna does not; a
        chain of fit-free processors transforms directly.
        """
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0]})
        chain = ProcessorChain([FillnaProcessor(fill_value=7)])
        result = chain.transform(df)

        assert result["a"].tolist() == [1.0, 7.0, 3.0]

    def test_empty_chain_is_passthrough(self, simple_df):
        """An empty chain should return the data unchanged."""
        chain = ProcessorChain([])
        result = chain.fit_transform(simple_df)

        pd.testing.assert_frame_equal(result, simple_df)


# ═══════════════════════════════════════════════════════════════════════════════
# Factory functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateStandardChain:
    """Tests for create_standard_chain factory."""

    def test_default_robust_no_population(self):
        """Default chain: Fillna + RobustZScore (no population step)."""
        chain = create_standard_chain()

        assert len(chain) == 2
        assert isinstance(chain[0], FillnaProcessor)
        assert isinstance(chain[1], RobustZScoreProcessor)

    def test_non_robust_uses_plain_zscore(self):
        """robust=False should use ZScoreProcessor as the final step."""
        chain = create_standard_chain(robust=False)

        assert isinstance(chain[-1], ZScoreProcessor)
        assert not isinstance(chain[-1], RobustZScoreProcessor)

    def test_with_dict_population_inserts_normalizer(self):
        """A dict population inserts a PopulationNormalizer step."""
        chain = create_standard_chain(population_data={"75": 100000})

        types = [type(p).__name__ for p in chain]
        assert types == ["FillnaProcessor", "PopulationNormalizer", "RobustZScoreProcessor"]

    def test_with_dataframe_population_inserts_normalizer(self):
        """A DataFrame population inserts a PopulationNormalizer step."""
        pop_df = pd.DataFrame({"code_dept": ["75"], "population": [100000]})
        chain = create_standard_chain(population_data=pop_df, robust=False)

        types = [type(p).__name__ for p in chain]
        assert types == ["FillnaProcessor", "PopulationNormalizer", "ZScoreProcessor"]

    def test_none_population_omits_normalizer(self):
        """population_data=None should not add a PopulationNormalizer."""
        chain = create_standard_chain(population_data=None)

        assert not any(isinstance(p, PopulationNormalizer) for p in chain)

    def test_end_to_end_fit_transform(self):
        """The standard chain should process a small frame end to end."""
        df = pd.DataFrame({"liquidations": [1.0, 2.0, np.nan, 4.0, 5.0]})
        chain = create_standard_chain(robust=True)
        result = chain.fit_transform(df)

        # NaN was filled (ffill then implicitly 0 for the leading edge) and
        # the column was robustly normalized; no NaN remains.
        assert result["liquidations"].isna().sum() == 0
        assert len(result) == len(df)


class TestCreateInferenceChain:
    """Tests for create_inference_chain factory."""

    def test_no_population_uses_double_fillna(self):
        """Without population, the middle step is a second FillnaProcessor."""
        chain = create_inference_chain()

        types = [type(p).__name__ for p in chain]
        assert types == ["FillnaProcessor", "FillnaProcessor", "RobustZScoreProcessor"]

    def test_with_dict_population_inserts_normalizer(self):
        """A dict population replaces the middle step with a normalizer."""
        chain = create_inference_chain(population_data={"75": 100000})

        types = [type(p).__name__ for p in chain]
        assert types == ["FillnaProcessor", "PopulationNormalizer", "RobustZScoreProcessor"]

    def test_with_dataframe_population_inserts_normalizer(self):
        """A DataFrame population replaces the middle step with a normalizer."""
        pop_df = pd.DataFrame({"code_dept": ["75"], "population": [100000]})
        chain = create_inference_chain(population_data=pop_df)

        types = [type(p).__name__ for p in chain]
        assert types == ["FillnaProcessor", "PopulationNormalizer", "RobustZScoreProcessor"]

    def test_uses_rolling_robust_zscore(self):
        """The final step should be a rolling RobustZScoreProcessor."""
        chain = create_inference_chain()
        final = chain[-1]

        assert isinstance(final, RobustZScoreProcessor)
        assert final.method == "rolling"
        assert final.window == 6

    def test_end_to_end_fit_transform(self):
        """The inference chain should process a small frame end to end."""
        df = pd.DataFrame({"liquidations": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0]})
        chain = create_inference_chain()
        result = chain.fit_transform(df)

        assert result["liquidations"].isna().sum() == 0
        assert len(result) == len(df)
