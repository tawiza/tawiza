"""Adaptive Refresh Manager - Reduces CPU usage by adjusting refresh rates.

This service manages refresh timers across the TUI to minimize CPU usage:
- Slows down refresh when screens are not visible
- Detects user activity to adjust refresh rates
- Suspends timers when app is idle
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger
from textual.app import App
from textual.timer import Timer


class RefreshPriority(Enum):
    """Priority levels for refresh operations."""

    CRITICAL = 1  # Always refresh at full rate (e.g., active task progress)
    HIGH = 2  # Refresh frequently when visible (e.g., metrics)
    NORMAL = 3  # Standard refresh rate
    LOW = 4  # Can be delayed (e.g., logs, history)
    BACKGROUND = 5  # Only refresh when explicitly requested


@dataclass
class RefreshConfig:
    """Configuration for a refresh timer."""

    name: str
    callback: Callable
    priority: RefreshPriority = RefreshPriority.NORMAL
    active_interval: float = 1.0  # Interval when screen is active (seconds)
    idle_interval: float = 5.0  # Interval when screen is idle
    background_interval: float = 30.0  # Interval when screen is not visible
    enabled: bool = True
    last_refresh: float = field(default_factory=time.time)


class AdaptiveRefreshManager:
    """Manages adaptive refresh timers for the TUI.

    Features:
    - Adjusts refresh rate based on screen visibility
    - Detects user activity to optimize CPU usage
    - Provides centralized timer management
    """

    # Idle threshold - no activity for this long = idle mode
    IDLE_THRESHOLD = 10.0  # seconds

    # Activity detection - any of these events reset idle timer
    ACTIVITY_EVENTS = {"key", "mouse_move", "mouse_down", "focus"}

    def __init__(self, app: App | None = None):
        """Initialize the refresh manager.

        Args:
            app: Optional Textual app reference for timer management
        """
        self._app = app
        self._timers: dict[str, Timer] = {}
        self._configs: dict[str, RefreshConfig] = {}
        self._active_screen: str | None = None
        self._last_activity: float = time.time()
        self._is_idle: bool = False
        self._suspended: bool = False

        # Track which screens have been mounted
        self._mounted_screens: set = set()

        logger.debug("AdaptiveRefreshManager initialized")

    def set_app(self, app: App) -> None:
        """Set the Textual app reference."""
        self._app = app

    def register_timer(
        self,
        name: str,
        callback: Callable,
        priority: RefreshPriority = RefreshPriority.NORMAL,
        active_interval: float = 1.0,
        idle_interval: float = 5.0,
        background_interval: float = 30.0,
    ) -> None:
        """Register a refresh timer with adaptive behavior.

        Args:
            name: Unique identifier for this timer
            callback: Function to call on refresh
            priority: Refresh priority level
            active_interval: Refresh rate when screen is active
            idle_interval: Refresh rate when user is idle
            background_interval: Refresh rate when screen is not visible
        """
        config = RefreshConfig(
            name=name,
            callback=callback,
            priority=priority,
            active_interval=active_interval,
            idle_interval=idle_interval,
            background_interval=background_interval,
        )
        self._configs[name] = config
        logger.debug(f"Registered adaptive timer: {name} (priority={priority.name})")

    def start_timer(self, name: str) -> Timer | None:
        """Start a registered timer.

        Args:
            name: Timer name to start

        Returns:
            The Timer object if started, None otherwise
        """
        if name not in self._configs:
            logger.warning(f"Timer {name} not registered")
            return None

        if not self._app:
            logger.warning("No app set, cannot start timer")
            return None

        config = self._configs[name]
        if not config.enabled:
            return None

        # Stop existing timer if any
        self.stop_timer(name)

        # Determine initial interval based on state
        interval = self._get_current_interval(config)

        # Create and store timer
        timer = self._app.set_interval(interval, config.callback)
        self._timers[name] = timer

        logger.debug(f"Started timer {name} with interval {interval}s")
        return timer

    def stop_timer(self, name: str) -> None:
        """Stop a timer.

        Args:
            name: Timer name to stop
        """
        if name in self._timers:
            self._timers[name].stop()
            del self._timers[name]
            logger.debug(f"Stopped timer {name}")

    def stop_all_timers(self) -> None:
        """Stop all managed timers."""
        for name in list(self._timers.keys()):
            self.stop_timer(name)

    def set_active_screen(self, screen_name: str) -> None:
        """Set the currently active screen.

        This will adjust refresh rates for all timers based on
        whether they belong to the active screen.

        Args:
            screen_name: Name of the active screen
        """
        if self._active_screen == screen_name:
            return

        old_screen = self._active_screen
        self._active_screen = screen_name
        self._mounted_screens.add(screen_name)

        logger.debug(f"Active screen changed: {old_screen} -> {screen_name}")

        # Adjust all timer intervals
        self._adjust_all_intervals()

    def record_activity(self) -> None:
        """Record user activity to reset idle timer."""
        self._last_activity = time.time()

        if self._is_idle:
            self._is_idle = False
            logger.debug("User activity detected, exiting idle mode")
            self._adjust_all_intervals()

    def check_idle(self) -> bool:
        """Check if user is idle and update state.

        Returns:
            True if user is now idle
        """
        was_idle = self._is_idle
        self._is_idle = (time.time() - self._last_activity) > self.IDLE_THRESHOLD

        if self._is_idle and not was_idle:
            logger.debug("User is now idle, reducing refresh rates")
            self._adjust_all_intervals()

        return self._is_idle

    def suspend(self) -> None:
        """Suspend all timers (e.g., when app loses focus)."""
        if self._suspended:
            return

        self._suspended = True
        for timer in self._timers.values():
            timer.pause()

        logger.debug("All timers suspended")

    def resume(self) -> None:
        """Resume all timers."""
        if not self._suspended:
            return

        self._suspended = False
        for timer in self._timers.values():
            timer.resume()

        self.record_activity()
        logger.debug("All timers resumed")

    def _get_current_interval(self, config: RefreshConfig) -> float:
        """Get the appropriate interval for a timer based on current state.

        Args:
            config: Timer configuration

        Returns:
            Appropriate refresh interval in seconds
        """
        # Critical priority always uses active interval
        if config.priority == RefreshPriority.CRITICAL:
            return config.active_interval

        # Check if timer's screen is active
        is_active_screen = self._active_screen and config.name.startswith(self._active_screen)

        if is_active_screen:
            # Active screen - use active or idle interval
            if self._is_idle:
                return config.idle_interval
            return config.active_interval
        else:
            # Background screen - use background interval
            return config.background_interval

    def _adjust_all_intervals(self) -> None:
        """Adjust all timer intervals based on current state."""
        if not self._app:
            return

        for name, config in self._configs.items():
            if name not in self._timers:
                continue

            new_interval = self._get_current_interval(config)

            # Recreate timer with new interval
            # (Textual timers don't support interval changes)
            self.stop_timer(name)
            timer = self._app.set_interval(new_interval, config.callback)
            self._timers[name] = timer

            logger.debug(f"Adjusted timer {name} to {new_interval}s")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about refresh state.

        Returns:
            Dict with refresh statistics
        """
        return {
            "active_screen": self._active_screen,
            "is_idle": self._is_idle,
            "suspended": self._suspended,
            "timer_count": len(self._timers),
            "registered_count": len(self._configs),
            "idle_for": time.time() - self._last_activity if self._is_idle else 0,
            "timers": {
                name: {
                    "priority": config.priority.name,
                    "current_interval": self._get_current_interval(config),
                    "enabled": config.enabled,
                }
                for name, config in self._configs.items()
            },
        }


# Singleton instance
_refresh_manager: AdaptiveRefreshManager | None = None


def get_refresh_manager() -> AdaptiveRefreshManager:
    """Get the singleton refresh manager instance."""
    global _refresh_manager
    if _refresh_manager is None:
        _refresh_manager = AdaptiveRefreshManager()
    return _refresh_manager


def init_refresh_manager(app: App) -> AdaptiveRefreshManager:
    """Initialize the refresh manager with an app.

    Args:
        app: The Textual app

    Returns:
        The initialized refresh manager
    """
    manager = get_refresh_manager()
    manager.set_app(app)
    return manager
