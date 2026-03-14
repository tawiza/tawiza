"""Unified Adaptive Agent - Self-improving multi-tool agent."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

from loguru import logger

from .config import AutonomyLevel, UnifiedAgentConfig
from .tool_router import ExecutionPlan, ToolRouter
from .trust_manager import TrustManager


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    """Status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"


@dataclass
class TaskRequest:
    """Request to execute a task.

    Attributes:
        task_id: Unique task identifier
        description: Natural language task description
        task_type: Optional task type for routing
        context: Additional context for execution
        priority: Task priority (higher = more urgent)
    """

    task_id: str
    description: str
    task_type: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class TaskResult:
    """Result of task execution.

    Attributes:
        task_id: Task identifier
        status: Execution status
        output: Task output data
        error: Error message if failed
        execution_time: Time taken in seconds
        tool_used: Which tool was used
    """

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0
    tool_used: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


class UnifiedAdaptiveAgent:
    """Self-improving multi-tool agent.

    Coordinates:
    - TrustManager: Controls autonomy level
    - ToolRouter: Selects appropriate tools
    - LearningEngine: Improves from experience

    Example:
        agent = UnifiedAdaptiveAgent()
        result = await agent.execute(TaskRequest(
            task_id="task_1",
            description="Scrape data from example.com"
        ))
    """

    def __init__(
        self,
        config: UnifiedAgentConfig | None = None,
        trust_manager: TrustManager | None = None,
        tool_router: ToolRouter | None = None,
    ):
        """Initialize agent.

        Args:
            config: Agent configuration
            trust_manager: Custom trust manager
            tool_router: Custom tool router
        """
        self.config = config or UnifiedAgentConfig()
        self.trust_manager = trust_manager or TrustManager(self.config.trust)
        self.tool_router = tool_router or ToolRouter()

        # Lazily import learning engine to avoid circular imports
        from src.infrastructure.learning.learning_engine import LearningEngine

        self.learning_engine = LearningEngine(
            trust_manager=self.trust_manager,
            min_examples=self.config.learning.min_examples_for_training,
            auto_train=self.config.learning.auto_learning_enabled,
        )

        # Task tracking
        self._pending_tasks: dict[str, TaskRequest] = {}
        self._completed_tasks: list[TaskResult] = []
        self._failed_count = 0
        self._completed_count = 0

        logger.info(
            f"UnifiedAdaptiveAgent initialized at autonomy level {self.trust_manager.level.name}"
        )

    @property
    def autonomy_level(self) -> AutonomyLevel:
        """Current autonomy level."""
        return self.trust_manager.level

    @property
    def trust_score(self) -> float:
        """Current trust score."""
        return self.trust_manager.score

    @property
    def is_learning_enabled(self) -> bool:
        """Check if learning is enabled."""
        return self.config.learning.auto_learning_enabled

    async def execute(self, request: TaskRequest) -> TaskResult:
        """Execute a task.

        Routes the task to appropriate tools and manages
        the approval workflow based on autonomy level.

        Args:
            request: Task request

        Returns:
            Task result
        """
        logger.info(f"Executing task {request.task_id}: {request.description[:50]}...")

        # Check if approval is needed
        task_type = request.task_type or "unknown"
        if self.trust_manager.requires_approval(task_type):
            logger.info(f"Task {request.task_id} requires approval")
            self._pending_tasks[request.task_id] = request
            return TaskResult(
                task_id=request.task_id,
                status=TaskStatus.AWAITING_APPROVAL,
            )

        # Execute the task
        return await self._execute_task(request)

    async def _execute_task(self, request: TaskRequest) -> TaskResult:
        """Internal task execution.

        Args:
            request: Task request

        Returns:
            Task result
        """
        start_time = utc_now()

        try:
            # Get execution plan from router
            plan = await self.tool_router.plan(
                request.description,
                context=request.context,
            )

            # Execute with selected tool
            output = await self._execute_with_tool(plan, request)

            result = TaskResult(
                task_id=request.task_id,
                status=TaskStatus.COMPLETED,
                output=output,
                tool_used=plan.steps[0].tool if plan.steps else None,
                execution_time=(utc_now() - start_time).total_seconds(),
                completed_at=utc_now(),
            )

            self._completed_count += 1
            self._completed_tasks.append(result)

            # Record for learning
            self.learning_engine.record_interaction(
                task_id=request.task_id,
                instruction=request.description,
                output=str(output),
            )

            logger.info(f"Task {request.task_id} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Task {request.task_id} failed: {e}")
            self._failed_count += 1

            return TaskResult(
                task_id=request.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time=(utc_now() - start_time).total_seconds(),
                completed_at=utc_now(),
            )

    async def _execute_with_tool(
        self,
        plan: ExecutionPlan,
        request: TaskRequest,
    ) -> dict[str, Any]:
        """Execute task with the planned tool.

        Args:
            plan: Execution plan from router
            request: Original request

        Returns:
            Execution output
        """
        # This would integrate with actual tool adapters
        # For now, return a placeholder
        if not plan.steps:
            return {"success": True, "message": "No steps to execute"}

        step = plan.steps[0]
        logger.debug(f"Executing with tool: {step.tool}, action: {step.action}")

        # TODO: Integrate with actual tool adapters
        # (OpenManus, Skyvern, Browser-Use, etc.)

        return {
            "success": True,
            "tool": step.tool,
            "action": step.action,
        }

    async def approve(self, task_id: str) -> TaskResult:
        """Approve a pending task.

        Args:
            task_id: Task to approve

        Returns:
            Execution result
        """
        if task_id not in self._pending_tasks:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"Task {task_id} not found in pending",
            )

        request = self._pending_tasks.pop(task_id)
        logger.info(f"Approved task {task_id}")

        # Record positive feedback
        self.trust_manager.record_feedback(
            positive=self.trust_manager._feedback["positive"] + 1,
            negative=self.trust_manager._feedback["negative"],
        )

        return await self._execute_task(request)

    async def reject(self, task_id: str, reason: str = "") -> TaskResult:
        """Reject a pending task.

        Args:
            task_id: Task to reject
            reason: Rejection reason

        Returns:
            Failure result
        """
        if task_id not in self._pending_tasks:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"Task {task_id} not found in pending",
            )

        self._pending_tasks.pop(task_id)
        logger.info(f"Rejected task {task_id}: {reason}")

        # Record negative feedback
        self.trust_manager.record_feedback(
            positive=self.trust_manager._feedback["positive"],
            negative=self.trust_manager._feedback["negative"] + 1,
        )

        return TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=f"Rejected: {reason}",
            completed_at=utc_now(),
        )

    def record_feedback(
        self,
        task_id: str,
        feedback: str,
        correction: str | None = None,
    ) -> None:
        """Record human feedback for a task.

        Args:
            task_id: Task identifier
            feedback: Feedback type (positive/negative)
            correction: Optional corrected output
        """
        # Update trust manager
        if feedback == "positive":
            self.trust_manager.record_feedback(
                positive=self.trust_manager._feedback["positive"] + 1,
                negative=self.trust_manager._feedback["negative"],
            )
        else:
            self.trust_manager.record_feedback(
                positive=self.trust_manager._feedback["positive"],
                negative=self.trust_manager._feedback["negative"] + 1,
            )

        # Update trust score
        self.trust_manager.calculate_score()
        self.trust_manager.update_level()

        logger.info(
            f"Recorded {feedback} feedback for {task_id}, "
            f"trust now at {self.trust_manager.level.name}"
        )

    def get_status(self) -> dict[str, Any]:
        """Get agent status.

        Returns:
            Status dictionary
        """
        return {
            "autonomy_level": self.trust_manager.level.name,
            "autonomy_level_value": self.trust_manager.level.value,
            "trust_score": self.trust_manager.score,
            "learning_enabled": self.is_learning_enabled,
            "pending_tasks": len(self._pending_tasks),
            "in_cooldown": self.trust_manager.is_in_cooldown,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get detailed statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "tasks_completed": self._completed_count,
            "tasks_failed": self._failed_count,
            "tasks_pending": len(self._pending_tasks),
            "success_rate": (
                self._completed_count / (self._completed_count + self._failed_count)
                if (self._completed_count + self._failed_count) > 0
                else 0.0
            ),
            "trust_stats": self.trust_manager.to_dict(),
            "learning_stats": self.learning_engine.get_stats(),
        }
