"""TUI Services."""

from src.cli.v3.tui.services.adaptive_refresh import (
    AdaptiveRefreshManager,
    RefreshPriority,
    get_refresh_manager,
    init_refresh_manager,
)
from src.cli.v3.tui.services.department_data import (
    DepartmentDataService,
    DepartmentStats,
    LoadingProgress,
    LoadingState,
    get_department_service,
)
from src.cli.v3.tui.services.error_telemetry import (
    ErrorCategory,
    ErrorEvent,
    ErrorSeverity,
    ErrorTelemetry,
    get_error_telemetry,
    track_errors,
    track_errors_async,
)
from src.cli.v3.tui.services.metrics_collector import MetricsCollector
from src.cli.v3.tui.services.session_recorder import SessionRecorder

__all__ = [
    "MetricsCollector",
    "SessionRecorder",
    "AdaptiveRefreshManager",
    "RefreshPriority",
    "get_refresh_manager",
    "init_refresh_manager",
    # Error telemetry
    "ErrorTelemetry",
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorEvent",
    "get_error_telemetry",
    "track_errors",
    "track_errors_async",
    # Department data (real API)
    "DepartmentDataService",
    "DepartmentStats",
    "LoadingState",
    "LoadingProgress",
    "get_department_service",
]
