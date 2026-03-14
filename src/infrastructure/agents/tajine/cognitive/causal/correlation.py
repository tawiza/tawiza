"""
Time series correlation analysis for causal inference.

Uses lagged cross-correlation to detect temporal causality.
"""

import numpy as np
from loguru import logger


def preprocess_series(values: list[float]) -> np.ndarray | None:
    """Preprocess time series: handle NaN, normalize.

    Args:
        values: Raw time series values

    Returns:
        Cleaned numpy array, or None if all values are NaN
    """
    arr = np.array(values, dtype=float)

    # Handle all-NaN case
    if np.all(np.isnan(arr)):
        logger.debug("All values are NaN, cannot compute correlation")
        return None

    # Replace NaN with mean (simple imputation)
    if np.any(np.isnan(arr)):
        mean_val = np.nanmean(arr)
        arr = np.where(np.isnan(arr), mean_val, arr)

    return arr


def compute_lagged_correlation(
    cause_values: list[float], effect_values: list[float], max_lag: int = 6
) -> tuple[float, int]:
    """Compute correlation at different lags to find optimal temporal offset.

    The cause series is shifted backward to test if it predicts the effect.
    A positive lag means the cause precedes the effect (temporal causality).

    Args:
        cause_values: Time series of potential cause
        effect_values: Time series of potential effect
        max_lag: Maximum lag to test (in time units, typically months)

    Returns:
        (best_correlation, optimal_lag) - highest |correlation| and its lag
    """
    cause = preprocess_series(cause_values)
    effect = preprocess_series(effect_values)

    # Handle invalid series (all NaN)
    if cause is None or effect is None:
        logger.debug("Invalid series (all NaN), returning zero correlation")
        return 0.0, 0

    min_len = min(len(cause), len(effect))
    if min_len < 4:  # Need minimum samples for meaningful correlation
        logger.debug(f"Insufficient data for correlation: {min_len} samples")
        return 0.0, 0

    best_corr = 0.0
    best_lag = 0

    for lag in range(max_lag + 1):
        if lag >= min_len - 2:
            break

        # Shift cause backward by lag (cause[:-lag] aligns with effect[lag:])
        if lag == 0:
            c = cause[:min_len]
            e = effect[:min_len]
        else:
            c = cause[: min_len - lag]
            e = effect[lag:min_len]

        if len(c) < 3:
            continue

        # Check for zero variance (constant series)
        if np.std(c) == 0 or np.std(e) == 0:
            logger.debug(f"Constant series at lag={lag}, skipping")
            continue

        # Compute Pearson correlation
        corr = np.corrcoef(c, e)[0, 1]

        if np.isnan(corr):
            continue

        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag

    return float(best_corr), best_lag


def assess_temporal_validity(correlation: float, lag: int) -> float:
    """Assess if the correlation represents valid temporal causality.

    Temporal causality requires:
    1. Strong correlation (|r| > threshold)
    2. Cause precedes effect (lag > 0)

    Args:
        correlation: Correlation coefficient (-1 to 1)
        lag: Temporal lag (positive = cause precedes effect)

    Returns:
        Confidence score 0-1
    """
    # Base confidence from correlation strength
    base_confidence = min(abs(correlation), 1.0)

    # Temporal validity factor
    if lag > 0:
        # Cause precedes effect - good!
        temporal_factor = 1.0
    elif lag == 0:
        # Instantaneous - ambiguous direction
        temporal_factor = 0.6
    else:
        # Effect precedes cause - wrong direction
        temporal_factor = 0.2

    return base_confidence * temporal_factor


def compute_causal_confidence(correlation: float, lag: int, sample_size: int) -> float:
    """Compute overall confidence in causal relationship.

    Combines:
    - Correlation strength
    - Temporal validity (cause precedes effect)
    - Sample size (more data = more confidence)

    Args:
        correlation: Correlation coefficient
        lag: Temporal lag
        sample_size: Number of data points used

    Returns:
        Confidence score 0-1
    """
    temporal_conf = assess_temporal_validity(correlation, lag)

    # Sample size factor (diminishing returns)
    # At 12 samples: 0.8, at 24: 0.9, at 48: 0.95
    sample_factor = min(1.0, 0.5 + 0.5 * (1 - np.exp(-sample_size / 20)))

    confidence = temporal_conf * sample_factor

    return round(float(confidence), 3)
