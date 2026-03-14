"""Service orchestrator implementation.

Coordinates workflows across multiple services:
- Web agents (OpenManus, Skyvern)
- MLflow (experiment tracking)
- Label Studio (data annotation)
- MinIO (storage)
- PostgreSQL (database)
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger

from src.application.ports.agent_ports import (
    IServiceOrchestrator,
    PipelineExecutionError,
    ServiceNotRegisteredError,
)


class PipelineStatus(StrEnum):
    """Status of pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ServiceOrchestrator(IServiceOrchestrator):
    """Orchestrates workflows across multiple services.

    Manages:
    - Service registration
    - Pipeline execution
    - Multi-step workflows
    - Error handling and retries
    - Progress tracking
    """

    def __init__(self) -> None:
        """Initialize service orchestrator."""
        self.services: dict[str, Any] = {}
        self.pipelines: dict[str, dict[str, Any]] = {}

        logger.info("Initialized Service Orchestrator")

    async def register_service(self, service_name: str, service_adapter: Any) -> None:
        """Register a service adapter.

        Args:
            service_name: Service identifier (e.g., "openmanus", "mlflow")
            service_adapter: Service adapter instance
        """
        self.services[service_name] = service_adapter
        logger.info(f"Registered service: {service_name}")

    async def get_registered_services(self) -> list[str]:
        """Get list of registered services.

        Returns:
            List of service names
        """
        return list(self.services.keys())

    async def execute_pipeline(self, pipeline_config: dict[str, Any]) -> dict[str, Any]:
        """Execute multi-service pipeline.

        Args:
            pipeline_config: Pipeline configuration:
                - name: Pipeline name
                - steps: List of steps
                - error_handling: "stop" | "continue" | "retry"
                - retry_policy: {max_retries, delay}

        Returns:
            Pipeline execution result

        Example:
            ```python
            {
                "name": "data-collection",
                "steps": [
                    {
                        "service": "skyvern",
                        "action": "scrape",
                        "config": {"url": "...", "selectors": {...}}
                    },
                    {
                        "service": "label_studio",
                        "action": "create_project",
                        "config": {"project_name": "..."}
                    }
                ]
            }
            ```
        """
        pipeline_id = str(uuid.uuid4())[:8]
        pipeline_name = pipeline_config.get("name", f"pipeline-{pipeline_id}")

        logger.info(f"Starting pipeline: {pipeline_name} (ID: {pipeline_id})")

        # Create pipeline state
        self.pipelines[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "name": pipeline_name,
            "config": pipeline_config,
            "status": PipelineStatus.PENDING,
            "steps_total": len(pipeline_config.get("steps", [])),
            "steps_completed": 0,
            "current_step": None,
            "results": [],
            "errors": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            # Update status to running
            self._update_pipeline(pipeline_id, {"status": PipelineStatus.RUNNING})

            # Execute steps
            steps = pipeline_config.get("steps", [])
            error_handling = pipeline_config.get("error_handling", "stop")

            for step_idx, step in enumerate(steps):
                step_num = step_idx + 1
                logger.info(f"Pipeline {pipeline_id}: Step {step_num}/{len(steps)}")

                self._update_pipeline(
                    pipeline_id,
                    {
                        "current_step": {
                            "number": step_num,
                            "service": step.get("service"),
                            "action": step.get("action"),
                        }
                    },
                )

                try:
                    # Execute step
                    result = await self._execute_step(pipeline_id, step)

                    # Store result
                    self.pipelines[pipeline_id]["results"].append(
                        {
                            "step": step_num,
                            "service": step.get("service"),
                            "action": step.get("action"),
                            "result": result,
                            "status": "success",
                        }
                    )

                    # Update progress
                    self._update_pipeline(pipeline_id, {"steps_completed": step_num})

                except Exception as e:
                    logger.error(
                        f"Pipeline {pipeline_id} step {step_num} failed: {e}", exc_info=True
                    )

                    # Store error
                    self.pipelines[pipeline_id]["errors"].append(
                        {
                            "step": step_num,
                            "service": step.get("service"),
                            "action": step.get("action"),
                            "error": str(e),
                        }
                    )

                    # Handle error based on policy
                    if error_handling == "stop":
                        raise PipelineExecutionError(
                            f"Pipeline failed at step {step_num}: {e}"
                        ) from e
                    elif error_handling == "continue":
                        logger.warning(f"Continuing despite error: {e}")
                        continue
                    # Note: retry logic can be added here

            # Mark as completed
            self._update_pipeline(pipeline_id, {"status": PipelineStatus.COMPLETED})

            logger.info(f"Pipeline {pipeline_id} completed successfully")

            return await self.get_pipeline_status(pipeline_id)

        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} failed: {e}", exc_info=True)

            self._update_pipeline(pipeline_id, {"status": PipelineStatus.FAILED})

            raise

    async def _execute_step(self, pipeline_id: str, step: dict[str, Any]) -> Any:
        """Execute a single pipeline step.

        Args:
            pipeline_id: Pipeline identifier
            step: Step configuration

        Returns:
            Step result
        """
        service_name = step.get("service")
        action = step.get("action")
        config = step.get("config", {})

        if not service_name:
            raise PipelineExecutionError("Step must specify service")

        if service_name not in self.services:
            raise ServiceNotRegisteredError(
                f"Service '{service_name}' not registered. Available: {list(self.services.keys())}"
            )

        service = self.services[service_name]

        logger.debug(f"Executing {service_name}.{action} for pipeline {pipeline_id}")

        # Route to appropriate service method
        if service_name in ["openmanus", "skyvern"]:
            # Web agent
            result = await service.execute_task({**config, "action": action})

        elif service_name == "mlflow":
            # MLflow operations
            result = await self._execute_mlflow_action(service, action, config)

        elif service_name == "label_studio":
            # Label Studio operations
            result = await self._execute_labelstudio_action(service, action, config)

        else:
            raise PipelineExecutionError(f"Unknown service type: {service_name}")

        return result

    async def _execute_mlflow_action(
        self, mlflow_service: Any, action: str, config: dict[str, Any]
    ) -> Any:
        """Execute MLflow action."""
        if action == "start_run":
            run_id = mlflow_service.start_run(
                run_name=config.get("run_name"), tags=config.get("tags")
            )
            return {"run_id": run_id}

        elif action == "log_metrics":
            await mlflow_service.log_metrics(run_id=config["run_id"], metrics=config["metrics"])
            return {"status": "logged"}

        elif action == "log_parameters":
            await mlflow_service.log_parameters(
                run_id=config["run_id"], parameters=config["parameters"]
            )
            return {"status": "logged"}

        elif action == "get_experiment_runs":
            runs = await mlflow_service.get_experiment_runs(
                experiment_name=config.get("experiment_name"),
                max_results=config.get("max_results", 100),
            )
            return {"runs": runs}

        else:
            raise PipelineExecutionError(f"Unknown MLflow action: {action}")

    async def _execute_labelstudio_action(
        self, labelstudio_service: Any, action: str, config: dict[str, Any]
    ) -> Any:
        """Execute Label Studio action."""
        if action == "create_project":
            project_id = await labelstudio_service.create_project(
                project_name=config["project_name"], labeling_config=config["labeling_config"]
            )
            return {"project_id": project_id}

        elif action == "import_tasks":
            task_ids = await labelstudio_service.import_tasks(
                project_id=config["project_id"], tasks=config["tasks"]
            )
            return {"task_ids": task_ids}

        elif action == "get_annotations":
            annotations = await labelstudio_service.get_annotations(project_id=config["project_id"])
            return {"annotations": annotations}

        elif action == "get_progress":
            progress = await labelstudio_service.get_annotation_progress(
                project_id=config["project_id"]
            )
            return progress

        else:
            raise PipelineExecutionError(f"Unknown Label Studio action: {action}")

    async def get_pipeline_status(self, pipeline_id: str) -> dict[str, Any]:
        """Get pipeline status.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Pipeline status
        """
        if pipeline_id not in self.pipelines:
            raise PipelineExecutionError(f"Pipeline {pipeline_id} not found")

        pipeline = self.pipelines[pipeline_id]

        return {
            "pipeline_id": pipeline["pipeline_id"],
            "name": pipeline["name"],
            "status": pipeline["status"],
            "steps_total": pipeline["steps_total"],
            "steps_completed": pipeline["steps_completed"],
            "current_step": pipeline["current_step"],
            "errors": pipeline["errors"],
            "created_at": pipeline["created_at"],
            "updated_at": pipeline["updated_at"],
        }

    async def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancel running pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            True if cancelled
        """
        if pipeline_id not in self.pipelines:
            raise PipelineExecutionError(f"Pipeline {pipeline_id} not found")

        pipeline = self.pipelines[pipeline_id]

        if pipeline["status"] not in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
            raise PipelineExecutionError(f"Cannot cancel pipeline with status {pipeline['status']}")

        self._update_pipeline(pipeline_id, {"status": PipelineStatus.CANCELLED})

        logger.info(f"Cancelled pipeline {pipeline_id}")
        return True

    async def stream_pipeline_progress(self, pipeline_id: str) -> AsyncGenerator[dict[str, Any]]:
        """Stream pipeline progress.

        Args:
            pipeline_id: Pipeline identifier

        Yields:
            Progress updates
        """
        import asyncio

        if pipeline_id not in self.pipelines:
            raise PipelineExecutionError(f"Pipeline {pipeline_id} not found")

        while True:
            status = await self.get_pipeline_status(pipeline_id)

            yield {
                "pipeline_id": pipeline_id,
                "status": status["status"],
                "progress": (
                    status["steps_completed"] / status["steps_total"] * 100
                    if status["steps_total"] > 0
                    else 0
                ),
                "current_step": status["current_step"],
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Stop if completed/failed/cancelled
            if status["status"] in [
                PipelineStatus.COMPLETED,
                PipelineStatus.FAILED,
                PipelineStatus.CANCELLED,
            ]:
                break

            await asyncio.sleep(1)

    def _update_pipeline(self, pipeline_id: str, updates: dict[str, Any]) -> None:
        """Update pipeline state."""
        if pipeline_id in self.pipelines:
            self.pipelines[pipeline_id].update(updates)
            self.pipelines[pipeline_id]["updated_at"] = datetime.utcnow().isoformat()
