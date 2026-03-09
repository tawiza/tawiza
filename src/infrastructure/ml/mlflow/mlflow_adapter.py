"""MLflow adapter for experiment tracking.

This adapter implements the IMLExperimentTracker port using MLflow.
"""

from typing import Any

import mlflow
from loguru import logger
from mlflow.tracking import MlflowClient

from src.application.ports.ml_ports import IMLExperimentTracker


class MLflowAdapter(IMLExperimentTracker):
    """Adapter for MLflow experiment tracking.

    This is an infrastructure adapter that implements the application port.
    It handles communication with MLflow tracking server.
    """

    def __init__(
        self,
        tracking_uri: str,
        experiment_name: str = "tawiza-training",
    ) -> None:
        """Initialize MLflow adapter.

        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: Name of the experiment
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.client = MlflowClient(tracking_uri=tracking_uri)

        # Set up experiment
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

        logger.info(
            f"Initialized MLflow adapter with tracking URI: {tracking_uri}, "
            f"experiment: {experiment_name}"
        )

    async def log_parameters(
        self,
        run_id: str,
        parameters: dict[str, Any],
    ) -> None:
        """Log parameters for an experiment run.

        Args:
            run_id: MLflow run ID
            parameters: Parameters to log
        """
        try:
            for key, value in parameters.items():
                self.client.log_param(run_id, key, value)
            logger.debug(f"Logged {len(parameters)} parameters to run {run_id}")
        except Exception as e:
            logger.error(f"Failed to log parameters: {e}")
            raise

    async def log_metrics(
        self,
        run_id: str,
        metrics: dict[str, float],
        step: int | None = None,
    ) -> None:
        """Log metrics for an experiment run.

        Args:
            run_id: MLflow run ID
            metrics: Metrics to log
            step: Optional step number for time-series metrics
        """
        try:
            for key, value in metrics.items():
                self.client.log_metric(run_id, key, value, step=step)
            logger.debug(
                f"Logged {len(metrics)} metrics to run {run_id}"
                + (f" at step {step}" if step else "")
            )
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")
            raise

    async def log_artifact(
        self,
        run_id: str,
        artifact_path: str,
        artifact_name: str,
    ) -> None:
        """Log an artifact for an experiment run.

        Args:
            run_id: MLflow run ID
            artifact_path: Local path to the artifact file
            artifact_name: Name for the artifact in MLflow
        """
        try:
            self.client.log_artifact(run_id, artifact_path, artifact_name)
            logger.debug(f"Logged artifact {artifact_name} to run {run_id}")
        except Exception as e:
            logger.error(f"Failed to log artifact: {e}")
            raise

    async def get_run(self, run_id: str) -> dict[str, Any]:
        """Get information about a run.

        Args:
            run_id: MLflow run ID

        Returns:
            Run information including parameters, metrics, and status
        """
        try:
            run = self.client.get_run(run_id)
            return {
                "run_id": run.info.run_id,
                "experiment_id": run.info.experiment_id,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                "artifact_uri": run.info.artifact_uri,
                "parameters": run.data.params,
                "metrics": run.data.metrics,
                "tags": run.data.tags,
            }
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            raise

    async def register_model(
        self,
        model_name: str,
        model_path: str,
        run_id: str,
    ) -> str:
        """Register a model in the MLflow model registry.

        Args:
            model_name: Name for the model in the registry
            model_path: Path to the model (usually artifact URI)
            run_id: Associated MLflow run ID

        Returns:
            Model version string
        """
        try:
            # Register model
            model_uri = f"runs:/{run_id}/{model_path}"
            result = mlflow.register_model(model_uri, model_name)

            logger.info(
                f"Registered model {model_name} version {result.version} "
                f"from run {run_id}"
            )

            return result.version

        except Exception as e:
            logger.error(f"Failed to register model: {e}")
            raise

    def start_run(
        self,
        run_name: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Start a new MLflow run.

        Args:
            run_name: Optional name for the run
            tags: Optional tags for the run

        Returns:
            Run ID
        """
        try:
            run = mlflow.start_run(run_name=run_name)
            run_id = run.info.run_id

            if tags:
                for key, value in tags.items():
                    mlflow.set_tag(key, value)

            logger.info(f"Started MLflow run: {run_id}")
            return run_id

        except Exception as e:
            logger.error(f"Failed to start run: {e}")
            raise

    def end_run(self, status: str = "FINISHED") -> None:
        """End the current MLflow run.

        Args:
            status: Run status ("FINISHED", "FAILED", "KILLED")
        """
        try:
            mlflow.end_run(status=status)
            logger.info(f"Ended MLflow run with status: {status}")
        except Exception as e:
            logger.error(f"Failed to end run: {e}")
            raise

    async def get_experiment_runs(
        self,
        experiment_name: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all runs for an experiment.

        Args:
            experiment_name: Name of the experiment (uses default if not provided)
            max_results: Maximum number of results to return

        Returns:
            List of run information dictionaries
        """
        try:
            exp_name = experiment_name or self.experiment_name
            experiment = self.client.get_experiment_by_name(exp_name)

            if not experiment:
                logger.warning(f"Experiment {exp_name} not found")
                return []

            runs = self.client.search_runs(
                experiment_ids=[experiment.experiment_id],
                max_results=max_results,
                order_by=["start_time DESC"],
            )

            return [
                {
                    "run_id": run.info.run_id,
                    "run_name": run.info.run_name,
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "parameters": run.data.params,
                    "metrics": run.data.metrics,
                }
                for run in runs
            ]

        except Exception as e:
            logger.error(f"Failed to get experiment runs: {e}")
            raise
