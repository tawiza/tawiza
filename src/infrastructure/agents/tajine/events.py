"""
Event emitter for TAJINEAgent real-time progress updates.

Provides callback-based and WebSocket-compatible event emission
for the PERCEIVE-PLAN-DELEGATE-SYNTHESIZE-LEARN cycle.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger


class TAJINEEvent(StrEnum):
    """Events emitted during TAJINE execution cycle."""

    # Lifecycle events
    TASK_STARTED = "tajine.task.started"
    TASK_COMPLETED = "tajine.task.completed"
    TASK_FAILED = "tajine.task.failed"

    # PPDSL cycle events
    PERCEIVE_START = "tajine.perceive.start"
    PERCEIVE_COMPLETE = "tajine.perceive.complete"
    PLAN_START = "tajine.plan.start"
    PLAN_COMPLETE = "tajine.plan.complete"
    DELEGATE_START = "tajine.delegate.start"
    DELEGATE_TOOL = "tajine.delegate.tool"
    DELEGATE_COMPLETE = "tajine.delegate.complete"
    SYNTHESIZE_START = "tajine.synthesize.start"
    SYNTHESIZE_LEVEL = "tajine.synthesize.level"
    SYNTHESIZE_COMPLETE = "tajine.synthesize.complete"
    LEARN_START = "tajine.learn.start"
    LEARN_COMPLETE = "tajine.learn.complete"

    # Progress events
    PROGRESS = "tajine.progress"
    THINKING = "tajine.thinking"


@dataclass
class TAJINECallback:
    """Callback data for TAJINE events."""

    event: TAJINEEvent
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: str = ""
    session_id: str | None = None
    phase: str = ""  # perceive, plan, delegate, synthesize, learn
    progress: int = 0  # 0-100
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for WebSocket transmission."""
        return {
            "type": self.event.value,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "session_id": self.session_id,
            "phase": self.phase,
            "progress": self.progress,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


# Type alias for event handlers
EventHandler = Callable[[TAJINECallback], None]


class EventEmitter:
    """
    Event emitter mixin for TAJINEAgent.

    Supports both callback functions and async WebSocket emission.
    """

    def __init__(self):
        """Initialize event emitter."""
        self._handlers: list[EventHandler] = []
        self._ws_handlers: list[Callable] = []
        self.session_id: str | None = None

    def on_event(self, handler: EventHandler) -> None:
        """
        Register an event handler.

        Args:
            handler: Callback function(TAJINECallback) -> None
        """
        if handler not in self._handlers:
            self._handlers.append(handler)
            logger.debug(f"Registered event handler: {handler.__name__}")

    def off_event(self, handler: EventHandler) -> None:
        """
        Unregister an event handler.

        Args:
            handler: Handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
            logger.debug(f"Unregistered event handler: {handler.__name__}")

    def on_ws(self, ws_handler: Callable) -> None:
        """
        Register a WebSocket handler for async emission.

        Args:
            ws_handler: Async function(dict) -> None
        """
        if ws_handler not in self._ws_handlers:
            self._ws_handlers.append(ws_handler)

    def emit(self, callback: TAJINECallback) -> None:
        """
        Emit an event to all registered handlers.

        Args:
            callback: Event callback data
        """
        if not callback.session_id and self.session_id:
            callback.session_id = self.session_id

        for handler in self._handlers:
            try:
                handler(callback)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def emit_async(self, callback: TAJINECallback) -> None:
        """
        Emit an event asynchronously to WebSocket handlers.

        Args:
            callback: Event callback data
        """
        if not callback.session_id and self.session_id:
            callback.session_id = self.session_id

        # Sync handlers first
        self.emit(callback)

        # Async WebSocket handlers
        for ws_handler in self._ws_handlers:
            try:
                await ws_handler(callback.to_dict())
            except Exception as e:
                logger.error(f"WebSocket handler error: {e}")

    def emit_progress(
        self,
        task_id: str,
        phase: str,
        progress: int,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """
        Convenience method to emit progress event.

        Args:
            task_id: Current task ID
            phase: Current PPDSL phase
            progress: Progress percentage (0-100)
            message: Human-readable message
            data: Optional additional data
        """
        self.emit(
            TAJINECallback(
                event=TAJINEEvent.PROGRESS,
                task_id=task_id,
                phase=phase,
                progress=progress,
                message=message,
                data=data or {},
            )
        )

    def emit_thinking(self, task_id: str, message: str) -> None:
        """
        Emit thinking/processing event.

        Args:
            task_id: Current task ID
            message: What the agent is thinking about
        """
        self.emit(
            TAJINECallback(
                event=TAJINEEvent.THINKING,
                task_id=task_id,
                message=message,
            )
        )


def create_cli_handler(console) -> EventHandler:
    """
    Create an event handler that updates CLI display.

    Args:
        console: Rich console instance

    Returns:
        Event handler function
    """
    phase_icons = {
        "perceive": "👁️",
        "plan": "📋",
        "delegate": "🔧",
        "synthesize": "🧠",
        "learn": "📚",
    }

    def handler(cb: TAJINECallback) -> None:
        icon = phase_icons.get(cb.phase, "⚙️")

        if cb.event == TAJINEEvent.PROGRESS:
            console.print(f"  {icon} [{cb.phase}] {cb.progress}% - {cb.message}")
        elif cb.event == TAJINEEvent.THINKING:
            console.print(f"  💭 {cb.message[:60]}...")
        elif cb.event == TAJINEEvent.TASK_COMPLETED:
            console.print(f"  ✅ Task completed: {cb.message}")
        elif cb.event == TAJINEEvent.TASK_FAILED:
            console.print(f"  ❌ Task failed: {cb.error}")
        elif cb.event == TAJINEEvent.DELEGATE_TOOL:
            tool = cb.data.get("tool", "unknown")
            console.print(f"    🔧 Executing: {tool}")

    return handler


def create_progress_bar_handler(console, task) -> EventHandler:
    """
    Create an event handler for Rich progress bar.

    Args:
        console: Rich console instance
        task: Rich Progress task

    Returns:
        Event handler function
    """

    def handler(cb: TAJINECallback) -> None:
        if cb.event == TAJINEEvent.PROGRESS:
            task.update(
                completed=cb.progress, description=f"[cyan]{cb.phase}[/]: {cb.message[:30]}"
            )

    return handler
