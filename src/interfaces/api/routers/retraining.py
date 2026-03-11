"""API routes for automatic model retraining."""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dtos.ml_dtos import TriggerRetrainingRequest, TriggerRetrainingResponse
from src.application.use_cases.automatic_retraining import (
    AutomaticRetrainingUseCase,
    PerformanceDegradationDetector,
    RetrainingScheduler,
)
from src.domain.entities.training_job import TrainingTrigger
from src.infrastructure.di.container import Container, get_container

router = APIRouter(prefix="/retraining", tags=["retraining"])


def get_automatic_retraining_use_case(
    container: Container = Depends(get_container),
) -> AutomaticRetrainingUseCase:
    """Get AutomaticRetrainingUseCase dependency."""
    return AutomaticRetrainingUseCase(
        model_repository=container.model_repository(),
        dataset_repository=container.dataset_repository(),
        training_job_repository=container.training_job_repository(),
        feedback_repository=container.feedback_repository(),
    )


def get_retraining_scheduler(
    container: Container = Depends(get_container),
) -> RetrainingScheduler:
    """Get RetrainingScheduler dependency."""
    automatic_retraining_uc = get_automatic_retraining_use_case(container)
    return RetrainingScheduler(
        automatic_retraining_uc=automatic_retraining_uc,
        model_repository=container.model_repository(),
    )


def get_performance_degradation_detector(
    container: Container = Depends(get_container),
) -> PerformanceDegradationDetector:
    """Get PerformanceDegradationDetector dependency."""
    automatic_retraining_uc = get_automatic_retraining_use_case(container)
    return PerformanceDegradationDetector(
        feedback_repository=container.feedback_repository(),
        automatic_retraining_uc=automatic_retraining_uc,
    )


@router.get("/check/{model_id}")
async def check_retraining_needed(
    model_id: UUID,
    use_case: AutomaticRetrainingUseCase = Depends(get_automatic_retraining_use_case),
) -> dict:
    """Check if a model needs retraining.

    Evaluates various conditions including:
    - Negative feedback percentage
    - Time since last deployment
    - Previous training job failures

    Args:
        model_id: Model ID to check
        use_case: Automatic retraining use case

    Returns:
        Decision with reasons and statistics

    Raises:
        HTTPException: If model not found
    """
    try:
        decision = await use_case.should_retrain(model_id)
        return decision

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check retraining status: {str(e)}",
        )


@router.post("/trigger", response_model=TriggerRetrainingResponse)
async def trigger_retraining(
    request: TriggerRetrainingRequest,
    use_case: AutomaticRetrainingUseCase = Depends(get_automatic_retraining_use_case),
) -> TriggerRetrainingResponse:
    """Manually trigger model retraining.

    Args:
        request: Retraining request
        use_case: Automatic retraining use case

    Returns:
        Training job information

    Raises:
        HTTPException: If model or dataset not found
    """
    try:
        # Convert string trigger_reason to TrainingTrigger enum
        trigger_map = {
            "scheduled": TrainingTrigger.SCHEDULED,
            "performance_degradation": TrainingTrigger.PERFORMANCE_DEGRADATION,
            "data_drift": TrainingTrigger.DATA_DRIFT,
            "manual": TrainingTrigger.MANUAL,
        }

        trigger = trigger_map.get(
            request.trigger_reason.lower(),
            TrainingTrigger.MANUAL,
        )

        training_job = await use_case.trigger_retraining(
            model_id=request.current_model_id,
            trigger=trigger,
            dataset_id=request.dataset_id,
        )

        return TriggerRetrainingResponse(
            training_job_id=training_job.id,
            trigger_reason=request.trigger_reason,
            status=training_job.status.value,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger retraining: {str(e)}",
        )


@router.post("/check-all-deployed")
async def check_all_deployed_models(
    scheduler: RetrainingScheduler = Depends(get_retraining_scheduler),
) -> list[dict]:
    """Check all deployed models and trigger retraining if needed.

    This endpoint is intended to be called by a scheduler (cron job, Prefect, etc.)
    to automatically check and retrain models.

    Args:
        scheduler: Retraining scheduler

    Returns:
        List of decisions for each deployed model
    """
    try:
        results = await scheduler.check_all_deployed_models()
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check deployed models: {str(e)}",
        )


@router.post("/check-degradation/{model_id}")
async def check_performance_degradation(
    model_id: UUID,
    detector: PerformanceDegradationDetector = Depends(get_performance_degradation_detector),
) -> dict:
    """Check for performance degradation and trigger retraining if needed.

    This endpoint can be called when significant negative feedback is detected
    to immediately trigger retraining.

    Args:
        model_id: Model ID to check
        detector: Performance degradation detector

    Returns:
        Information about retraining status
    """
    try:
        training_job = await detector.check_recent_degradation(model_id)

        if training_job:
            return {
                "degradation_detected": True,
                "retraining_triggered": True,
                "training_job_id": str(training_job.id),
                "status": training_job.status.value,
            }
        else:
            return {
                "degradation_detected": False,
                "retraining_triggered": False,
                "message": "No significant performance degradation detected",
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check performance degradation: {str(e)}",
        )
