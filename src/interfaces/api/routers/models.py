"""Models API router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from src.domain.entities.ml_model import ModelStatus
from src.domain.exceptions import EntityNotFoundError
from src.infrastructure.di.container import get_container
from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.repositories.ml_model_repository import (
    SQLAlchemyMLModelRepository,
)

router = APIRouter()


# API models
class ModelInfoResponse(BaseModel):
    """API model for model information."""

    id: UUID
    name: str
    version: str
    status: str
    base_model: str
    description: str
    accuracy: float | None = None
    deployed_at: str | None = None
    traffic_percentage: int = 0
    created_at: str
    updated_at: str


class ListModelsResponse(BaseModel):
    """API model for list models response."""

    models: list[ModelInfoResponse]
    total: int
    page: int
    page_size: int


class DeployModelRequest(BaseModel):
    """API model for deploy model request."""

    model_id: UUID = Field(..., description="ID of the model to deploy")
    strategy: str = Field(
        "canary",
        description="Deployment strategy: 'direct', 'canary', 'blue_green', or 'a_b_test'",
    )
    traffic_percentage: int = Field(
        10,
        ge=0,
        le=100,
        description="Initial traffic percentage (for canary deployments)",
    )
    auto_promote: bool = Field(
        False,
        description="Automatically promote if metrics are good",
    )


class DeployModelResponse(BaseModel):
    """API model for deploy model response."""

    model_id: UUID
    deployment_status: str
    traffic_percentage: int
    endpoint_url: str | None = None


class UpdateTrafficRequest(BaseModel):
    """API model for update traffic request."""

    new_percentage: int = Field(
        ...,
        ge=0,
        le=100,
        description="New traffic percentage",
    )


@router.get(
    "",
    response_model=ListModelsResponse,
    summary="List models",
    description="List all ML models with pagination",
)
async def list_models(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, description="Filter by status"),
) -> ListModelsResponse:
    """List all models with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        status_filter: Optional status filter

    Returns:
        List of models with pagination info
    """
    try:
        repository = SQLAlchemyMLModelRepository(get_session)

        # Parse status filter
        status_enum = None
        if status_filter:
            try:
                status_enum = ModelStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in ModelStatus]}",
                )

        # Get paginated models
        models, total = await repository.list_paginated(
            page=page, page_size=page_size, status=status_enum
        )

        # Convert to response
        model_responses = []
        for model in models:
            model_responses.append(
                ModelInfoResponse(
                    id=model.id,
                    name=model.name,
                    version=model.version,
                    status=model.status.value,
                    base_model=model.base_model,
                    description=model.description,
                    accuracy=model.metrics.accuracy if model.metrics else None,
                    deployed_at=model._deployed_at.isoformat() if model._deployed_at else None,
                    traffic_percentage=model.traffic_percentage,
                    created_at=model.created_at.isoformat(),
                    updated_at=model.updated_at.isoformat(),
                )
            )

        return ListModelsResponse(
            models=model_responses, total=total, page=page, page_size=page_size
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list models",
        )


@router.get(
    "/{model_id}",
    response_model=ModelInfoResponse,
    summary="Get model",
    description="Get detailed information about a specific model",
)
async def get_model(
    model_id: UUID,
) -> ModelInfoResponse:
    """Get detailed information about a model.

    Args:
        model_id: Model UUID

    Returns:
        Model information

    Raises:
        HTTPException: If model not found
    """
    try:
        repository = SQLAlchemyMLModelRepository(get_session)
        model = await repository.get_by_id(model_id)

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found",
            )

        return ModelInfoResponse(
            id=model.id,
            name=model.name,
            version=model.version,
            status=model.status.value,
            base_model=model.base_model,
            description=model.description,
            accuracy=model.metrics.accuracy if model.metrics else None,
            deployed_at=model._deployed_at.isoformat() if model._deployed_at else None,
            traffic_percentage=model.traffic_percentage,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get model",
        )


@router.post(
    "/deploy",
    response_model=DeployModelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Deploy model",
    description="Deploy a trained model to production",
)
async def deploy_model(
    request: DeployModelRequest,
) -> DeployModelResponse:
    """Deploy a model to production.

    Args:
        request: Deployment request

    Returns:
        Deployment response with status

    Raises:
        HTTPException: If deployment fails
    """
    try:
        container = get_container()
        use_case = container.deploy_model_use_case()

        result = await use_case.execute(
            model_id=str(request.model_id),
            strategy=request.strategy,
            traffic_percentage=request.traffic_percentage,
            auto_promote=request.auto_promote,
        )

        return DeployModelResponse(
            model_id=request.model_id,
            deployment_status="deploying",
            traffic_percentage=request.traffic_percentage,
            endpoint_url=result.endpoint if hasattr(result, "endpoint") else None,
        )

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except RuntimeError as e:
        logger.error(f"Deployment dependencies not ready: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment service not available",
        )
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Deployment failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deployment failed",
        )


@router.patch(
    "/{model_id}/traffic",
    summary="Update traffic",
    description="Update traffic percentage for canary deployment",
)
async def update_traffic(
    model_id: UUID,
    request: UpdateTrafficRequest,
):
    """Update traffic routing for a canary deployment.

    Args:
        model_id: Model UUID
        request: Traffic update request

    Returns:
        Updated traffic information

    Raises:
        HTTPException: If update fails
    """
    try:
        container = get_container()
        deployer = container.model_deployer()
        repo = container.model_repository()

        # Verify model exists
        model = await repo.get_by_id(str(model_id))
        if model is None:
            raise EntityNotFoundError("Model", str(model_id))

        # Update traffic
        await deployer.update_traffic(
            model_id=str(model_id),
            traffic_percentage=request.new_percentage,
        )

        return {
            "model_id": str(model_id),
            "traffic_percentage": request.new_percentage,
            "status": "updated",
        }

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Traffic update failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Traffic update failed",
        )


@router.post(
    "/{model_id}/retire",
    status_code=status.HTTP_200_OK,
    summary="Retire model",
    description="Retire a deployed model",
)
async def retire_model(
    model_id: UUID,
    reason: str = Query("", description="Reason for retirement"),
):
    """Retire a deployed model.

    Args:
        model_id: Model UUID
        reason: Reason for retirement

    Returns:
        Retirement confirmation

    Raises:
        HTTPException: If retirement fails
    """
    try:
        container = get_container()
        repo = container.model_repository()
        deployer = container.model_deployer()

        # Verify model exists
        model = await repo.get_by_id(str(model_id))
        if model is None:
            raise EntityNotFoundError("Model", str(model_id))

        # Undeploy if deployed
        try:
            await deployer.undeploy(str(model_id))
        except Exception as e:
            logger.warning(f"Could not undeploy model {model_id}: {e}")

        # Update status to retired
        await repo.update_status(str(model_id), ModelStatus.RETIRED)

        return {
            "model_id": str(model_id),
            "status": "retired",
            "reason": reason,
            "message": "Model retired successfully",
        }

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Model retirement failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model retirement failed",
        )


@router.get(
    "/{model_id}/metrics",
    summary="Get model metrics",
    description="Get performance metrics for a model",
)
async def get_model_metrics(
    model_id: UUID,
    time_range_hours: int = Query(24, ge=1, le=720, description="Time range in hours"),
):
    """Get performance metrics for a model.

    Args:
        model_id: Model UUID
        time_range_hours: Time range for metrics

    Returns:
        Model metrics

    Raises:
        HTTPException: If failed to get metrics
    """
    try:
        container = get_container()
        repo = container.model_repository()
        experiment_tracker = container.mlflow_adapter()

        # Verify model exists
        model = await repo.get_by_id(str(model_id))
        if model is None:
            raise EntityNotFoundError("Model", str(model_id))

        # Get metrics from MLflow
        metrics = await experiment_tracker.get_model_metrics(
            model_id=str(model_id),
            time_range_hours=time_range_hours,
        )

        return {
            "model_id": str(model_id),
            "time_range_hours": time_range_hours,
            "metrics": metrics if metrics else {},
            "status": model.status.value if hasattr(model.status, "value") else str(model.status),
        }

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metrics",
        )
