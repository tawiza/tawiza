"""
Data processors adapted from Microsoft QLib.

This module provides chainable data transformers for territorial intelligence,
similar to scikit-learn transformers but optimized for time series data
with MultiIndex (date, territory).

Adapted from: https://github.com/microsoft/qlib/blob/main/qlib/data/dataset/processor.py
License: MIT
"""

import warnings
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from scipy.stats import median_abs_deviation
from sklearn.preprocessing import MinMaxScaler


class Processor(ABC):
    """Base class for all data processors."""

    @abstractmethod
    def fit(self, data: pd.DataFrame) -> "Processor":
        """Fit the processor to data."""
        pass

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform the data."""
        pass

    def fit_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform in one step."""
        return self.fit(data).transform(data)

    def __call__(self, data: pd.DataFrame) -> pd.DataFrame:
        """Make processor callable."""
        return self.transform(data)


class DropnaProcessor(Processor):
    """
    Drop rows with NaN values.

    Args:
        fields: Specific fields to check for NaN (default: all fields)
    """

    def __init__(self, fields: list[str] | None = None):
        self.fields = fields

    def fit(self, data: pd.DataFrame) -> "DropnaProcessor":
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        if self.fields is not None:
            available_fields = [f for f in self.fields if f in data.columns]
            if available_fields:
                return data.dropna(subset=available_fields)
        return data.dropna()


class FillnaProcessor(Processor):
    """
    Fill NaN values with specified method.

    Args:
        fields: Fields to fill (default: all numeric fields)
        fill_value: Value to fill with (default: 0)
        method: Fill method ('ffill', 'bfill', 'value')
    """

    def __init__(
        self, fill_value: float | int = 0, method: str = "value", fields: list[str] | None = None
    ):
        self.fill_value = fill_value
        self.method = method
        self.fields = fields

    def fit(self, data: pd.DataFrame) -> "FillnaProcessor":
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        if not fields_to_process:
            return result

        if isinstance(data.index, pd.MultiIndex):
            # Handle MultiIndex by grouping by territory
            for field in fields_to_process:
                if self.method == "ffill":
                    result[field] = data.groupby(level=1)[field].fillna(method="ffill")
                elif self.method == "bfill":
                    result[field] = data.groupby(level=1)[field].fillna(method="bfill")
                else:  # value
                    result[field] = data[field].fillna(self.fill_value)
        else:
            # Simple fillna
            for field in fields_to_process:
                if self.method == "ffill":
                    result[field] = data[field].fillna(method="ffill")
                elif self.method == "bfill":
                    result[field] = data[field].fillna(method="bfill")
                else:  # value
                    result[field] = data[field].fillna(self.fill_value)

        return result


class ZScoreProcessor(Processor):
    """
    Z-score normalization processor.

    Args:
        fields: Fields to normalize (default: all numeric fields)
        method: 'global' (across all data) or 'rolling' (rolling window)
        window: Window size for rolling method
    """

    def __init__(
        self, fields: list[str] | None = None, method: str = "global", window: int | None = None
    ):
        self.fields = fields
        self.method = method
        self.window = window
        self.stats_ = {}

    def fit(self, data: pd.DataFrame) -> "ZScoreProcessor":
        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        if self.method == "global":
            # Calculate global statistics
            for field in fields_to_process:
                self.stats_[field] = {"mean": data[field].mean(), "std": data[field].std()}

        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        for field in fields_to_process:
            if self.method == "global":
                # Use fitted statistics
                mean = self.stats_[field]["mean"]
                std = self.stats_[field]["std"]
                if std > 0:
                    result[field] = (data[field] - mean) / std
                else:
                    result[field] = 0

            elif self.method == "rolling" and self.window:
                # Rolling z-score
                if isinstance(data.index, pd.MultiIndex):
                    # Rolling by territory
                    def rolling_zscore(group):
                        rolling = group.rolling(self.window, min_periods=1)
                        mean = rolling.mean()
                        std = rolling.std()
                        return (group - mean) / (std + 1e-8)

                    result[field] = data.groupby(level=1)[field].apply(rolling_zscore)
                else:
                    rolling = data[field].rolling(self.window, min_periods=1)
                    mean = rolling.mean()
                    std = rolling.std()
                    result[field] = (data[field] - mean) / (std + 1e-8)

        return result


class RobustZScoreProcessor(Processor):
    """
    Robust Z-score normalization using median and MAD.

    More robust to outliers than standard z-score.

    Args:
        fields: Fields to normalize
        method: 'global' or 'rolling'
        window: Window size for rolling method
    """

    def __init__(
        self, fields: list[str] | None = None, method: str = "global", window: int | None = None
    ):
        self.fields = fields
        self.method = method
        self.window = window
        self.stats_ = {}

    def fit(self, data: pd.DataFrame) -> "RobustZScoreProcessor":
        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        if self.method == "global":
            for field in fields_to_process:
                clean_data = data[field].dropna()
                self.stats_[field] = {
                    "median": clean_data.median(),
                    "mad": median_abs_deviation(clean_data, nan_policy="omit"),
                }

        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        for field in fields_to_process:
            if self.method == "global":
                # Use fitted statistics
                median = self.stats_[field]["median"]
                mad = self.stats_[field]["mad"]
                if mad > 0:
                    result[field] = (data[field] - median) / mad
                else:
                    result[field] = 0

            elif self.method == "rolling" and self.window:
                # Rolling robust z-score
                if isinstance(data.index, pd.MultiIndex):
                    # Rolling by territory
                    def rolling_robust_zscore(group):
                        def calc_robust_zscore(window_data):
                            if len(window_data.dropna()) < 2:
                                return window_data.iloc[-1]  # Return last value if not enough data
                            median = window_data.median()
                            mad = median_abs_deviation(window_data.dropna())
                            if mad > 0:
                                return (window_data.iloc[-1] - median) / mad
                            return 0

                        return group.rolling(self.window, min_periods=1).apply(calc_robust_zscore)

                    result[field] = data.groupby(level=1)[field].apply(rolling_robust_zscore)
                else:

                    def calc_robust_zscore(window_data):
                        if len(window_data.dropna()) < 2:
                            return window_data.iloc[-1]
                        median = window_data.median()
                        mad = median_abs_deviation(window_data.dropna())
                        if mad > 0:
                            return (window_data.iloc[-1] - median) / mad
                        return 0

                    result[field] = (
                        data[field].rolling(self.window, min_periods=1).apply(calc_robust_zscore)
                    )

        return result


class MinMaxProcessor(Processor):
    """
    Min-Max normalization to [0, 1] range.

    Args:
        fields: Fields to normalize
        feature_range: Target range (default: (0, 1))
    """

    def __init__(
        self, fields: list[str] | None = None, feature_range: tuple[float, float] = (0, 1)
    ):
        self.fields = fields
        self.feature_range = feature_range
        self.scalers_ = {}

    def fit(self, data: pd.DataFrame) -> "MinMaxProcessor":
        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        for field in fields_to_process:
            clean_data = data[field].dropna()
            if len(clean_data) > 0:
                scaler = MinMaxScaler(feature_range=self.feature_range)
                scaler.fit(clean_data.values.reshape(-1, 1))
                self.scalers_[field] = scaler

        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        for field, scaler in self.scalers_.items():
            if field in data.columns:
                # Handle NaN values
                mask = data[field].notna()
                if mask.any():
                    result.loc[mask, field] = scaler.transform(
                        data.loc[mask, field].values.reshape(-1, 1)
                    ).flatten()

        return result


class PopulationNormalizer(Processor):
    """
    Normalize metrics by population (per 10k inhabitants).

    Args:
        population_data: DataFrame or dict with population per territory
        per_n: Scale factor (default: 10000)
        fields: Fields to normalize (default: count-based metrics)
    """

    def __init__(
        self,
        population_data: pd.DataFrame | dict,
        per_n: int = 10000,
        fields: list[str] | None = None,
    ):
        self.population_data = population_data
        self.per_n = per_n
        self.fields = fields

        # Convert to dict for easier lookup
        if isinstance(population_data, pd.DataFrame):
            if "code_dept" in population_data.columns and "population" in population_data.columns:
                self.pop_dict = dict(
                    zip(population_data["code_dept"], population_data["population"], strict=False)
                )
            else:
                # Assume index is territory and first column is population
                self.pop_dict = population_data.iloc[:, 0].to_dict()
        else:
            self.pop_dict = population_data

    def fit(self, data: pd.DataFrame) -> "PopulationNormalizer":
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        # Select fields to normalize
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            # Default: normalize count-based metrics
            count_fields = [
                "liquidations",
                "liquidation_judiciaire",
                "creation_entreprise",
                "fermeture_entreprise",
                "offres_emploi",
                "logements_autorises",
                "transactions_immobilieres",
                "vente_fonds_commerce",
            ]
            fields_to_process = [f for f in data.columns if any(cf in f for cf in count_fields)]

        if isinstance(data.index, pd.MultiIndex):
            # MultiIndex: get territory from level 1
            for field in fields_to_process:
                # Get the territory codes for mapping
                territory_codes = data.index.get_level_values(1)
                pop_series = territory_codes.map(self.pop_dict).fillna(1)
                result[field] = data[field] / pop_series * self.per_n
        else:
            # Simple index: assume index contains territory codes
            for field in fields_to_process:
                pop_series = data.index.map(self.pop_dict).fillna(1)
                result[field] = data[field] / pop_series * self.per_n

        return result


class SeasonalDecompProcessor(Processor):
    """
    Seasonal decomposition processor.

    Args:
        fields: Fields to deseasonalize
        period: Seasonal period (default: 12 for monthly data)
        method: 'additive' or 'multiplicative'
    """

    def __init__(self, fields: list[str] | None = None, period: int = 12, method: str = "additive"):
        self.fields = fields
        self.period = period
        self.method = method

    def fit(self, data: pd.DataFrame) -> "SeasonalDecompProcessor":
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()

        try:
            from statsmodels.tsa.seasonal import seasonal_decompose
        except ImportError:
            warnings.warn(
                "statsmodels not available. Skipping seasonal decomposition.", stacklevel=2
            )
            return result

        # Select fields to process
        if self.fields is not None:
            fields_to_process = [f for f in self.fields if f in data.columns]
        else:
            fields_to_process = data.select_dtypes(include=[np.number]).columns.tolist()

        if isinstance(data.index, pd.MultiIndex):
            # Decompose within each territory
            for field in fields_to_process:

                def deseasonalize(group):
                    if len(group.dropna()) < self.period * 2:  # Need enough data
                        return group  # Return original if not enough data

                    try:
                        decomposition = seasonal_decompose(
                            group.dropna(),
                            model=self.method,
                            period=self.period,
                            extrapolate_trend="freq",
                        )
                        # Return trend + residual (without seasonal component)
                        return decomposition.trend + decomposition.resid
                    except Exception:
                        return group  # Return original on error

                result[f"{field}_deseasonalized"] = data.groupby(level=1)[field].apply(
                    deseasonalize
                )

        return result


class ProcessorChain:
    """
    Chain multiple processors together.

    Args:
        processors: List of processors to chain
    """

    def __init__(self, processors: list[Processor]):
        self.processors = processors

    def fit(self, data: pd.DataFrame) -> "ProcessorChain":
        """Fit all processors sequentially."""
        current_data = data
        for processor in self.processors:
            processor.fit(current_data)
            current_data = processor.transform(current_data)
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data through all processors."""
        result = data
        for processor in self.processors:
            result = processor.transform(result)
        return result

    def fit_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform in one step."""
        return self.fit(data).transform(data)

    def add_processor(self, processor: Processor):
        """Add a processor to the chain."""
        self.processors.append(processor)

    def __len__(self):
        return len(self.processors)

    def __getitem__(self, index):
        return self.processors[index]


# Convenience functions
def create_standard_chain(
    population_data: pd.DataFrame | dict | None = None, robust: bool = True
) -> ProcessorChain:
    """
    Create a standard processing chain for territorial data.

    Args:
        population_data: Population data for normalization
        robust: Use robust statistics if True

    Returns:
        Configured ProcessorChain
    """
    processors = [
        FillnaProcessor(fill_value=0, method="ffill"),  # Fill NaN with forward fill then 0
    ]

    if population_data is not None:
        processors.append(PopulationNormalizer(population_data))

    if robust:
        processors.append(RobustZScoreProcessor())
    else:
        processors.append(ZScoreProcessor())

    return ProcessorChain(processors)


def create_inference_chain(population_data: pd.DataFrame | dict | None = None) -> ProcessorChain:
    """
    Create a processing chain optimized for inference (real-time processing).

    Args:
        population_data: Population data for normalization

    Returns:
        ProcessorChain optimized for inference
    """
    return ProcessorChain(
        [
            FillnaProcessor(fill_value=0),
            PopulationNormalizer(population_data)
            if population_data is not None
            else FillnaProcessor(fill_value=0),
            RobustZScoreProcessor(method="rolling", window=6),  # Rolling normalization
        ]
    )
