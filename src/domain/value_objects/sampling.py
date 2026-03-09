"""Value objects for active learning sampling strategies."""

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from .base import ValueObject


class SamplingStrategyType(StrEnum):
    """Type of sampling strategy for active learning."""

    UNCERTAINTY = "uncertainty"  # Select samples with lowest confidence
    MARGIN = "margin"  # Select samples with smallest margin between top predictions
    ENTROPY = "entropy"  # Select samples with highest entropy
    DIVERSITY = "diversity"  # Select diverse samples using clustering
    RANDOM = "random"  # Random sampling as baseline


@dataclass(frozen=True)
class SamplingConfig(ValueObject):
    """Configuration for a sampling strategy.

    Immutable value object that defines parameters for sample selection.
    """

    strategy_type: SamplingStrategyType
    sample_count: int
    threshold: float | None = None  # Optional confidence/entropy threshold
    diversity_metric: str | None = None  # For diversity sampling (e.g., "cosine", "euclidean")
    min_samples_per_cluster: int | None = None  # For diversity sampling
    filters: dict[str, Any] | None = None  # Additional filters

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")

        if self.threshold is not None and not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")

        if self.min_samples_per_cluster is not None and self.min_samples_per_cluster <= 0:
            raise ValueError("min_samples_per_cluster must be positive")


@dataclass(frozen=True)
class SampleScore(ValueObject):
    """Score assigned to a sample by a sampling strategy.

    Represents the informativeness or priority of a sample for labeling.
    Higher scores indicate more valuable samples for active learning.
    """

    sample_id: str  # Unique identifier for the sample (e.g., prediction_id)
    score: float  # Score assigned by the strategy
    confidence: float | None = None  # Model confidence (if applicable)
    entropy: float | None = None  # Prediction entropy (if applicable)
    margin: float | None = None  # Margin between top predictions (if applicable)
    metadata: dict[str, Any] | None = None  # Additional sample metadata

    def __post_init__(self) -> None:
        """Validate score values."""
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

        if self.entropy is not None and self.entropy < 0:
            raise ValueError("entropy must be non-negative")

        if self.margin is not None and not 0 <= self.margin <= 1:
            raise ValueError("margin must be between 0 and 1")


@dataclass(frozen=True)
class SamplingResult(ValueObject):
    """Result of a sampling operation.

    Contains the selected samples and metadata about the selection process.
    """

    strategy_type: SamplingStrategyType
    selected_samples: list[SampleScore]
    total_candidates: int  # Total number of candidates considered
    config: SamplingConfig  # Configuration used
    execution_time_ms: float | None = None  # Time taken to select samples
    metadata: dict[str, Any] | None = None  # Additional metadata

    def __post_init__(self) -> None:
        """Validate sampling result."""
        if self.total_candidates < 0:
            raise ValueError("total_candidates must be non-negative")

        if len(self.selected_samples) > self.total_candidates:
            raise ValueError("selected_samples cannot exceed total_candidates")

        if self.execution_time_ms is not None and self.execution_time_ms < 0:
            raise ValueError("execution_time_ms must be non-negative")

    def get_sample_ids(self) -> list[str]:
        """Get list of selected sample IDs.

        Returns:
            List of sample IDs
        """
        return [sample.sample_id for sample in self.selected_samples]

    def get_average_score(self) -> float:
        """Calculate average score of selected samples.

        Returns:
            Average score, 0.0 if no samples
        """
        if not self.selected_samples:
            return 0.0
        return sum(s.score for s in self.selected_samples) / len(self.selected_samples)

    def get_top_n(self, n: int) -> list[SampleScore]:
        """Get top N samples by score.

        Args:
            n: Number of samples to return

        Returns:
            Top N samples (or all if fewer than N)
        """
        return sorted(self.selected_samples, key=lambda s: s.score, reverse=True)[:n]


@dataclass(frozen=True)
class DriftMetric(ValueObject):
    """Value object representing a drift detection metric.

    Encapsulates a specific metric used to detect distribution or performance drift.
    """

    metric_name: str
    current_value: float
    baseline_value: float
    threshold: float
    is_drifted: bool

    def __post_init__(self) -> None:
        """Validate drift metric values."""
        if self.threshold < 0:
            raise ValueError("threshold must be non-negative")

    def get_deviation(self) -> float:
        """Calculate absolute deviation from baseline.

        Returns:
            Absolute deviation
        """
        return abs(self.current_value - self.baseline_value)

    def get_deviation_percentage(self) -> float:
        """Calculate percentage deviation from baseline.

        Returns:
            Percentage deviation (0-100)
        """
        if self.baseline_value == 0:
            return 0.0
        return (self.get_deviation() / abs(self.baseline_value)) * 100

    def calculate_drift_score(self) -> float:
        """Calculate normalized drift score (0-1).

        Returns:
            Drift score where 0 = no drift, 1 = maximum drift
        """
        deviation = self.get_deviation()
        if self.threshold == 0:
            return 1.0 if deviation > 0 else 0.0
        return min(deviation / self.threshold, 1.0)
