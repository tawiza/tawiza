"""
Alpha expression operators adapted from Microsoft QLib.

This module provides the building blocks for creating alpha factors
in territorial intelligence. Each operator is a pure function that
operates on pandas Series or DataFrames with MultiIndex (date, territory).

Adapted from: https://github.com/microsoft/qlib/blob/main/qlib/data/ops.py
License: MIT
"""

import numpy as np
import pandas as pd
from typing import Union, Optional, Any
from scipy.stats import rankdata
import warnings

# Type aliases
Series = pd.Series
DataFrame = pd.DataFrame
Numeric = Union[int, float]


def _ensure_series(data: Union[Series, DataFrame]) -> Series:
    """Ensure input is a pandas Series."""
    if isinstance(data, DataFrame):
        if len(data.columns) == 1:
            return data.iloc[:, 0]
        else:
            raise ValueError("DataFrame must have exactly one column")
    return data


def _rolling_window(series: Series, window: int) -> pd.core.window.rolling.Rolling:
    """Create a rolling window, handling MultiIndex properly."""
    if isinstance(series.index, pd.MultiIndex):
        # Group by territory (second level), then roll
        return series.groupby(level=1).rolling(window, min_periods=1)
    else:
        return series.rolling(window, min_periods=1)


# Core temporal operators
def Ref(data: Union[Series, DataFrame], n: int) -> Series:
    """
    Reference: value n periods ago.
    
    Args:
        data: Input series
        n: Number of periods to look back (positive integer)
        
    Returns:
        Series with values shifted n periods
        
    Examples:
        Ref($liquidations, 3)  # Liquidations 3 months ago
        Ref($prix_m2, 1)       # Price per m² last month
    """
    series = _ensure_series(data)
    
    if isinstance(series.index, pd.MultiIndex):
        # Shift within each territory group
        return series.groupby(level=1).shift(n)
    else:
        return series.shift(n)


def Mean(data: Union[Series, DataFrame], window: int) -> Series:
    """
    Moving average over n periods.
    
    Args:
        data: Input series
        window: Window size for moving average
        
    Returns:
        Rolling mean series
        
    Examples:
        Mean($offres_emploi, 3)    # 3-month MA of job offers
        Mean($liquidations, 6)     # 6-month MA of liquidations
    """
    series = _ensure_series(data)
    return _rolling_window(series, window).mean()


def Std(data: Union[Series, DataFrame], window: int) -> Series:
    """
    Moving standard deviation over n periods.
    
    Args:
        data: Input series
        window: Window size
        
    Returns:
        Rolling standard deviation
        
    Examples:
        Std($prix_m2, 12)     # Price volatility over 12 months
        Std($creation_entreprise, 6)  # Business creation volatility
    """
    series = _ensure_series(data)
    return _rolling_window(series, window).std()


def Max(data: Union[Series, DataFrame], window: int) -> Series:
    """
    Rolling maximum over n periods.
    
    Args:
        data: Input series
        window: Window size
        
    Returns:
        Rolling maximum
    """
    series = _ensure_series(data)
    return _rolling_window(series, window).max()


def Min(data: Union[Series, DataFrame], window: int) -> Series:
    """
    Rolling minimum over n periods.
    
    Args:
        data: Input series
        window: Window size
        
    Returns:
        Rolling minimum
    """
    series = _ensure_series(data)
    return _rolling_window(series, window).min()


def Delta(data: Union[Series, DataFrame], n: int) -> Series:
    """
    Absolute change over n periods.
    
    Args:
        data: Input series
        n: Number of periods
        
    Returns:
        Absolute change: data - Ref(data, n)
        
    Examples:
        Delta($offres_emploi, 6)    # Change in job offers over 6 months
        Delta($population, 12)      # Population change over 12 months
    """
    series = _ensure_series(data)
    return series - Ref(series, n)


def ROC(data: Union[Series, DataFrame], n: int) -> Series:
    """
    Rate of Change (relative change) over n periods.
    
    Args:
        data: Input series
        n: Number of periods
        
    Returns:
        Relative change: (data - Ref(data, n)) / (Ref(data, n) + 1e-6)
        
    Examples:
        ROC($transactions_immobilieres, 6)  # Real estate momentum
        ROC($creation_entreprise, 3)        # Business creation growth
    """
    series = _ensure_series(data)
    ref_value = Ref(series, n)
    return (series - ref_value) / (ref_value + 1e-6)  # Avoid division by zero


def Rank(data: Union[Series, DataFrame], method: str = 'average') -> Series:
    """
    Cross-sectional rank among territories.
    
    Args:
        data: Input series
        method: Ranking method ('average', 'min', 'max', 'first', 'dense')
        
    Returns:
        Normalized ranks between 0 and 1
        
    Examples:
        Rank($prix_m2)           # Rank departments by price per m²
        Rank($dynamisme_score)   # Rank by dynamism score
    """
    series = _ensure_series(data)
    
    if isinstance(series.index, pd.MultiIndex):
        # Rank within each date group
        def rank_group(group):
            if group.isna().all():
                return group
            return pd.Series(
                rankdata(group, method=method, nan_policy='omit') / len(group.dropna()),
                index=group.index
            )
        
        return series.groupby(level=0).apply(rank_group)
    else:
        # Simple ranking
        ranks = rankdata(series, method=method, nan_policy='omit')
        return pd.Series(ranks / len(series.dropna()), index=series.index)


def Corr(data1: Union[Series, DataFrame], data2: Union[Series, DataFrame], 
         window: int) -> Series:
    """
    Rolling correlation between two series.
    
    Args:
        data1: First series
        data2: Second series
        window: Window size for correlation
        
    Returns:
        Rolling correlation coefficient
        
    Examples:
        Corr($liquidations, $creation_entreprise, 6)  # Health correlation
        Corr($offres_emploi, $prix_m2, 12)           # Employment-housing correlation
    """
    series1 = _ensure_series(data1)
    series2 = _ensure_series(data2)
    
    if isinstance(series1.index, pd.MultiIndex):
        # Correlation within each territory
        def corr_group(group):
            s1 = group[series1.name] if series1.name else group.iloc[:, 0]
            s2 = group[series2.name] if series2.name else group.iloc[:, 1]
            return s1.rolling(window, min_periods=2).corr(s2)
        
        combined = pd.concat([series1, series2], axis=1)
        return combined.groupby(level=1).apply(corr_group).droplevel(0)
    else:
        return series1.rolling(window, min_periods=2).corr(series2)


# Territorial-specific operators
def PerCapita(data: Union[Series, DataFrame], 
              population: Optional[pd.Series] = None,
              per_n: int = 10000) -> Series:
    """
    Normalize by population (per 10k inhabitants).
    
    Args:
        data: Input series
        population: Population data per territory
        per_n: Scale factor (default: per 10,000 inhabitants)
        
    Returns:
        Population-normalized series
        
    Examples:
        PerCapita($liquidations)     # Liquidations per 10k inhabitants
        PerCapita($creation_entreprise)  # Business creation rate
    """
    series = _ensure_series(data)
    
    if population is None:
        # Try to load from our population module
        try:
            from ..population import get_population_data
            population = get_population_data()
        except ImportError:
            warnings.warn("Population data not available. Using raw values.")
            return series
    
    if isinstance(series.index, pd.MultiIndex):
        # Map population by department code
        def normalize_group(group):
            dept_code = group.index.get_level_values(1)[0]
            pop = population.get(dept_code, 1)  # Default to 1 to avoid division by zero
            return group / pop * per_n
        
        return series.groupby(level=1).apply(normalize_group)
    else:
        # Assume index contains department codes
        pop_mapped = series.index.map(population).fillna(1)
        return series / pop_mapped * per_n


def CSZScore(data: Union[Series, DataFrame]) -> Series:
    """
    Cross-sectional Z-score normalization.
    
    Args:
        data: Input series
        
    Returns:
        Z-score normalized series (mean=0, std=1 within each time period)
        
    Examples:
        CSZScore($prix_m2)         # Normalized price levels across departments
        CSZScore($dynamisme_score) # Normalized dynamism scores
    """
    series = _ensure_series(data)
    
    if isinstance(series.index, pd.MultiIndex):
        # Z-score within each date
        def zscore_group(group):
            if len(group.dropna()) < 2:
                return group
            mean = group.mean()
            std = group.std()
            if std == 0:
                return pd.Series(0, index=group.index)
            return (group - mean) / std
        
        return series.groupby(level=0).apply(zscore_group)
    else:
        # Simple z-score
        return (series - series.mean()) / series.std()


def CSRank(data: Union[Series, DataFrame]) -> Series:
    """
    Cross-sectional rank (alias for Rank for QLib compatibility).
    
    Args:
        data: Input series
        
    Returns:
        Normalized ranks between 0 and 1
    """
    return Rank(data)


def Slope(data: Union[Series, DataFrame], window: int) -> Series:
    """
    Linear regression slope over n periods.
    
    Args:
        data: Input series
        window: Window size for regression
        
    Returns:
        Rolling linear trend slope
        
    Examples:
        Slope($liquidations, 6)    # Liquidation trend over 6 months
        Slope($offres_emploi, 12)  # Employment trend over 12 months
    """
    series = _ensure_series(data)
    
    def calc_slope(window_data):
        """Calculate slope of linear regression."""
        if len(window_data.dropna()) < 2:
            return np.nan
        
        y = window_data.dropna().values
        x = np.arange(len(y))
        
        if len(y) < 2:
            return np.nan
            
        # Simple linear regression: slope = cov(x,y) / var(x)
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        
        cov_xy = np.mean((x - mean_x) * (y - mean_y))
        var_x = np.mean((x - mean_x) ** 2)
        
        if var_x == 0:
            return 0
        
        return cov_xy / var_x
    
    if isinstance(series.index, pd.MultiIndex):
        # Slope within each territory
        return series.groupby(level=1).rolling(window, min_periods=2).apply(calc_slope)
    else:
        return series.rolling(window, min_periods=2).apply(calc_slope)


# Convenience functions for common patterns
def Momentum(data: Union[Series, DataFrame], short: int = 3, long: int = 12) -> Series:
    """
    Momentum factor: ratio of short MA to long MA.
    
    Args:
        data: Input series
        short: Short moving average window
        long: Long moving average window
        
    Returns:
        Momentum indicator (short_MA / long_MA)
        
    Examples:
        Momentum($logements_autorises, 3, 12)  # Construction momentum
        Momentum($creation_entreprise, 1, 6)   # Business creation momentum
    """
    short_ma = Mean(data, short)
    long_ma = Mean(data, long)
    return short_ma / (long_ma + 1e-6)


def Volatility(data: Union[Series, DataFrame], window: int = 6) -> Series:
    """
    Volatility indicator: coefficient of variation.
    
    Args:
        data: Input series
        window: Window size for calculation
        
    Returns:
        Volatility (std / mean)
    """
    mean_val = Mean(data, window)
    std_val = Std(data, window)
    return std_val / (mean_val + 1e-6)


def HealthRatio(liquidations: Union[Series, DataFrame], 
                creations: Union[Series, DataFrame]) -> Series:
    """
    Business health ratio: liquidations / (creations + 1).
    
    Args:
        liquidations: Liquidation series
        creations: Business creation series
        
    Returns:
        Health ratio (lower is better)
    """
    liq = _ensure_series(liquidations)
    crea = _ensure_series(creations)
    return liq / (crea + 1)


# Expression evaluator (simplified)
def evaluate_expression(expression: str, data: DataFrame) -> Series:
    """
    Evaluate a simple alpha expression.
    
    Args:
        expression: Alpha expression string (e.g., "$liquidations / ($creations + 1)")
        data: DataFrame with columns for each metric
        
    Returns:
        Evaluated expression result
        
    Note:
        This is a simplified evaluator. Production code should use a proper
        expression parser for security and robustness.
    """
    # Replace $ variables with column access
    import re
    
    # Find all $variable references
    variables = re.findall(r'\$(\w+)', expression)
    
    # Build evaluation context
    context = {}
    for var in variables:
        if var in data.columns:
            context[var] = data[var]
        else:
            warnings.warn(f"Variable ${var} not found in data columns")
            context[var] = pd.Series(0, index=data.index)
    
    # Add operator functions to context
    context.update({
        'Mean': Mean,
        'Ref': Ref,
        'Std': Std,
        'Rank': Rank,
        'Delta': Delta,
        'ROC': ROC,
        'Max': Max,
        'Min': Min,
        'Corr': Corr,
        'PerCapita': PerCapita,
        'CSZScore': CSZScore,
        'CSRank': CSRank,
        'Slope': Slope,
        'Momentum': Momentum,
        'Volatility': Volatility,
        'HealthRatio': HealthRatio,
    })
    
    # Replace $variables with context access
    eval_expr = expression
    for var in variables:
        eval_expr = eval_expr.replace(f'${var}', f'context["{var}"]')
    
    try:
        # Note: In production, use a safe expression evaluator like simpleeval
        result = eval(eval_expr, {"__builtins__": {}, "context": context}, context)
        return result
    except Exception as e:
        warnings.warn(f"Expression evaluation failed: {e}")
        return pd.Series(np.nan, index=data.index)