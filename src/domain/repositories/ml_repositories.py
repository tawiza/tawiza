"""ML-specific repository interfaces."""

from abc import abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.dataset import Dataset, DatasetStatus, DatasetType
from src.domain.entities.drift_report import DriftReport, DriftType
from src.domain.entities.feedback import Feedback, FeedbackStatus, FeedbackType
from src.domain.entities.ml_model import MLModel, ModelStatus
from src.domain.entities.retraining_job import (
    RetrainingJob,
    RetrainingStatus,
    RetrainingTriggerReason,
)
from src.domain.entities.training_job import TrainingJob, TrainingJobStatus, TrainingTrigger
from src.domain.repositories.base import IRepository


class IMLModelRepository(IRepository[MLModel]):
    """Repository interface for ML models."""

    @abstractmethod
    async def get_by_name_and_version(
        self,
        name: str,
        version: str,
    ) -> MLModel | None:
        """Get a model by name and version.

        Args:
            name: Model name
            version: Model version

        Returns:
            The model if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_deployed_models(self) -> list[MLModel]:
        """Get all currently deployed models.

        Returns:
            List of deployed models
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: ModelStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[MLModel]:
        """Get models by status.

        Args:
            status: Model status to filter by
            skip: Number of models to skip
            limit: Maximum number of models to return

        Returns:
            List of models with the specified status
        """
        pass

    @abstractmethod
    async def get_latest_deployed(self) -> MLModel | None:
        """Get the latest deployed model.

        Returns:
            The latest deployed model, None if no models deployed
        """
        pass

    @abstractmethod
    async def get_by_mlflow_run_id(self, mlflow_run_id: str) -> MLModel | None:
        """Get a model by its MLflow run ID.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            The model if found, None otherwise
        """
        pass


class IDatasetRepository(IRepository[Dataset]):
    """Repository interface for datasets."""

    @abstractmethod
    async def get_by_name(self, name: str) -> Dataset | None:
        """Get a dataset by name.

        Args:
            name: Dataset name

        Returns:
            The dataset if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_type(
        self,
        dataset_type: DatasetType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Dataset]:
        """Get datasets by type.

        Args:
            dataset_type: Dataset type to filter by
            skip: Number of datasets to skip
            limit: Maximum number of datasets to return

        Returns:
            List of datasets with the specified type
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: DatasetStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Dataset]:
        """Get datasets by status.

        Args:
            status: Dataset status to filter by
            skip: Number of datasets to skip
            limit: Maximum number of datasets to return

        Returns:
            List of datasets with the specified status
        """
        pass

    @abstractmethod
    async def get_ready_datasets(
        self,
        dataset_type: DatasetType | None = None,
    ) -> list[Dataset]:
        """Get all ready datasets, optionally filtered by type.

        Args:
            dataset_type: Optional dataset type to filter by

        Returns:
            List of ready datasets
        """
        pass

    @abstractmethod
    async def get_by_label_studio_project(
        self,
        project_id: int,
    ) -> Dataset | None:
        """Get dataset by Label Studio project ID.

        Args:
            project_id: Label Studio project ID

        Returns:
            The dataset if found, None otherwise
        """
        pass


class ITrainingJobRepository(IRepository[TrainingJob]):
    """Repository interface for training jobs."""

    @abstractmethod
    async def get_by_status(
        self,
        status: TrainingJobStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TrainingJob]:
        """Get training jobs by status.

        Args:
            status: Training job status to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List of jobs with the specified status
        """
        pass

    @abstractmethod
    async def get_by_trigger(
        self,
        trigger: TrainingTrigger,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TrainingJob]:
        """Get training jobs by trigger type.

        Args:
            trigger: Training trigger to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List of jobs with the specified trigger
        """
        pass

    @abstractmethod
    async def get_running_jobs(self) -> list[TrainingJob]:
        """Get all currently running training jobs.

        Returns:
            List of running jobs
        """
        pass

    @abstractmethod
    async def get_by_mlflow_run_id(
        self,
        mlflow_run_id: str,
    ) -> TrainingJob | None:
        """Get a training job by its MLflow run ID.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            The job if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_latest_completed(self) -> TrainingJob | None:
        """Get the most recently completed training job.

        Returns:
            The latest completed job, None if no completed jobs
        """
        pass

    @abstractmethod
    async def get_recent_jobs(
        self,
        limit: int = 10,
    ) -> list[TrainingJob]:
        """Get the most recent training jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of recent jobs
        """
        pass


class IFeedbackRepository(IRepository[Feedback]):
    """Repository interface for user feedback."""

    @abstractmethod
    async def get_by_model_id(
        self,
        model_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by model ID.

        Args:
            model_id: Model ID to filter by
            skip: Number of feedback items to skip
            limit: Maximum number of feedback items to return

        Returns:
            List of feedback for the specified model
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: FeedbackStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by status.

        Args:
            status: Feedback status to filter by
            skip: Number of feedback items to skip
            limit: Maximum number of feedback items to return

        Returns:
            List of feedback with the specified status
        """
        pass

    @abstractmethod
    async def get_by_type(
        self,
        feedback_type: FeedbackType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get feedback by type.

        Args:
            feedback_type: Feedback type to filter by
            skip: Number of feedback items to skip
            limit: Maximum number of feedback items to return

        Returns:
            List of feedback with the specified type
        """
        pass

    @abstractmethod
    async def get_negative_feedback(
        self,
        model_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Feedback]:
        """Get negative feedback, optionally filtered by model.

        Args:
            model_id: Optional model ID to filter by
            skip: Number of feedback items to skip
            limit: Maximum number of feedback items to return

        Returns:
            List of negative feedback
        """
        pass

    @abstractmethod
    async def get_by_prediction_id(
        self,
        prediction_id: str,
    ) -> list[Feedback]:
        """Get feedback by prediction ID.

        Args:
            prediction_id: Prediction ID to filter by

        Returns:
            List of feedback for the specified prediction
        """
        pass

    @abstractmethod
    async def get_feedback_statistics(
        self,
        model_id: UUID,
    ) -> dict:
        """Get feedback statistics for a model.

        Args:
            model_id: Model ID

        Returns:
            Dictionary with statistics (counts by type, average rating, etc.)
        """
        pass


class IDriftReportRepository(IRepository["DriftReport"]):
    """Repository interface for drift reports."""

    @abstractmethod
    async def get_by_model(
        self,
        model_name: str,
        model_version: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list["DriftReport"]:
        """Get drift reports by model.

        Args:
            model_name: Model name
            model_version: Model version
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of drift reports for the model
        """
        pass

    @abstractmethod
    async def get_by_drift_type(
        self,
        drift_type: "DriftType",
        skip: int = 0,
        limit: int = 100,
    ) -> list["DriftReport"]:
        """Get drift reports by type.

        Args:
            drift_type: Drift type to filter by
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of drift reports with the specified type
        """
        pass

    @abstractmethod
    async def get_drifted_reports(
        self,
        model_name: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list["DriftReport"]:
        """Get reports where drift was detected.

        Args:
            model_name: Optional model name to filter by
            skip: Number of reports to skip
            limit: Maximum number of reports to return

        Returns:
            List of drift reports where is_drifted=True
        """
        pass

    @abstractmethod
    async def get_latest_by_model(
        self, model_name: str, model_version: str
    ) -> Optional["DriftReport"]:
        """Get the latest drift report for a model.

        Args:
            model_name: Model name
            model_version: Model version

        Returns:
            Latest drift report if exists, None otherwise
        """
        pass


class IRetrainingJobRepository(IRepository["RetrainingJob"]):
    """Repository interface for retraining jobs."""

    @abstractmethod
    async def get_by_model(
        self,
        model_name: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list["RetrainingJob"]:
        """Get retraining jobs by model name.

        Args:
            model_name: Model name
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List of retraining jobs for the model
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: "RetrainingStatus",
        skip: int = 0,
        limit: int = 100,
    ) -> list["RetrainingJob"]:
        """Get retraining jobs by status.

        Args:
            status: Job status to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List of jobs with the specified status
        """
        pass

    @abstractmethod
    async def get_by_trigger_reason(
        self,
        trigger_reason: "RetrainingTriggerReason",
        skip: int = 0,
        limit: int = 100,
    ) -> list["RetrainingJob"]:
        """Get retraining jobs by trigger reason.

        Args:
            trigger_reason: Trigger reason to filter by
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return

        Returns:
            List of jobs with the specified trigger reason
        """
        pass

    @abstractmethod
    async def get_running_jobs(self) -> list["RetrainingJob"]:
        """Get all currently running retraining jobs.

        Returns:
            List of running jobs
        """
        pass

    @abstractmethod
    async def get_latest_by_model(self, model_name: str) -> Optional["RetrainingJob"]:
        """Get the most recent retraining job for a model.

        Args:
            model_name: Model name

        Returns:
            Latest retraining job if exists, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_drift_report(self, drift_report_id: UUID) -> list["RetrainingJob"]:
        """Get retraining jobs triggered by a specific drift report.

        Args:
            drift_report_id: Drift report ID

        Returns:
            List of retraining jobs linked to the drift report
        """
        pass
