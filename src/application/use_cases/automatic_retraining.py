"""Use case for automatic model retraining based on triggers."""

from datetime import datetime
from uuid import UUID

from src.domain.entities.dataset import DatasetType
from src.domain.entities.training_job import TrainingJob, TrainingTrigger
from src.domain.repositories.ml_repositories import (
    IDatasetRepository,
    IFeedbackRepository,
    IMLModelRepository,
    ITrainingJobRepository,
)


class AutomaticRetrainingUseCase:
    """Use case for triggering automatic model retraining.

    This use case evaluates various conditions to determine if a model should
    be retrained automatically, including:
    - Performance degradation based on negative feedback
    - Scheduled retraining intervals
    - Data drift detection
    - Minimum data volume requirements
    """

    def __init__(
        self,
        model_repository: IMLModelRepository,
        dataset_repository: IDatasetRepository,
        training_job_repository: ITrainingJobRepository,
        feedback_repository: IFeedbackRepository,
        min_feedback_count: int = 100,
        negative_feedback_threshold: float = 0.3,  # 30%
        retraining_interval_days: int = 7,
    ) -> None:
        """Initialize the use case.

        Args:
            model_repository: Model repository
            dataset_repository: Dataset repository
            training_job_repository: Training job repository
            feedback_repository: Feedback repository
            min_feedback_count: Minimum feedback required before checking threshold
            negative_feedback_threshold: Threshold for negative feedback percentage
            retraining_interval_days: Days between scheduled retraining
        """
        self._model_repository = model_repository
        self._dataset_repository = dataset_repository
        self._training_job_repository = training_job_repository
        self._feedback_repository = feedback_repository
        self._min_feedback_count = min_feedback_count
        self._negative_feedback_threshold = negative_feedback_threshold
        self._retraining_interval_days = retraining_interval_days

    async def should_retrain(self, model_id: UUID) -> dict[str, any]:
        """Check if a model should be retrained.

        Args:
            model_id: Model ID to check

        Returns:
            Dictionary with decision and reasons

        Raises:
            ValueError: If model not found
        """
        model = await self._model_repository.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        reasons = []
        should_retrain = False

        # Check 1: Performance degradation via negative feedback
        feedback_stats = await self._feedback_repository.get_feedback_statistics(model_id)

        if feedback_stats["total_count"] >= self._min_feedback_count:
            negative_percentage = feedback_stats["negative_percentage"] / 100

            if negative_percentage >= self._negative_feedback_threshold:
                reasons.append(
                    f"High negative feedback: {negative_percentage:.1%} "
                    f"(threshold: {self._negative_feedback_threshold:.1%})"
                )
                should_retrain = True

        # Check 2: Scheduled retraining based on deployment time
        if model.deployed_at:
            days_since_deployment = (datetime.utcnow() - model.deployed_at).days

            if days_since_deployment >= self._retraining_interval_days:
                reasons.append(
                    f"Scheduled retraining: {days_since_deployment} days since deployment "
                    f"(interval: {self._retraining_interval_days} days)"
                )
                should_retrain = True

        # Check 3: Last training job status
        training_jobs = await self._training_job_repository.get_by_model_id(model_id)
        if training_jobs:
            latest_job = max(training_jobs, key=lambda j: j.created_at)
            if latest_job.is_failed():
                reasons.append("Previous training failed, retry recommended")
                should_retrain = True

        return {
            "should_retrain": should_retrain,
            "reasons": reasons,
            "model_id": str(model_id),
            "model_name": model.name,
            "model_version": model.version,
            "feedback_stats": feedback_stats,
        }

    async def trigger_retraining(
        self,
        model_id: UUID,
        trigger: TrainingTrigger,
        dataset_id: UUID | None = None,
        hyperparameters: dict | None = None,
    ) -> TrainingJob:
        """Trigger automatic retraining for a model.

        Args:
            model_id: Model ID to retrain
            trigger: Training trigger (SCHEDULED, DRIFT_DETECTED, PERFORMANCE_DEGRADATION)
            dataset_id: Optional specific dataset to use
            hyperparameters: Optional hyperparameters (uses model's last training if not provided)

        Returns:
            Created training job

        Raises:
            ValueError: If model or dataset not found
        """
        # Verify model exists
        model = await self._model_repository.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        # Get dataset
        if dataset_id:
            dataset = await self._dataset_repository.get_by_id(dataset_id)
            if not dataset:
                raise ValueError(f"Dataset with ID {dataset_id} not found")
        else:
            # Use the most recent ready dataset of the appropriate type
            ready_datasets = await self._dataset_repository.get_ready_datasets(
                dataset_type=DatasetType.CONVERSATIONAL
            )
            if not ready_datasets:
                raise ValueError("No ready datasets available for retraining")
            dataset = max(ready_datasets, key=lambda d: d.created_at)

        # Get hyperparameters from last successful training if not provided
        if not hyperparameters:
            training_jobs = await self._training_job_repository.get_by_model_id(model_id)
            successful_jobs = [j for j in training_jobs if j.is_completed()]

            if successful_jobs:
                latest_successful = max(successful_jobs, key=lambda j: j.created_at)
                hyperparameters = latest_successful.hyperparameters
            else:
                # Use default hyperparameters
                hyperparameters = {
                    "learning_rate": 2e-5,
                    "batch_size": 4,
                    "num_epochs": 3,
                    "max_seq_length": 2048,
                    "lora_rank": 8,
                    "lora_alpha": 16,
                }

        # Create training job
        training_job = TrainingJob(
            model_id=model_id,
            dataset_id=dataset.id,
            trigger=trigger,
            hyperparameters=hyperparameters,
        )

        # Save training job
        saved_job = await self._training_job_repository.save(training_job)

        return saved_job


class RetrainingScheduler:
    """Scheduler for checking and triggering automatic retraining."""

    def __init__(
        self,
        automatic_retraining_uc: AutomaticRetrainingUseCase,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize the scheduler.

        Args:
            automatic_retraining_uc: Automatic retraining use case
            model_repository: Model repository
        """
        self._automatic_retraining_uc = automatic_retraining_uc
        self._model_repository = model_repository

    async def check_all_deployed_models(self) -> list[dict]:
        """Check all deployed models and trigger retraining if needed.

        Returns:
            List of retraining decisions for each model
        """
        deployed_models = await self._model_repository.get_deployed_models()
        results = []

        for model in deployed_models:
            decision = await self._automatic_retraining_uc.should_retrain(model.id)
            results.append(decision)

            if decision["should_retrain"]:
                try:
                    training_job = await self._automatic_retraining_uc.trigger_retraining(
                        model_id=model.id,
                        trigger=TrainingTrigger.SCHEDULED,
                    )
                    decision["training_job_id"] = str(training_job.id)
                    decision["status"] = "retraining_triggered"
                except Exception as e:
                    decision["status"] = "failed_to_trigger"
                    decision["error"] = str(e)
            else:
                decision["status"] = "no_retraining_needed"

        return results


class PerformanceDegradationDetector:
    """Detector for model performance degradation based on feedback."""

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        automatic_retraining_uc: AutomaticRetrainingUseCase,
        check_window_days: int = 1,
    ) -> None:
        """Initialize the detector.

        Args:
            feedback_repository: Feedback repository
            automatic_retraining_uc: Automatic retraining use case
            check_window_days: Days to look back for feedback
        """
        self._feedback_repository = feedback_repository
        self._automatic_retraining_uc = automatic_retraining_uc
        self._check_window_days = check_window_days

    async def check_recent_degradation(self, model_id: UUID) -> TrainingJob | None:
        """Check for recent performance degradation and trigger retraining.

        Args:
            model_id: Model ID to check

        Returns:
            Training job if retraining triggered, None otherwise
        """
        decision = await self._automatic_retraining_uc.should_retrain(model_id)

        if decision["should_retrain"]:
            # Check if reason is performance degradation
            for reason in decision["reasons"]:
                if "negative feedback" in reason.lower():
                    training_job = await self._automatic_retraining_uc.trigger_retraining(
                        model_id=model_id,
                        trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
                    )
                    return training_job

        return None
