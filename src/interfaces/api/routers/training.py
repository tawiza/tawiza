"""Training API router."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.dataset import DatasetStatus
from src.domain.entities.ml_model import MLModel, ModelStatus
from src.domain.entities.training_job import (
    TrainingConfig,
    TrainingJob,
    TrainingJobStatus,
    TrainingTrigger,
)
from src.infrastructure.di.container import get_container
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.repositories.dataset_repository import (
    SQLAlchemyDatasetRepository,
)
from src.infrastructure.persistence.repositories.ml_model_repository import (
    SQLAlchemyMLModelRepository,
)
from src.infrastructure.persistence.repositories.training_job_repository import (
    SQLAlchemyTrainingJobRepository,
)

router = APIRouter()


# API models
class TrainModelRequest(BaseModel):
    """API model for train model request."""

    name: str = Field(..., description="Model name")
    version: str = Field("1.0.0", description="Model version")
    base_model: str = Field(
        ..., description="Base model to fine-tune (e.g., 'meta-llama/Llama-2-7b-chat-hf')"
    )
    dataset_id: UUID = Field(..., description="Dataset ID to use for training")
    description: str = Field("", description="Model description")

    # Training hyperparameters
    batch_size: int = Field(4, ge=1, le=128, description="Training batch size")
    learning_rate: float = Field(2e-5, gt=0, description="Learning rate")
    num_epochs: int = Field(3, ge=1, le=100, description="Number of training epochs")
    max_seq_length: int = Field(2048, ge=128, le=8192, description="Maximum sequence length")
    lora_rank: int = Field(8, ge=1, le=256, description="LoRA rank")
    lora_alpha: int = Field(16, ge=1, le=512, description="LoRA alpha")
    use_rlhf: bool = Field(False, description="Use RLHF training")


class TrainModelResponse(BaseModel):
    """API model for train model response."""

    training_job_id: UUID
    model_id: UUID
    status: str
    mlflow_run_id: str | None = None
    message: str = "Training job started successfully"


class TrainingJobInfo(BaseModel):
    """API model for training job information."""

    id: UUID
    name: str
    status: str
    trigger: str
    model_id: UUID | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    metrics: dict = {}


class ListTrainingJobsResponse(BaseModel):
    """API model for list training jobs response."""

    jobs: list[TrainingJobInfo]
    total: int
    page: int
    page_size: int


class TriggerRetrainingRequest(BaseModel):
    """API model for trigger retraining request."""

    trigger_reason: str = Field(
        ...,
        description="Reason for retraining: 'scheduled', 'performance_degradation', 'data_drift', or 'new_data_threshold'",
    )
    current_model_id: UUID | None = Field(
        None,
        description="Current model ID (uses latest deployed if not provided)",
    )
    dataset_id: UUID | None = Field(
        None,
        description="Dataset ID (uses latest if not provided)",
    )


@router.post(
    "",
    response_model=TrainModelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train model",
    description="Start training a new ML model",
)
async def train_model(
    request: TrainModelRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TrainModelResponse:
    """Train a new model.

    MVP version: Creates model and training job entities, but doesn't actually start training.
    Real training will be implemented with TrainModelUseCase + MLflow + Celery.

    Args:
        request: Training request with model configuration
        session: Database session

    Returns:
        Training job information

    Raises:
        HTTPException: If training fails to start
    """
    try:
        model_repo = SQLAlchemyMLModelRepository(session)
        dataset_repo = SQLAlchemyDatasetRepository(session)
        job_repo = SQLAlchemyTrainingJobRepository(session)

        # 1. Validate dataset exists and is ready
        dataset = await dataset_repo.get_by_id(request.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {request.dataset_id} not found")

        if dataset.status != DatasetStatus.READY:
            raise ValueError(
                f"Dataset {dataset.name} is not ready (status: {dataset.status.value})"
            )

        # 2. Check if model with same name/version already exists
        existing = await model_repo.get_by_name_and_version(request.name, request.version)
        if existing:
            raise ValueError(f"Model {request.name} v{request.version} already exists")

        # 3. Create model entity
        model_id = uuid4()
        model = MLModel(
            id=model_id,
            name=request.name,
            version=request.version,
            base_model=request.base_model,
            description=request.description,
            status=ModelStatus.DRAFT,
        )

        # 4. Create training config
        config = TrainingConfig(
            base_model=request.base_model,
            dataset_id=request.dataset_id,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            num_epochs=request.num_epochs,
            max_seq_length=request.max_seq_length,
            lora_rank=request.lora_rank,
            lora_alpha=request.lora_alpha,
            use_rlhf=request.use_rlhf,
        )

        # 5. Create training job
        job_id = uuid4()
        job = TrainingJob(
            id=job_id,
            name=f"train_{request.name}_{request.version}",
            trigger=TrainingTrigger.MANUAL,
        )
        job.configure(config=config)
        # Note: Job status is PENDING by default

        # 6. Save entities
        await model_repo.save(model)
        await job_repo.save(job)
        await session.commit()

        logger.info(
            f"Created training job {job_id} for model {model_id} (MVP - training not started)"
        )

        return TrainModelResponse(
            training_job_id=job_id,
            model_id=model_id,
            status=job.status.value,
            mlflow_run_id=None,  # Will be set when real training starts
            message="Training job created (MVP mode - manual start required for actual training)",
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Training failed to start: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start training",
        )


@router.get(
    "",
    response_model=ListTrainingJobsResponse,
    summary="List training jobs",
    description="List all training jobs with pagination",
)
async def list_training_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_db_session),
) -> ListTrainingJobsResponse:
    """List all training jobs with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        status_filter: Optional status filter
        session: Database session

    Returns:
        List of training jobs with pagination info
    """
    try:
        job_repo = SQLAlchemyTrainingJobRepository(session)

        # Parse status filter
        status_enum = None
        if status_filter:
            try:
                status_enum = TrainingJobStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in TrainingJobStatus]}",
                )

        # Get jobs (with filter if provided)
        if status_enum:
            jobs = await job_repo.get_by_status(
                status=status_enum,
                skip=(page - 1) * page_size,
                limit=page_size,
            )
            # Get count with filter (use count_by_status if available, else approximate)
            try:
                total = await job_repo.count_by_status(status_enum)
            except AttributeError:
                total = len(jobs)  # Fallback for repositories without count_by_status
        else:
            jobs = await job_repo.get_all(
                skip=(page - 1) * page_size,
                limit=page_size,
            )
            total = await job_repo.count()

        # Convert to response
        job_responses = []
        for job in jobs:
            job_responses.append(
                TrainingJobInfo(
                    id=job.id,
                    name=job.name,
                    status=job.status.value,
                    trigger=job.trigger.value,
                    model_id=job.output_model_id,
                    started_at=job._started_at.isoformat() if job._started_at else None,
                    completed_at=job._completed_at.isoformat() if job._completed_at else None,
                    duration_seconds=job.duration_seconds,
                    metrics=job.metrics,
                )
            )

        return ListTrainingJobsResponse(
            jobs=job_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list training jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list training jobs",
        )


@router.get(
    "/{job_id}",
    response_model=TrainingJobInfo,
    summary="Get training job",
    description="Get detailed information about a training job",
)
async def get_training_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingJobInfo:
    """Get training job details.

    Args:
        job_id: Training job UUID
        session: Database session

    Returns:
        Training job information

    Raises:
        HTTPException: If job not found
    """
    try:
        job_repo = SQLAlchemyTrainingJobRepository(session)
        job = await job_repo.get_by_id(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Training job {job_id} not found",
            )

        return TrainingJobInfo(
            id=job.id,
            name=job.name,
            status=job.status.value,
            trigger=job.trigger.value,
            model_id=job.output_model_id,
            started_at=job._started_at.isoformat() if job._started_at else None,
            completed_at=job._completed_at.isoformat() if job._completed_at else None,
            duration_seconds=job.duration_seconds,
            metrics=job.metrics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get training job",
        )


@router.post(
    "/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel training job",
    description="Cancel a running training job",
)
async def cancel_training_job(job_id: UUID):
    """Cancel a training job.

    Args:
        job_id: Training job UUID

    Returns:
        Cancellation confirmation

    Raises:
        HTTPException: If cancellation fails
    """
    try:
        container = get_container()
        job_repo = container.training_job_repository()
        trainer = container.model_trainer()

        # Get job
        job = await job_repo.get_by_id(str(job_id))
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Training job {job_id} not found",
            )

        # Check if cancellable
        if job.status not in [TrainingJobStatus.PENDING, TrainingJobStatus.RUNNING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {job.status.value}",
            )

        # Cancel via trainer
        try:
            await trainer.cancel_job(str(job_id))
        except Exception as e:
            logger.warning(f"Trainer cancel failed: {e}")

        # Update status
        job.status = TrainingJobStatus.CANCELLED
        await job_repo.update(job)

        return {
            "job_id": str(job_id),
            "status": "cancelled",
            "message": "Training job cancelled",
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to cancel training job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel training job",
        )


@router.post(
    "/retrain",
    response_model=TrainModelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger retraining",
    description="Trigger automatic retraining based on various conditions",
)
async def trigger_retraining(
    request: TriggerRetrainingRequest,
) -> TrainModelResponse:
    """Trigger automatic retraining.

    This is used by the continuous learning system to automatically
    retrain models based on performance degradation, data drift, etc.

    Args:
        request: Retraining trigger request

    Returns:
        Training job information

    Raises:
        HTTPException: If retraining fails to start
    """
    try:
        container = get_container()
        use_case = container.train_model_use_case()

        # Execute training
        result = await use_case.execute(
            model_id=str(request.model_id),
            dataset_id=str(request.dataset_id) if request.dataset_id else None,
            config=request.config,
        )

        return TrainModelResponse(
            job_id=result.job_id if hasattr(result, "job_id") else uuid4(),
            status="started",
            message="Retraining job started",
        )

    except RuntimeError as e:
        logger.error(f"Retraining dependencies not ready: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training service not available",
        )
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Retraining failed to start: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger retraining",
        )


@router.get(
    "/{job_id}/logs",
    summary="Get training logs",
    description="Get logs for a training job",
)
async def get_training_logs(
    job_id: UUID,
    tail: int = Query(100, ge=1, le=10000, description="Number of log lines to return"),
):
    """Get training logs.

    Args:
        job_id: Training job UUID
        tail: Number of log lines to return

    Returns:
        Training logs

    Raises:
        HTTPException: If logs not found
    """
    try:
        container = get_container()
        job_repo = container.training_job_repository()
        trainer = container.model_trainer()

        # Verify job exists
        job = await job_repo.get_by_id(str(job_id))
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Training job {job_id} not found",
            )

        # Get logs from trainer
        try:
            logs = await trainer.get_logs(str(job_id), tail=tail)
        except Exception as e:
            logger.warning(f"Could not get trainer logs: {e}")
            logs = []

        return {
            "job_id": str(job_id),
            "logs": logs,
            "tail": tail,
            "job_status": job.status.value,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get training logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get training logs",
        )
