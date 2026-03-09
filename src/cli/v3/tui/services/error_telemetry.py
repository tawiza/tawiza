"""Error Telemetry - Captures and analyzes errors across UI and backend.

Provides comprehensive error tracking for:
- Graphical/widget rendering errors
- Backend service errors
- API call failures
- WebSocket disconnections
- Exception stack traces with context
"""

import traceback
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger


class ErrorCategory(Enum):
    """Categories of errors for analysis."""
    RENDER = "render"           # Widget/graphical rendering errors
    BACKEND = "backend"         # Backend service errors
    API = "api"                 # API call failures
    WEBSOCKET = "websocket"     # WebSocket connection errors
    DATA = "data"               # Data processing errors
    NETWORK = "network"         # Network connectivity errors
    RESOURCE = "resource"       # Resource loading errors (files, etc.)
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorEvent:
    """Single error event with full context."""
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    component: str              # Which component (widget, service, etc.)
    exception_type: str | None = None
    stack_trace: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "component": self.component,
            "exception_type": self.exception_type,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "resolved": self.resolved,
        }


@dataclass
class ErrorStats:
    """Statistics about errors."""
    total_errors: int = 0
    errors_by_category: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_severity: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_component: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_rate_per_minute: float = 0.0
    most_common_error: str | None = None
    last_error_time: datetime | None = None


class ErrorTelemetry:
    """Centralized error telemetry service.

    Usage:
        telemetry = get_error_telemetry()

        # Track a render error
        telemetry.track_error(
            category=ErrorCategory.RENDER,
            message="Map widget failed to render",
            component="FranceMapPNG",
            exception=e,
            context={"geojson_path": str(path)}
        )

        # Track a backend error
        telemetry.track_error(
            category=ErrorCategory.BACKEND,
            message="Ollama connection failed",
            component="TAJINEService",
            severity=ErrorSeverity.ERROR
        )
    """

    def __init__(self, max_history: int = 1000):
        self._history: list[ErrorEvent] = []
        self._max_history = max_history
        self._listeners: list[Callable[[ErrorEvent], None]] = []
        self._start_time = datetime.now()

    def track_error(
        self,
        category: ErrorCategory,
        message: str,
        component: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """Track a new error event.

        Args:
            category: Type of error (RENDER, BACKEND, etc.)
            message: Human-readable error description
            component: Component where error occurred
            severity: Error severity level
            exception: Optional exception object
            context: Additional context data

        Returns:
            The created ErrorEvent
        """
        event = ErrorEvent(
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            message=message,
            component=component,
            exception_type=type(exception).__name__ if exception else None,
            stack_trace=traceback.format_exc() if exception else None,
            context=context or {},
        )

        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Error listener failed: {e}")

        # Log based on severity
        log_msg = f"[{category.value}] {component}: {message}"
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_msg)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.debug(log_msg)

        return event

    def track_render_error(
        self,
        widget: str,
        message: str,
        exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """Convenience method for tracking render errors."""
        return self.track_error(
            category=ErrorCategory.RENDER,
            message=message,
            component=widget,
            severity=ErrorSeverity.WARNING,
            exception=exception,
            context=context,
        )

    def track_backend_error(
        self,
        service: str,
        message: str,
        exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """Convenience method for tracking backend errors."""
        return self.track_error(
            category=ErrorCategory.BACKEND,
            message=message,
            component=service,
            severity=ErrorSeverity.ERROR,
            exception=exception,
            context=context,
        )

    def track_api_error(
        self,
        endpoint: str,
        status_code: int | None = None,
        message: str = "API call failed",
        context: dict[str, Any] | None = None,
    ) -> ErrorEvent:
        """Convenience method for tracking API errors."""
        ctx = context or {}
        if status_code:
            ctx["status_code"] = status_code
        return self.track_error(
            category=ErrorCategory.API,
            message=message,
            component=endpoint,
            severity=ErrorSeverity.ERROR,
            context=ctx,
        )

    def add_listener(self, listener: Callable[[ErrorEvent], None]) -> None:
        """Add a listener for error events."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ErrorEvent], None]) -> None:
        """Remove an error event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def get_recent_errors(
        self,
        limit: int = 50,
        category: ErrorCategory | None = None,
        severity: ErrorSeverity | None = None,
        component: str | None = None,
    ) -> list[ErrorEvent]:
        """Get recent errors with optional filtering."""
        filtered = self._history

        if category:
            filtered = [e for e in filtered if e.category == category]
        if severity:
            filtered = [e for e in filtered if e.severity == severity]
        if component:
            filtered = [e for e in filtered if e.component == component]

        return filtered[-limit:]

    def get_stats(self) -> ErrorStats:
        """Get error statistics."""
        stats = ErrorStats()
        stats.total_errors = len(self._history)

        if not self._history:
            return stats

        # Count by category, severity, component
        for event in self._history:
            stats.errors_by_category[event.category.value] += 1
            stats.errors_by_severity[event.severity.value] += 1
            stats.errors_by_component[event.component] += 1

        # Calculate error rate
        elapsed_minutes = (datetime.now() - self._start_time).total_seconds() / 60
        if elapsed_minutes > 0:
            stats.error_rate_per_minute = stats.total_errors / elapsed_minutes

        # Most common error message
        message_counts: dict[str, int] = defaultdict(int)
        for event in self._history:
            message_counts[event.message] += 1
        if message_counts:
            stats.most_common_error = max(message_counts, key=message_counts.get)

        stats.last_error_time = self._history[-1].timestamp

        return stats

    def get_component_health(self) -> dict[str, dict[str, Any]]:
        """Get health status for each component."""
        health: dict[str, dict[str, Any]] = {}

        # Group by component
        by_component: dict[str, list[ErrorEvent]] = defaultdict(list)
        for event in self._history:
            by_component[event.component].append(event)

        for component, events in by_component.items():
            recent = [e for e in events if (datetime.now() - e.timestamp).seconds < 300]
            critical = sum(1 for e in recent if e.severity == ErrorSeverity.CRITICAL)
            errors = sum(1 for e in recent if e.severity == ErrorSeverity.ERROR)

            if critical > 0:
                status = "critical"
            elif errors > 3:
                status = "degraded"
            elif errors > 0:
                status = "warning"
            else:
                status = "healthy"

            health[component] = {
                "status": status,
                "total_errors": len(events),
                "recent_errors": len(recent),
                "last_error": events[-1].timestamp.isoformat() if events else None,
            }

        return health

    def clear(self) -> None:
        """Clear all error history."""
        self._history.clear()
        self._start_time = datetime.now()

    def export_to_json(self) -> list[dict[str, Any]]:
        """Export all errors to JSON-serializable format."""
        return [e.to_dict() for e in self._history]


# Singleton instance
_telemetry: ErrorTelemetry | None = None


def get_error_telemetry() -> ErrorTelemetry:
    """Get the global error telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = ErrorTelemetry()
    return _telemetry


# Decorator for automatic error tracking
def track_errors(category: ErrorCategory, component: str):
    """Decorator to automatically track errors in a function.

    Usage:
        @track_errors(ErrorCategory.RENDER, "MyWidget")
        def render_complex_widget():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                get_error_telemetry().track_error(
                    category=category,
                    message=str(e),
                    component=component,
                    exception=e,
                    context={"function": func.__name__}
                )
                raise
        return wrapper
    return decorator


# Async version of the decorator
def track_errors_async(category: ErrorCategory, component: str):
    """Async decorator to automatically track errors.

    Usage:
        @track_errors_async(ErrorCategory.BACKEND, "TAJINEService")
        async def call_backend():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                get_error_telemetry().track_error(
                    category=category,
                    message=str(e),
                    component=component,
                    exception=e,
                    context={"function": func.__name__}
                )
                raise
        return wrapper
    return decorator
