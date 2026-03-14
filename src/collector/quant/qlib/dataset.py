"""
Territorial dataset class adapted from Microsoft QLib.

This module provides a dataset abstraction for territorial intelligence
that wraps processed features and labels in a convenient interface
for machine learning workflows.

Adapted from: https://github.com/microsoft/qlib/blob/main/qlib/data/dataset/
License: MIT
"""

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit


class TerritorialDataset:
    """
    Dataset for territorial intelligence analysis.

    This class wraps features and labels for territorial data,
    providing convenient methods for ML workflows.

    Args:
        features_df: DataFrame with feature data (MultiIndex: date, territory)
        labels_df: Optional DataFrame with label data
        metadata: Optional metadata dictionary
    """

    def __init__(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame | None = None,
        metadata: dict[str, Any] | None = None,
    ):

        self.features = features_df.copy()
        self.labels = labels_df.copy() if labels_df is not None else None
        self.metadata = metadata or {}

        # Validate data structure
        self._validate_data()

        # Store useful properties
        self._territories = self._extract_territories()
        self._dates = self._extract_dates()

    def _validate_data(self):
        """Validate the dataset structure."""
        # Check if features have MultiIndex
        if not isinstance(self.features.index, pd.MultiIndex):
            warnings.warn(
                "Features DataFrame should have MultiIndex (date, territory)", stacklevel=2
            )

        # Check if labels match features structure
        if self.labels is not None:
            if not self.features.index.equals(self.labels.index):
                warnings.warn("Labels index does not match features index", stacklevel=2)

        # Check for empty dataset
        if len(self.features) == 0:
            warnings.warn("Empty dataset provided", stacklevel=2)

    def _extract_territories(self) -> list[str]:
        """Extract unique territories from the index."""
        if isinstance(self.features.index, pd.MultiIndex):
            return sorted(self.features.index.get_level_values(1).unique().tolist())
        else:
            # Assume single index contains territories
            return sorted(self.features.index.unique().tolist())

    def _extract_dates(self) -> list:
        """Extract unique dates from the index."""
        if isinstance(self.features.index, pd.MultiIndex):
            return sorted(self.features.index.get_level_values(0).unique().tolist())
        else:
            # If no MultiIndex, return empty list
            return []

    @property
    def territories(self) -> list[str]:
        """Get list of territories in the dataset."""
        return self._territories

    @property
    def dates(self) -> list:
        """Get list of dates in the dataset."""
        return self._dates

    @property
    def feature_names(self) -> list[str]:
        """Get list of feature names."""
        return self.features.columns.tolist()

    @property
    def label_names(self) -> list[str]:
        """Get list of label names."""
        if self.labels is not None:
            return self.labels.columns.tolist()
        return []

    @property
    def shape(self) -> tuple[int, int]:
        """Get dataset shape (n_samples, n_features)."""
        return self.features.shape

    def __len__(self) -> int:
        """Get number of samples."""
        return len(self.features)

    def __getitem__(self, key) -> "TerritorialDataset":
        """Subset the dataset."""
        if isinstance(key, (slice, list, np.ndarray)):
            features_subset = self.features.iloc[key]
            labels_subset = self.labels.iloc[key] if self.labels is not None else None
        else:
            raise ValueError(f"Unsupported key type: {type(key)}")

        return TerritorialDataset(features_subset, labels_subset, self.metadata)

    def get_territory(self, territory_code: str) -> pd.DataFrame:
        """
        Get data for a specific territory.

        Args:
            territory_code: Territory identifier

        Returns:
            DataFrame with data for the specified territory
        """
        if isinstance(self.features.index, pd.MultiIndex):
            territory_data = self.features.loc[
                self.features.index.get_level_values(1) == territory_code
            ]
        else:
            # Simple index - assume it contains territory codes
            territory_data = self.features.loc[self.features.index == territory_code]

        if len(territory_data) == 0:
            warnings.warn(f"No data found for territory: {territory_code}", stacklevel=2)

        return territory_data

    def get_date_range(self, start_date, end_date) -> "TerritorialDataset":
        """
        Get data for a specific date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            TerritorialDataset with data in the specified date range
        """
        if isinstance(self.features.index, pd.MultiIndex):
            mask = (self.features.index.get_level_values(0) >= start_date) & (
                self.features.index.get_level_values(0) <= end_date
            )
            features_subset = self.features.loc[mask]
            labels_subset = self.labels.loc[mask] if self.labels is not None else None
        else:
            warnings.warn("Date filtering not available for non-MultiIndex data", stacklevel=2)
            features_subset = self.features
            labels_subset = self.labels

        return TerritorialDataset(features_subset, labels_subset, self.metadata)

    def get_latest_data(self, n_periods: int = 1) -> "TerritorialDataset":
        """
        Get the latest n periods of data.

        Args:
            n_periods: Number of latest periods to include

        Returns:
            TerritorialDataset with latest data
        """
        if not self.dates:
            warnings.warn("No date information available", stacklevel=2)
            return self

        latest_dates = sorted(self.dates)[-n_periods:]

        if isinstance(self.features.index, pd.MultiIndex):
            mask = self.features.index.get_level_values(0).isin(latest_dates)
            features_subset = self.features.loc[mask]
            labels_subset = self.labels.loc[mask] if self.labels is not None else None
        else:
            features_subset = self.features.tail(n_periods)
            labels_subset = self.labels.tail(n_periods) if self.labels is not None else None

        return TerritorialDataset(features_subset, labels_subset, self.metadata)

    def to_numpy(self) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Convert dataset to NumPy arrays.

        Returns:
            Tuple of (features_array, labels_array)
            labels_array is None if no labels provided
        """
        X = self.features.values
        y = self.labels.values if self.labels is not None else None
        return X, y

    def split_temporal(
        self, train_ratio: float = 0.8
    ) -> tuple["TerritorialDataset", "TerritorialDataset"]:
        """
        Split dataset temporally (respecting time ordering).

        Args:
            train_ratio: Ratio of data to use for training

        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        if not self.dates:
            # If no date information, use simple split
            split_idx = int(len(self.features) * train_ratio)
            train_features = self.features.iloc[:split_idx]
            test_features = self.features.iloc[split_idx:]

            train_labels = self.labels.iloc[:split_idx] if self.labels is not None else None
            test_labels = self.labels.iloc[split_idx:] if self.labels is not None else None
        else:
            # Split by date
            split_date_idx = int(len(self.dates) * train_ratio)
            split_date = self.dates[split_date_idx]

            if isinstance(self.features.index, pd.MultiIndex):
                train_mask = self.features.index.get_level_values(0) < split_date
                test_mask = self.features.index.get_level_values(0) >= split_date

                train_features = self.features.loc[train_mask]
                test_features = self.features.loc[test_mask]

                train_labels = self.labels.loc[train_mask] if self.labels is not None else None
                test_labels = self.labels.loc[test_mask] if self.labels is not None else None
            else:
                # Fallback to simple split
                split_idx = int(len(self.features) * train_ratio)
                train_features = self.features.iloc[:split_idx]
                test_features = self.features.iloc[split_idx:]

                train_labels = self.labels.iloc[:split_idx] if self.labels is not None else None
                test_labels = self.labels.iloc[split_idx:] if self.labels is not None else None

        train_dataset = TerritorialDataset(train_features, train_labels, self.metadata)
        test_dataset = TerritorialDataset(test_features, test_labels, self.metadata)

        return train_dataset, test_dataset

    def split_by_territory(
        self, test_territories: list[str]
    ) -> tuple["TerritorialDataset", "TerritorialDataset"]:
        """
        Split dataset by territory (spatial split).

        Args:
            test_territories: List of territories to use for testing

        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        if isinstance(self.features.index, pd.MultiIndex):
            train_mask = ~self.features.index.get_level_values(1).isin(test_territories)
            test_mask = self.features.index.get_level_values(1).isin(test_territories)

            train_features = self.features.loc[train_mask]
            test_features = self.features.loc[test_mask]

            train_labels = self.labels.loc[train_mask] if self.labels is not None else None
            test_labels = self.labels.loc[test_mask] if self.labels is not None else None
        else:
            # Assume index contains territories
            train_mask = ~self.features.index.isin(test_territories)
            test_mask = self.features.index.isin(test_territories)

            train_features = self.features.loc[train_mask]
            test_features = self.features.loc[test_mask]

            train_labels = self.labels.loc[train_mask] if self.labels is not None else None
            test_labels = self.labels.loc[test_mask] if self.labels is not None else None

        train_dataset = TerritorialDataset(train_features, train_labels, self.metadata)
        test_dataset = TerritorialDataset(test_features, test_labels, self.metadata)

        return train_dataset, test_dataset

    def cross_validate_temporal(
        self, n_splits: int = 5
    ) -> list[tuple["TerritorialDataset", "TerritorialDataset"]]:
        """
        Create temporal cross-validation splits.

        Args:
            n_splits: Number of splits

        Returns:
            List of (train_dataset, test_dataset) tuples
        """
        tscv = TimeSeriesSplit(n_splits=n_splits)
        splits = []

        X, y = self.to_numpy()

        for train_idx, test_idx in tscv.split(X):
            train_features = self.features.iloc[train_idx]
            test_features = self.features.iloc[test_idx]

            train_labels = self.labels.iloc[train_idx] if self.labels is not None else None
            test_labels = self.labels.iloc[test_idx] if self.labels is not None else None

            train_dataset = TerritorialDataset(train_features, train_labels, self.metadata)
            test_dataset = TerritorialDataset(test_features, test_labels, self.metadata)

            splits.append((train_dataset, test_dataset))

        return splits

    def get_summary_stats(self) -> pd.DataFrame:
        """
        Get summary statistics for all features.

        Returns:
            DataFrame with summary statistics
        """
        return self.features.describe()

    def get_missing_data_report(self) -> pd.DataFrame:
        """
        Get report on missing data.

        Returns:
            DataFrame with missing data statistics
        """
        missing_stats = pd.DataFrame(
            {
                "missing_count": self.features.isnull().sum(),
                "missing_percentage": (
                    self.features.isnull().sum() / len(self.features) * 100
                ).round(2),
            }
        )
        return missing_stats.sort_values("missing_percentage", ascending=False)

    def get_correlation_matrix(self) -> pd.DataFrame:
        """
        Get feature correlation matrix.

        Returns:
            DataFrame with correlation coefficients
        """
        return self.features.corr()

    def add_feature(self, name: str, data: pd.Series) -> "TerritorialDataset":
        """
        Add a new feature to the dataset.

        Args:
            name: Feature name
            data: Feature data

        Returns:
            New TerritorialDataset with added feature
        """
        new_features = self.features.copy()
        new_features[name] = data

        return TerritorialDataset(new_features, self.labels, self.metadata)

    def select_features(self, feature_names: list[str]) -> "TerritorialDataset":
        """
        Select subset of features.

        Args:
            feature_names: List of feature names to select

        Returns:
            New TerritorialDataset with selected features
        """
        available_features = [f for f in feature_names if f in self.features.columns]
        if len(available_features) != len(feature_names):
            missing = set(feature_names) - set(available_features)
            warnings.warn(f"Missing features: {missing}", stacklevel=2)

        new_features = self.features[available_features]
        return TerritorialDataset(new_features, self.labels, self.metadata)

    def normalize_features(self, method: str = "zscore") -> "TerritorialDataset":
        """
        Normalize features using specified method.

        Args:
            method: Normalization method ('zscore', 'minmax', 'robust')

        Returns:
            New TerritorialDataset with normalized features
        """
        from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

        if method == "zscore":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler()
        elif method == "robust":
            scaler = RobustScaler()
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        normalized_features = pd.DataFrame(
            scaler.fit_transform(self.features),
            index=self.features.index,
            columns=self.features.columns,
        )

        return TerritorialDataset(normalized_features, self.labels, self.metadata)

    def export_to_csv(self, filepath: str, include_labels: bool = True):
        """
        Export dataset to CSV file.

        Args:
            filepath: Output file path
            include_labels: Whether to include labels in export
        """
        if include_labels and self.labels is not None:
            combined = pd.concat([self.features, self.labels], axis=1)
            combined.to_csv(filepath)
        else:
            self.features.to_csv(filepath)

    def export_to_parquet(self, filepath: str, include_labels: bool = True):
        """
        Export dataset to Parquet file.

        Args:
            filepath: Output file path
            include_labels: Whether to include labels in export
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError("pyarrow required for parquet export")

        if include_labels and self.labels is not None:
            combined = pd.concat([self.features, self.labels], axis=1)
            combined.to_parquet(filepath)
        else:
            self.features.to_parquet(filepath)

    def info(self) -> dict[str, Any]:
        """
        Get dataset information.

        Returns:
            Dictionary with dataset information
        """
        return {
            "n_samples": len(self.features),
            "n_features": len(self.feature_names),
            "n_territories": len(self.territories),
            "n_dates": len(self.dates),
            "date_range": (min(self.dates), max(self.dates)) if self.dates else None,
            "feature_names": self.feature_names,
            "territories": self.territories,
            "has_labels": self.labels is not None,
            "label_names": self.label_names,
            "memory_usage_mb": (self.features.memory_usage(deep=True).sum() / 1024 / 1024).round(2),
        }

    def __repr__(self) -> str:
        info = self.info()
        return (
            f"TerritorialDataset(\n"
            f"  samples: {info['n_samples']}, features: {info['n_features']}, "
            f"territories: {info['n_territories']}\n"
            f"  date_range: {info['date_range']}\n"
            f"  has_labels: {info['has_labels']}\n"
            f"  memory: {info['memory_usage_mb']} MB\n"
            f")"
        )
