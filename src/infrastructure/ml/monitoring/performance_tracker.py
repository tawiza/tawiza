"""
Performance tracker for monitoring model metrics over time.
"""

from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class PerformanceTracker:
    """Tracks model performance metrics over time."""

    def __init__(self, model_id: str):
        """
        Initialize performance tracker.

        Args:
            model_id: ID of the model to track
        """
        self.model_id = model_id
        self.metrics_history: list[dict[str, Any]] = []

    def record_metrics(
        self,
        timestamp: datetime,
        accuracy: float,
        precision: float,
        recall: float,
        f1_score: float,
        total_predictions: int,
        errors: int,
    ) -> None:
        """
        Record metrics at a specific timestamp.

        Args:
            timestamp: When metrics were recorded
            accuracy: Model accuracy
            precision: Model precision
            recall: Model recall
            f1_score: Model F1 score
            total_predictions: Total predictions made
            errors: Number of errors
        """
        metrics = {
            "timestamp": timestamp,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "total_predictions": total_predictions,
            "errors": errors,
            "error_rate": errors / total_predictions if total_predictions > 0 else 0,
        }

        self.metrics_history.append(metrics)

        logger.debug(
            f"Recorded metrics for {self.model_id} at {timestamp}: "
            f"acc={accuracy:.2%}, errors={errors}"
        )

    def detect_degradation(
        self,
        metric: str,
        threshold: float,
        window_days: int = 7,
    ) -> dict[str, Any]:
        """
        Detect performance degradation.

        Args:
            metric: Metric to check (e.g., "accuracy")
            threshold: Minimum acceptable value
            window_days: Number of days to look back

        Returns:
            Degradation detection result
        """
        if not self.metrics_history:
            return {
                "is_degraded": False,
                "reason": "No metrics history",
            }

        # Get recent metrics
        cutoff_date = datetime.now() - timedelta(days=window_days)
        recent_metrics = [
            m for m in self.metrics_history
            if m["timestamp"] >= cutoff_date
        ]

        if not recent_metrics:
            return {
                "is_degraded": False,
                "reason": "No recent metrics",
            }

        # Get current value (latest metric)
        current_value = recent_metrics[-1].get(metric)

        if current_value is None:
            return {
                "is_degraded": False,
                "reason": f"Metric {metric} not found",
            }

        # Check if degraded
        is_degraded = current_value < threshold

        result = {
            "is_degraded": is_degraded,
            "current_value": current_value,
            "threshold": threshold,
            "metric": metric,
            "window_days": window_days,
        }

        if is_degraded:
            logger.warning(
                f"Performance degradation detected for {self.model_id}: "
                f"{metric}={current_value:.2%} < {threshold:.2%}"
            )

        return result

    def get_trend(
        self,
        metric: str,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """
        Get trend for a metric over time.

        Args:
            metric: Metric to analyze
            window_days: Number of days to analyze

        Returns:
            Trend analysis
        """
        cutoff_date = datetime.now() - timedelta(days=window_days)
        recent_metrics = [
            m for m in self.metrics_history
            if m["timestamp"] >= cutoff_date and metric in m
        ]

        if len(recent_metrics) < 2:
            return {
                "trend": "unknown",
                "reason": "Insufficient data",
            }

        values = [m[metric] for m in recent_metrics]

        # Simple trend detection
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_second > avg_first * 1.05:
            trend = "improving"
        elif avg_second < avg_first * 0.95:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "avg_first_half": avg_first,
            "avg_second_half": avg_second,
            "change_percent": ((avg_second - avg_first) / avg_first) * 100,
        }
