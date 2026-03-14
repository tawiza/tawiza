"""System state management for Tawiza-V2.

This module provides a thread-safe singleton for managing system state,
replacing dangerous global mutable variables with controlled access.

Design Pattern: Singleton with Thread Safety
Benefits:
- Eliminates global mutable state
- Thread-safe access to system state
- Immutable state snapshots
- Clear state lifecycle management
"""

from dataclasses import dataclass
from datetime import datetime
from threading import Lock, RLock
from typing import Any, Optional

from loguru import logger


@dataclass(frozen=True)
class InitializationConfig:
    """Immutable initialization configuration.

    Frozen dataclass ensures configuration cannot be modified after creation.
    """

    gpu_enabled: bool
    monitoring_enabled: bool
    max_concurrent_tasks: int = 5
    auto_scale: bool = True
    retry_failed_tasks: int = 3
    verbose: bool = False


@dataclass(frozen=True)
class SystemState:
    """Immutable system state snapshot.

    Represents a point-in-time state of the system. Frozen ensures
    that once created, the state cannot be modified.

    This promotes:
    - Functional programming principles
    - Easier reasoning about state changes
    - Thread safety (immutable objects are inherently thread-safe)
    """

    # Core components (can be None if not initialized)
    agents: Any | None = None
    monitoring: Any | None = None

    # Configuration
    config: InitializationConfig | None = None

    # Metadata
    initialized_at: datetime | None = None
    version: str = "2.0.3"

    # Runtime metrics
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    def __post_init__(self):
        """Log state creation."""
        logger.debug(f"SystemState created: {self.initialized_at}")

    @property
    def is_initialized(self) -> bool:
        """Check if system is initialized."""
        return self.initialized_at is not None

    @property
    def has_gpu(self) -> bool:
        """Check if GPU is enabled."""
        return self.config is not None and self.config.gpu_enabled

    @property
    def has_monitoring(self) -> bool:
        """Check if monitoring is enabled."""
        return self.monitoring is not None

    def with_updates(self, **updates) -> "SystemState":
        """Create new state with updates (functional approach).

        Args:
            **updates: Fields to update

        Returns:
            New SystemState instance with updates applied

        Example:
            >>> state = SystemState(active_tasks=5)
            >>> new_state = state.with_updates(active_tasks=6)
            >>> assert state.active_tasks == 5  # Original unchanged
            >>> assert new_state.active_tasks == 6  # New state
        """
        from dataclasses import replace

        return replace(self, **updates)


class SystemStateManager:
    """Thread-safe singleton for managing system state.

    This class replaces global mutable variables with a controlled,
    thread-safe state management system.

    Design Pattern: Singleton (Double-Checked Locking)
    Thread Safety: Uses RLock for reentrant locking

    Example:
        >>> manager = SystemStateManager()
        >>> config = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        >>> state = SystemState(config=config, initialized_at=datetime.utcnow())
        >>> manager.update_state(state)
        >>> current = manager.state
        >>> print(current.is_initialized)
        True
    """

    _instance: Optional["SystemStateManager"] = None
    _lock: Lock = Lock()  # Class-level lock for singleton creation

    def __new__(cls) -> "SystemStateManager":
        """Implement thread-safe singleton pattern.

        Uses double-checked locking to minimize lock overhead.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    instance = super().__new__(cls)
                    # Initialize instance variables
                    instance._state: SystemState | None = None
                    instance._state_lock: RLock = RLock()  # Reentrant lock for state access
                    instance._history: list[SystemState] = []
                    instance._max_history: int = 10  # Keep last 10 states
                    cls._instance = instance
                    logger.info("SystemStateManager singleton created")
        return cls._instance

    @property
    def state(self) -> SystemState | None:
        """Get current system state (thread-safe read).

        Returns:
            Current system state or None if not initialized
        """
        with self._state_lock:
            return self._state

    def update_state(self, state: SystemState) -> None:
        """Update system state (thread-safe write).

        Args:
            state: New system state

        Raises:
            TypeError: If state is not a SystemState instance
        """
        if not isinstance(state, SystemState):
            raise TypeError(f"Expected SystemState, got {type(state)}")

        with self._state_lock:
            # Save previous state to history
            if self._state is not None:
                self._history.append(self._state)
                # Trim history if needed
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history :]

            self._state = state
            logger.info(f"System state updated: initialized={state.is_initialized}")

    def clear_state(self) -> None:
        """Clear current system state (thread-safe).

        This is equivalent to system shutdown.
        """
        with self._state_lock:
            if self._state is not None:
                self._history.append(self._state)
            self._state = None
            logger.info("System state cleared")

    def is_initialized(self) -> bool:
        """Check if system is initialized (thread-safe).

        Returns:
            True if system is initialized
        """
        with self._state_lock:
            return self._state is not None and self._state.is_initialized

    def get_state_or_raise(self) -> SystemState:
        """Get state or raise exception if not initialized.

        Returns:
            Current system state

        Raises:
            SystemNotInitializedError: If system is not initialized
        """
        from src.core.exceptions import SystemNotInitializedError

        with self._state_lock:
            if self._state is None or not self._state.is_initialized:
                raise SystemNotInitializedError()
            return self._state

    def increment_tasks(self, active: int = 0, completed: int = 0, failed: int = 0) -> None:
        """Increment task counters (thread-safe).

        Args:
            active: Change in active tasks
            completed: Change in completed tasks
            failed: Change in failed tasks
        """
        with self._state_lock:
            if self._state is not None:
                self._state = self._state.with_updates(
                    active_tasks=max(0, self._state.active_tasks + active),
                    completed_tasks=self._state.completed_tasks + completed,
                    failed_tasks=self._state.failed_tasks + failed,
                )

    def get_history(self) -> list[SystemState]:
        """Get state history (thread-safe).

        Returns:
            List of previous states (most recent last)
        """
        with self._state_lock:
            return self._history.copy()

    def get_metrics(self) -> dict[str, Any]:
        """Get current system metrics (thread-safe).

        Returns:
            Dictionary with system metrics
        """
        with self._state_lock:
            if self._state is None:
                return {
                    "initialized": False,
                    "active_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                }

            return {
                "initialized": self._state.is_initialized,
                "gpu_enabled": self._state.has_gpu,
                "monitoring_enabled": self._state.has_monitoring,
                "active_tasks": self._state.active_tasks,
                "completed_tasks": self._state.completed_tasks,
                "failed_tasks": self._state.failed_tasks,
                "initialized_at": self._state.initialized_at.isoformat()
                if self._state.initialized_at
                else None,
                "version": self._state.version,
            }

    def __repr__(self) -> str:
        """String representation for debugging."""
        with self._state_lock:
            if self._state is None:
                return "SystemStateManager(state=None)"
            return f"SystemStateManager(initialized={self._state.is_initialized})"


# ============================================================================
# Module-level convenience functions
# ============================================================================


def get_system_state_manager() -> SystemStateManager:
    """Get the global SystemStateManager instance.

    Returns:
        SystemStateManager singleton

    Example:
        >>> manager = get_system_state_manager()
        >>> if manager.is_initialized():
        ...     print("System is ready")
    """
    return SystemStateManager()


def get_current_state() -> SystemState | None:
    """Get current system state (convenience function).

    Returns:
        Current system state or None
    """
    return get_system_state_manager().state


def is_system_initialized() -> bool:
    """Check if system is initialized (convenience function).

    Returns:
        True if system is initialized
    """
    return get_system_state_manager().is_initialized()


def require_initialized() -> SystemState:
    """Require system to be initialized, raise if not (convenience function).

    Returns:
        Current system state

    Raises:
        SystemNotInitializedError: If system is not initialized
    """
    return get_system_state_manager().get_state_or_raise()
