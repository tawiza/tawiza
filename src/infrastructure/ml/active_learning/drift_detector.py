"""Drift detection service implementation."""

from datetime import datetime, timedelta

from src.application.ports.active_learning_ports import IDriftDetector
from src.domain.entities.drift_report import DriftReport, DriftType
from src.domain.repositories.ml_repositories import IFeedbackRepository, IMLModelRepository
from src.domain.value_objects.sampling import DriftMetric


class PerformanceDriftDetector(IDriftDetector):
    """Detect drift in model performance based on feedback.

    Monitors model accuracy, error rates, and feedback patterns
    to detect when model performance degrades over time.
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
        default_window_days: int = 7,
        error_rate_threshold: float = 0.15,
        accuracy_drop_threshold: float = 0.10,
    ) -> None:
        """Initialize drift detector.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
            default_window_days: Default monitoring window in days
            error_rate_threshold: Threshold for error rate drift (0-1)
            accuracy_drop_threshold: Threshold for accuracy drop (0-1)
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository
        self._default_window = timedelta(days=default_window_days)
        self._error_threshold = error_rate_threshold
        self._accuracy_threshold = accuracy_drop_threshold

    async def detect_drift(
        self,
        model_name: str,
        model_version: str,
        drift_type: DriftType,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DriftReport | None:
        """Detect drift for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            drift_type: Type of drift to detect
            window_start: Start of monitoring window
            window_end: End of monitoring window

        Returns:
            Drift report if drift detected, None otherwise

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Set window
        if window_end is None:
            window_end = datetime.utcnow()
        if window_start is None:
            window_start = window_end - self._default_window

        # Get baseline metrics
        baseline_metrics = await self.get_baseline_metrics(model_name, model_version)

        # Calculate current metrics
        drift_metrics = await self.calculate_drift_metrics(
            model_name, model_version, window_start, window_end
        )

        # Check for performance drift
        if drift_type == DriftType.PERFORMANCE_DRIFT:
            return await self._detect_performance_drift(
                model, baseline_metrics, drift_metrics, window_start, window_end
            )

        return None

    async def _detect_performance_drift(
        self,
        model,
        baseline_metrics: dict[str, float],
        drift_metrics: list[DriftMetric],
        window_start: datetime,
        window_end: datetime,
    ) -> DriftReport | None:
        """Detect performance drift.

        Args:
            model: Model entity
            baseline_metrics: Baseline performance metrics
            drift_metrics: Current drift metrics
            window_start: Window start
            window_end: Window end

        Returns:
            Drift report if detected, None otherwise
        """
        # Find error rate metric
        error_rate_metric = next((m for m in drift_metrics if m.metric_name == "error_rate"), None)

        if error_rate_metric and error_rate_metric.is_drifted:
            # Calculate drift score based on deviation
            drift_score = error_rate_metric.calculate_drift_score()

            return DriftReport(
                model_name=model.name,
                model_version=model.version,
                drift_type=DriftType.PERFORMANCE_DRIFT,
                metric_name="error_rate",
                current_value=error_rate_metric.current_value,
                baseline_value=error_rate_metric.baseline_value,
                drift_score=drift_score,
                is_drifted=True,
                threshold=error_rate_metric.threshold,
                window_start=window_start,
                window_end=window_end,
                sample_count=baseline_metrics.get("sample_count"),
                details={
                    "all_metrics": [m.to_dict() for m in drift_metrics],
                    "baseline_metrics": baseline_metrics,
                },
            )

        return None

    async def calculate_drift_metrics(
        self,
        model_name: str,
        model_version: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[DriftMetric]:
        """Calculate drift metrics.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            window_start: Start of window
            window_end: End of window

        Returns:
            List of drift metrics

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get baseline
        baseline = await self.get_baseline_metrics(model_name, model_version)

        # Get feedback statistics
        stats = await self._feedback_repo.get_feedback_statistics(model.id)

        # Calculate error rate
        negative_pct = stats.get("negative_percentage", 0.0) / 100
        baseline_error = baseline.get("error_rate", 0.0)

        error_rate_drifted = negative_pct > (baseline_error + self._error_threshold)

        metrics = [
            DriftMetric(
                metric_name="error_rate",
                current_value=negative_pct,
                baseline_value=baseline_error,
                threshold=self._error_threshold,
                is_drifted=error_rate_drifted,
            )
        ]

        # Calculate accuracy drop if we have rating data
        avg_rating = stats.get("average_rating")
        if avg_rating is not None:
            baseline_rating = baseline.get("average_rating", 4.0)
            rating_drop = baseline_rating - avg_rating
            rating_drifted = rating_drop > (baseline_rating * self._accuracy_threshold)

            metrics.append(
                DriftMetric(
                    metric_name="average_rating",
                    current_value=avg_rating,
                    baseline_value=baseline_rating,
                    threshold=baseline_rating * self._accuracy_threshold,
                    is_drifted=rating_drifted,
                )
            )

        return metrics

    async def get_baseline_metrics(self, model_name: str, model_version: str) -> dict[str, float]:
        """Get baseline metrics for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary of baseline metrics

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # In production, these would be stored during model training/validation
        # For now, return defaults
        return {
            "error_rate": 0.05,  # 5% baseline error rate
            "average_rating": 4.0,  # 4/5 stars baseline
            "accuracy": 0.95,  # 95% accuracy
            "sample_count": 1000,  # Sample count used for baseline
        }
