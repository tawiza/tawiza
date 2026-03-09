"""
Real-time Progress Tracker

Provides real-time progress tracking for long-running tasks using Server-Sent Events (SSE).

Features:
- Track progress for multiple concurrent tasks
- Real-time updates via SSE (Server-Sent Events)
- Screenshot and step tracking
- In-memory storage with optional Redis backend
- Thread-safe operations
- Automatic cleanup of old events
"""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import uuid4

from loguru import logger


class ProgressStatus(StrEnum):
    """Progress status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    """
    Progress event for a task.

    Contains information about a single progress update.
    """
    event_id: str
    task_id: str
    timestamp: datetime
    status: ProgressStatus
    progress: int  # 0-100
    current_step: str
    total_steps: int | None = None
    step_number: int | None = None
    screenshot_url: str | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["status"] = self.status.value
        return data


class ProgressTracker:
    """
    Track and stream progress updates for long-running tasks.

    Usage:
        tracker = ProgressTracker()

        # Update progress
        await tracker.update_progress(
            task_id="123",
            status=ProgressStatus.RUNNING,
            progress=50,
            current_step="Processing data..."
        )

        # Stream updates to client
        async for event in tracker.stream_progress("123"):
            print(event)
    """

    def __init__(
        self,
        cleanup_after: int = 3600,  # 1 hour
        max_events_per_task: int = 1000
    ):
        """
        Initialize progress tracker.

        Args:
            cleanup_after: Seconds after which to cleanup old events
            max_events_per_task: Maximum events to store per task
        """
        # Event storage: task_id -> list of events
        self._events: dict[str, list[ProgressEvent]] = defaultdict(list)

        # Active listeners: task_id -> list of asyncio.Queue
        self._listeners: dict[str, list[asyncio.Queue]] = defaultdict(list)

        # Task metadata
        self._task_metadata: dict[str, dict[str, Any]] = {}

        # Configuration
        self._cleanup_after = cleanup_after
        self._max_events_per_task = max_events_per_task

        # Locks for thread safety
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        logger.info(
            f"ProgressTracker initialized "
            f"(cleanup: {cleanup_after}s, max_events: {max_events_per_task})"
        )

    async def create_task(
        self,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Create a new tracked task.

        Args:
            task_id: Task identifier (generated if not provided)
            metadata: Task metadata

        Returns:
            str: Task ID
        """
        if task_id is None:
            task_id = str(uuid4())

        async with self._locks[task_id]:
            self._task_metadata[task_id] = metadata or {}

            # Create initial progress event
            await self._add_event(
                task_id=task_id,
                status=ProgressStatus.PENDING,
                progress=0,
                current_step="Task created"
            )

        logger.info(f"Created tracked task: {task_id}")
        return task_id

    async def update_progress(
        self,
        task_id: str,
        status: ProgressStatus,
        progress: int,
        current_step: str,
        total_steps: int | None = None,
        step_number: int | None = None,
        screenshot_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None
    ) -> ProgressEvent:
        """
        Update task progress.

        Args:
            task_id: Task identifier
            status: Current status
            progress: Progress percentage (0-100)
            current_step: Description of current step
            total_steps: Total number of steps
            step_number: Current step number
            screenshot_url: URL to screenshot (for browser tasks)
            metadata: Additional metadata
            error: Error message (if failed)

        Returns:
            ProgressEvent: Created progress event
        """
        async with self._locks[task_id]:
            event = await self._add_event(
                task_id=task_id,
                status=status,
                progress=progress,
                current_step=current_step,
                total_steps=total_steps,
                step_number=step_number,
                screenshot_url=screenshot_url,
                metadata=metadata,
                error=error
            )

            # Notify all listeners
            await self._notify_listeners(task_id, event)

        logger.debug(
            f"Progress updated: {task_id} - {progress}% - {current_step}"
        )

        return event

    async def _add_event(
        self,
        task_id: str,
        status: ProgressStatus,
        progress: int,
        current_step: str,
        total_steps: int | None = None,
        step_number: int | None = None,
        screenshot_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None
    ) -> ProgressEvent:
        """
        Add a progress event (internal).

        Args:
            Same as update_progress

        Returns:
            ProgressEvent: Created event
        """
        event = ProgressEvent(
            event_id=str(uuid4()),
            task_id=task_id,
            timestamp=datetime.utcnow(),
            status=status,
            progress=max(0, min(100, progress)),  # Clamp to 0-100
            current_step=current_step,
            total_steps=total_steps,
            step_number=step_number,
            screenshot_url=screenshot_url,
            metadata=metadata,
            error=error
        )

        # Add to event list
        self._events[task_id].append(event)

        # Cleanup old events if needed
        if len(self._events[task_id]) > self._max_events_per_task:
            # Keep only the latest events
            self._events[task_id] = self._events[task_id][-self._max_events_per_task:]

        return event

    async def _notify_listeners(self, task_id: str, event: ProgressEvent):
        """
        Notify all listeners of a new event.

        Args:
            task_id: Task identifier
            event: Progress event to send
        """
        if task_id in self._listeners:
            # Send to all active listeners
            dead_listeners = []
            for i, queue in enumerate(self._listeners[task_id]):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Listener queue full for task {task_id}")
                    dead_listeners.append(i)
                except Exception as e:
                    logger.error(f"Failed to notify listener: {e}")
                    dead_listeners.append(i)

            # Remove dead listeners
            for i in reversed(dead_listeners):
                self._listeners[task_id].pop(i)

    async def stream_progress(
        self,
        task_id: str,
        send_history: bool = True
    ) -> AsyncIterator[ProgressEvent]:
        """
        Stream progress updates for a task.

        Args:
            task_id: Task identifier
            send_history: Whether to send historical events first

        Yields:
            ProgressEvent: Progress events
        """
        # Create queue for this listener
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        async with self._locks[task_id]:
            # Add to listeners
            self._listeners[task_id].append(queue)

            # Send historical events if requested
            if send_history and task_id in self._events:
                for event in self._events[task_id]:
                    yield event

        logger.info(f"Started streaming progress for task: {task_id}")

        try:
            # Stream new events
            while True:
                try:
                    # Wait for new event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event

                    # Stop streaming if task is finished
                    if event.status in [
                        ProgressStatus.COMPLETED,
                        ProgressStatus.FAILED,
                        ProgressStatus.CANCELLED
                    ]:
                        logger.info(
                            f"Task {task_id} finished with status: {event.status}"
                        )
                        break

                except TimeoutError:
                    # Send keepalive
                    # Client can detect if connection is still alive
                    continue

        except asyncio.CancelledError:
            logger.info(f"Progress streaming cancelled for task: {task_id}")
            raise
        finally:
            # Remove from listeners
            async with self._locks[task_id]:
                if queue in self._listeners[task_id]:
                    self._listeners[task_id].remove(queue)

    async def get_latest_progress(self, task_id: str) -> ProgressEvent | None:
        """
        Get the latest progress event for a task.

        Args:
            task_id: Task identifier

        Returns:
            ProgressEvent or None if no events
        """
        async with self._locks[task_id]:
            if task_id in self._events and self._events[task_id]:
                return self._events[task_id][-1]
            return None

    async def get_progress_history(
        self,
        task_id: str,
        limit: int = 100
    ) -> list[ProgressEvent]:
        """
        Get progress history for a task.

        Args:
            task_id: Task identifier
            limit: Maximum events to return

        Returns:
            List of progress events
        """
        async with self._locks[task_id]:
            if task_id in self._events:
                return self._events[task_id][-limit:]
            return []

    async def cleanup_old_tasks(self):
        """
        Cleanup old completed tasks.

        Removes events for tasks that finished more than cleanup_after seconds ago.
        """
        now = datetime.utcnow()
        tasks_to_remove = []

        for task_id in list(self._events.keys()):
            async with self._locks[task_id]:
                if not self._events[task_id]:
                    tasks_to_remove.append(task_id)
                    continue

                latest_event = self._events[task_id][-1]

                # Check if task is finished and old
                if latest_event.status in [
                    ProgressStatus.COMPLETED,
                    ProgressStatus.FAILED,
                    ProgressStatus.CANCELLED
                ]:
                    age = (now - latest_event.timestamp).total_seconds()
                    if age > self._cleanup_after:
                        tasks_to_remove.append(task_id)

        # Remove old tasks
        for task_id in tasks_to_remove:
            async with self._locks[task_id]:
                if task_id in self._events:
                    del self._events[task_id]
                if task_id in self._listeners:
                    del self._listeners[task_id]
                if task_id in self._task_metadata:
                    del self._task_metadata[task_id]
                if task_id in self._locks:
                    del self._locks[task_id]

        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

    async def get_active_tasks(self) -> list[str]:
        """
        Get list of active task IDs.

        Returns:
            List of task IDs
        """
        active_tasks = []

        for task_id in list(self._events.keys()):
            async with self._locks[task_id]:
                if self._events[task_id]:
                    latest = self._events[task_id][-1]
                    if latest.status in [ProgressStatus.PENDING, ProgressStatus.RUNNING]:
                        active_tasks.append(task_id)

        return active_tasks

    async def get_stats(self) -> dict[str, Any]:
        """
        Get tracker statistics.

        Returns:
            dict: Statistics including task counts, event counts
        """
        total_events = sum(len(events) for events in self._events.values())
        total_listeners = sum(len(listeners) for listeners in self._listeners.values())
        active_tasks = await self.get_active_tasks()

        return {
            "total_tasks": len(self._events),
            "active_tasks": len(active_tasks),
            "total_events": total_events,
            "total_listeners": total_listeners,
            "cleanup_after": self._cleanup_after,
            "max_events_per_task": self._max_events_per_task
        }
