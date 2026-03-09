"""Data Transfer Objects for Active Learning API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# Sampling DTOs
class SelectSamplesRequest(BaseModel):
    """Request to select samples for labeling."""

    model_name: str = Field(..., description="Name of the model")
    model_version: str = Field(..., description="Version of the model")
    strategy_type: str = Field(
        ...,
        description="Sampling strategy: uncertainty, margin, entropy, diversity",
        pattern="^(uncertainty|margin|entropy|diversity|random)$",
    )
    sample_count: int = Field(..., gt=0, le=1000, description="Number of samples to select")
    threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Optional confidence/score threshold"
    )
    diversity_metric: str | None = Field(
        None, description="Distance metric for diversity sampling (cosine, euclidean)"
    )
    filters: dict[str, Any] | None = Field(
        None, description="Optional filters for candidate samples"
    )


class SampleScoreResponse(BaseModel):
    """Response model for a sample score."""

    sample_id: str
    score: float
    confidence: float | None = None
    entropy: float | None = None
    margin: float | None = None
    metadata: dict[str, Any] | None = None


class SamplingResultResponse(BaseModel):
    """Response model for sampling result."""

    strategy_type: str
    selected_samples: list[SampleScoreResponse]
    total_candidates: int
    sample_count: int = Field(..., description="Number of samples selected")
    average_score: float
    execution_time_ms: float | None = None
    metadata: dict[str, Any] | None = None


# Drift Detection DTOs
class DetectDriftRequest(BaseModel):
    """Request to detect drift for a model."""

    model_name: str = Field(..., description="Name of the model")
    model_version: str = Field(..., description="Version of the model")
    drift_type: str = Field(
        ...,
        description="Type of drift: data_drift, concept_drift, prediction_drift, performance_drift",
        pattern="^(data_drift|concept_drift|prediction_drift|performance_drift)$",
    )
    window_start: datetime | None = Field(
        None, description="Start of monitoring window (ISO format)"
    )
    window_end: datetime | None = Field(
        None, description="End of monitoring window (ISO format)"
    )


class DriftReportResponse(BaseModel):
    """Response model for drift report."""

    id: UUID
    model_name: str
    model_version: str
    drift_type: str
    metric_name: str
    current_value: float
    baseline_value: float
    drift_score: float
    is_drifted: bool
    severity: str
    threshold: float | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_count: int | None = None
    deviation_percentage: float
    requires_action: bool
    details: dict[str, Any] | None = None
    created_at: datetime


# Retraining DTOs
class TriggerRetrainingRequest(BaseModel):
    """Request to trigger model retraining."""

    model_name: str = Field(..., description="Name of the model")
    model_version: str = Field(..., description="Version of the model")
    trigger_reason: str = Field(
        ..., description="Reason for triggering retraining (drift_detected, error_threshold, manual, etc.)"
    )
    config: dict[str, Any] | None = Field(
        None, description="Optional training configuration"
    )


class RetrainingJobResponse(BaseModel):
    """Response model for retraining job."""

    id: UUID
    trigger_reason: str
    model_name: str
    base_model_version: str
    new_samples_count: int
    status: str
    fine_tuning_job_id: str | None = None
    new_model_version: str | None = None
    drift_report_id: UUID | None = None
    error_message: str | None = None
    config: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    is_terminal: bool


class RetrainingConditionsResponse(BaseModel):
    """Response model for retraining conditions."""

    model_name: str
    model_version: str
    conditions: dict[str, Any]
    retraining_recommended: bool
    recommendation_reason: str | None = None


# Active Learning Health Status DTOs
class ModelHealthStatusResponse(BaseModel):
    """Response model for model health status."""

    model_name: str
    model_version: str
    drift_detected: bool
    latest_drift_report: DriftReportResponse | None = None
    error_rate: float
    new_samples_available: int
    days_since_training: int
    retraining_recommended: bool
    recommendation_reason: str | None = None
    pending_labeling_samples: int
    last_checked: datetime
