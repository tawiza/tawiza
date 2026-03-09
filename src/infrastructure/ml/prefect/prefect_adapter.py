"""Prefect adapter for workflow orchestration.

This adapter implements IWorkflowOrchestrator using Prefect
for ML training pipelines and automation.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger

from src.application.ports.ml_ports import IWorkflowOrchestrator

try:
    from prefect import flow, get_run_logger, task
    from prefect.client import get_client
    from prefect.deployments import Deployment
    from prefect.states import Cancelled, Completed, Failed, Pending, Running

    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    logger.warning(
        "Prefect not installed. Install with: pip install prefect"
    )


class PrefectAdapter(IWorkflowOrchestrator):
    """Adapter for Prefect workflow orchestration.

    Provides workflow management for ML operations including:
    - Training pipeline orchestration
    - Retraining automation
    - Model deployment workflows
    - Monitoring and alerting

    Attributes:
        api_url: Prefect API URL
        work_pool: Name of the work pool for execution
    """

    def __init__(
        self,
        api_url: str | None = None,
        work_pool: str = "default",
    ):
        """Initialize the Prefect adapter.

        Args:
            api_url: Prefect API URL (uses env var PREFECT_API_URL if not set)
            work_pool: Name of the work pool for flow execution
        """
        if not PREFECT_AVAILABLE:
            raise ImportError(
                "Prefect is not installed. "
                "Install with: pip install prefect"
            )

        self.api_url = api_url
        self.work_pool = work_pool
        self._client = None

        logger.info(
            f"PrefectAdapter initialized with work_pool={work_pool}"
        )

    async def _get_client(self):
        """Get or create Prefect client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    async def trigger_training_workflow(
        self,
        training_job_id: UUID,
        parameters: dict[str, Any],
    ) -> str:
        """Trigger a training workflow.

        Creates and runs a Prefect flow for model training with
        the specified parameters.

        Args:
            training_job_id: Training job UUID
            parameters: Workflow parameters including:
                - model_name: Name of the model
                - base_model: Base model to fine-tune
                - dataset_path: Path to training data
                - hyperparameters: Training hyperparameters
                - output_dir: Output directory

        Returns:
            Flow run ID
        """
        logger.info(
            f"Triggering training workflow for job {training_job_id}"
        )

        client = await self._get_client()

        # Create flow run
        flow_run = await client.create_flow_run(
            name=f"training-{training_job_id}",
            parameters={
                "training_job_id": str(training_job_id),
                **parameters,
            },
            tags=["training", "ml"],
        )

        flow_run_id = str(flow_run.id)

        logger.info(
            f"Training workflow started: flow_run_id={flow_run_id}"
        )

        return flow_run_id

    async def get_workflow_status(
        self,
        flow_run_id: str,
    ) -> dict[str, Any]:
        """Get the status of a workflow.

        Retrieves detailed information about a flow run including
        state, timing, and any errors.

        Args:
            flow_run_id: Flow run ID

        Returns:
            Dict containing:
                - status: Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
                - state_name: Prefect state name
                - start_time: Flow start time
                - end_time: Flow end time (if completed)
                - duration_seconds: Run duration
                - error_message: Error message (if failed)
                - task_runs: List of task run statuses
        """
        logger.debug(f"Getting workflow status: {flow_run_id}")

        client = await self._get_client()

        try:
            flow_run = await client.read_flow_run(flow_run_id)
        except Exception as e:
            logger.error(f"Failed to get flow run {flow_run_id}: {e}")
            return {
                "status": "UNKNOWN",
                "error": str(e),
                "flow_run_id": flow_run_id,
            }

        state = flow_run.state
        state_name = state.name if state else "UNKNOWN"

        # Map Prefect states to simple status
        status_map = {
            "PENDING": "PENDING",
            "RUNNING": "RUNNING",
            "COMPLETED": "COMPLETED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
            "CANCELLING": "CANCELLING",
            "PAUSED": "PAUSED",
            "SCHEDULED": "PENDING",
        }
        status = status_map.get(state_name, "UNKNOWN")

        # Calculate duration
        duration_seconds = None
        if flow_run.start_time:
            end_time = flow_run.end_time or datetime.utcnow()
            duration = end_time - flow_run.start_time
            duration_seconds = duration.total_seconds()

        # Get error message if failed
        error_message = None
        if state and state.is_failed():
            error_message = str(state.message) if state.message else "Unknown error"

        # Get task runs
        task_runs = await client.read_task_runs(
            flow_run_filter={"id": {"any_": [flow_run_id]}}
        )

        task_statuses = [
            {
                "task_name": tr.name,
                "status": tr.state.name if tr.state else "UNKNOWN",
                "start_time": tr.start_time.isoformat() if tr.start_time else None,
                "end_time": tr.end_time.isoformat() if tr.end_time else None,
            }
            for tr in task_runs
        ]

        response = {
            "flow_run_id": flow_run_id,
            "status": status,
            "state_name": state_name,
            "name": flow_run.name,
            "start_time": (
                flow_run.start_time.isoformat() if flow_run.start_time else None
            ),
            "end_time": (
                flow_run.end_time.isoformat() if flow_run.end_time else None
            ),
            "duration_seconds": duration_seconds,
            "error_message": error_message,
            "task_runs": task_statuses,
            "parameters": flow_run.parameters,
            "tags": flow_run.tags,
        }

        return response

    async def cancel_workflow(
        self,
        flow_run_id: str,
    ) -> None:
        """Cancel a running workflow.

        Sends a cancellation request to the flow run.
        The flow will transition to CANCELLED state.

        Args:
            flow_run_id: Flow run ID to cancel
        """
        logger.info(f"Cancelling workflow: {flow_run_id}")

        client = await self._get_client()

        try:
            await client.set_flow_run_state(
                flow_run_id=flow_run_id,
                state=Cancelled(message="Cancelled by user"),
            )
            logger.info(f"Workflow cancelled: {flow_run_id}")
        except Exception as e:
            logger.error(f"Failed to cancel workflow {flow_run_id}: {e}")
            raise

    async def trigger_retraining_workflow(
        self,
        model_id: str,
        trigger_reason: str,
        parameters: dict[str, Any],
    ) -> str:
        """Trigger an automated retraining workflow.

        Args:
            model_id: ID of the model to retrain
            trigger_reason: Reason for retraining (drift, schedule, manual)
            parameters: Retraining parameters

        Returns:
            Flow run ID
        """
        logger.info(
            f"Triggering retraining workflow for model {model_id}: {trigger_reason}"
        )

        client = await self._get_client()

        flow_run = await client.create_flow_run(
            name=f"retrain-{model_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            parameters={
                "model_id": model_id,
                "trigger_reason": trigger_reason,
                **parameters,
            },
            tags=["retraining", "ml", trigger_reason],
        )

        flow_run_id = str(flow_run.id)

        logger.info(
            f"Retraining workflow started: flow_run_id={flow_run_id}"
        )

        return flow_run_id

    async def trigger_deployment_workflow(
        self,
        model_id: str,
        model_path: str,
        deployment_config: dict[str, Any],
    ) -> str:
        """Trigger a model deployment workflow.

        Args:
            model_id: ID of the model to deploy
            model_path: Path to the trained model
            deployment_config: Deployment configuration

        Returns:
            Flow run ID
        """
        logger.info(f"Triggering deployment workflow for model {model_id}")

        client = await self._get_client()

        flow_run = await client.create_flow_run(
            name=f"deploy-{model_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            parameters={
                "model_id": model_id,
                "model_path": model_path,
                "config": deployment_config,
            },
            tags=["deployment", "ml"],
        )

        flow_run_id = str(flow_run.id)

        logger.info(
            f"Deployment workflow started: flow_run_id={flow_run_id}"
        )

        return flow_run_id

    async def list_flow_runs(
        self,
        limit: int = 50,
        tags: list[str] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent flow runs.

        Args:
            limit: Maximum number of runs to return
            tags: Filter by tags
            status: Filter by status

        Returns:
            List of flow run summaries
        """
        client = await self._get_client()

        # Build filters
        filters = {}
        if tags:
            filters["tags"] = {"all_": tags}
        if status:
            filters["state"] = {"name": {"any_": [status]}}

        flow_runs = await client.read_flow_runs(
            limit=limit,
            sort="EXPECTED_START_TIME_DESC",
            flow_run_filter=filters if filters else None,
        )

        return [
            {
                "flow_run_id": str(fr.id),
                "name": fr.name,
                "status": fr.state.name if fr.state else "UNKNOWN",
                "start_time": fr.start_time.isoformat() if fr.start_time else None,
                "end_time": fr.end_time.isoformat() if fr.end_time else None,
                "tags": fr.tags,
            }
            for fr in flow_runs
        ]

    async def health_check(self) -> bool:
        """Check if Prefect is properly configured and accessible.

        Returns:
            True if healthy
        """
        if not PREFECT_AVAILABLE:
            return False

        try:
            client = await self._get_client()
            # Try to read something to verify connection
            await client.read_flow_runs(limit=1)
            return True
        except Exception as e:
            logger.warning(f"Prefect health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the Prefect client connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.debug("Prefect client closed")


# Define reusable flows and tasks
if PREFECT_AVAILABLE:

    @task(name="validate_data")
    def validate_training_data(dataset_path: str) -> bool:
        """Validate training data exists and is valid."""
        from pathlib import Path
        path = Path(dataset_path)
        return path.exists() and path.stat().st_size > 0

    @task(name="prepare_training")
    def prepare_training_config(
        model_name: str,
        base_model: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare training configuration."""
        return {
            "model_name": model_name,
            "base_model": base_model,
            "hyperparameters": hyperparameters,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @task(name="run_training")
    async def run_training_task(
        config: dict[str, Any],
        dataset_path: str,
        output_dir: str,
    ) -> str:
        """Run the actual training."""
        logger = get_run_logger()
        logger.info(f"Starting training with config: {config}")

        # This would call the actual trainer
        # For now, return a mock run ID
        return f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    @flow(name="training_pipeline")
    async def training_pipeline_flow(
        training_job_id: str,
        model_name: str,
        base_model: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Main training pipeline flow.

        Args:
            training_job_id: Training job ID
            model_name: Model name
            base_model: Base model
            dataset_path: Training data path
            output_dir: Output directory
            hyperparameters: Training hyperparameters

        Returns:
            Training result
        """
        logger = get_run_logger()
        logger.info(f"Starting training pipeline for job {training_job_id}")

        # Validate data
        is_valid = validate_training_data(dataset_path)
        if not is_valid:
            raise ValueError(f"Invalid training data: {dataset_path}")

        # Prepare config
        config = prepare_training_config(
            model_name=model_name,
            base_model=base_model,
            hyperparameters=hyperparameters or {},
        )

        # Run training
        run_id = await run_training_task(
            config=config,
            dataset_path=dataset_path,
            output_dir=output_dir,
        )

        return {
            "training_job_id": training_job_id,
            "run_id": run_id,
            "status": "completed",
        }
