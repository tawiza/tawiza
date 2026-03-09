"""Base agent implementation.

Provides common functionality for all web automation agents.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from src.application.ports.agent_ports import (
    AgentType,
    IWebAgent,
    TaskNotCancellableError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskStatus,
)


class BaseAgent(IWebAgent, ABC):
    """Base implementation for web automation agents.

    Provides:
    - Task state management
    - Common utilities
    - Error handling patterns
    - Logging integration
    """

    def __init__(
        self,
        agent_type: AgentType,
        config: dict[str, Any] | None = None
    ) -> None:
        """Initialize base agent.

        Args:
            agent_type: Type of agent
            config: Agent configuration
        """
        self.agent_type = agent_type
        self.config = config or {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.session_id: str | None = None  # WebSocket session ID for targeted updates

        logger.info(f"Initialized {agent_type} agent")

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        return f"{self.agent_type.value}-{uuid.uuid4().hex[:8]}"

    def _create_task(
        self,
        task_config: dict[str, Any]
    ) -> str:
        """Create task entry.

        Args:
            task_config: Task configuration

        Returns:
            Task ID
        """
        task_id = task_config.get("task_id") or self._generate_task_id()

        self.tasks[task_id] = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "config": task_config,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "progress": 0,
            "current_step": "Initializing",
            "result": None,
            "error": None,
            "screenshots": [],
            "logs": []
        }

        return task_id

    def _update_task(
        self,
        task_id: str,
        updates: dict[str, Any]
    ) -> None:
        """Update task state.

        Args:
            task_id: Task identifier
            updates: Fields to update
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")

        self.tasks[task_id].update(updates)
        self.tasks[task_id]["updated_at"] = datetime.now(UTC).isoformat()

    def _update_progress(
        self,
        task_id: str,
        progress: int,
        current_step: str
    ) -> None:
        """Update task progress.

        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            current_step: Description of current step
        """
        self._update_task(task_id, {
            "progress": progress,
            "current_step": current_step
        })

    def _add_log(
        self,
        task_id: str,
        message: str,
        level: str = "info"
    ) -> None:
        """Add log entry to task.

        Args:
            task_id: Task identifier
            message: Log message
            level: Log level
        """
        if task_id in self.tasks:
            self.tasks[task_id]["logs"].append({
                "timestamp": datetime.now(UTC).isoformat(),
                "level": level,
                "message": message
            })

    def _add_screenshot(
        self,
        task_id: str,
        screenshot_url: str,
        label: str | None = None
    ) -> None:
        """Add screenshot to task.

        Args:
            task_id: Task identifier
            screenshot_url: Screenshot URL
            label: Optional label
        """
        if task_id in self.tasks:
            self.tasks[task_id]["screenshots"].append({
                "url": screenshot_url,
                "label": label,
                "timestamp": datetime.now(UTC).isoformat()
            })

    async def get_task_status(
        self,
        task_id: str
    ) -> dict[str, Any]:
        """Get current task status.

        Args:
            task_id: Task identifier

        Returns:
            Task status information

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "progress": task["progress"],
            "current_step": task["current_step"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"]
        }

    async def get_task_result(
        self,
        task_id: str
    ) -> dict[str, Any]:
        """Get task result.

        Args:
            task_id: Task identifier

        Returns:
            Task result

        Raises:
            TaskNotFoundError: If task doesn't exist
            TaskNotCompletedError: If task not completed
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")

        task = self.tasks[task_id]

        if task["status"] not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise TaskNotCompletedError(
                f"Task {task_id} is {task['status']}, not completed"
            )

        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "result": task["result"],
            "error": task["error"],
            "screenshots": task["screenshots"],
            "logs": task["logs"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"]
        }

    async def cancel_task(
        self,
        task_id: str
    ) -> bool:
        """Cancel running task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled

        Raises:
            TaskNotFoundError: If task doesn't exist
            TaskNotCancellableError: If task cannot be cancelled
        """
        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")

        task = self.tasks[task_id]

        if task["status"] not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise TaskNotCancellableError(
                f"Cannot cancel task with status {task['status']}"
            )

        self._update_task(task_id, {
            "status": TaskStatus.CANCELLED
        })

        logger.info(f"Cancelled task {task_id}")
        return True

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """List tasks.

        Args:
            status: Filter by status
            limit: Maximum tasks
            offset: Offset for pagination

        Returns:
            List of task summaries
        """
        tasks = list(self.tasks.values())

        # Filter by status
        if status:
            tasks = [t for t in tasks if t["status"] == status]

        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t["created_at"], reverse=True)

        # Paginate
        tasks = tasks[offset:offset + limit]

        # Return summaries
        return [
            {
                "task_id": t["task_id"],
                "status": t["status"],
                "progress": t["progress"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"]
            }
            for t in tasks
        ]

    async def stream_progress(
        self,
        task_id: str
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream task progress.

        Args:
            task_id: Task identifier

        Yields:
            Progress updates

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        import asyncio

        if task_id not in self.tasks:
            raise TaskNotFoundError(f"Task {task_id} not found")

        # Stream progress until task completes
        while True:
            task = self.tasks[task_id]

            yield {
                "task_id": task_id,
                "status": task["status"],
                "progress": task["progress"],
                "current_step": task["current_step"],
                "screenshot_url": (
                    task["screenshots"][-1]["url"]
                    if task["screenshots"]
                    else None
                ),
                "timestamp": datetime.now(UTC).isoformat()
            }

            # Stop if task completed/failed/cancelled
            if task["status"] in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED
            ]:
                break

            await asyncio.sleep(1)  # Update every second

    @abstractmethod
    async def execute_task(
        self,
        task_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute task - must be implemented by subclasses."""
