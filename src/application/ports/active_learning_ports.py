"""Port interfaces for active learning services."""

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities.drift_report import DriftReport, DriftType
from src.domain.entities.retraining_job import RetrainingJob
from src.domain.value_objects.sampling import (
    DriftMetric,
    SamplingConfig,
    SamplingResult,
)


class ISamplingStrategy(ABC):
    """Interface for active learning sampling strategies.

    Implementations select the most informative samples for labeling
    based on different selection criteria (uncertainty, diversity, etc.).
    """

    @abstractmethod
    async def select_samples(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select samples for labeling based on strategy.

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
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of this sampling strategy.

        Returns:
            Strategy name
        """
        pass


class IDriftDetector(ABC):
    """Interface for drift detection services.

    Implementations analyze model performance and data distributions
    to detect when models need retraining.
    """

    @abstractmethod
    async def detect_drift(
        self,
        model_name: str,
        model_version: str,
        drift_type: DriftType,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> DriftReport | None:
        """Detect drift in model performance or data distribution.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            drift_type: Type of drift to detect
            window_start: Start of monitoring window (None = use default)
            window_end: End of monitoring window (None = use now)

        Returns:
            Drift report if drift detected, None otherwise

        Raises:
            ValueError: If model not found
        """
        pass

    @abstractmethod
    async def calculate_drift_metrics(
        self,
        model_name: str,
        model_version: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[DriftMetric]:
        """Calculate drift metrics for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            window_start: Start of monitoring window
            window_end: End of monitoring window

        Returns:
            List of drift metrics

        Raises:
            ValueError: If model not found
        """
        pass

    @abstractmethod
    async def get_baseline_metrics(self, model_name: str, model_version: str) -> dict[str, float]:
        """Get baseline metrics for a model.

        Baseline metrics are typically from training/validation data
        or initial deployment period.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary of baseline metrics

        Raises:
            ValueError: If model not found
        """
        pass


class IRetrainingTrigger(ABC):
    """Interface for retraining trigger service.

    Determines when models should be retrained based on various conditions
    and manages the creation of retraining jobs.
    """

    @abstractmethod
    async def should_trigger_retraining(
        self, model_name: str, model_version: str
    ) -> tuple[bool, str | None]:
        """Check if retraining should be triggered for a model.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Tuple of (should_retrain, reason)
            - should_retrain: True if retraining recommended
            - reason: Reason for retraining (if applicable)

        Raises:
            ValueError: If model not found
        """
        pass

    @abstractmethod
    async def trigger_retraining(
        self,
        model_name: str,
        model_version: str,
        trigger_reason: str,
        config: dict | None = None,
    ) -> RetrainingJob:
        """Trigger a retraining job for a model.

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
        pass

    @abstractmethod
    async def get_retraining_conditions(self, model_name: str, model_version: str) -> dict:
        """Get current retraining condition metrics for a model.

        Returns metrics used to determine if retraining should be triggered:
        - Error rate
        - Drift scores
        - New labeled samples count
        - Time since last training
        - etc.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary of condition metrics

        Raises:
            ValueError: If model not found
        """
        pass


class IActiveLearningOrchestrator(ABC):
    """Interface for orchestrating the complete active learning loop.

    Coordinates sampling, drift detection, and retraining to create
    a continuous improvement cycle for models.
    """

    @abstractmethod
    async def run_active_learning_cycle(self, model_name: str, model_version: str) -> dict:
        """Run a complete active learning cycle for a model.

        This includes:
        1. Detect drift
        2. Select samples for labeling
        3. Check retraining conditions
        4. Trigger retraining if needed

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary with cycle results (drift reports, samples selected, etc.)

        Raises:
            ValueError: If model not found
        """
        pass

    @abstractmethod
    async def get_model_health_status(self, model_name: str, model_version: str) -> dict:
        """Get comprehensive health status for a model.

        Includes drift status, error rates, pending samples, etc.

        Args:
            model_name: Name of the model
            model_version: Version of the model

        Returns:
            Dictionary with health status metrics

        Raises:
            ValueError: If model not found
        """
        pass
