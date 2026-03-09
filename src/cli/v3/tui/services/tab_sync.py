"""Tab synchronization service for TUI v6.

Provides pub/sub pattern for synchronizing state between tabs/screens.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SyncEventType(Enum):
    """Types of synchronization events."""

    REGION_SELECTED = "region_selected"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETE = "analysis_complete"
    FILTER_CHANGED = "filter_changed"
    THEME_CHANGED = "theme_changed"
    SERVICE_STATUS_CHANGED = "service_status_changed"


@dataclass
class SyncEvent:
    """Event for synchronizing state between tabs."""

    event_type: SyncEventType
    source: str  # Screen ID
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# Type alias for sync callbacks
SyncCallback = Callable[[SyncEvent], None]


class TabSyncService:
    """Service for synchronizing state between tabs/screens using pub/sub pattern.

    This is a singleton service that allows screens to:
    1. Subscribe to specific event types
    2. Emit events to notify other screens
    3. Share state across screens
    4. Access event history
    """

    _instance: Optional["TabSyncService"] = None

    def __new__(cls) -> "TabSyncService":
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the tab sync service."""
        if self._initialized:
            return

        self._subscribers: dict[SyncEventType, list[SyncCallback]] = {
            event_type: [] for event_type in SyncEventType
        }
        self._state: dict[str, Any] = {}
        self._event_history: list[SyncEvent] = []
        self._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset singleton for testing."""
        cls._instance = None

    def subscribe(self, event_type: SyncEventType, callback: SyncCallback) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is emitted

        Note:
            Duplicate subscriptions are idempotent - subscribing the same
            callback multiple times has no additional effect.
        """
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: SyncEventType, callback: SyncCallback) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            callback: Function to remove from subscribers
        """
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def emit(self, event: SyncEvent) -> None:
        """Emit an event to all subscribers.

        The event is also stored in history (max 100 events).

        Args:
            event: Event to emit
        """
        # Add to history (keep last 100)
        self._event_history.append(event)
        if len(self._event_history) > 100:
            self._event_history = self._event_history[-100:]

        # Call all subscribers for this event type
        for callback in self._subscribers[event.event_type]:
            try:
                callback(event)
            except Exception:
                pass  # Continue notifying other subscribers

    def set_state(self, key: str, value: Any) -> None:
        """Set shared state.

        Args:
            key: State key
            value: State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get shared state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self) -> None:
        """Clear all shared state."""
        self._state.clear()

    def get_recent_events(
        self,
        event_type: SyncEventType | None = None,
        limit: int = 10
    ) -> list[SyncEvent]:
        """Get recent events from history.

        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of recent events (most recent first)
        """
        events = self._event_history

        # Filter by event type if specified
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        # Return most recent first, limited to requested count
        return list(reversed(events[-limit:]))


def get_tab_sync_service() -> TabSyncService:
    """Get the global tab sync service instance.

    Returns:
        TabSyncService singleton instance
    """
    return TabSyncService()
