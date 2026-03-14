"""API schemas for agents."""

from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AgentType(StrEnum):
    """Agent types."""

    OPENMANUS = "openmanus"
    SKYVERN = "skyvern"


class TaskAction(StrEnum):
    """Task actions."""

    NAVIGATE = "navigate"
    EXTRACT = "extract"
    FILL_FORM = "fill_form"
    CLICK = "click"
    SCREENSHOT = "screenshot"


class TaskStatus(StrEnum):
    """Task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTaskCreate(BaseModel):
    """Create agent task request."""

    agent_type: AgentType = Field(default=AgentType.OPENMANUS, description="Type of agent to use")
    url: HttpUrl = Field(..., description="Target URL for the task")
    action: TaskAction = Field(..., description="Action to perform")
    selectors: dict[str, str] | None = Field(default=None, description="CSS selectors for elements")
    data: dict[str, Any] | None = Field(
        default=None, description="Data for the action (e.g., form fields, extraction targets)"
    )
    options: dict[str, Any] | None = Field(default=None, description="Additional options")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_type": "openmanus",
                "url": "https://example.com",
                "action": "extract",
                "data": {"target": "main content"},
            }
        }
    )


class AgentTaskResponse(BaseModel):
    """Agent task response."""

    task_id: str = Field(..., description="Task identifier")
    agent_type: AgentType = Field(..., description="Agent type")
    status: TaskStatus = Field(..., description="Current status")
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    current_step: str | None = Field(None, description="Current step description")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class AgentTaskResult(BaseModel):
    """Agent task result."""

    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    screenshots: list[dict[str, str]] = Field(default_factory=list)
    logs: list[dict[str, str]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class AgentTaskList(BaseModel):
    """List of agent tasks."""

    tasks: list[AgentTaskResponse]
    total: int
    limit: int
    offset: int
