"""Unit tests for TerritorialDataset (issue #161, batch 3 coverage).

Target module: src/collector/quant/qlib/dataset.py

The production code is the source of truth. These tests assert its *real*
behaviour, including its quirks:

- The constructor only *warns* (never raises) on a missing MultiIndex,
  a label/feature index mismatch, or an empty dataset.
- ``__getitem__`` only accepts slice / list / ndarray keys; an ``int`` key
  raises ``ValueError``.
- ``get_date_range`` / ``get_latest_data`` fall back gracefully (with a
  warning) when there is no MultiIndex / no date information.
- ``normalize_features`` raises ``ValueError`` for an unknown method.

Data is built qlib-style: a MultiIndex of (date, territory) on the rows
and one column per feature / label.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from src.collector.quant.qlib.dataset import TerritorialDataset


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
DATES = pd.to_datetime(
    [
        "2020-01-01",
        "2020-01-02",
        "2020-01-03",
        "2020-01-04",
        "2020-01-05",
        "2020-01-06",
    ]
)
TERRITORIES = ["75", "13"]


def _make_multiindex(dates=DATES, territories=TERRITORIES):
    return pd.MultiIndex.from_product(
        [dates, territories], names=["date", "territory"]
    )


@pytest.fixture
def multi_features():
    """MultiIndex (date, territory) feature frame with two numeric columns."""
    idx = _make_multiindex()
    n = len(idx)
    return pd.DataFrame(
        {
            "f1": np.arange(n, dtype=float),
            "f2": np.arange(n, dtype=float) * 1.5,
        },
        index=idx,
    )


@pytest.fixture
def multi_labels():
    """Labels frame sharing the MultiIndex of ``multi_features``."""
    idx = _make_multiindex()
    n = len(idx)
    return pd.DataFrame({"y": np.arange(n, dtype=float)}, index=idx)


@pytest.fixture
def dataset(multi_features, multi_labels):
    return TerritorialDataset(multi_features, multi_labels, {"src": "test"})


@pytest.fixture
def simple_dataset():
    """Dataset with a plain (non-MultiIndex) index of territory codes."""
    feats = pd.DataFrame(
        {"f1": [1.0, 2.0, 3.0], "f2": [4.0, 5.0, 6.0]},
        index=["75", "13", "69"],
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return TerritorialDataset(feats)


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_valid_multiindex_construction(self, multi_features, multi_labels):
        ds = TerritorialDataset(multi_features, multi_labels)
        assert isinstance(ds.features, pd.DataFrame)
        assert ds.labels is not None
        assert ds.metadata == {}

    def test_features_are_copied(self, multi_features):
        ds = TerritorialDataset(multi_features)
        ds.features.iloc[0, 0] = 999.0
        # Original input must remain untouched (constructor uses .copy()).
        assert multi_features.iloc[0, 0] != 999.0

    def test_labels_are_copied(self, multi_features, multi_labels):
        ds = TerritorialDataset(multi_features, multi_labels)
        ds.labels.iloc[0, 0] = 999.0
        assert multi_labels.iloc[0, 0] != 999.0

    def test_metadata_defaults_to_empty_dict(self, multi_features):
        ds = TerritorialDataset(multi_features)
        assert ds.metadata == {}

    def test_metadata_preserved(self, multi_features):
        meta = {"source": "ademe", "version": 2}
        ds = TerritorialDataset(multi_features, metadata=meta)
        assert ds.metadata == meta

    def test_no_labels(self, multi_features):
        ds = TerritorialDataset(multi_features)
        assert ds.labels is None

    def test_warns_on_non_multiindex(self):
        feats = pd.DataFrame({"f1": [1.0, 2.0]}, index=["75", "13"])
        with pytest.warns(UserWarning, match="MultiIndex"):
            TerritorialDataset(feats)

    def test_warns_on_label_index_mismatch(self, multi_features):
        bad_labels = multi_features.iloc[:3].rename(columns={"f1": "y"})[["y"]]
        with pytest.warns(UserWarning, match="Labels index does not match"):
            TerritorialDataset(multi_features, bad_labels)

    def test_warns_on_empty_dataset(self):
        empty = pd.DataFrame({"f1": []})
        with pytest.warns(UserWarning, match="Empty dataset"):
            TerritorialDataset(empty)

    def test_construction_never_raises_on_invalid_structure(self):
        # Only warnings are emitted; construction must still succeed.
        empty = pd.DataFrame({"f1": []})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ds = TerritorialDataset(empty)
        assert len(ds) == 0


# ---------------------------------------------------------------------------
# Index extraction & basic properties
# ---------------------------------------------------------------------------
class TestProperties:
    def test_territories_sorted_unique(self, dataset):
        assert dataset.territories == ["13", "75"]

    def test_dates_sorted_unique(self, dataset):
        assert dataset.dates == list(DATES)

    def test_feature_names(self, dataset):
        assert dataset.feature_names == ["f1", "f2"]

    def test_label_names(self, dataset):
        assert dataset.label_names == ["y"]

    def test_label_names_empty_without_labels(self, multi_features):
        ds = TerritorialDataset(multi_features)
        assert ds.label_names == []

    def test_shape(self, dataset):
        assert dataset.shape == (len(DATES) * len(TERRITORIES), 2)

    def test_len(self, dataset):
        assert len(dataset) == len(DATES) * len(TERRITORIES)

    def test_simple_index_territories(self, simple_dataset):
        assert simple_dataset.territories == ["13", "69", "75"]

    def test_simple_index_has_no_dates(self, simple_dataset):
        assert simple_dataset.dates == []


# ---------------------------------------------------------------------------
# __getitem__ subsetting
# ---------------------------------------------------------------------------
class TestGetItem:
    def test_slice_returns_dataset(self, dataset):
        sub = dataset[0:4]
        assert isinstance(sub, TerritorialDataset)
        assert len(sub) == 4

    def test_slice_subsets_labels_too(self, dataset):
        sub = dataset[0:4]
        assert sub.labels is not None
        assert len(sub.labels) == 4

    def test_list_key(self, dataset):
        sub = dataset[[0, 1, 2]]
        assert len(sub) == 3

    def test_ndarray_key(self, dataset):
        sub = dataset[np.array([0, 2, 4])]
        assert len(sub) == 3

    def test_int_key_raises_value_error(self, dataset):
        with pytest.raises(ValueError, match="Unsupported key type"):
            _ = dataset[0]

    def test_str_key_raises_value_error(self, dataset):
        with pytest.raises(ValueError, match="Unsupported key type"):
            _ = dataset["foo"]

    def test_subset_without_labels(self, multi_features):
        ds = TerritorialDataset(multi_features)
        sub = ds[0:2]
        assert sub.labels is None


# ---------------------------------------------------------------------------
# get_territory
# ---------------------------------------------------------------------------
class TestGetTerritory:
    def test_multiindex_returns_only_that_territory(self, dataset):
        td = dataset.get_territory("75")
        # One row per date for territory "75".
        assert len(td) == len(DATES)
        assert (td.index.get_level_values(1) == "75").all()

    def test_simple_index_territory(self, simple_dataset):
        td = simple_dataset.get_territory("69")
        assert len(td) == 1

    def test_missing_territory_warns_and_returns_empty(self, dataset):
        with pytest.warns(UserWarning, match="No data found for territory"):
            td = dataset.get_territory("99")
        assert len(td) == 0

    def test_returns_dataframe(self, dataset):
        assert isinstance(dataset.get_territory("75"), pd.DataFrame)


# ---------------------------------------------------------------------------
# get_date_range
# ---------------------------------------------------------------------------
class TestGetDateRange:
    def test_filters_inclusive(self, dataset):
        sub = dataset.get_date_range(DATES[0], DATES[1])
        assert sub.dates == [DATES[0], DATES[1]]

    def test_returns_dataset(self, dataset):
        sub = dataset.get_date_range(DATES[0], DATES[2])
        assert isinstance(sub, TerritorialDataset)

    def test_keeps_labels(self, dataset):
        sub = dataset.get_date_range(DATES[0], DATES[1])
        assert sub.labels is not None
        assert len(sub.labels) == 2 * len(TERRITORIES)

    def test_non_multiindex_warns_and_returns_all(self, simple_dataset):
        with pytest.warns(UserWarning, match="Date filtering not available"):
            sub = simple_dataset.get_date_range("a", "b")
        assert len(sub.features) == len(simple_dataset.features)


# ---------------------------------------------------------------------------
# get_latest_data
# ---------------------------------------------------------------------------
class TestGetLatestData:
    def test_default_one_period(self, dataset):
        sub = dataset.get_latest_data()
        assert sub.dates == [DATES[-1]]

    def test_n_periods(self, dataset):
        sub = dataset.get_latest_data(2)
        assert sub.dates == list(DATES[-2:])

    def test_keeps_labels(self, dataset):
        sub = dataset.get_latest_data(1)
        assert sub.labels is not None

    def test_no_dates_warns_and_returns_self(self, simple_dataset):
        with pytest.warns(UserWarning, match="No date information"):
            sub = simple_dataset.get_latest_data(2)
        assert sub is simple_dataset


# ---------------------------------------------------------------------------
# to_numpy
# ---------------------------------------------------------------------------
class TestToNumpy:
    def test_with_labels(self, dataset):
        X, y = dataset.to_numpy()
        assert isinstance(X, np.ndarray)
        assert isinstance(y, np.ndarray)
        assert X.shape == (len(dataset), 2)
        assert y.shape == (len(dataset), 1)

    def test_without_labels(self, multi_features):
        ds = TerritorialDataset(multi_features)
        X, y = ds.to_numpy()
        assert X.shape == (len(ds), 2)
        assert y is None


# ---------------------------------------------------------------------------
# split_temporal
# ---------------------------------------------------------------------------
class TestSplitTemporal:
    def test_returns_two_datasets(self, dataset):
        train, test = dataset.split_temporal(0.5)
        assert isinstance(train, TerritorialDataset)
        assert isinstance(test, TerritorialDataset)

    def test_split_respects_time_order(self, dataset):
        # 6 dates, ratio 0.5 -> split index 3 -> split_date = DATES[3]
        train, test = dataset.split_temporal(0.5)
        assert max(train.dates) < min(test.dates)
        assert train.dates == list(DATES[:3])
        assert test.dates == list(DATES[3:])

    def test_no_overlap(self, dataset):
        train, test = dataset.split_temporal(0.5)
        assert set(train.dates).isdisjoint(set(test.dates))

    def test_total_samples_preserved(self, dataset):
        train, test = dataset.split_temporal(0.5)
        assert len(train) + len(test) == len(dataset)

    def test_labels_propagated(self, dataset):
        train, test = dataset.split_temporal(0.5)
        assert train.labels is not None
        assert test.labels is not None

    def test_simple_index_fallback_split(self, simple_dataset):
        # No dates -> positional split on len(features).
        train, test = simple_dataset.split_temporal(0.66)
        assert len(train) + len(test) == len(simple_dataset)
        assert len(train) == int(3 * 0.66)


# ---------------------------------------------------------------------------
# split_by_territory
# ---------------------------------------------------------------------------
class TestSplitByTerritory:
    def test_multiindex_split(self, dataset):
        train, test = dataset.split_by_territory(["13"])
        assert test.territories == ["13"]
        assert "13" not in train.territories
        assert "75" in train.territories

    def test_total_preserved(self, dataset):
        train, test = dataset.split_by_territory(["13"])
        assert len(train) + len(test) == len(dataset)

    def test_simple_index_split(self, simple_dataset):
        train, test = simple_dataset.split_by_territory(["13"])
        assert test.territories == ["13"]
        assert "13" not in train.territories

    def test_labels_propagated(self, dataset):
        train, test = dataset.split_by_territory(["75"])
        assert train.labels is not None
        assert test.labels is not None


# ---------------------------------------------------------------------------
# cross_validate_temporal
# ---------------------------------------------------------------------------
class TestCrossValidateTemporal:
    def test_returns_expected_number_of_splits(self, dataset):
        splits = dataset.cross_validate_temporal(n_splits=3)
        assert len(splits) == 3

    def test_each_split_is_a_pair_of_datasets(self, dataset):
        splits = dataset.cross_validate_temporal(n_splits=3)
        for train, test in splits:
            assert isinstance(train, TerritorialDataset)
            assert isinstance(test, TerritorialDataset)
            assert len(train) > 0
            assert len(test) > 0

    def test_train_size_grows(self, dataset):
        # TimeSeriesSplit grows the training window across folds.
        splits = dataset.cross_validate_temporal(n_splits=3)
        sizes = [len(train) for train, _ in splits]
        assert sizes == sorted(sizes)

    def test_labels_propagated(self, dataset):
        splits = dataset.cross_validate_temporal(n_splits=2)
        train, test = splits[0]
        assert train.labels is not None
        assert test.labels is not None


# ---------------------------------------------------------------------------
# Statistics & reports
# ---------------------------------------------------------------------------
class TestStatsAndReports:
    def test_summary_stats(self, dataset):
        stats = dataset.get_summary_stats()
        assert "mean" in stats.index
        assert list(stats.columns) == ["f1", "f2"]

    def test_missing_data_report_columns(self, dataset):
        report = dataset.get_missing_data_report()
        assert list(report.columns) == ["missing_count", "missing_percentage"]

    def test_missing_data_report_counts(self, multi_features):
        feats = multi_features.copy()
        feats.iloc[0, 0] = np.nan
        ds = TerritorialDataset(feats)
        report = ds.get_missing_data_report()
        assert int(report.loc["f1", "missing_count"]) == 1
        assert report.loc["f1", "missing_percentage"] > 0

    def test_correlation_matrix_shape(self, dataset):
        corr = dataset.get_correlation_matrix()
        assert corr.shape == (2, 2)


# ---------------------------------------------------------------------------
# Feature manipulation
# ---------------------------------------------------------------------------
class TestFeatureManipulation:
    def test_add_feature(self, dataset):
        new_col = pd.Series(
            np.arange(len(dataset), dtype=float), index=dataset.features.index
        )
        ds2 = dataset.add_feature("f3", new_col)
        assert "f3" in ds2.feature_names
        # Original dataset is unchanged (returns a new dataset).
        assert "f3" not in dataset.feature_names

    def test_add_feature_returns_new_dataset(self, dataset):
        new_col = pd.Series(
            np.zeros(len(dataset)), index=dataset.features.index
        )
        ds2 = dataset.add_feature("f3", new_col)
        assert isinstance(ds2, TerritorialDataset)
        assert ds2 is not dataset

    def test_select_features(self, dataset):
        ds2 = dataset.select_features(["f1"])
        assert ds2.feature_names == ["f1"]

    def test_select_features_missing_warns(self, dataset):
        with pytest.warns(UserWarning, match="Missing features"):
            ds2 = dataset.select_features(["f1", "does_not_exist"])
        # Only the available feature survives.
        assert ds2.feature_names == ["f1"]

    def test_select_features_preserves_labels(self, dataset):
        ds2 = dataset.select_features(["f1"])
        assert ds2.labels is not None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
class TestNormalization:
    def test_zscore_mean_near_zero(self, dataset):
        norm = dataset.normalize_features("zscore")
        assert abs(float(norm.features["f1"].mean())) < 1e-9

    def test_minmax_range(self, dataset):
        norm = dataset.normalize_features("minmax")
        assert float(norm.features["f1"].min()) == pytest.approx(0.0)
        assert float(norm.features["f1"].max()) == pytest.approx(1.0)

    def test_robust_runs(self, dataset):
        norm = dataset.normalize_features("robust")
        assert norm.feature_names == ["f1", "f2"]
        assert norm.features.index.equals(dataset.features.index)

    def test_preserves_index_and_columns(self, dataset):
        norm = dataset.normalize_features("zscore")
        assert norm.features.index.equals(dataset.features.index)
        assert list(norm.features.columns) == list(dataset.features.columns)

    def test_unknown_method_raises(self, dataset):
        with pytest.raises(ValueError, match="Unknown normalization method"):
            dataset.normalize_features("bogus")

    def test_labels_preserved(self, dataset):
        norm = dataset.normalize_features("zscore")
        assert norm.labels is not None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
class TestExport:
    def test_csv_with_labels(self, dataset, tmp_path):
        path = tmp_path / "out.csv"
        dataset.export_to_csv(str(path), include_labels=True)
        assert path.exists()
        df = pd.read_csv(path)
        assert "y" in df.columns
        assert "f1" in df.columns

    def test_csv_without_labels(self, dataset, tmp_path):
        path = tmp_path / "out.csv"
        dataset.export_to_csv(str(path), include_labels=False)
        df = pd.read_csv(path)
        assert "y" not in df.columns
        assert "f1" in df.columns

    def test_csv_no_labels_dataset(self, multi_features, tmp_path):
        ds = TerritorialDataset(multi_features)
        path = tmp_path / "out.csv"
        # include_labels=True but no labels -> falls back to features only.
        ds.export_to_csv(str(path), include_labels=True)
        df = pd.read_csv(path)
        assert "f1" in df.columns

    def test_parquet_with_labels(self, dataset, tmp_path):
        pytest.importorskip("pyarrow")
        path = tmp_path / "out.parquet"
        dataset.export_to_parquet(str(path), include_labels=True)
        assert path.exists()
        df = pd.read_parquet(path)
        assert "y" in df.columns

    def test_parquet_without_labels(self, dataset, tmp_path):
        pytest.importorskip("pyarrow")
        path = tmp_path / "out.parquet"
        dataset.export_to_parquet(str(path), include_labels=False)
        df = pd.read_parquet(path)
        assert "y" not in df.columns


# ---------------------------------------------------------------------------
# info() & __repr__
# ---------------------------------------------------------------------------
class TestInfoAndRepr:
    def test_info_keys(self, dataset):
        info = dataset.info()
        expected = {
            "n_samples",
            "n_features",
            "n_territories",
            "n_dates",
            "date_range",
            "feature_names",
            "territories",
            "has_labels",
            "label_names",
            "memory_usage_mb",
        }
        assert expected.issubset(info.keys())

    def test_info_values(self, dataset):
        info = dataset.info()
        assert info["n_samples"] == len(dataset)
        assert info["n_features"] == 2
        assert info["n_territories"] == 2
        assert info["n_dates"] == len(DATES)
        assert info["has_labels"] is True
        assert info["date_range"] == (DATES[0], DATES[-1])

    def test_info_no_dates_date_range_none(self, simple_dataset):
        assert simple_dataset.info()["date_range"] is None

    def test_info_has_labels_false(self, multi_features):
        ds = TerritorialDataset(multi_features)
        assert ds.info()["has_labels"] is False

    def test_repr_contains_summary(self, dataset):
        text = repr(dataset)
        assert "TerritorialDataset" in text
        assert "samples:" in text
        assert "has_labels:" in text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_dataset_info(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ds = TerritorialDataset(pd.DataFrame({"f1": []}))
        info = ds.info()
        assert info["n_samples"] == 0
        assert info["date_range"] is None

    def test_empty_dataset_to_numpy(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ds = TerritorialDataset(pd.DataFrame({"f1": []}))
        X, y = ds.to_numpy()
        assert X.shape[0] == 0
        assert y is None

    def test_single_feature_dataset(self):
        idx = _make_multiindex()
        feats = pd.DataFrame(
            {"only": np.arange(len(idx), dtype=float)}, index=idx
        )
        ds = TerritorialDataset(feats)
        assert ds.feature_names == ["only"]
        assert ds.shape == (len(idx), 1)

    def test_select_no_existing_features_returns_empty_columns(self, dataset):
        with pytest.warns(UserWarning, match="Missing features"):
            ds2 = dataset.select_features(["nope1", "nope2"])
        assert ds2.feature_names == []
