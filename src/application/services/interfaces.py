"""Service interfaces (protocols) for Tawiza-V2.

This module defines the contracts that services must implement.
Using Protocol allows for structural subtyping (duck typing with type checking).

Benefits:
- Loose coupling between components
- Easy to mock for testing
- Follows Dependency Inversion Principle
"""

from pathlib import Path
from typing import Any, Protocol

from src.core.system_state import InitializationConfig, SystemState

# ============================================================================
# System Verification Services
# ============================================================================


class ISystemVerificationService(Protocol):
    """Interface for system requirement verification.

    Responsible for checking that all system requirements are met.
    """

    async def verify_python_version(self) -> bool:
        """Verify Python version meets requirements.

        Returns:
            True if Python version is adequate

        Raises:
            PythonVersionError: If Python version is too old
        """
        ...

    async def verify_docker(self) -> bool:
        """Verify Docker is installed and running.

        Returns:
            True if Docker is available

        Raises:
            DockerNotAvailableError: If Docker is not available
        """
        ...

    async def verify_gpu(self) -> bool:
        """Verify GPU (ROCm) is available.

        Returns:
            True if GPU is available and configured

        Raises:
            GPUNotAvailableError: If GPU is not available
        """
        ...

    async def verify_all(self, config: InitializationConfig) -> dict[str, bool]:
        """Verify all system requirements.

        Args:
            config: Initialization configuration

        Returns:
            Dictionary with verification results
        """
        ...


class IGPUDetectionService(Protocol):
    """Interface for GPU detection and information gathering."""

    async def detect_amd_gpu(self) -> bool:
        """Detect if AMD GPU with ROCm is available.

        Returns:
            True if AMD GPU detected
        """
        ...

    async def get_gpu_info(self) -> dict[str, Any]:
        """Get detailed GPU information.

        Returns:
            Dictionary with GPU details (model, memory, etc.)
        """
        ...

    async def test_gpu_functionality(self) -> bool:
        """Test if GPU is functional (can run computations).

        Returns:
            True if GPU is functional
        """
        ...


# ============================================================================
# Directory Management Services
# ============================================================================


class IDirectoryManagerService(Protocol):
    """Interface for directory management operations."""

    def create_required_directories(self, directories: list[str]) -> None:
        """Create all required directories.

        Args:
            directories: List of directory paths to create

        Raises:
            OSError: If directory creation fails
        """
        ...

    def verify_directory_structure(self) -> bool:
        """Verify all required directories exist.

        Returns:
            True if all directories exist
        """
        ...

    def get_directory_status(self) -> dict[str, bool]:
        """Get status of all directories.

        Returns:
            Dictionary mapping directory names to existence status
        """
        ...


# ============================================================================
# System Initialization Services
# ============================================================================


class ISystemInitializationService(Protocol):
    """Interface for system initialization.

    Coordinates the entire system initialization process.
    """

    async def initialize_system(self, config: InitializationConfig) -> SystemState:
        """Initialize the complete system.

        Args:
            config: Initialization configuration

        Returns:
            New system state

        Raises:
            SystemInitializationError: If initialization fails
        """
        ...

    async def shutdown_system(self) -> None:
        """Shutdown the system gracefully.

        Raises:
            SystemNotInitializedError: If system not initialized
        """
        ...

    async def restart_system(self, config: InitializationConfig | None = None) -> SystemState:
        """Restart the system.

        Args:
            config: Optional new configuration

        Returns:
            New system state after restart
        """
        ...


# ============================================================================
# Health Check Services
# ============================================================================


class IHealthCheckService(Protocol):
    """Interface for system health checking."""

    async def check_system_health(self) -> dict[str, Any]:
        """Perform comprehensive system health check.

        Returns:
            Dictionary with health check results including:
            - overall_health: Overall health score (0-100)
            - checks: Individual check results
            - issues: List of detected issues
            - recommendations: List of recommendations
        """
        ...

    async def check_cpu_health(self) -> dict[str, Any]:
        """Check CPU health and usage.

        Returns:
            CPU health metrics
        """
        ...

    async def check_memory_health(self) -> dict[str, Any]:
        """Check memory health and usage.

        Returns:
            Memory health metrics
        """
        ...

    async def check_disk_health(self) -> dict[str, Any]:
        """Check disk health and usage.

        Returns:
            Disk health metrics
        """
        ...

    async def check_services_health(self) -> dict[str, Any]:
        """Check external services health (Docker, GPU, etc.).

        Returns:
            Services health status
        """
        ...

    def calculate_health_score(self, check_results: dict[str, Any]) -> int:
        """Calculate overall health score from check results.

        Args:
            check_results: Results from health checks

        Returns:
            Health score (0-100)
        """
        ...


# ============================================================================
# Configuration Services
# ============================================================================


class IConfigurationService(Protocol):
    """Interface for configuration management."""

    async def load_configuration(self, config_path: Path) -> dict[str, Any]:
        """Load configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationNotFoundError: If file not found
            ConfigurationCorruptedError: If file is corrupted
        """
        ...

    async def save_configuration(self, config: dict[str, Any], config_path: Path) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save
            config_path: Path to save to

        Raises:
            OSError: If save fails
        """
        ...

    async def validate_configuration(self, config: dict[str, Any]) -> bool:
        """Validate configuration values.

        Args:
            config: Configuration to validate

        Returns:
            True if valid

        Raises:
            InvalidConfigurationError: If validation fails
        """
        ...


# ============================================================================
# Logging Services
# ============================================================================


class ILoggingService(Protocol):
    """Interface for logging operations."""

    async def get_logs(
        self, lines: int = 50, component: str | None = None, level: str | None = None
    ) -> list[str]:
        """Get recent log entries.

        Args:
            lines: Number of lines to retrieve
            component: Filter by component name
            level: Filter by log level

        Returns:
            List of log entries
        """
        ...

    async def follow_logs(self, component: str | None = None):
        """Follow logs in real-time (async generator).

        Args:
            component: Filter by component name

        Yields:
            Log entries as they appear
        """
        ...

    async def clear_logs(self) -> None:
        """Clear log files.

        Raises:
            OSError: If clearing fails
        """
        ...


# ============================================================================
# Metric Collection Services
# ============================================================================


class IMetricsCollectionService(Protocol):
    """Interface for collecting system metrics."""

    async def collect_system_metrics(self) -> dict[str, Any]:
        """Collect current system metrics.

        Returns:
            Dictionary with system metrics (CPU, memory, disk, etc.)
        """
        ...

    async def collect_application_metrics(self) -> dict[str, Any]:
        """Collect application-specific metrics.

        Returns:
            Dictionary with application metrics (tasks, agents, etc.)
        """
        ...

    async def get_historical_metrics(self, duration_minutes: int = 60) -> dict[str, list]:
        """Get historical metrics.

        Args:
            duration_minutes: How far back to retrieve metrics

        Returns:
            Dictionary with time-series metrics
        """
        ...


# ============================================================================
# Agent Management Services
# ============================================================================


class IAgentManagementService(Protocol):
    """Interface for agent lifecycle management."""

    async def initialize_agents(self, config: dict[str, Any]) -> Any:
        """Initialize agent system.

        Args:
            config: Agent configuration

        Returns:
            Agent integration instance
        """
        ...

    async def shutdown_agents(self) -> None:
        """Shutdown all agents gracefully."""
        ...

    async def get_agent_status(self) -> dict[str, Any]:
        """Get status of all agents.

        Returns:
            Dictionary with agent status
        """
        ...


# ============================================================================
# Monitoring Services
# ============================================================================


class IMonitoringService(Protocol):
    """Interface for monitoring and debugging."""

    async def start_monitoring(self, config: dict[str, Any]) -> Any:
        """Start monitoring/debugging system.

        Args:
            config: Monitoring configuration

        Returns:
            Monitoring system instance
        """
        ...

    async def stop_monitoring(self) -> None:
        """Stop monitoring system."""
        ...

    async def get_monitoring_status(self) -> dict[str, Any]:
        """Get monitoring system status.

        Returns:
            Monitoring status
        """
        ...
