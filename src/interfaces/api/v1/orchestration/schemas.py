"""API schemas for orchestration."""

from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineStatus(StrEnum):
    """Pipeline status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorHandling(StrEnum):
    """Error handling strategies."""

    STOP = "stop"  # Stop pipeline on first error
    CONTINUE = "continue"  # Continue despite errors
    RETRY = "retry"  # Retry failed steps


class PipelineStep(BaseModel):
    """Single pipeline step."""

    service: str = Field(..., description="Service name (openmanus, skyvern, mlflow, label_studio)")
    action: str = Field(..., description="Action to perform")
    config: dict[str, Any] = Field(..., description="Step configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "openmanus",
                "action": "extract",
                "config": {"url": "https://example.com", "data": {"target": "main content"}},
            }
        }
    )


class PipelineCreate(BaseModel):
    """Create pipeline request."""

    name: str = Field(..., description="Pipeline name")
    steps: list[PipelineStep] = Field(..., description="Pipeline steps")
    error_handling: ErrorHandling = Field(
        default=ErrorHandling.STOP, description="Error handling strategy"
    )
    retry_policy: dict[str, int] | None = Field(
        default=None, description="Retry policy (max_retries, delay_seconds)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "data-collection-pipeline",
                "steps": [
                    {
                        "service": "skyvern",
                        "action": "extract",
                        "config": {
                            "url": "https://news.ycombinator.com",
                            "data": {"target": "top stories"},
                        },
                    },
                    {
                        "service": "label_studio",
                        "action": "create_project",
                        "config": {
                            "project_name": "HN Stories",
                            "labeling_config": '<View><Text name="text" value="$text"/></View>',
                        },
                    },
                ],
                "error_handling": "stop",
            }
        }
    )


class PipelineResponse(BaseModel):
    """Pipeline execution response."""

    pipeline_id: str
    name: str
    status: PipelineStatus
    steps_total: int
    steps_completed: int
    current_step: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PipelineResult(BaseModel):
    """Complete pipeline result."""

    pipeline_id: str
    name: str
    status: PipelineStatus
    steps_total: int
    steps_completed: int
    results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ServiceInfo(BaseModel):
    """Service information."""

    name: str
    type: str
    status: str = "active"
    description: str | None = None


class ServicesListResponse(BaseModel):
    """List of registered services."""

    services: list[ServiceInfo]
    total: int
