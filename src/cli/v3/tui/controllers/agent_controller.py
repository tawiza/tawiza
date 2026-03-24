"""Agent Controller - Manages agent lifecycle and control.

Integrates with:
- WebSocket client for server communication
- AgentRegistry for agent dispatch
- TaskManager for task state
"""

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from loguru import logger

from src.cli.v3.tui.widgets.task_list import TaskInfo, TaskStatus


class AgentState(Enum):
    """Agent execution state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentSession:
    """Represents an agent session."""

    session_id: str
    agent_name: str
    task_description: str
    model: str
    state: AgentState
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    parent_session_id: str | None = None  # For forked sessions
    error: str | None = None
    iterations: int = 0
    tokens_used: int = 0

    def to_task_info(self) -> TaskInfo:
        """Convert to TaskInfo for display."""
        status_map = {
            AgentState.IDLE: TaskStatus.PENDING,
            AgentState.RUNNING: TaskStatus.RUNNING,
            AgentState.PAUSED: TaskStatus.PAUSED,
            AgentState.STOPPED: TaskStatus.CANCELLED,
            AgentState.COMPLETED: TaskStatus.COMPLETED,
            AgentState.FAILED: TaskStatus.FAILED,
        }

        return TaskInfo(
            task_id=self.session_id,
            agent=self.agent_name,
            description=self.task_description,
            status=status_map.get(self.state, TaskStatus.PENDING),
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            iterations=self.iterations,
            tokens_used=self.tokens_used,
            model=self.model,
        )


class AgentController:
    """Controller for managing agent execution and control."""

    def __init__(self):
        self._sessions: dict[str, AgentSession] = {}
        self._active_session_id: str | None = None
        self._listeners: list[Callable[[str, AgentSession], None]] = []
        self._correction_queue: asyncio.Queue = asyncio.Queue()

    def add_listener(self, callback: Callable[[str, AgentSession], None]) -> None:
        """Add a listener for session state changes."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, AgentSession], None]) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, event: str, session: AgentSession) -> None:
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            with contextlib.suppress(Exception):
                listener(event, session)

    def create_session(
        self,
        agent_name: str,
        task_description: str,
        model: str = "qwen3.5:27b",
        parent_session_id: str | None = None,
    ) -> AgentSession:
        """Create a new agent session."""
        session_id = str(uuid.uuid4())[:8]

        session = AgentSession(
            session_id=session_id,
            agent_name=agent_name,
            task_description=task_description,
            model=model,
            state=AgentState.IDLE,
            created_at=datetime.now(),
            parent_session_id=parent_session_id,
        )

        self._sessions[session_id] = session
        self._notify_listeners("created", session)

        return session

    def start_session(self, session_id: str) -> bool:
        """Start a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.state != AgentState.IDLE:
            return False

        session.state = AgentState.RUNNING
        session.started_at = datetime.now()
        self._active_session_id = session_id

        self._notify_listeners("started", session)
        return True

    def pause_session(self, session_id: str | None = None) -> bool:
        """Pause a session (or active session if not specified)."""
        sid = session_id or self._active_session_id
        if not sid:
            return False

        session = self._sessions.get(sid)
        if not session or session.state != AgentState.RUNNING:
            return False

        session.state = AgentState.PAUSED
        self._notify_listeners("paused", session)
        return True

    def resume_session(self, session_id: str | None = None) -> bool:
        """Resume a paused session."""
        sid = session_id or self._active_session_id
        if not sid:
            return False

        session = self._sessions.get(sid)
        if not session or session.state != AgentState.PAUSED:
            return False

        session.state = AgentState.RUNNING
        self._notify_listeners("resumed", session)
        return True

    def stop_session(self, session_id: str | None = None) -> bool:
        """Stop a session."""
        sid = session_id or self._active_session_id
        if not sid:
            return False

        session = self._sessions.get(sid)
        if not session:
            return False

        session.state = AgentState.STOPPED
        session.completed_at = datetime.now()

        if self._active_session_id == sid:
            self._active_session_id = None

        self._notify_listeners("stopped", session)
        return True

    def complete_session(self, session_id: str, error: str | None = None) -> bool:
        """Mark a session as completed (or failed if error provided)."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if error:
            session.state = AgentState.FAILED
            session.error = error
        else:
            session.state = AgentState.COMPLETED

        session.completed_at = datetime.now()

        if self._active_session_id == session_id:
            self._active_session_id = None

        self._notify_listeners("completed" if not error else "failed", session)
        return True

    def fork_session(self, session_id: str | None = None) -> AgentSession | None:
        """Fork a session to try a different approach."""
        sid = session_id or self._active_session_id
        if not sid:
            return None

        original = self._sessions.get(sid)
        if not original:
            return None

        # Create forked session
        forked = self.create_session(
            agent_name=original.agent_name,
            task_description=f"[Fork] {original.task_description}",
            model=original.model,
            parent_session_id=sid,
        )

        self._notify_listeners("forked", forked)
        return forked

    def change_model(self, session_id: str | None, new_model: str) -> bool:
        """Change the model for a session."""
        sid = session_id or self._active_session_id
        if not sid:
            return False

        session = self._sessions.get(sid)
        if not session:
            return False

        session.model = new_model

        self._notify_listeners("model_changed", session)
        return True

    async def send_correction(self, message: str, session_id: str | None = None) -> bool:
        """Send a correction message to the agent."""
        sid = session_id or self._active_session_id
        if not sid:
            return False

        session = self._sessions.get(sid)
        if not session or session.state not in (AgentState.RUNNING, AgentState.PAUSED):
            return False

        await self._correction_queue.put((sid, message))
        self._notify_listeners("correction_sent", session)
        return True

    async def get_next_correction(self) -> tuple | None:
        """Get the next correction from the queue."""
        try:
            return await asyncio.wait_for(self._correction_queue.get(), timeout=0.1)
        except TimeoutError:
            return None

    def get_session(self, session_id: str) -> AgentSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_active_session(self) -> AgentSession | None:
        """Get the currently active session."""
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    def get_all_sessions(self) -> list[AgentSession]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_running_sessions(self) -> list[AgentSession]:
        """Get all running sessions."""
        return [s for s in self._sessions.values() if s.state == AgentState.RUNNING]

    def pause_all(self) -> int:
        """Pause all running sessions. Returns count of paused sessions."""
        count = 0
        for session in self._sessions.values():
            if session.state == AgentState.RUNNING:
                session.state = AgentState.PAUSED
                self._notify_listeners("paused", session)
                count += 1
        return count

    def update_session_stats(
        self, session_id: str, iterations: int | None = None, tokens: int | None = None
    ) -> None:
        """Update session statistics."""
        session = self._sessions.get(session_id)
        if session:
            if iterations is not None:
                session.iterations = iterations
            if tokens is not None:
                session.tokens_used = tokens


# Singleton instance
_controller: AgentController | None = None


def get_agent_controller() -> AgentController:
    """Get the global agent controller instance."""
    global _controller
    if _controller is None:
        _controller = AgentController()
    return _controller


class WebSocketAgentController(AgentController):
    """Agent controller with WebSocket integration."""

    def __init__(self):
        super().__init__()
        self._ws_client = None
        self._connected = False

    async def connect(self, url: str = "ws://localhost:8765/ws") -> bool:
        """Connect to the WebSocket server."""
        try:
            from src.cli.v3.tui.services.websocket_client import get_ws_client

            self._ws_client = get_ws_client(url)

            # Register message handlers
            self._ws_client.on_message("task.created", self._on_task_created)
            self._ws_client.on_message("task.progress", self._on_task_progress)
            self._ws_client.on_message("task.thinking", self._on_task_thinking)
            self._ws_client.on_message("task.completed", self._on_task_completed)
            self._ws_client.on_message("task.error", self._on_task_error)

            self._connected = await self._ws_client.connect()
            return self._connected

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        if self._ws_client:
            await self._ws_client.disconnect()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether connected to WebSocket server."""
        return self._connected and self._ws_client and self._ws_client.is_connected

    async def create_remote_session(
        self, agent_name: str, task_description: str, model: str = "qwen3.5:27b"
    ) -> AgentSession | None:
        """Create a session via WebSocket."""
        if not self.is_connected:
            logger.warning("Not connected to server")
            return None

        # Create local session first
        session = self.create_session(agent_name, task_description, model)

        # Send to server
        await self._ws_client.create_task(
            agent=agent_name,
            prompt=task_description,
            context={"model": model, "local_session_id": session.session_id},
        )

        return session

    async def _on_task_created(self, data: dict) -> None:
        """Handle task created message from server."""
        task_id = data.get("task_id")
        logger.info(f"Server created task: {task_id}")

    async def _on_task_progress(self, data: dict) -> None:
        """Handle task progress update."""
        data.get("task_id")
        step = data.get("step", 0)
        data.get("total_steps", 1)
        data.get("message", "")

        # Find matching session and update
        for session in self._sessions.values():
            if session.state == AgentState.RUNNING:
                session.iterations = step
                self._notify_listeners("progress", session)
                break

    async def _on_task_thinking(self, data: dict) -> None:
        """Handle agent thinking update."""
        content = data.get("content", "")
        logger.debug(f"Agent thinking: {content[:50]}...")

        # Notify listeners
        for session in self._sessions.values():
            if session.state == AgentState.RUNNING:
                self._notify_listeners("thinking", session)
                break

    async def _on_task_completed(self, data: dict) -> None:
        """Handle task completion."""
        data.get("task_id")
        data.get("result")

        # Find and complete matching session
        for session in self._sessions.values():
            if session.state == AgentState.RUNNING:
                self.complete_session(session.session_id)
                break

    async def _on_task_error(self, data: dict) -> None:
        """Handle task error."""
        data.get("task_id")
        error = data.get("error", "Unknown error")

        # Find and fail matching session
        for session in self._sessions.values():
            if session.state == AgentState.RUNNING:
                self.complete_session(session.session_id, error=error)
                break


# Global WebSocket controller
_ws_controller: WebSocketAgentController | None = None


def get_ws_agent_controller() -> WebSocketAgentController:
    """Get the global WebSocket agent controller."""
    global _ws_controller
    if _ws_controller is None:
        _ws_controller = WebSocketAgentController()
    return _ws_controller
