"""API routes for Active Learning system."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.dtos.active_learning_dtos import (
    DetectDriftRequest,
    DriftReportResponse,
    RetrainingConditionsResponse,
    RetrainingJobResponse,
    SampleScoreResponse,
    SamplingResultResponse,
    SelectSamplesRequest,
    TriggerRetrainingRequest,
)
from src.application.use_cases.active_learning import (
    DetectDriftUseCase,
    GetDriftReportsUseCase,
    GetRetrainingConditionsUseCase,
    SelectSamplesForLabelingUseCase,
    TriggerRetrainingUseCase,
)
from src.domain.entities.drift_report import DriftType
from src.domain.value_objects.sampling import SamplingConfig, SamplingStrategyType
from src.infrastructure.di.container import Container, get_container

router = APIRouter(prefix="/active-learning", tags=["active-learning"])


# Dependency injection helpers
def get_select_samples_use_case(
    container: Container = Depends(get_container),
) -> SelectSamplesForLabelingUseCase:
    """Get SelectSamplesForLabelingUseCase dependency."""
    # Note: Strategy selection would be based on request params
    # For now, return uncertainty sampling as default
    from src.infrastructure.ml.active_learning.sampling_strategies import (
        UncertaintySamplingStrategy,
    )

    strategy = UncertaintySamplingStrategy(
        feedback_repository=container.feedback_repository(),
        model_repository=container.model_repository(),
    )

    return SelectSamplesForLabelingUseCase(
        sampling_strategy=strategy,
        model_repository=container.model_repository(),
        event_bus=None,  # container.event_bus() if available
    )


def get_detect_drift_use_case(
    container: Container = Depends(get_container),
) -> DetectDriftUseCase:
    """Get DetectDriftUseCase dependency."""
    from src.infrastructure.ml.active_learning.drift_detector import (
        PerformanceDriftDetector,
    )

    drift_detector = PerformanceDriftDetector(
        feedback_repository=container.feedback_repository(),
        model_repository=container.model_repository(),
    )

    return DetectDriftUseCase(
        drift_detector=drift_detector,
        drift_report_repository=container.drift_report_repository(),
        model_repository=container.model_repository(),
        event_bus=None,
    )


def get_trigger_retraining_use_case(
    container: Container = Depends(get_container),
) -> TriggerRetrainingUseCase:
    """Get TriggerRetrainingUseCase dependency."""
    from src.infrastructure.ml.active_learning.retraining_trigger import (
        RetrainingTriggerService,
    )

    retraining_trigger = RetrainingTriggerService(
        feedback_repository=container.feedback_repository(),
        model_repository=container.model_repository(),
    )

    return TriggerRetrainingUseCase(
        retraining_trigger=retraining_trigger,
        retraining_job_repository=container.retraining_job_repository(),
        model_repository=container.model_repository(),
        event_bus=None,
    )


def get_retraining_conditions_use_case(
    container: Container = Depends(get_container),
) -> GetRetrainingConditionsUseCase:
    """Get GetRetrainingConditionsUseCase dependency."""
    from src.infrastructure.ml.active_learning.retraining_trigger import (
        RetrainingTriggerService,
    )

    retraining_trigger = RetrainingTriggerService(
        feedback_repository=container.feedback_repository(),
        model_repository=container.model_repository(),
    )

    return GetRetrainingConditionsUseCase(
        retraining_trigger=retraining_trigger,
        model_repository=container.model_repository(),
    )


def get_drift_reports_use_case(
    container: Container = Depends(get_container),
) -> GetDriftReportsUseCase:
    """Get GetDriftReportsUseCase dependency."""
    return GetDriftReportsUseCase(
        drift_report_repository=container.drift_report_repository(),
    )


# Sample Selection Endpoints
@router.post("/samples/select", response_model=SamplingResultResponse)
async def select_samples_for_labeling(
    request: SelectSamplesRequest,
    use_case: SelectSamplesForLabelingUseCase = Depends(get_select_samples_use_case),
) -> SamplingResultResponse:
    """Select samples for labeling using active learning.

    This endpoint applies a sampling strategy to identify the most informative
    samples for labeling, helping to improve model performance efficiently.

    Strategies:
    - **uncertainty**: Select samples with lowest model confidence
    - **margin**: Select samples with smallest margin between top predictions
    - **entropy**: Select samples with highest prediction entropy
    - **diversity**: Select diverse samples using clustering
    """
    try:
        # Create sampling config
        config = SamplingConfig(
            strategy_type=SamplingStrategyType(request.strategy_type),
            sample_count=request.sample_count,
            threshold=request.threshold,
            diversity_metric=request.diversity_metric,
            filters=request.filters,
        )

        # Execute use case
        result = await use_case.execute(
            model_name=request.model_name,
            model_version=request.model_version,
            config=config,
            feedback_filters=request.filters,
        )

        # Convert to response
        return SamplingResultResponse(
            strategy_type=result.strategy_type.value,
            selected_samples=[
                SampleScoreResponse(
                    sample_id=s.sample_id,
                    score=s.score,
                    confidence=s.confidence,
                    entropy=s.entropy,
                    margin=s.margin,
                    metadata=s.metadata,
                )
                for s in result.selected_samples
            ],
            total_candidates=result.total_candidates,
            sample_count=len(result.selected_samples),
            average_score=result.get_average_score(),
            execution_time_ms=result.execution_time_ms,
            metadata=result.metadata,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select samples: {str(e)}",
        )


# Drift Detection Endpoints
@router.post("/drift/detect", response_model=DriftReportResponse | None)
async def detect_drift(
    request: DetectDriftRequest,
    use_case: DetectDriftUseCase = Depends(get_detect_drift_use_case),
) -> DriftReportResponse | None:
    """Detect drift in model performance or data distribution.

    Analyzes model predictions and feedback to detect when the model's
    performance has degraded or data distribution has changed.

    Returns drift report if drift is detected, None otherwise.
    """
    try:
        drift_report = await use_case.execute(
            model_name=request.model_name,
            model_version=request.model_version,
            drift_type=DriftType(request.drift_type),
            window_start=request.window_start,
            window_end=request.window_end,
        )

        if drift_report:
            return DriftReportResponse(
                id=drift_report.id,
                model_name=drift_report.model_name,
                model_version=drift_report.model_version,
                drift_type=drift_report.drift_type.value,
                metric_name=drift_report.metric_name,
                current_value=drift_report.current_value,
                baseline_value=drift_report.baseline_value,
                drift_score=drift_report.drift_score,
                is_drifted=drift_report.is_drifted,
                severity=drift_report.severity.value,
                threshold=drift_report.threshold,
                window_start=drift_report.window_start,
                window_end=drift_report.window_end,
                sample_count=drift_report.sample_count,
                deviation_percentage=drift_report.get_deviation_percentage(),
                requires_action=drift_report.requires_action(),
                details=drift_report.details,
                created_at=drift_report.created_at,
            )

        return None

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect drift: {str(e)}",
        )


@router.get("/drift/reports")
async def get_drift_reports(
    model_name: str | None = Query(None, description="Filter by model name"),
    model_version: str | None = Query(None, description="Filter by model version"),
    drifted_only: bool = Query(False, description="Show only reports where drift was detected"),
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reports to return"),
    use_case: GetDriftReportsUseCase = Depends(get_drift_reports_use_case),
) -> list[DriftReportResponse]:
    """Get drift reports with optional filtering.

    Returns a list of drift reports, optionally filtered by model
    and whether drift was actually detected.
    """
    try:
        if model_name and model_version:
            reports = await use_case.get_by_model(
                model_name=model_name,
                model_version=model_version,
                skip=skip,
                limit=limit,
            )
        elif drifted_only:
            reports = await use_case.get_drifted_reports(
                model_name=model_name, skip=skip, limit=limit
            )
        else:
            # Get all reports (would need to add this to use case)
            reports = []

        return [
            DriftReportResponse(
                id=r.id,
                model_name=r.model_name,
                model_version=r.model_version,
                drift_type=r.drift_type.value,
                metric_name=r.metric_name,
                current_value=r.current_value,
                baseline_value=r.baseline_value,
                drift_score=r.drift_score,
                is_drifted=r.is_drifted,
                severity=r.severity.value,
                threshold=r.threshold,
                window_start=r.window_start,
                window_end=r.window_end,
                sample_count=r.sample_count,
                deviation_percentage=r.get_deviation_percentage(),
                requires_action=r.requires_action(),
                details=r.details,
                created_at=r.created_at,
            )
            for r in reports
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drift reports: {str(e)}",
        )


# Retraining Endpoints
@router.post("/retraining/trigger", response_model=RetrainingJobResponse)
async def trigger_retraining(
    request: TriggerRetrainingRequest,
    use_case: TriggerRetrainingUseCase = Depends(get_trigger_retraining_use_case),
) -> RetrainingJobResponse:
    """Trigger model retraining.

    Creates a retraining job for the specified model. This can be used
    to manually trigger retraining or as part of an automated workflow.
    """
    try:
        job = await use_case.execute(
            model_name=request.model_name,
            model_version=request.model_version,
            trigger_reason=request.trigger_reason,
            config=request.config,
        )

        return RetrainingJobResponse(
            id=job.id,
            trigger_reason=job.trigger_reason.value,
            model_name=job.model_name,
            base_model_version=job.base_model_version,
            new_samples_count=job.new_samples_count,
            status=job.status.value,
            fine_tuning_job_id=job.fine_tuning_job_id,
            new_model_version=job.new_model_version,
            drift_report_id=job.drift_report_id,
            error_message=job.error_message,
            config=job.config,
            metrics=job.metrics,
            metadata=job.metadata,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.get_duration_seconds(),
            is_terminal=job.is_terminal_state(),
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger retraining: {str(e)}",
        )


@router.get("/retraining/conditions")
async def get_retraining_conditions(
    model_name: str = Query(..., description="Model name"),
    model_version: str = Query(..., description="Model version"),
    use_case: GetRetrainingConditionsUseCase = Depends(get_retraining_conditions_use_case),
) -> RetrainingConditionsResponse:
    """Get retraining conditions and recommendations for a model.

    Returns metrics used to determine if retraining should be triggered,
    along with a recommendation and reason.
    """
    try:
        result = await use_case.execute(
            model_name=model_name, model_version=model_version
        )

        return RetrainingConditionsResponse(
            model_name=result["model_name"],
            model_version=result["model_version"],
            conditions=result["conditions"],
            retraining_recommended=result["retraining_recommended"],
            recommendation_reason=result["recommendation_reason"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get retraining conditions: {str(e)}",
        )


@router.post("/retraining/check-and-trigger")
async def check_and_trigger_retraining(
    model_name: str = Query(..., description="Model name"),
    model_version: str = Query(..., description="Model version"),
    use_case: TriggerRetrainingUseCase = Depends(get_trigger_retraining_use_case),
) -> RetrainingJobResponse | None:
    """Check if retraining is needed and trigger if so.

    Evaluates retraining conditions and automatically triggers retraining
    if recommended. Returns the retraining job if triggered, None otherwise.
    """
    try:
        job = await use_case.check_and_trigger_if_needed(
            model_name=model_name, model_version=model_version
        )

        if job:
            return RetrainingJobResponse(
                id=job.id,
                trigger_reason=job.trigger_reason.value,
                model_name=job.model_name,
                base_model_version=job.base_model_version,
                new_samples_count=job.new_samples_count,
                status=job.status.value,
                fine_tuning_job_id=job.fine_tuning_job_id,
                new_model_version=job.new_model_version,
                drift_report_id=job.drift_report_id,
                error_message=job.error_message,
                config=job.config,
                metrics=job.metrics,
                metadata=job.metadata,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=job.get_duration_seconds(),
                is_terminal=job.is_terminal_state(),
            )

        return None

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check and trigger retraining: {str(e)}",
        )
