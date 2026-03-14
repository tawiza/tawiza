"""Temporal analysis for Tawiza-V2 signals - Phase 3 of the algorithm.

Moving averages, rate of change, and cross-source lag correlations.
Inspired by quantitative finance techniques adapted to territorial intelligence.
"""

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import pearsonr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class TemporalAnalyzer:
    """Temporal analysis of territorial signals."""

    def __init__(self, database_url: str):
        """Initialize with database connection.

        Args:
            database_url: PostgreSQL URL for collector database
        """
        self.database_url = database_url
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)


async def compute_moving_averages(
    db_url: str, dept: str, metric_name: str, windows: list[int] | None = None
) -> dict[str, Any]:
    """Compute moving averages over N months for a metric in a department.

    Args:
        db_url: Database connection URL
        dept: Department code (e.g., '59')
        metric_name: Name of the metric to analyze
        windows: List of window sizes in months

    Returns:
        Dict with moving averages and crossover signals:
        {
            'moving_averages': {window_months: average_value},
            'crossovers': [{'type': 'golden_cross'/'death_cross', 'date': '...'}],
            'current_trend': 'bullish'/'bearish'/'neutral'
        }
    """
    if windows is None:
        windows = [3, 6, 12]
    logger.info(f"Computing moving averages for {dept} - {metric_name}")

    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.begin() as conn:
            # Query signals grouped by month
            query = text("""
                SELECT
                    DATE_TRUNC('month', event_date) as month,
                    COUNT(*) as signal_count,
                    AVG(metric_value) as avg_value,
                    SUM(metric_value) as total_value
                FROM signals
                WHERE code_dept = :dept
                    AND metric_name = :metric_name
                    AND event_date IS NOT NULL
                    AND event_date >= CURRENT_DATE - INTERVAL '24 months'
                GROUP BY DATE_TRUNC('month', event_date)
                ORDER BY month ASC
            """)

            result = await conn.execute(query, {"dept": dept, "metric_name": metric_name})
            rows = result.fetchall()

            if len(rows) < max(windows):
                logger.warning(
                    f"Not enough data for {dept} - {metric_name}: {len(rows)} months, need {max(windows)}"
                )
                return {
                    "moving_averages": {},
                    "crossovers": [],
                    "current_trend": "insufficient_data",
                    "data_points": len(rows),
                }

            # Convert to pandas for easier manipulation
            df = pd.DataFrame(rows, columns=["month", "signal_count", "avg_value", "total_value"])
            df["month"] = pd.to_datetime(df["month"])
            df = df.set_index("month").sort_index()

            # Compute moving averages
            mas = {}
            for window in windows:
                if len(df) >= window:
                    ma = df["total_value"].rolling(window=window).mean()
                    mas[f"MA{window}"] = ma.iloc[-1] if not pd.isna(ma.iloc[-1]) else None
                else:
                    mas[f"MA{window}"] = None

            # Detect crossovers (golden cross: MA3 > MA12, death cross: MA3 < MA12)
            crossovers = []
            current_trend = "neutral"

            if mas.get("MA3") is not None and mas.get("MA12") is not None:
                ma3 = mas["MA3"]
                ma12 = mas["MA12"]

                if ma3 > ma12 * 1.05:  # 5% threshold to avoid noise
                    current_trend = "bullish"
                    # Check if this is a recent cross
                    if len(df) >= 13:
                        ma3_prev = df["total_value"].rolling(window=3).mean().iloc[-2]
                        ma12_prev = df["total_value"].rolling(window=12).mean().iloc[-2]
                        if ma3_prev <= ma12_prev and ma3 > ma12:
                            crossovers.append(
                                {
                                    "type": "golden_cross",
                                    "date": df.index[-1].strftime("%Y-%m-%d"),
                                    "ma3": ma3,
                                    "ma12": ma12,
                                }
                            )
                elif ma3 < ma12 * 0.95:
                    current_trend = "bearish"
                    # Check if this is a recent cross
                    if len(df) >= 13:
                        ma3_prev = df["total_value"].rolling(window=3).mean().iloc[-2]
                        ma12_prev = df["total_value"].rolling(window=12).mean().iloc[-2]
                        if ma3_prev >= ma12_prev and ma3 < ma12:
                            crossovers.append(
                                {
                                    "type": "death_cross",
                                    "date": df.index[-1].strftime("%Y-%m-%d"),
                                    "ma3": ma3,
                                    "ma12": ma12,
                                }
                            )

            return {
                "moving_averages": mas,
                "crossovers": crossovers,
                "current_trend": current_trend,
                "data_points": len(rows),
                "latest_month": df.index[-1].strftime("%Y-%m-%d") if len(df) > 0 else None,
            }

    except Exception as e:
        logger.error(f"Error computing moving averages for {dept}-{metric_name}: {e}")
        return {"moving_averages": {}, "crossovers": [], "current_trend": "error", "error": str(e)}
    finally:
        await engine.dispose()


async def compute_rate_of_change(
    db_url: str, dept: str, periods: list[int] | None = None
) -> dict[str, dict[str, float | None]]:
    """Compute rate of change over N months for all metrics in a department.

    Args:
        db_url: Database connection URL
        dept: Department code
        periods: List of periods in months for ROC calculation

    Returns:
        Dict: {metric_name: {period: roc_value, 'alert': bool}}
        ROC = (current - N_months_ago) / N_months_ago
    """
    if periods is None:
        periods = [3, 6]
    logger.info(f"Computing rate of change for department {dept}")

    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.begin() as conn:
            # Get all metrics for this department
            query = text("""
                SELECT
                    metric_name,
                    DATE_TRUNC('month', event_date) as month,
                    SUM(metric_value) as total_value
                FROM signals
                WHERE code_dept = :dept
                    AND event_date IS NOT NULL
                    AND event_date >= CURRENT_DATE - INTERVAL '18 months'
                GROUP BY metric_name, DATE_TRUNC('month', event_date)
                ORDER BY metric_name, month ASC
            """)

            result = await conn.execute(query, {"dept": dept})
            rows = result.fetchall()

            if not rows:
                logger.warning(f"No data for department {dept}")
                return {}

            # Group by metric
            metrics_data = defaultdict(list)
            for row in rows:
                metrics_data[row.metric_name].append(
                    {"month": row.month, "total_value": float(row.total_value)}
                )

            roc_results = {}

            for metric_name, data in metrics_data.items():
                if len(data) < max(periods) + 1:
                    roc_results[metric_name] = {f"ROC_{p}m": None for p in periods}
                    roc_results[metric_name]["alert"] = False
                    continue

                # Convert to DataFrame for easier calculation
                df = pd.DataFrame(data)
                df["month"] = pd.to_datetime(df["month"])
                df = df.set_index("month").sort_index()

                rocs = {}
                max_roc = 0

                for period in periods:
                    if len(df) >= period + 1:
                        current = df["total_value"].iloc[-1]
                        past = df["total_value"].iloc[-(period + 1)]

                        if past != 0:
                            roc = (current - past) / past
                            rocs[f"ROC_{period}m"] = roc
                            max_roc = max(max_roc, abs(roc))
                        else:
                            rocs[f"ROC_{period}m"] = None
                    else:
                        rocs[f"ROC_{period}m"] = None

                # Flag departments with ROC > 50% as alert (especially for negative metrics like liquidations)
                alert = max_roc > 0.5
                if "liquidation" in metric_name.lower() or "fermeture" in metric_name.lower():
                    # For negative metrics, high positive ROC is bad
                    rocs["alert"] = alert
                else:
                    # For positive metrics, high negative ROC is bad
                    rocs["alert"] = alert

                roc_results[metric_name] = rocs

            return roc_results

    except Exception as e:
        logger.error(f"Error computing ROC for {dept}: {e}")
        return {}
    finally:
        await engine.dispose()


async def compute_lag_correlations(
    db_url: str, source_pairs: list[tuple[str, str]] | None = None
) -> dict[str, dict[str, float]]:
    """Compute cross-correlations between sources with time lag.

    Args:
        db_url: Database connection URL
        source_pairs: List of (source1, source2) tuples to analyze

    Returns:
        Dict: {pair_name: {lag_months: correlation}}

    Known lags to test:
    - presse "plan social" → +2 months → BODACC liquidations
    - Sitadel chute permis → +6 months → DVF baisse transactions
    - BODACC liquidation → +3 months → France Travail baisse offres
    """
    logger.info("Computing lag correlations between sources")

    if source_pairs is None:
        # Default pairs based on known business relationships
        source_pairs = [
            ("presse_locale", "bodacc"),  # Presse mentions → liquidations
            ("sitadel", "dvf"),  # Building permits → transactions
            ("bodacc", "france_travail"),  # Liquidations → job offers down
            ("sirene", "bodacc"),  # Company creation/closure → liquidations
        ]

    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.begin() as conn:
            correlations = {}

            for source1, source2 in source_pairs:
                pair_name = f"{source1}_vs_{source2}"
                logger.info(f"Analyzing correlation between {source1} and {source2}")

                # Get monthly aggregated data for both sources
                query = text("""
                    WITH monthly_data AS (
                        SELECT
                            source,
                            code_dept,
                            DATE_TRUNC('month', event_date) as month,
                            COUNT(*) as signal_count,
                            SUM(CASE WHEN signal_type = 'negatif' THEN 1 ELSE 0 END) as negative_signals
                        FROM signals
                        WHERE source IN (:source1, :source2)
                            AND event_date IS NOT NULL
                            AND event_date >= CURRENT_DATE - INTERVAL '12 months'
                            AND code_dept IS NOT NULL
                        GROUP BY source, code_dept, DATE_TRUNC('month', event_date)
                    )
                    SELECT * FROM monthly_data ORDER BY month, code_dept, source
                """)

                result = await conn.execute(query, {"source1": source1, "source2": source2})
                rows = result.fetchall()

                if len(rows) < 20:  # Need sufficient data points
                    logger.warning(f"Insufficient data for {pair_name}: {len(rows)} rows")
                    correlations[pair_name] = {"insufficient_data": True}
                    continue

                # Organize data by department and month
                dept_data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

                for row in rows:
                    dept_data[row.code_dept][row.month][row.source] = row.signal_count

                # Calculate correlations with different lags (0 to 6 months)
                lag_correlations = {}
                best_correlation = 0
                best_lag = 0

                for lag in range(0, 7):  # 0 to 6 months lag
                    correlations_this_lag = []

                    for dept, months_data in dept_data.items():
                        source1_values = []
                        source2_values = []

                        sorted_months = sorted(months_data.keys())

                        for i, month in enumerate(sorted_months):
                            if i + lag < len(sorted_months):
                                future_month = sorted_months[i + lag]
                                s1_val = months_data[month].get(source1, 0)
                                s2_val = months_data[future_month].get(source2, 0)

                                if s1_val > 0 or s2_val > 0:  # Avoid all-zero series
                                    source1_values.append(s1_val)
                                    source2_values.append(s2_val)

                        # Calculate correlation for this department
                        if len(source1_values) >= 3:  # Need at least 3 points
                            try:
                                corr, p_value = pearsonr(source1_values, source2_values)
                                if not np.isnan(corr):
                                    correlations_this_lag.append(corr)
                            except Exception as e:
                                logger.debug(f"Correlation error for {dept}: {e}")

                    # Average correlation across departments for this lag
                    if correlations_this_lag:
                        avg_corr = np.mean(correlations_this_lag)
                        lag_correlations[f"lag_{lag}m"] = avg_corr

                        if abs(avg_corr) > abs(best_correlation):
                            best_correlation = avg_corr
                            best_lag = lag
                    else:
                        lag_correlations[f"lag_{lag}m"] = 0.0

                lag_correlations["best_lag_months"] = best_lag
                lag_correlations["best_correlation"] = best_correlation
                lag_correlations["significant"] = abs(best_correlation) > 0.3

                correlations[pair_name] = lag_correlations

            return correlations

    except Exception as e:
        logger.error(f"Error computing lag correlations: {e}")
        return {}
    finally:
        await engine.dispose()
