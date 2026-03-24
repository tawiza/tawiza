"""Use cases for Active Learning system."""

from datetime import datetime
from uuid import uuid4

from src.application.ports.active_learning_ports import (
    IDriftDetector,
    IRetrainingTrigger,
    ISamplingStrategy,
)
from src.domain.entities.drift_report import DriftReport, DriftType
from src.domain.entities.retraining_job import RetrainingJob
from src.domain.events.ml_events import (
    DriftDetectedEvent,
    RetrainingTriggeredEvent,
    SamplesSelectedForLabelingEvent,
)
from src.domain.repositories.ml_repositories import (
    IDriftReportRepository,
    IMLModelRepository,
    IRetrainingJobRepository,
)
from src.domain.value_objects.sampling import SamplingConfig, SamplingResult
from src.infrastructure.messaging.event_bus import EventBus


class SelectSamplesForLabelingUseCase:
    """Use case for selecting samples for labeling via active learning."""

    def __init__(
        self,
        sampling_strategy: ISamplingStrategy,
        model_repository: IMLModelRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            sampling_strategy: Sampling strategy to use
            model_repository: Model repository
            event_bus: Optional event bus for publishing events
        """
        self._sampling_strategy = sampling_strategy
        self._model_repo = model_repository
        self._event_bus = event_bus

    async def execute(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select samples for labeling.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            config: Sampling configuration
            feedback_filters: Optional filters for feedback data

        Returns:
            Sampling result with selected samples

        Raises:
            ValueError: If model not found or invalid config
        """
        # Verify model exists
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Select samples using strategy
        result = await self._sampling_strategy.select_samples(
            model_name=model_name,
            model_version=model_version,
            config=config,
            feedback_filters=feedback_filters,
        )

        # Publish event if event bus available
        if self._event_bus:
            event = SamplesSelectedForLabelingEvent(
                selection_id=uuid4(),
                strategy_type=config.strategy_type.value,
                sample_count=len(result.selected_samples),
                model_name=model_name,
                model_version=model_version,
                average_score=result.get_average_score(),
            )
            await self._event_bus.publish(event)

        return result


class DetectDriftUseCase:
    """Use case for detecting model drift."""

    def __init__(
        self,
        drift_detector: IDriftDetector,
        drift_report_repository: IDriftReportRepository,
        model_repository: IMLModelRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            drift_detector: Drift detection service
            drift_report_repository: Drift report repository
            model_repository: Model repository
            event_bus: Optional event bus for publishing events
        """
        self._drift_detector = drift_detector
        self._drift_report_repo = drift_report_repository
        self._model_repo = model_repository
        self._event_bus = event_bus

    async def execute(
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
        # Verify model exists
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Detect drift
        drift_report = await self._drift_detector.detect_drift(
            model_name=model_name,
            model_version=model_version,
            drift_type=drift_type,
            window_start=window_start,
            window_end=window_end,
        )

        # Save drift report if detected
        if drift_report:
            saved_report = await self._drift_report_repo.save(drift_report)

            # Publish event if event bus available
            if self._event_bus:
                event = DriftDetectedEvent(
                    drift_report_id=saved_report.id,
                    model_name=model_name,
                    model_version=model_version,
                    drift_type=drift_type.value,
                    drift_score=saved_report.drift_score,
                    severity=saved_report.severity.value,
                    metric_name=saved_report.metric_name,
                    current_value=saved_report.current_value,
                    baseline_value=saved_report.baseline_value,
                )
                await self._event_bus.publish(event)

            return saved_report

        return None


class TriggerRetrainingUseCase:
    """Use case for triggering model retraining."""

    def __init__(
        self,
        retraining_trigger: IRetrainingTrigger,
        retraining_job_repository: IRetrainingJobRepository,
        model_repository: IMLModelRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            retraining_trigger: Retraining trigger service
            retraining_job_repository: Retraining job repository
            model_repository: Model repository
            event_bus: Optional event bus for publishing events
        """
        self._retraining_trigger = retraining_trigger
        self._job_repo = retraining_job_repository
        self._model_repo = model_repository
        self._event_bus = event_bus

    async def execute(
        self,
        model_name: str,
        model_version: str,
        trigger_reason: str,
        config: dict | None = None,
    ) -> RetrainingJob:
        """Trigger retraining for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            trigger_reason: Reason for triggering retraining
            config: Optional training configuration

        Returns:
            Created retraining job

        Raises:
            ValueError: If model not found or validation fails
        """
        # Verify model exists
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Trigger retraining
        job = await self._retraining_trigger.trigger_retraining(
            model_name=model_name,
            model_version=model_version,
            trigger_reason=trigger_reason,
            config=config,
        )

        # Save job
        saved_job = await self._job_repo.save(job)

        # Publish event if event bus available
        if self._event_bus:
            event = RetrainingTriggeredEvent(
                training_job_id=saved_job.id,
                trigger_reason=trigger_reason,
                current_model_id=model.id,
                metrics={
                    "new_samples_count": saved_job.new_samples_count,
                    "base_model_version": saved_job.base_model_version,
                },
            )
            await self._event_bus.publish(event)

        return saved_job

    async def check_and_trigger_if_needed(
        self, model_name: str, model_version: str
    ) -> RetrainingJob | None:
        """Check if retraining is needed and trigger if so.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Retraining job if triggered, None otherwise

        Raises:
            ValueError: If model not found
        """
        should_retrain, reason = await self._retraining_trigger.should_trigger_retraining(
            model_name=model_name, model_version=model_version
        )

        if should_retrain and reason:
            return await self.execute(
                model_name=model_name,
                model_version=model_version,
                trigger_reason=reason,
            )

        return None


class GetRetrainingConditionsUseCase:
    """Use case for getting retraining conditions for a model."""

    def __init__(
        self,
        retraining_trigger: IRetrainingTrigger,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            retraining_trigger: Retraining trigger service
            model_repository: Model repository
        """
        self._retraining_trigger = retraining_trigger
        self._model_repo = model_repository

    async def execute(self, model_name: str, model_version: str) -> dict:
        """Get retraining conditions for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary with condition metrics and recommendation

        Raises:
            ValueError: If model not found
        """
        # Verify model exists
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get conditions
        conditions = await self._retraining_trigger.get_retraining_conditions(
            model_name=model_name, model_version=model_version
        )

        # Check if retraining recommended
        should_retrain, reason = await self._retraining_trigger.should_trigger_retraining(
            model_name=model_name, model_version=model_version
        )

        return {
            "model_name": model_name,
            "model_version": model_version,
            "conditions": conditions,
            "retraining_recommended": should_retrain,
            "recommendation_reason": reason,
        }


class GetDriftReportsUseCase:
    """Use case for retrieving drift reports."""

    def __init__(
        self,
        drift_report_repository: IDriftReportRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            drift_report_repository: Drift report repository
        """
        self._drift_report_repo = drift_report_repository

    async def get_by_model(
        self, model_name: str, model_version: str, skip: int = 0, limit: int = 100
    ) -> list[DriftReport]:
        """Get drift reports for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of drift reports
        """
        return await self._drift_report_repo.get_by_model(
            model_name=model_name,
            model_version=model_version,
            skip=skip,
            limit=limit,
        )

    async def get_drifted_reports(
        self, model_name: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[DriftReport]:
        """Get reports where drift was detected.

        Args:
            model_name: Optional model name to filter by
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of drift reports where drift was detected
        """
        return await self._drift_report_repo.get_drifted_reports(
            model_name=model_name, skip=skip, limit=limit
        )
