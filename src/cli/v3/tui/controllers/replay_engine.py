"""Replay Engine - Records and replays agent sessions."""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ActionType(Enum):
    """Type of recorded action."""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    USER_MESSAGE = "user_message"
    ERROR = "error"
    STATE_CHANGE = "state_change"
    SCREENSHOT = "screenshot"


@dataclass
class RecordedAction:
    """A single recorded action."""
    action_id: str
    timestamp: datetime
    action_type: ActionType
    content: str
    details: dict[str, Any] | None = None
    screenshot_path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_id": self.action_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "content": self.content,
            "details": self.details,
            "screenshot_path": self.screenshot_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecordedAction":
        """Create from dictionary."""
        return cls(
            action_id=data["action_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action_type=ActionType(data["action_type"]),
            content=data["content"],
            details=data.get("details"),
            screenshot_path=data.get("screenshot_path"),
        )


@dataclass
class SessionRecording:
    """A complete session recording."""
    session_id: str
    agent_name: str
    task_description: str
    model: str
    started_at: datetime
    completed_at: datetime | None
    actions: list[RecordedAction]
    final_status: str
    parent_session_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actions": [a.to_dict() for a in self.actions],
            "final_status": self.final_status,
            "parent_session_id": self.parent_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionRecording":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            agent_name=data["agent_name"],
            task_description=data["task_description"],
            model=data["model"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            actions=[RecordedAction.from_dict(a) for a in data["actions"]],
            final_status=data["final_status"],
            parent_session_id=data.get("parent_session_id"),
        )


class ReplayEngine:
    """Engine for recording and replaying agent sessions."""

    def __init__(self, storage_dir: Path | None = None):
        self._storage_dir = storage_dir or Path.home() / ".tawiza" / "recordings"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._active_recordings: dict[str, SessionRecording] = {}
        self._current_replay_index: int = 0

    def start_recording(
        self,
        session_id: str,
        agent_name: str,
        task_description: str,
        model: str,
        parent_session_id: str | None = None
    ) -> SessionRecording:
        """Start recording a new session."""
        recording = SessionRecording(
            session_id=session_id,
            agent_name=agent_name,
            task_description=task_description,
            model=model,
            started_at=datetime.now(),
            completed_at=None,
            actions=[],
            final_status="running",
            parent_session_id=parent_session_id,
        )
        self._active_recordings[session_id] = recording
        return recording

    def record_action(
        self,
        session_id: str,
        action_type: ActionType,
        content: str,
        details: dict[str, Any] | None = None,
        screenshot_path: str | None = None
    ) -> RecordedAction | None:
        """Record an action for a session."""
        recording = self._active_recordings.get(session_id)
        if not recording:
            return None

        action = RecordedAction(
            action_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            action_type=action_type,
            content=content,
            details=details,
            screenshot_path=screenshot_path,
        )
        recording.actions.append(action)
        return action

    def record_thinking(self, session_id: str, content: str) -> RecordedAction | None:
        """Record a thinking action."""
        return self.record_action(session_id, ActionType.THINKING, content)

    def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        params: dict | None = None
    ) -> RecordedAction | None:
        """Record a tool call."""
        return self.record_action(
            session_id,
            ActionType.TOOL_CALL,
            f"Call: {tool_name}",
            details={"tool": tool_name, "params": params}
        )

    def record_tool_result(
        self,
        session_id: str,
        result: str,
        success: bool = True
    ) -> RecordedAction | None:
        """Record a tool result."""
        return self.record_action(
            session_id,
            ActionType.TOOL_RESULT,
            result,
            details={"success": success}
        )

    def record_user_message(self, session_id: str, message: str) -> RecordedAction | None:
        """Record a user message/correction."""
        return self.record_action(session_id, ActionType.USER_MESSAGE, message)

    def record_error(self, session_id: str, error: str) -> RecordedAction | None:
        """Record an error."""
        return self.record_action(session_id, ActionType.ERROR, error)

    def record_screenshot(
        self,
        session_id: str,
        screenshot_path: str,
        description: str = "Screenshot"
    ) -> RecordedAction | None:
        """Record a screenshot."""
        return self.record_action(
            session_id,
            ActionType.SCREENSHOT,
            description,
            screenshot_path=screenshot_path
        )

    def stop_recording(self, session_id: str, final_status: str) -> SessionRecording | None:
        """Stop recording and save the session."""
        recording = self._active_recordings.pop(session_id, None)
        if not recording:
            return None

        recording.completed_at = datetime.now()
        recording.final_status = final_status

        # Save to file
        self._save_recording(recording)

        return recording

    def _save_recording(self, recording: SessionRecording) -> Path:
        """Save a recording to disk."""
        filename = f"{recording.session_id}_{recording.started_at.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self._storage_dir / filename

        with open(filepath, "w") as f:
            json.dump(recording.to_dict(), f, indent=2)

        return filepath

    def load_recording(self, session_id: str) -> SessionRecording | None:
        """Load a recording by session ID."""
        # Search for file matching session_id
        for filepath in self._storage_dir.glob(f"{session_id}_*.json"):
            with open(filepath) as f:
                data = json.load(f)
            return SessionRecording.from_dict(data)
        return None

    def list_recordings(self, limit: int = 50) -> list[dict]:
        """List available recordings."""
        recordings = []
        files = sorted(self._storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

        for filepath in files[:limit]:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                recordings.append({
                    "session_id": data["session_id"],
                    "agent_name": data["agent_name"],
                    "task_description": data["task_description"][:50],
                    "started_at": data["started_at"],
                    "final_status": data["final_status"],
                    "action_count": len(data["actions"]),
                })
            except Exception:
                continue

        return recordings

    def delete_recording(self, session_id: str) -> bool:
        """Delete a recording."""
        for filepath in self._storage_dir.glob(f"{session_id}_*.json"):
            filepath.unlink()
            return True
        return False

    # Replay functionality

    def start_replay(self, session_id: str) -> SessionRecording | None:
        """Start replaying a session."""
        recording = self.load_recording(session_id)
        if recording:
            self._current_replay_index = 0
        return recording

    def get_replay_action(
        self,
        recording: SessionRecording,
        index: int
    ) -> RecordedAction | None:
        """Get a specific action from a recording."""
        if 0 <= index < len(recording.actions):
            return recording.actions[index]
        return None

    def get_next_replay_action(
        self,
        recording: SessionRecording
    ) -> RecordedAction | None:
        """Get the next action in replay."""
        action = self.get_replay_action(recording, self._current_replay_index)
        if action:
            self._current_replay_index += 1
        return action

    def get_previous_replay_action(
        self,
        recording: SessionRecording
    ) -> RecordedAction | None:
        """Get the previous action in replay."""
        if self._current_replay_index > 0:
            self._current_replay_index -= 1
        return self.get_replay_action(recording, self._current_replay_index)

    def seek_replay(self, index: int) -> None:
        """Seek to a specific position in replay."""
        self._current_replay_index = max(0, index)

    @property
    def replay_index(self) -> int:
        """Get current replay index."""
        return self._current_replay_index


# Singleton instance
_engine: ReplayEngine | None = None


def get_replay_engine() -> ReplayEngine:
    """Get the global replay engine instance."""
    global _engine
    if _engine is None:
        _engine = ReplayEngine()
    return _engine
