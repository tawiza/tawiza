"""Session Recorder - Simplified interface to ReplayEngine for TUI."""

from src.cli.v3.tui.controllers.replay_engine import (
    SessionRecording,
    get_replay_engine,
)


class SessionRecorder:
    """Simplified session recording interface for TUI components."""

    def __init__(self):
        self._engine = get_replay_engine()
        self._current_session_id: str | None = None

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._current_session_id is not None

    @property
    def current_session_id(self) -> str | None:
        """Get current recording session ID."""
        return self._current_session_id

    def start(self, session_id: str, agent_name: str, task: str, model: str = "default") -> None:
        """Start recording a session."""
        self._engine.start_recording(
            session_id=session_id,
            agent_name=agent_name,
            task_description=task,
            model=model,
        )
        self._current_session_id = session_id

    def stop(self, status: str = "completed") -> SessionRecording | None:
        """Stop current recording."""
        if not self._current_session_id:
            return None

        recording = self._engine.stop_recording(self._current_session_id, status)
        self._current_session_id = None
        return recording

    def thinking(self, content: str) -> None:
        """Record thinking."""
        if self._current_session_id:
            self._engine.record_thinking(self._current_session_id, content)

    def tool_call(self, tool_name: str, params: dict | None = None) -> None:
        """Record tool call."""
        if self._current_session_id:
            self._engine.record_tool_call(self._current_session_id, tool_name, params)

    def tool_result(self, result: str, success: bool = True) -> None:
        """Record tool result."""
        if self._current_session_id:
            self._engine.record_tool_result(self._current_session_id, result, success)

    def user_message(self, message: str) -> None:
        """Record user message/correction."""
        if self._current_session_id:
            self._engine.record_user_message(self._current_session_id, message)

    def error(self, error: str) -> None:
        """Record error."""
        if self._current_session_id:
            self._engine.record_error(self._current_session_id, error)

    def screenshot(self, path: str, description: str = "Screenshot") -> None:
        """Record screenshot."""
        if self._current_session_id:
            self._engine.record_screenshot(self._current_session_id, path, description)

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List available recordings."""
        return self._engine.list_recordings(limit)

    def load_session(self, session_id: str) -> SessionRecording | None:
        """Load a session recording."""
        return self._engine.load_recording(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session recording."""
        return self._engine.delete_recording(session_id)


# Singleton instance
_recorder: SessionRecorder | None = None


def get_session_recorder() -> SessionRecorder:
    """Get the global session recorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = SessionRecorder()
    return _recorder
