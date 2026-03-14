"""Agent port interfaces.

These interfaces define the contracts for web automation agents
and service orchestration in the Tawiza platform.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import Enum, StrEnum
from typing import Any


class AgentType(StrEnum):
    """Types of automation agents."""

    OPENMANUS = "openmanus"
    SKYVERN = "skyvern"
    CUSTOM = "custom"


class TaskStatus(StrEnum):
    """Status of agent tasks."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Priority levels for tasks."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ActionType(StrEnum):
    """Types of web automation actions."""

    NAVIGATE = "navigate"
    EXTRACT = "extract"
    FILL_FORM = "fill_form"
    CLICK = "click"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    CUSTOM = "custom"


class PlanStatus(StrEnum):
    """Status of an autonomous agent plan execution."""

    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IAgent(ABC):
    """Interface générique pour tous les agents.

    Cette interface de base définit le contrat minimal que tous les agents
    doivent implémenter, qu'ils soient des agents web, ML, ou conversationnels.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom unique de l'agent."""
        pass

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Type de l'agent (web, ml, data, etc.)."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialise l'agent et ses ressources.

        Cette méthode doit être appelée avant d'utiliser l'agent.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Vérifie si l'agent est opérationnel.

        Returns:
            True si l'agent est prêt, False sinon.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Libère les ressources de l'agent.

        Cette méthode doit être appelée lors de l'arrêt de l'application.
        """
        pass


class ITaskPlanner(ABC):
    """Interface for LLM-based task planning.

    This port defines the contract for autonomous task planning
    that decomposes natural language tasks into executable steps.
    """

    @abstractmethod
    async def create_plan(
        self,
        task_description: str,
        starting_url: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create execution plan from natural language task.

        Args:
            task_description: Natural language task description
            starting_url: Optional starting URL
            context: Additional context

        Returns:
            Plan dict containing:
                - plan_id: Unique plan identifier
                - original_task: Original task description
                - steps: List of planned steps
                - confidence_score: Planning confidence (0-1)
                - estimated_duration: Estimated total duration
        """
        pass

    @abstractmethod
    async def refine_plan(
        self,
        plan: dict[str, Any],
        feedback: str,
    ) -> dict[str, Any]:
        """Refine plan based on user feedback.

        Args:
            plan: Current plan
            feedback: User's feedback/corrections

        Returns:
            Updated plan
        """
        pass


class IAutonomousAgent(ABC):
    """Interface for autonomous web automation agents.

    This port defines the contract for agents that can plan
    and execute complex multi-step tasks autonomously.
    """

    @abstractmethod
    async def plan_task(
        self,
        task: str,
        starting_url: str | None = None,
    ) -> dict[str, Any]:
        """Create execution plan for a task.

        Args:
            task: Natural language task description
            starting_url: Optional starting URL

        Returns:
            Execution plan
        """
        pass

    @abstractmethod
    async def execute_plan(
        self,
        plan: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Execute a validated plan.

        Args:
            plan: Plan to execute
            dry_run: If True, simulate without browser interaction

        Returns:
            Execution result
        """
        pass

    @abstractmethod
    async def cancel_execution(
        self,
        plan_id: str,
    ) -> bool:
        """Cancel a running execution.

        Args:
            plan_id: Plan ID to cancel

        Returns:
            True if cancelled
        """
        pass

    @abstractmethod
    async def get_execution_status(
        self,
        plan_id: str,
    ) -> dict[str, Any] | None:
        """Get execution status.

        Args:
            plan_id: Plan ID to check

        Returns:
            Status dict or None
        """
        pass


class IWebAgent(ABC):
    """Interface for web automation agents.

    This port defines the contract for web automation agents like
    OpenManus and Skyvern. Adapters implement this interface to
    provide web automation capabilities.
    """

    @abstractmethod
    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """Execute a web automation task.

        Args:
            task_config: Task configuration containing:
                - task_id: Unique task identifier
                - url: Target URL
                - action: Action type
                - selectors: CSS/XPath selectors
                - data: Data for the action
                - options: Additional options

        Returns:
            Task result containing:
                - task_id: Task identifier
                - status: Final status
                - result: Extracted data or action result
                - screenshots: List of screenshot URLs
                - logs: Execution logs
                - error: Error message if failed

        Raises:
            AgentExecutionError: If task execution fails
        """
        pass

    @abstractmethod
    async def stream_progress(self, task_id: str) -> AsyncGenerator[dict[str, Any]]:
        """Stream task execution progress.

        Yields progress updates in real-time via async generator.

        Args:
            task_id: Task identifier

        Yields:
            Progress updates containing:
                - task_id: Task identifier
                - status: Current status
                - progress: Progress percentage (0-100)
                - current_step: Description of current step
                - screenshot_url: Latest screenshot URL
                - timestamp: Update timestamp

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status information

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled successfully

        Raises:
            TaskNotFoundError: If task doesn't exist
            TaskNotCancellableError: If task cannot be cancelled
        """
        pass

    @abstractmethod
    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        """Get task result after completion.

        Args:
            task_id: Task identifier

        Returns:
            Task result data

        Raises:
            TaskNotFoundError: If task doesn't exist
            TaskNotCompletedError: If task hasn't completed
        """
        pass

    @abstractmethod
    async def list_tasks(
        self, status: TaskStatus | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List tasks with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum number of tasks
            offset: Offset for pagination

        Returns:
            List of task summaries
        """
        pass


class IServiceOrchestrator(ABC):
    """Interface for orchestrating multiple services.

    This port defines the contract for coordinating workflows
    across multiple services (agents, MLflow, Label Studio, etc.)
    """

    @abstractmethod
    async def execute_pipeline(self, pipeline_config: dict[str, Any]) -> dict[str, Any]:
        """Execute a multi-service pipeline.

        Args:
            pipeline_config: Pipeline configuration containing:
                - name: Pipeline name
                - steps: List of pipeline steps
                - error_handling: Error handling strategy
                - retry_policy: Retry configuration

        Returns:
            Pipeline execution result

        Example:
            ```python
            pipeline = {
                "name": "data-collection-annotation",
                "steps": [
                    {
                        "service": "skyvern",
                        "action": "scrape",
                        "config": {...}
                    },
                    {
                        "service": "label_studio",
                        "action": "create_project",
                        "config": {...}
                    }
                ]
            }
            ```
        """
        pass

    @abstractmethod
    async def get_pipeline_status(self, pipeline_id: str) -> dict[str, Any]:
        """Get pipeline execution status.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Pipeline status including:
                - pipeline_id: Identifier
                - status: Current status
                - steps_completed: Number of completed steps
                - steps_total: Total number of steps
                - current_step: Current step details
                - errors: List of errors if any
        """
        pass

    @abstractmethod
    async def cancel_pipeline(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            True if cancelled successfully
        """
        pass

    @abstractmethod
    async def stream_pipeline_progress(self, pipeline_id: str) -> AsyncGenerator[dict[str, Any]]:
        """Stream pipeline execution progress.

        Args:
            pipeline_id: Pipeline identifier

        Yields:
            Progress updates
        """
        pass

    @abstractmethod
    async def register_service(self, service_name: str, service_adapter: Any) -> None:
        """Register a service adapter.

        Args:
            service_name: Service identifier
            service_adapter: Service adapter instance
        """
        pass

    @abstractmethod
    async def get_registered_services(self) -> list[str]:
        """Get list of registered services.

        Returns:
            List of service names
        """
        pass


class IAgentMetrics(ABC):
    """Interface for agent metrics and monitoring."""

    @abstractmethod
    async def record_task_start(self, task_id: str, agent_type: AgentType) -> None:
        """Record task start."""
        pass

    @abstractmethod
    async def record_task_completion(
        self, task_id: str, duration_seconds: float, status: TaskStatus
    ) -> None:
        """Record task completion."""
        pass

    @abstractmethod
    async def get_agent_metrics(self, agent_type: AgentType | None = None) -> dict[str, Any]:
        """Get agent performance metrics."""
        pass


# Exception classes


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""

    pass


class TaskNotFoundError(AgentError):
    """Raised when task is not found."""

    pass


class TaskNotCompletedError(AgentError):
    """Raised when attempting to get result of incomplete task."""

    pass


class TaskNotCancellableError(AgentError):
    """Raised when task cannot be cancelled."""

    pass


class PipelineExecutionError(AgentError):
    """Raised when pipeline execution fails."""

    pass


class ServiceNotRegisteredError(AgentError):
    """Raised when service is not registered."""

    pass
