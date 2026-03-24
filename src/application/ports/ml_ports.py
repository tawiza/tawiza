"""Port interfaces for ML operations."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class IModelTrainer(ABC):
    """Port for training ML models.

    This will be implemented by LLaMA-Factory adapter in infrastructure.
    """

    @abstractmethod
    async def train(
        self,
        model_name: str,
        base_model: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> str:
        """Train a model.

        Args:
            model_name: Name of the model being trained
            base_model: Base model to fine-tune (e.g., "meta-llama/Llama-2-7b-chat-hf")
            dataset_path: Path to training dataset
            output_dir: Directory to save the trained model
            hyperparameters: Training hyperparameters

        Returns:
            MLflow run ID
        """
        pass

    @abstractmethod
    async def train_with_rlhf(
        self,
        model_path: str,
        reward_model_path: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> str:
        """Train a model with RLHF.

        Args:
            model_path: Path to the base model
            reward_model_path: Path to the reward model
            dataset_path: Path to training dataset
            output_dir: Directory to save the trained model
            hyperparameters: Training hyperparameters

        Returns:
            MLflow run ID
        """
        pass

    @abstractmethod
    async def get_training_status(self, mlflow_run_id: str) -> dict[str, Any]:
        """Get the status of a training job.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            Training status information
        """
        pass


class IModelInference(ABC):
    """Port for model inference.

    This will be implemented by vLLM adapter in infrastructure.
    """

    @abstractmethod
    async def predict(
        self,
        model_id: str,
        input_data: dict[str, Any],
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run inference on a model.

        Args:
            model_id: Model identifier
            input_data: Input data for prediction
            parameters: Optional inference parameters (temperature, max_tokens, etc.)

        Returns:
            Prediction output
        """
        pass

    @abstractmethod
    async def health_check(self, model_id: str) -> bool:
        """Check if a model is healthy and ready.

        Args:
            model_id: Model identifier

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def get_model_info(self, model_id: str) -> dict[str, Any]:
        """Get information about a deployed model.

        Args:
            model_id: Model identifier

        Returns:
            Model information
        """
        pass


class IModelDeployer(ABC):
    """Port for deploying models.

    This will handle deployment strategies (canary, blue-green, etc.).
    """

    @abstractmethod
    async def deploy(
        self,
        model_path: str,
        model_id: UUID,
        strategy: str,
        traffic_percentage: int = 100,
    ) -> str:
        """Deploy a model.

        Args:
            model_path: Path to the model
            model_id: Model UUID
            strategy: Deployment strategy ("direct", "canary", "blue_green")
            traffic_percentage: Initial traffic percentage

        Returns:
            Deployment endpoint URL
        """
        pass

    @abstractmethod
    async def update_traffic(
        self,
        model_id: UUID,
        new_percentage: int,
    ) -> None:
        """Update traffic routing for canary deployment.

        Args:
            model_id: Model UUID
            new_percentage: New traffic percentage
        """
        pass

    @abstractmethod
    async def rollback(self, model_id: UUID) -> None:
        """Rollback a deployment.

        Args:
            model_id: Model UUID to rollback
        """
        pass

    @abstractmethod
    async def retire(self, model_id: UUID) -> None:
        """Retire a deployed model.

        Args:
            model_id: Model UUID
        """
        pass


class IMLExperimentTracker(ABC):
    """Port for ML experiment tracking.

    This will be implemented by MLflow adapter in infrastructure.
    """

    @abstractmethod
    async def log_parameters(
        self,
        run_id: str,
        parameters: dict[str, Any],
    ) -> None:
        """Log parameters for an experiment run.

        Args:
            run_id: Run identifier
            parameters: Parameters to log
        """
        pass

    @abstractmethod
    async def log_metrics(
        self,
        run_id: str,
        metrics: dict[str, float],
        step: int | None = None,
    ) -> None:
        """Log metrics for an experiment run.

        Args:
            run_id: Run identifier
            metrics: Metrics to log
            step: Optional step number
        """
        pass

    @abstractmethod
    async def log_artifact(
        self,
        run_id: str,
        artifact_path: str,
        artifact_name: str,
    ) -> None:
        """Log an artifact for an experiment run.

        Args:
            run_id: Run identifier
            artifact_path: Path to the artifact file
            artifact_name: Name for the artifact
        """
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Get information about a run.

        Args:
            run_id: Run identifier

        Returns:
            Run information
        """
        pass

    @abstractmethod
    async def register_model(
        self,
        model_name: str,
        model_path: str,
        run_id: str,
    ) -> str:
        """Register a model in the model registry.

        Args:
            model_name: Name for the model
            model_path: Path to the model
            run_id: Associated run ID

        Returns:
            Model version
        """
        pass


class IDataAnnotator(ABC):
    """Port for data annotation.

    This will be implemented by Label Studio adapter in infrastructure.
    """

    @abstractmethod
    async def create_project(
        self,
        project_name: str,
        labeling_config: str,
    ) -> int:
        """Create an annotation project.

        Args:
            project_name: Name of the project
            labeling_config: Label Studio labeling configuration XML

        Returns:
            Project ID
        """
        pass

    @abstractmethod
    async def import_tasks(
        self,
        project_id: int,
        tasks: list[dict[str, Any]],
    ) -> list[int]:
        """Import tasks for annotation.

        Args:
            project_id: Project ID
            tasks: List of tasks to import

        Returns:
            List of task IDs
        """
        pass

    @abstractmethod
    async def get_annotations(
        self,
        project_id: int,
    ) -> list[dict[str, Any]]:
        """Get annotations from a project.

        Args:
            project_id: Project ID

        Returns:
            List of annotations
        """
        pass

    @abstractmethod
    async def get_annotation_progress(
        self,
        project_id: int,
    ) -> dict[str, int]:
        """Get annotation progress.

        Args:
            project_id: Project ID

        Returns:
            Progress information (total, completed, etc.)
        """
        pass

    @abstractmethod
    async def enable_ml_backend(
        self,
        project_id: int,
        model_url: str,
    ) -> None:
        """Enable ML backend for auto-annotation.

        Args:
            project_id: Project ID
            model_url: URL of the ML backend
        """
        pass


class IDataDriftDetector(ABC):
    """Port for data drift detection.

    This will be implemented by Evidently AI adapter in infrastructure.
    """

    @abstractmethod
    async def check_drift(
        self,
        reference_data_path: str,
        current_data_path: str,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Check for data drift.

        Args:
            reference_data_path: Path to reference dataset
            current_data_path: Path to current dataset
            threshold: Drift detection threshold

        Returns:
            Drift detection report
        """
        pass

    @abstractmethod
    async def generate_report(
        self,
        reference_data_path: str,
        current_data_path: str,
        output_path: str,
    ) -> str:
        """Generate a comprehensive drift report.

        Args:
            reference_data_path: Path to reference dataset
            current_data_path: Path to current dataset
            output_path: Path to save the report

        Returns:
            Path to the generated report
        """
        pass


class IWorkflowOrchestrator(ABC):
    """Port for workflow orchestration.

    This will be implemented by Prefect adapter in infrastructure.
    """

    @abstractmethod
    async def trigger_training_workflow(
        self,
        training_job_id: UUID,
        parameters: dict[str, Any],
    ) -> str:
        """Trigger a training workflow.

        Args:
            training_job_id: Training job UUID
            parameters: Workflow parameters

        Returns:
            Flow run ID
        """
        pass

    @abstractmethod
    async def get_workflow_status(
        self,
        flow_run_id: str,
    ) -> dict[str, Any]:
        """Get the status of a workflow.

        Args:
            flow_run_id: Flow run ID

        Returns:
            Workflow status information
        """
        pass

    @abstractmethod
    async def cancel_workflow(
        self,
        flow_run_id: str,
    ) -> None:
        """Cancel a running workflow.

        Args:
            flow_run_id: Flow run ID
        """
        pass
