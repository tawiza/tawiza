"""Unified Adaptive Agent API routes.

Provides REST API for the self-improving UAA:
- GET /status: Agent status (autonomy level, trust score)
- POST /execute: Execute a task
- POST /tasks/{id}/approve: Approve pending task
- POST /tasks/{id}/reject: Reject pending task
- POST /tasks/{id}/feedback: Record feedback
- GET /stats: Detailed statistics
- POST /learn: Trigger learning cycle
- GET /pending: List pending tasks
- GET /config: Get configuration
- PUT /config: Update configuration
"""

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/uaa", tags=["Unified Adaptive Agent"])

# Global agent instance (singleton)
_agent_instance = None


def get_agent():
    """Get or create the global UAA instance."""
    global _agent_instance
    if _agent_instance is None:
        from src.infrastructure.agents.unified import UnifiedAdaptiveAgent

        _agent_instance = UnifiedAdaptiveAgent()
    return _agent_instance


# Pydantic schemas
class StatusResponse(BaseModel):
    """Agent status response."""

    autonomy_level: str
    autonomy_level_value: int = 0
    trust_score: float
    learning_enabled: bool
    pending_tasks: int
    in_cooldown: bool = False


class ExecuteRequest(BaseModel):
    """Task execution request."""

    description: str = Field(..., description="Natural language task description")
    task_type: str | None = Field(None, description="Task type for routing")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    priority: int = Field(0, description="Task priority (higher = more urgent)")


class TaskResultResponse(BaseModel):
    """Task result response."""

    task_id: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0
    tool_used: str | None = None


class RejectRequest(BaseModel):
    """Task rejection request."""

    reason: str = Field("", description="Rejection reason")


class FeedbackRequest(BaseModel):
    """Feedback request."""

    feedback: str = Field(..., description="positive or negative")
    correction: str | None = Field(None, description="Corrected output for learning")


class FeedbackResponse(BaseModel):
    """Feedback response."""

    success: bool
    trust_score: float
    autonomy_level: str


class StatsResponse(BaseModel):
    """Agent statistics response."""

    tasks_completed: int
    tasks_failed: int
    tasks_pending: int
    success_rate: float
    trust_stats: dict[str, Any]
    learning_stats: dict[str, Any]


class LearningResponse(BaseModel):
    """Learning cycle response."""

    state: str
    accuracy_before: float = 0.0
    accuracy_after: float = 0.0
    improvement: float = 0.0
    message: str = ""


class PendingTaskResponse(BaseModel):
    """Pending task info."""

    task_id: str
    description: str
    task_type: str | None = None
    priority: int = 0
    created_at: str


class ConfigResponse(BaseModel):
    """Agent configuration response."""

    llm_model: str
    max_concurrent_tasks: int
    default_timeout: int
    autonomy_level: str
    learning_enabled: bool


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""

    autonomy_level: str | None = None
    learning_enabled: bool | None = None


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get agent status.

    Returns current autonomy level, trust score, and operational status.
    """
    agent = get_agent()
    status = agent.get_status()
    return StatusResponse(**status)


@router.post("/execute", response_model=TaskResultResponse)
async def execute_task(request: ExecuteRequest):
    """Execute a task through the agent.

    The agent will route the task to the appropriate tool based on
    the task description and current autonomy level.

    If approval is required, returns status='awaiting_approval'.
    """
    from src.infrastructure.agents.unified import TaskRequest

    agent = get_agent()
    task_id = str(uuid.uuid4())[:8]

    task_request = TaskRequest(
        task_id=task_id,
        description=request.description,
        task_type=request.task_type,
        context=request.context,
        priority=request.priority,
    )

    try:
        result = await agent.execute(task_request)

        return TaskResultResponse(
            task_id=result.task_id,
            status=result.status.value,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            tool_used=result.tool_used,
        )
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/approve", response_model=TaskResultResponse)
async def approve_task(task_id: str):
    """Approve a pending task.

    Approves the task and executes it immediately.
    Records positive feedback to improve trust score.
    """
    agent = get_agent()

    try:
        result = await agent.approve(task_id)

        return TaskResultResponse(
            task_id=result.task_id,
            status=result.status.value,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            tool_used=result.tool_used,
        )
    except Exception as e:
        logger.error(f"Task approval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/reject", response_model=TaskResultResponse)
async def reject_task(task_id: str, request: RejectRequest):
    """Reject a pending task.

    Cancels the task and records negative feedback.
    """
    agent = get_agent()

    try:
        result = await agent.reject(task_id, request.reason)

        return TaskResultResponse(
            task_id=result.task_id,
            status=result.status.value,
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            tool_used=result.tool_used,
        )
    except Exception as e:
        logger.error(f"Task rejection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/feedback", response_model=FeedbackResponse)
async def record_feedback(task_id: str, request: FeedbackRequest):
    """Record feedback for a task.

    Positive feedback improves trust score.
    Negative feedback with correction is saved for learning.
    """
    if request.feedback not in ("positive", "negative"):
        raise HTTPException(
            status_code=400,
            detail="Feedback must be 'positive' or 'negative'",
        )

    agent = get_agent()

    try:
        agent.record_feedback(
            task_id=task_id,
            feedback=request.feedback,
            correction=request.correction,
        )

        return FeedbackResponse(
            success=True,
            trust_score=agent.trust_score,
            autonomy_level=agent.autonomy_level.name,
        )
    except Exception as e:
        logger.error(f"Feedback recording failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get detailed agent statistics.

    Returns task completion stats, trust metrics, and learning progress.
    """
    agent = get_agent()
    stats = agent.get_stats()
    return StatsResponse(**stats)


@router.post("/learn", response_model=LearningResponse)
async def trigger_learning(
    force: bool = False,
    background_tasks: BackgroundTasks = None,
):
    """Trigger a learning cycle.

    Collects examples, prepares dataset, and fine-tunes the model.
    Use force=true to trigger even if not enough examples.
    """
    agent = get_agent()

    if not agent.learning_engine.should_trigger_learning() and not force:
        stats = agent.learning_engine.get_stats()
        return LearningResponse(
            state="NOT_READY",
            message=f"Need {stats.get('min_examples', 50)} examples, have {stats.get('examples_collected', 0)}",
        )

    try:
        cycle = await agent.learning_engine.run_full_cycle()

        if cycle:
            return LearningResponse(
                state=cycle.state if hasattr(cycle, "state") else "COMPLETED",
                accuracy_before=cycle.metrics.accuracy_before if hasattr(cycle, "metrics") else 0.0,
                accuracy_after=cycle.metrics.accuracy_after if hasattr(cycle, "metrics") else 0.0,
                improvement=cycle.metrics.accuracy_improvement
                if hasattr(cycle, "metrics")
                else 0.0,
            )
        else:
            return LearningResponse(
                state="COMPLETED",
                message="Learning cycle completed",
            )
    except Exception as e:
        logger.error(f"Learning cycle failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending", response_model=list[PendingTaskResponse])
async def list_pending():
    """List all pending tasks awaiting approval.

    Returns task details including description, type, and priority.
    """
    agent = get_agent()
    pending = []

    for task_id, request in agent._pending_tasks.items():
        pending.append(
            PendingTaskResponse(
                task_id=task_id,
                description=request.description,
                task_type=request.task_type,
                priority=request.priority,
                created_at=request.created_at.isoformat(),
            )
        )

    return pending


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get current agent configuration.

    Returns model, concurrency, timeout, and learning settings.
    """
    agent = get_agent()

    return ConfigResponse(
        llm_model=agent.config.llm_model,
        max_concurrent_tasks=agent.config.max_concurrent_tasks,
        default_timeout=agent.config.default_timeout,
        autonomy_level=agent.trust_manager.level.name,
        learning_enabled=agent.config.learning.auto_learning_enabled,
    )


@router.put("/config", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest):
    """Update agent configuration.

    Allows changing autonomy level and learning settings.
    """
    from src.infrastructure.agents.unified import AutonomyLevel

    agent = get_agent()

    if request.autonomy_level:
        try:
            level = AutonomyLevel[request.autonomy_level.upper()]
            agent.trust_manager._level = level
            logger.info(f"Autonomy level set to {level.name}")
        except KeyError:
            valid = ", ".join(l.name for l in AutonomyLevel)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid autonomy level. Valid: {valid}",
            )

    if request.learning_enabled is not None:
        agent.config.learning.auto_learning_enabled = request.learning_enabled
        logger.info(f"Learning {'enabled' if request.learning_enabled else 'disabled'}")

    return ConfigResponse(
        llm_model=agent.config.llm_model,
        max_concurrent_tasks=agent.config.max_concurrent_tasks,
        default_timeout=agent.config.default_timeout,
        autonomy_level=agent.trust_manager.level.name,
        learning_enabled=agent.config.learning.auto_learning_enabled,
    )
