"""Drift report entity for tracking model performance degradation."""

from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from .base import Entity


class DriftType(StrEnum):
    """Type of drift detected."""

    DATA_DRIFT = "data_drift"  # Input distribution has changed
    CONCEPT_DRIFT = "concept_drift"  # Input-output relationship has changed
    PREDICTION_DRIFT = "prediction_drift"  # Output distribution has changed
    PERFORMANCE_DRIFT = "performance_drift"  # Model accuracy has degraded


class DriftSeverity(StrEnum):
    """Severity level of detected drift."""

    LOW = "low"  # Minor drift, monitoring recommended
    MEDIUM = "medium"  # Moderate drift, investigation needed
    HIGH = "high"  # Significant drift, action required
    CRITICAL = "critical"  # Severe drift, immediate retraining needed


class DriftReport(Entity):
    """Entity representing a drift detection report.

    Tracks when model performance degrades or data distribution changes,
    enabling proactive model updates and quality maintenance.
    """

    def __init__(
        self,
        model_name: str,
        model_version: str,
        drift_type: DriftType,
        metric_name: str,
        current_value: float,
        baseline_value: float,
        drift_score: float,
        is_drifted: bool,
        id: UUID | None = None,
        severity: DriftSeverity | None = None,
        threshold: float | None = None,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
        sample_count: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize drift report entity.

        Args:
            model_name: Name of the model being monitored
            model_version: Version of the model
            drift_type: Type of drift detected
            metric_name: Name of the metric being monitored
            current_value: Current value of the metric
            baseline_value: Baseline (expected) value
            drift_score: Calculated drift score (0-1, higher = more drift)
            is_drifted: Whether drift threshold was exceeded
            id: Optional entity ID
            severity: Severity level of the drift
            threshold: Threshold used for drift detection
            window_start: Start of the monitoring window
            window_end: End of the monitoring window
            sample_count: Number of samples analyzed
            details: Additional details about the drift
        """
        super().__init__(id)
        self._model_name = model_name
        self._model_version = model_version
        self._drift_type = drift_type
        self._metric_name = metric_name
        self._current_value = current_value
        self._baseline_value = baseline_value
        self._drift_score = drift_score
        self._is_drifted = is_drifted
        self._severity = severity or self._calculate_severity(drift_score)
        self._threshold = threshold
        self._window_start = window_start
        self._window_end = window_end
        self._sample_count = sample_count
        self._details = details or {}

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name

    @property
    def model_version(self) -> str:
        """Get the model version."""
        return self._model_version

    @property
    def drift_type(self) -> DriftType:
        """Get the drift type."""
        return self._drift_type

    @property
    def metric_name(self) -> str:
        """Get the metric name."""
        return self._metric_name

    @property
    def current_value(self) -> float:
        """Get the current metric value."""
        return self._current_value

    @property
    def baseline_value(self) -> float:
        """Get the baseline metric value."""
        return self._baseline_value

    @property
    def drift_score(self) -> float:
        """Get the drift score."""
        return self._drift_score

    @property
    def is_drifted(self) -> bool:
        """Check if drift was detected."""
        return self._is_drifted

    @property
    def severity(self) -> DriftSeverity:
        """Get the drift severity."""
        return self._severity

    @property
    def threshold(self) -> float | None:
        """Get the detection threshold."""
        return self._threshold

    @property
    def window_start(self) -> datetime | None:
        """Get the monitoring window start."""
        return self._window_start

    @property
    def window_end(self) -> datetime | None:
        """Get the monitoring window end."""
        return self._window_end

    @property
    def sample_count(self) -> int | None:
        """Get the sample count."""
        return self._sample_count

    @property
    def details(self) -> dict[str, Any]:
        """Get additional details."""
        return self._details.copy()

    def _calculate_severity(self, drift_score: float) -> DriftSeverity:
        """Calculate severity based on drift score.

        Args:
            drift_score: Drift score (0-1)

        Returns:
            Calculated severity level
        """
        if drift_score >= 0.8:
            return DriftSeverity.CRITICAL
        elif drift_score >= 0.5:
            return DriftSeverity.HIGH
        elif drift_score >= 0.3:
            return DriftSeverity.MEDIUM
        else:
            return DriftSeverity.LOW

    def get_deviation_percentage(self) -> float:
        """Calculate percentage deviation from baseline.

        Returns:
            Percentage deviation
        """
        if self._baseline_value == 0:
            return 0.0
        return abs((self._current_value - self._baseline_value) / self._baseline_value) * 100

    def requires_action(self) -> bool:
        """Check if drift requires immediate action.

        Returns:
            True if action is required
        """
        return self._is_drifted and self._severity in [
            DriftSeverity.HIGH,
            DriftSeverity.CRITICAL,
        ]

    def update_details(self, details: dict[str, Any]) -> None:
        """Update report details.

        Args:
            details: New details to merge
        """
        self._details.update(details)
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base = super().to_dict()
        base.update(
            {
                "model_name": self._model_name,
                "model_version": self._model_version,
                "drift_type": self._drift_type.value,
                "metric_name": self._metric_name,
                "current_value": self._current_value,
                "baseline_value": self._baseline_value,
                "drift_score": self._drift_score,
                "is_drifted": self._is_drifted,
                "severity": self._severity.value,
                "threshold": self._threshold,
                "window_start": self._window_start.isoformat() if self._window_start else None,
                "window_end": self._window_end.isoformat() if self._window_end else None,
                "sample_count": self._sample_count,
                "details": self._details,
                "deviation_percentage": self.get_deviation_percentage(),
                "requires_action": self.requires_action(),
            }
        )
        return base
