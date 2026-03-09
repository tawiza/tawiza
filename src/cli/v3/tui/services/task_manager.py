"""Task Manager for TUI - manages task lifecycle and state."""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


@dataclass
class TaskStep:
    """A step in task execution."""
    index: int
    name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any | None = None


@dataclass
class Task:
    """Represents a task in the TUI."""
    id: str
    agent: str
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
    progress: float = 0.0
    current_step: int = 0
    total_steps: int = 0
    steps: list[TaskStep] = field(default_factory=list)
    thinking_log: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Get task duration in seconds."""
        if self.started_at:
            end = self.completed_at or datetime.now()
            return (end - self.started_at).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        """Whether task is currently active."""
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent": self.agent,
            "prompt": self.prompt,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "result": self.result,
            "error": self.error,
        }


class TaskEvent(Enum):
    """Task lifecycle events."""
    CREATED = "created"
    STARTED = "started"
    PROGRESS = "progress"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskManager:
    """Manages task lifecycle and state for the TUI."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._listeners: dict[TaskEvent, list[Callable]] = {}
        self._active_task_id: str | None = None

    @property
    def tasks(self) -> list[Task]:
        """Get all tasks."""
        return list(self._tasks.values())

    @property
    def active_tasks(self) -> list[Task]:
        """Get all active tasks."""
        return [t for t in self._tasks.values() if t.is_active]

    @property
    def active_task(self) -> Task | None:
        """Get the currently focused task."""
        if self._active_task_id:
            return self._tasks.get(self._active_task_id)
        return None

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def create_task(
        self,
        agent: str,
        prompt: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        context: dict | None = None
    ) -> Task:
        """Create a new task."""
        task_id = str(uuid.uuid4())[:8]

        task = Task(
            id=task_id,
            agent=agent,
            prompt=prompt,
            priority=priority,
            context=context or {}
        )

        self._tasks[task_id] = task

        # Set as active if no active task
        if self._active_task_id is None:
            self._active_task_id = task_id

        self._emit(TaskEvent.CREATED, task)
        logger.info(f"Created task {task_id}: {prompt[:50]}...")

        return task

    def start_task(self, task_id: str) -> bool:
        """Mark a task as started."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        self._emit(TaskEvent.STARTED, task)
        return True

    def update_progress(
        self,
        task_id: str,
        step: int,
        total_steps: int,
        message: str,
        percent: float | None = None
    ) -> bool:
        """Update task progress."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.current_step = step
        task.total_steps = total_steps
        task.progress = percent if percent is not None else (step / total_steps * 100)

        # Update or add step
        if len(task.steps) < step:
            task.steps.append(TaskStep(index=step, name=message, status="running"))
        else:
            task.steps[step - 1].status = "running"

        # Mark previous steps as completed
        for i in range(step - 1):
            if task.steps[i].status == "running":
                task.steps[i].status = "completed"
                task.steps[i].completed_at = datetime.now()

        self._emit(TaskEvent.PROGRESS, task, {
            "step": step,
            "total_steps": total_steps,
            "message": message,
            "percent": task.progress
        })
        return True

    def add_thinking(self, task_id: str, content: str) -> bool:
        """Add a thinking log entry."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.thinking_log.append(content)
        self._emit(TaskEvent.THINKING, task, {"content": content})
        return True

    def add_tool_call(
        self,
        task_id: str,
        tool: str,
        args: dict[str, Any],
        result: Any | None = None
    ) -> bool:
        """Record a tool call."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        call = {
            "tool": tool,
            "args": args,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        task.tool_calls.append(call)

        self._emit(TaskEvent.TOOL_CALL, task, call)
        return True

    def pause_task(self, task_id: str) -> bool:
        """Pause a running task."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        task.status = TaskStatus.PAUSED
        self._emit(TaskEvent.PAUSED, task)
        logger.info(f"Paused task {task_id}")
        return True

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False

        task.status = TaskStatus.RUNNING
        self._emit(TaskEvent.RESUMED, task)
        logger.info(f"Resumed task {task_id}")
        return True

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result
        task.progress = 100.0

        # Mark all steps as completed
        for step in task.steps:
            if step.status != "completed":
                step.status = "completed"
                step.completed_at = datetime.now()

        self._emit(TaskEvent.COMPLETED, task)
        logger.info(f"Completed task {task_id}")
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.error = error

        self._emit(TaskEvent.FAILED, task, {"error": error})
        logger.error(f"Task {task_id} failed: {error}")
        return True

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if not task or not task.is_active:
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()

        self._emit(TaskEvent.CANCELLED, task)
        logger.info(f"Cancelled task {task_id}")
        return True

    def set_active_task(self, task_id: str) -> bool:
        """Set the currently focused task."""
        if task_id not in self._tasks:
            return False
        self._active_task_id = task_id
        return True

    def clear_completed(self) -> int:
        """Remove all completed/failed/cancelled tasks."""
        to_remove = [
            tid for tid, task in self._tasks.items()
            if not task.is_active
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)

    # =========================================================================
    # Event system
    # =========================================================================

    def on(self, event: TaskEvent, callback: Callable) -> None:
        """Register an event listener."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def off(self, event: TaskEvent, callback: Callable) -> None:
        """Remove an event listener."""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]

    def _emit(
        self,
        event: TaskEvent,
        task: Task,
        data: dict | None = None
    ) -> None:
        """Emit an event to all listeners."""
        listeners = self._listeners.get(event, [])
        for listener in listeners:
            try:
                result = listener(task, data)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Event listener error: {e}")


# Global instance
_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """Get or create the global task manager."""
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager
