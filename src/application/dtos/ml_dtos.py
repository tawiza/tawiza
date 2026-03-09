"""Data Transfer Objects for ML operations."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


# Training DTOs
@dataclass
class TrainModelRequest:
    """Request to train a new model."""

    name: str
    base_model: str
    dataset_id: UUID
    version: str = "1.0.0"
    description: str = ""
    batch_size: int = 4
    learning_rate: float = 2e-5
    num_epochs: int = 3
    max_seq_length: int = 2048
    lora_rank: int = 8
    lora_alpha: int = 16
    use_rlhf: bool = False


@dataclass
class TrainModelResponse:
    """Response from training a model."""

    training_job_id: UUID
    model_id: UUID
    status: str
    mlflow_run_id: str | None = None


# Prediction DTOs
@dataclass
class PredictionRequest:
    """Request for model prediction."""

    input_data: dict[str, Any]
    model_id: UUID | None = None  # If None, use latest deployed model
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 0.9


@dataclass
class PredictionResponse:
    """Response from model prediction."""

    prediction_id: UUID
    model_id: UUID
    model_version: str
    output: dict[str, Any]
    confidence: float | None = None
    latency_ms: float | None = None


# Feedback DTOs
@dataclass
class SubmitFeedbackRequest:
    """Request to submit feedback on a prediction."""

    model_id: UUID
    feedback_type: str  # "thumbs_up", "thumbs_down", "rating", "correction", "bug_report"
    prediction_id: str | None = None
    rating: int | None = None  # 1-5 for rating type
    comment: str | None = None
    correction: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SubmitFeedbackResponse:
    """Response from submitting feedback."""

    feedback_id: UUID
    model_id: UUID
    feedback_type: str
    status: str
    created_at: str


@dataclass
class FeedbackStatisticsResponse:
    """Response with feedback statistics for a model."""

    model_id: UUID
    model_name: str
    model_version: str
    total_count: int
    counts_by_type: dict[str, int]
    average_rating: float | None
    negative_count: int
    negative_percentage: float


# Dataset DTOs
@dataclass
class CreateDatasetRequest:
    """Request to create a new dataset."""

    name: str
    dataset_type: str  # "training", "validation", "test"
    source: str
    storage_path: str
    size: int
    format: str = "jsonl"
    annotations_required: bool = True


@dataclass
class CreateDatasetResponse:
    """Response from creating a dataset."""

    dataset_id: UUID
    name: str
    status: str


# Deployment DTOs
@dataclass
class DeployModelRequest:
    """Request to deploy a model."""

    model_id: UUID
    strategy: str = "canary"  # "direct", "canary", "blue_green", "a_b_test"
    traffic_percentage: int = 10
    auto_promote: bool = False
    rollback_threshold: float = 0.1  # Rollback if error rate > 10%


@dataclass
class DeployModelResponse:
    """Response from deploying a model."""

    model_id: UUID
    deployment_status: str
    traffic_percentage: int
    endpoint_url: str | None = None


@dataclass
class UpdateTrafficRequest:
    """Request to update traffic for canary deployment."""

    model_id: UUID
    new_percentage: int


@dataclass
class UpdateTrafficResponse:
    """Response from updating traffic."""

    model_id: UUID
    traffic_percentage: int
    status: str


# Model DTOs
@dataclass
class ModelInfo:
    """Information about a model."""

    id: UUID
    name: str
    version: str
    status: str
    accuracy: float | None = None
    deployed_at: str | None = None
    traffic_percentage: int = 0


@dataclass
class ListModelsResponse:
    """Response from listing models."""

    models: list[ModelInfo]
    total: int
    page: int
    page_size: int


# Training Job DTOs
@dataclass
class TrainingJobInfo:
    """Information about a training job."""

    id: UUID
    name: str
    status: str
    trigger: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    metrics: dict[str, float] = None

    def __post_init__(self) -> None:
        """Initialize metrics dict if None."""
        if self.metrics is None:
            self.metrics = {}


@dataclass
class ListTrainingJobsResponse:
    """Response from listing training jobs."""

    jobs: list[TrainingJobInfo]
    total: int
    page: int
    page_size: int


# Retraining DTOs
@dataclass
class TriggerRetrainingRequest:
    """Request to trigger automatic retraining."""

    trigger_reason: str  # "scheduled", "performance_degradation", "data_drift"
    current_model_id: UUID | None = None
    dataset_id: UUID | None = None  # If None, use latest available


@dataclass
class TriggerRetrainingResponse:
    """Response from triggering retraining."""

    training_job_id: UUID
    trigger_reason: str
    status: str


# Annotation DTOs
@dataclass
class CreateAnnotationProjectRequest:
    """Request to create annotation project in Label Studio."""

    dataset_id: UUID
    project_name: str
    labeling_config: str
    enable_ml_backend: bool = True


@dataclass
class CreateAnnotationProjectResponse:
    """Response from creating annotation project."""

    project_id: int
    dataset_id: UUID
    project_url: str


# Metrics DTOs
@dataclass
class ModelMetricsRequest:
    """Request for model metrics."""

    model_id: UUID
    metric_types: list[str]  # ["accuracy", "latency", "throughput", "error_rate"]
    time_range_hours: int = 24


@dataclass
class ModelMetricsResponse:
    """Response with model metrics."""

    model_id: UUID
    metrics: dict[str, Any]
    time_range_hours: int


# Data drift DTOs
@dataclass
class DataDriftReport:
    """Data drift detection report."""

    drift_detected: bool
    drift_score: float
    drifted_features: list[str]
    report_path: str | None = None


@dataclass
class CheckDataDriftRequest:
    """Request to check for data drift."""

    reference_dataset_id: UUID
    current_dataset_id: UUID | None = None  # If None, use production data
    threshold: float = 0.5


@dataclass
class CheckDataDriftResponse:
    """Response from data drift check."""

    report: DataDriftReport
    should_retrain: bool
