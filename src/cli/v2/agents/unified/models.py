"""Data models for the unified ReAct agent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    """A tool invocation by the agent."""

    model_config = ConfigDict(frozen=True)

    name: str  # e.g., "browser.navigate", "analyst.analyze", "finish"
    params: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    """Result of a tool execution."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    result: Any
    success: bool
    error: str | None = None
    duration_seconds: float = 0.0


class AgentStep(BaseModel):
    """A single step in the ReAct loop."""

    thought: str  # Agent's reasoning
    tool_call: ToolCall
    observation: Observation
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentResult(BaseModel):
    """Final result from agent execution."""

    success: bool
    answer: str | None = None
    error: str | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    duration_seconds: float = 0.0
    artifacts: list[str] = Field(default_factory=list)  # File paths created
