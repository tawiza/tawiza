"""Retraining trigger service implementation."""

from datetime import UTC, datetime

from src.application.ports.active_learning_ports import IRetrainingTrigger
from src.domain.entities.retraining_job import (
    RetrainingJob,
    RetrainingTriggerReason,
)
from src.domain.repositories.ml_repositories import (
    IFeedbackRepository,
    IMLModelRepository,
)


class RetrainingTriggerService(IRetrainingTrigger):
    """Service to determine when models should be retrained.

    Evaluates multiple conditions including:
    - Error rate thresholds
    - Drift detection
    - Sufficient new labeled data
    - Time since last training
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
        error_rate_threshold: float = 0.15,
        min_new_samples: int = 100,
        max_days_without_training: int = 30,
    ) -> None:
        """Initialize retraining trigger service.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
            error_rate_threshold: Error rate threshold (0-1)
            min_new_samples: Minimum new samples needed for retraining
            max_days_without_training: Maximum days without retraining
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository
        self._error_threshold = error_rate_threshold
        self._min_samples = min_new_samples
        self._max_days = max_days_without_training

    async def should_trigger_retraining(
        self, model_name: str, model_version: str
    ) -> tuple[bool, str | None]:
        """Check if retraining should be triggered.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Tuple of (should_retrain, reason)

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get conditions
        conditions = await self.get_retraining_conditions(model_name, model_version)

        # Check error rate
        if conditions["error_rate"] > self._error_threshold:
            return (
                True,
                f"Error rate ({conditions['error_rate']:.2%}) exceeds threshold ({self._error_threshold:.2%})",
            )

        # Check new samples
        if conditions["new_samples_count"] >= self._min_samples:
            return (
                True,
                f"Sufficient new samples ({conditions['new_samples_count']}) available for retraining",
            )

        # Check time since last training
        if conditions["days_since_training"] > self._max_days:
            return True, f"Model hasn't been retrained in {conditions['days_since_training']} days"

        return False, None

    async def trigger_retraining(
        self,
        model_name: str,
        model_version: str,
        trigger_reason: str,
        config: dict | None = None,
    ) -> RetrainingJob:
        """Trigger a retraining job.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            trigger_reason: Reason for triggering
            config: Optional training configuration

        Returns:
            Created retraining job

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback count for new samples
        stats = await self._feedback_repo.get_feedback_statistics(model.id)
        new_samples = stats.get("total_count", 0)

        # Map reason string to enum
        reason_map = {
            "drift_detected": RetrainingTriggerReason.DRIFT_DETECTED,
            "error_threshold": RetrainingTriggerReason.ERROR_THRESHOLD,
            "sufficient_data": RetrainingTriggerReason.SUFFICIENT_DATA,
            "manual": RetrainingTriggerReason.MANUAL,
            "scheduled": RetrainingTriggerReason.SCHEDULED,
            "feedback_volume": RetrainingTriggerReason.FEEDBACK_VOLUME,
        }

        trigger_enum = reason_map.get(trigger_reason.lower(), RetrainingTriggerReason.MANUAL)

        # Create retraining job
        job = RetrainingJob(
            trigger_reason=trigger_enum,
            model_name=model_name,
            base_model_version=model_version,
            new_samples_count=new_samples,
            config=config or {},
            metadata={
                "trigger_reason_detail": trigger_reason,
                "triggered_at": datetime.now(UTC).isoformat(),
            },
        )

        return job

    async def get_retraining_conditions(self, model_name: str, model_version: str) -> dict:
        """Get retraining condition metrics.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary of condition metrics

        Raises:
            ValueError: If model not found
        """
        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback statistics
        stats = await self._feedback_repo.get_feedback_statistics(model.id)

        # Calculate error rate
        error_rate = stats.get("negative_percentage", 0.0) / 100

        # Calculate days since training
        days_since = (datetime.now(UTC) - model.created_at).days

        return {
            "error_rate": error_rate,
            "new_samples_count": stats.get("total_count", 0),
            "negative_feedback_count": stats.get("negative_count", 0),
            "average_rating": stats.get("average_rating"),
            "days_since_training": days_since,
            "thresholds": {
                "error_rate": self._error_threshold,
                "min_samples": self._min_samples,
                "max_days": self._max_days,
            },
        }
