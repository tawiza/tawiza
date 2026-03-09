"""Orchestration API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from src.infrastructure.agents.openmanus import OpenManusAdapter
from src.infrastructure.agents.skyvern import SkyvernAdapter
from src.infrastructure.config.settings import Settings
from src.infrastructure.ml.label_studio import LabelStudioAdapter
from src.infrastructure.ml.mlflow import MLflowAdapter
from src.infrastructure.orchestration import ServiceOrchestrator
from src.interfaces.api.v1.orchestration.schemas import (
    PipelineCreate,
    PipelineResponse,
    PipelineResult,
    PipelineStatus,
    ServiceInfo,
    ServicesListResponse,
)

router = APIRouter(prefix="/orchestration", tags=["Orchestration"])

# Global orchestrator instance
_orchestrator: ServiceOrchestrator | None = None
_initialized = False


async def get_orchestrator() -> ServiceOrchestrator:
    """Get or initialize orchestrator with all services."""
    global _orchestrator, _initialized

    if not _orchestrator:
        _orchestrator = ServiceOrchestrator()

    if not _initialized:
        # Register agents
        _orchestrator.services["openmanus"] = OpenManusAdapter()
        _orchestrator.services["skyvern"] = SkyvernAdapter()

        # Register ML services (if configured)
        try:
            settings = Settings()

            # MLflow
            mlflow_adapter = MLflowAdapter(
                tracking_uri=str(settings.mlflow.tracking_uri),
                experiment_name=settings.mlflow.experiment_name
            )
            _orchestrator.services["mlflow"] = mlflow_adapter
            logger.info("Registered MLflow service")

            # Label Studio
            labelstudio_adapter = LabelStudioAdapter(settings)
            _orchestrator.services["label_studio"] = labelstudio_adapter
            logger.info("Registered Label Studio service")

        except Exception as e:
            logger.warning(f"Could not register ML services: {e}")

        _initialized = True
        logger.info(
            f"Orchestrator initialized with services: "
            f"{list(_orchestrator.services.keys())}"
        )

    return _orchestrator


@router.get("/pipelines")
async def list_pipelines(
    limit: int = 10,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """List all pipelines.

    Returns a list of all pipelines with their current status.
    """
    try:
        pipelines = []

        # Get all pipelines from orchestrator
        for pipeline_id, pipeline_data in orchestrator.pipelines.items():
            pipelines.append({
                "pipeline_id": pipeline_id,
                "name": pipeline_data.get("name", "Unknown"),
                "status": pipeline_data.get("status", "unknown"),
                "steps_total": pipeline_data.get("steps_total", 0),
                "steps_completed": pipeline_data.get("steps_completed", 0),
                "created_at": pipeline_data.get("created_at", ""),
                "updated_at": pipeline_data.get("updated_at", "")
            })

        # Sort by created_at (most recent first) and apply limit
        pipelines.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        pipelines = pipelines[:limit]

        return {
            "pipelines": pipelines,
            "total": len(orchestrator.pipelines),
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines", response_model=PipelineResponse, status_code=202)
async def create_pipeline(
    pipeline: PipelineCreate,
    background_tasks: BackgroundTasks,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Create and execute a multi-service pipeline.

    Pipelines coordinate tasks across multiple services:
    - Web agents (OpenManus, Skyvern)
    - MLflow (experiment tracking)
    - Label Studio (data annotation)

    **Example:**
    ```json
    {
        "name": "data-collection",
        "steps": [
            {
                "service": "skyvern",
                "action": "extract",
                "config": {
                    "url": "https://example.com",
                    "data": {"target": "articles"}
                }
            },
            {
                "service": "label_studio",
                "action": "create_project",
                "config": {
                    "project_name": "Article Annotation",
                    "labeling_config": "<View>...</View>"
                }
            }
        ],
        "error_handling": "stop"
    }
    ```
    """
    logger.info(f"Creating pipeline: {pipeline.name}")

    try:
        # Convert to dict
        pipeline_config = pipeline.model_dump()

        # Start pipeline in background
        background_tasks.add_task(
            orchestrator.execute_pipeline,
            pipeline_config
        )

        # Create temporary pipeline ID for immediate response
        # (actual execution creates real ID)
        import uuid
        temp_id = str(uuid.uuid4())[:8]

        return PipelineResponse(
            pipeline_id=temp_id,
            name=pipeline.name,
            status=PipelineStatus.PENDING,
            steps_total=len(pipeline.steps),
            steps_completed=0,
            current_step=None,
            errors=[],
            created_at="",
            updated_at=""
        )

    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline_status(
    pipeline_id: str,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Get pipeline status."""
    try:
        status = await orchestrator.get_pipeline_status(pipeline_id)
        return PipelineResponse(**status)

    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pipelines/{pipeline_id}/result", response_model=PipelineResult)
async def get_pipeline_result(
    pipeline_id: str,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Get complete pipeline result.

    Returns detailed results from all pipeline steps.
    """
    try:
        if pipeline_id not in orchestrator.pipelines:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline {pipeline_id} not found"
            )

        pipeline = orchestrator.pipelines[pipeline_id]

        return PipelineResult(
            pipeline_id=pipeline["pipeline_id"],
            name=pipeline["name"],
            status=PipelineStatus(pipeline["status"]),
            steps_total=pipeline["steps_total"],
            steps_completed=pipeline["steps_completed"],
            results=pipeline.get("results", []),
            errors=pipeline.get("errors", []),
            created_at=pipeline["created_at"],
            updated_at=pipeline["updated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pipelines/{pipeline_id}")
async def cancel_pipeline(
    pipeline_id: str,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Cancel running pipeline."""
    try:
        success = await orchestrator.cancel_pipeline(pipeline_id)

        return {
            "pipeline_id": pipeline_id,
            "cancelled": success,
            "message": f"Pipeline {pipeline_id} cancelled"
        }

    except Exception as e:
        logger.error(f"Failed to cancel pipeline: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pipelines/{pipeline_id}/stream")
async def stream_pipeline_progress(
    pipeline_id: str,
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Stream pipeline progress via Server-Sent Events.

    Example (JavaScript):
    ```javascript
    const eventSource = new EventSource(
        '/api/v1/orchestration/pipelines/pipeline-123/stream'
    );
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Pipeline progress:', data.progress, '%');
    };
    ```
    """
    try:
        async def event_stream():
            """Generate SSE events."""
            async for progress in orchestrator.stream_pipeline_progress(pipeline_id):
                import json
                yield f"data: {json.dumps(progress)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Failed to stream pipeline progress: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/services", response_model=ServicesListResponse)
async def list_services(
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """List registered services.

    Returns all services available for pipeline orchestration.
    """
    try:
        service_names = await orchestrator.get_registered_services()

        services = []
        for name in service_names:
            service_info = ServiceInfo(
                name=name,
                type=_get_service_type(name),
                status="active",
                description=_get_service_description(name)
            )
            services.append(service_info)

        return ServicesListResponse(
            services=services,
            total=len(services)
        )

    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(
    orchestrator: ServiceOrchestrator = Depends(get_orchestrator)
):
    """Orchestration service health check."""
    services = await orchestrator.get_registered_services()

    return {
        "status": "healthy",
        "services_registered": len(services),
        "services": services
    }


def _get_service_type(service_name: str) -> str:
    """Get service type."""
    type_map = {
        "openmanus": "agent",
        "skyvern": "agent",
        "mlflow": "ml_tracking",
        "label_studio": "annotation"
    }
    return type_map.get(service_name, "unknown")


def _get_service_description(service_name: str) -> str:
    """Get service description."""
    descriptions = {
        "openmanus": "Web automation agent for data collection",
        "skyvern": "Production-ready web automation with vision AI",
        "mlflow": "ML experiment tracking and model registry",
        "label_studio": "Data annotation and labeling platform"
    }
    return descriptions.get(service_name, "")
