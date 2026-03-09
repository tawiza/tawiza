"""
MLflow Service for experiment tracking and model registry.
"""

from typing import Any

import mlflow
from loguru import logger
from mlflow.tracking import MlflowClient


class MLflowService:
    """
    Service for MLflow experiment tracking and model management.

    Provides a clean interface for:
    - Starting and ending runs
    - Logging parameters, metrics, and artifacts
    - Registering models
    - Retrieving run information
    """

    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "tawiza-training",
    ):
        """
        Initialize MLflow service.

        Args:
            tracking_uri: MLflow tracking server URL
            experiment_name: Default experiment name
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name

        # Set tracking URI
        mlflow.set_tracking_uri(tracking_uri)

        # Create experiment if it doesn't exist
        try:
            self.experiment_id = mlflow.create_experiment(experiment_name)
            logger.info(f"Created MLflow experiment: {experiment_name}")
        except Exception:
            # Experiment already exists
            experiment = mlflow.get_experiment_by_name(experiment_name)
            self.experiment_id = experiment.experiment_id
            logger.info(f"Using existing MLflow experiment: {experiment_name}")

        # Initialize client
        self.client = MlflowClient(tracking_uri=tracking_uri)

    def start_run(
        self,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """
        Start a new MLflow run.

        Args:
            run_name: Optional run name
            tags: Optional tags for the run

        Returns:
            Run ID
        """
        run = mlflow.start_run(
            experiment_id=self.experiment_id,
            run_name=run_name,
            tags=tags or {},
        )
        logger.info(f"Started MLflow run: {run.info.run_id}")
        return run.info.run_id

    def end_run(self, status: str = "FINISHED") -> None:
        """
        End the current MLflow run.

        Args:
            status: Run status (FINISHED, FAILED, KILLED)
        """
        mlflow.end_run(status=status)
        logger.info(f"Ended MLflow run with status: {status}")

    def log_params(self, params: dict[str, Any]) -> None:
        """
        Log parameters to current run.

        Args:
            params: Parameters to log
        """
        mlflow.log_params(params)
        logger.debug(f"Logged {len(params)} parameters")

    def log_param(self, key: str, value: Any) -> None:
        """
        Log a single parameter.

        Args:
            key: Parameter name
            value: Parameter value
        """
        mlflow.log_param(key, value)

    def log_metrics(
        self,
        metrics: dict[str, float],
        step: int | None = None,
    ) -> None:
        """
        Log metrics to current run.

        Args:
            metrics: Metrics to log
            step: Optional step number
        """
        mlflow.log_metrics(metrics, step=step)
        logger.debug(f"Logged {len(metrics)} metrics")

    def log_metric(
        self,
        key: str,
        value: float,
        step: int | None = None,
    ) -> None:
        """
        Log a single metric.

        Args:
            key: Metric name
            value: Metric value
            step: Optional step number
        """
        mlflow.log_metric(key, value, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        """
        Log an artifact (file).

        Args:
            local_path: Local path to the file
            artifact_path: Optional artifact path in MLflow
        """
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
        logger.debug(f"Logged artifact: {local_path}")

    def log_artifacts(self, local_dir: str, artifact_path: str | None = None) -> None:
        """
        Log all artifacts in a directory.

        Args:
            local_dir: Local directory path
            artifact_path: Optional artifact path in MLflow
        """
        mlflow.log_artifacts(local_dir, artifact_path=artifact_path)
        logger.debug(f"Logged artifacts from: {local_dir}")

    def log_model(
        self,
        model_path: str,
        artifact_path: str = "model",
        registered_model_name: str | None = None,
    ) -> None:
        """
        Log a model to MLflow.

        Args:
            model_path: Path to model
            artifact_path: Artifact path for the model
            registered_model_name: Optional name for model registry
        """
        # For now, just log as artifact
        # In production, would use mlflow.pytorch.log_model or similar
        self.log_artifacts(model_path, artifact_path=artifact_path)

        if registered_model_name:
            logger.info(f"Registering model: {registered_model_name}")
            # Would register to model registry here

    def get_run(self, run_id: str) -> dict[str, Any]:
        """
        Get run information.

        Args:
            run_id: Run ID

        Returns:
            Run information
        """
        run = self.client.get_run(run_id)
        return {
            "run_id": run.info.run_id,
            "status": run.info.status,
            "start_time": run.info.start_time,
            "end_time": run.info.end_time,
            "artifact_uri": run.info.artifact_uri,
            "params": run.data.params,
            "metrics": run.data.metrics,
            "tags": run.data.tags,
        }

    def search_runs(
        self,
        filter_string: str = "",
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for runs.

        Args:
            filter_string: MLflow filter string
            max_results: Maximum number of results

        Returns:
            List of runs
        """
        runs = self.client.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=filter_string,
            max_results=max_results,
        )

        return [
            {
                "run_id": run.info.run_id,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "metrics": run.data.metrics,
                "params": run.data.params,
            }
            for run in runs
        ]

    def register_model(
        self,
        model_uri: str,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """
        Register a model to the model registry.

        Args:
            model_uri: Model URI (e.g., runs:/<run_id>/model)
            name: Model name
            tags: Optional tags

        Returns:
            Model version
        """
        result = mlflow.register_model(model_uri, name, tags=tags)
        logger.info(f"Registered model {name} version {result.version}")
        return result.version

    def transition_model_stage(
        self,
        name: str,
        version: str,
        stage: str,
    ) -> None:
        """
        Transition model to a new stage.

        Args:
            name: Model name
            version: Model version
            stage: New stage (Staging, Production, Archived)
        """
        self.client.transition_model_version_stage(
            name=name,
            version=version,
            stage=stage,
        )
        logger.info(f"Transitioned {name} v{version} to {stage}")

    def get_latest_model_version(
        self,
        name: str,
        stage: str | None = None,
    ) -> str | None:
        """
        Get the latest version of a model.

        Args:
            name: Model name
            stage: Optional stage filter

        Returns:
            Model version or None
        """
        try:
            if stage:
                versions = self.client.get_latest_versions(name, stages=[stage])
            else:
                versions = self.client.get_latest_versions(name)

            if versions:
                return versions[0].version
            return None
        except Exception as e:
            logger.error(f"Failed to get latest model version: {e}")
            return None

    def set_tag(self, key: str, value: str) -> None:
        """
        Set a tag on the current run.

        Args:
            key: Tag key
            value: Tag value
        """
        mlflow.set_tag(key, value)

    def set_tags(self, tags: dict[str, str]) -> None:
        """
        Set multiple tags on the current run.

        Args:
            tags: Tags to set
        """
        mlflow.set_tags(tags)


# Singleton instance
_mlflow_service: MLflowService | None = None


def get_mlflow_service(
    tracking_uri: str = "http://localhost:5000",
    experiment_name: str = "tawiza-training",
) -> MLflowService:
    """
    Get or create MLflow service instance.

    Args:
        tracking_uri: MLflow tracking URI
        experiment_name: Experiment name

    Returns:
        MLflow service instance
    """
    global _mlflow_service
    if _mlflow_service is None:
        _mlflow_service = MLflowService(
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
        )
    return _mlflow_service
