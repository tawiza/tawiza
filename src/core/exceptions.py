"""Custom exceptions for Tawiza-V2.

This module defines a hierarchy of exceptions to replace bare except blocks
and provide better error handling with specific exception types.
"""


# ============================================================================
# Base Exceptions
# ============================================================================

class TawizaException(Exception):
    """Base exception for all Tawiza-V2 errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TawizaConfigurationError(TawizaException):
    """Configuration-related errors."""
    pass


class TawizaResourceError(TawizaException):
    """Resource availability or access errors."""
    pass


class TawizaValidationError(TawizaException):
    """Validation errors."""
    pass


# ============================================================================
# System Initialization Exceptions
# ============================================================================

class SystemNotInitializedError(TawizaException):
    """Raised when system operations are attempted before initialization."""

    def __init__(self, operation: str | None = None):
        message = "System not initialized"
        if operation:
            message += f" - cannot perform operation: {operation}"
        super().__init__(message)


class SystemAlreadyInitializedError(TawizaException):
    """Raised when attempting to initialize an already-initialized system."""

    def __init__(self):
        super().__init__(
            "System is already initialized. Use force=True to reinitialize."
        )


class SystemInitializationError(TawizaException):
    """Raised when system initialization fails."""
    pass


# ============================================================================
# System Requirements Exceptions
# ============================================================================

class SystemRequirementError(TawizaException):
    """Base exception for system requirement failures."""
    pass


class PythonVersionError(SystemRequirementError):
    """Raised when Python version requirement is not met."""

    def __init__(self, current_version: tuple, required_version: tuple):
        current = ".".join(map(str, current_version))
        required = ".".join(map(str, required_version))
        super().__init__(
            f"Python {required}+ required, but {current} detected",
            details={
                "current_version": current_version,
                "required_version": required_version
            }
        )


class DockerNotAvailableError(SystemRequirementError):
    """Raised when Docker is required but not available."""

    def __init__(self, reason: str | None = None):
        message = "Docker is not available or not functional"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class GPUNotAvailableError(SystemRequirementError):
    """Raised when GPU is required but not available."""

    def __init__(self, reason: str | None = None):
        message = "GPU is not available or not detected"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class ROCmNotInstalledError(GPUNotAvailableError):
    """Raised when ROCm is required but not installed."""

    def __init__(self):
        super().__init__("ROCm is not installed or not in PATH")


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationNotFoundError(TawizaConfigurationError):
    """Raised when configuration file is not found."""

    def __init__(self, config_path: str):
        super().__init__(
            f"Configuration file not found: {config_path}",
            details={"config_path": config_path}
        )


class ConfigurationCorruptedError(TawizaConfigurationError):
    """Raised when configuration file is corrupted or invalid."""

    def __init__(self, config_path: str, reason: str):
        super().__init__(
            f"Configuration file corrupted: {config_path} - {reason}",
            details={"config_path": config_path, "reason": reason}
        )


class InvalidConfigurationError(TawizaConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, field: str, value: any, reason: str):
        super().__init__(
            f"Invalid configuration for '{field}': {reason}",
            details={"field": field, "value": value, "reason": reason}
        )


# ============================================================================
# Agent Exceptions
# ============================================================================

class AgentError(TawizaException):
    """Base exception for agent-related errors."""
    pass


class AgentNotAvailableError(AgentError):
    """Raised when an agent is not available."""

    def __init__(self, agent_type: str):
        super().__init__(
            f"Agent not available: {agent_type}",
            details={"agent_type": agent_type}
        )


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""

    def __init__(self, agent_type: str, task_id: str, reason: str):
        super().__init__(
            f"Agent execution failed: {agent_type} (task: {task_id}) - {reason}",
            details={
                "agent_type": agent_type,
                "task_id": task_id,
                "reason": reason
            }
        )


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""

    def __init__(self, agent_type: str, task_id: str, timeout: int):
        super().__init__(
            f"Agent execution timeout: {agent_type} (task: {task_id}) "
            f"exceeded {timeout}s",
            details={
                "agent_type": agent_type,
                "task_id": task_id,
                "timeout": timeout
            }
        )


# ============================================================================
# Task Exceptions
# ============================================================================

class TaskError(TawizaException):
    """Base exception for task-related errors."""
    pass


class TaskNotFoundError(TaskError):
    """Raised when a task is not found."""

    def __init__(self, task_id: str):
        super().__init__(
            f"Task not found: {task_id}",
            details={"task_id": task_id}
        )


class TaskNotCompletedError(TaskError):
    """Raised when trying to get results from incomplete task."""

    def __init__(self, task_id: str, current_status: str):
        super().__init__(
            f"Task {task_id} is {current_status}, not completed",
            details={"task_id": task_id, "status": current_status}
        )


class TaskNotCancellableError(TaskError):
    """Raised when trying to cancel a non-cancellable task."""

    def __init__(self, task_id: str, current_status: str):
        super().__init__(
            f"Cannot cancel task {task_id} with status {current_status}",
            details={"task_id": task_id, "status": current_status}
        )


class TaskAlreadyRunningError(TaskError):
    """Raised when trying to start an already-running task."""

    def __init__(self, task_id: str):
        super().__init__(
            f"Task is already running: {task_id}",
            details={"task_id": task_id}
        )


# ============================================================================
# Resource Exceptions
# ============================================================================

class ResourceExhaustedError(TawizaResourceError):
    """Raised when system resources are exhausted."""

    def __init__(self, resource_type: str, usage: float, limit: float):
        super().__init__(
            f"Resource exhausted: {resource_type} "
            f"({usage:.1f}% used, limit: {limit:.1f}%)",
            details={
                "resource_type": resource_type,
                "usage": usage,
                "limit": limit
            }
        )


class MemoryExhaustedError(ResourceExhaustedError):
    """Raised when memory is exhausted."""

    def __init__(self, usage: float, limit: float):
        super().__init__("memory", usage, limit)


class DiskSpaceExhaustedError(ResourceExhaustedError):
    """Raised when disk space is exhausted."""

    def __init__(self, usage: float, limit: float):
        super().__init__("disk", usage, limit)


# ============================================================================
# Security Exceptions
# ============================================================================

class SecurityError(TawizaException):
    """Base exception for security-related errors."""
    pass


class InsecureConfigurationError(SecurityError):
    """Raised when insecure configuration is detected."""

    def __init__(self, issue: str):
        super().__init__(
            f"Insecure configuration detected: {issue}",
            details={"issue": issue}
        )


class PathTraversalError(SecurityError):
    """Raised when path traversal attack is detected."""

    def __init__(self, attempted_path: str):
        super().__init__(
            f"Path traversal detected: {attempted_path}",
            details={"attempted_path": attempted_path}
        )


class CommandInjectionError(SecurityError):
    """Raised when command injection is detected."""

    def __init__(self, attempted_command: str):
        super().__init__(
            f"Command injection detected: {attempted_command}",
            details={"attempted_command": attempted_command}
        )


# ============================================================================
# Debugging Exceptions
# ============================================================================

class DebugError(TawizaException):
    """Base exception for debugging-related errors."""
    pass


class DebuggerNotStartedError(DebugError):
    """Raised when debugger operations are attempted before starting."""

    def __init__(self):
        super().__init__("Debugger not started. Use 'tawiza debug start' first.")


class DebuggerAlreadyRunningError(DebugError):
    """Raised when trying to start an already-running debugger."""

    def __init__(self):
        super().__init__("Debugger is already running.")


# ============================================================================
# External Service Exceptions
# ============================================================================

class ExternalServiceError(TawizaException):
    """Base exception for external service errors."""
    pass


class ServiceUnavailableError(ExternalServiceError):
    """Raised when an external service is unavailable."""

    def __init__(self, service_name: str, reason: str | None = None):
        message = f"Service unavailable: {service_name}"
        if reason:
            message += f" - {reason}"
        super().__init__(
            message,
            details={"service": service_name, "reason": reason}
        )


class ServiceTimeoutError(ExternalServiceError):
    """Raised when external service request times out."""

    def __init__(self, service_name: str, timeout: int):
        super().__init__(
            f"Service timeout: {service_name} (exceeded {timeout}s)",
            details={"service": service_name, "timeout": timeout}
        )


class OllamaServiceError(ExternalServiceError):
    """Raised when Ollama service encounters an error."""

    def __init__(self, reason: str):
        super().__init__(
            f"Ollama service error: {reason}",
            details={"service": "ollama", "reason": reason}
        )


class MLflowServiceError(ExternalServiceError):
    """Raised when MLflow service encounters an error."""

    def __init__(self, reason: str):
        super().__init__(
            f"MLflow service error: {reason}",
            details={"service": "mlflow", "reason": reason}
        )


# ============================================================================
# Model Exceptions
# ============================================================================

class ModelError(TawizaException):
    """Base exception for model-related errors."""
    pass


class ModelNotFoundError(ModelError):
    """Raised when a model is not found."""

    def __init__(self, model_name: str):
        super().__init__(
            f"Model not found: {model_name}",
            details={"model_name": model_name}
        )


class ModelLoadError(ModelError):
    """Raised when model loading fails."""

    def __init__(self, model_name: str, reason: str):
        super().__init__(
            f"Failed to load model {model_name}: {reason}",
            details={"model_name": model_name, "reason": reason}
        )


# ============================================================================
# Convenience Functions
# ============================================================================

def require_system_initialized(state_manager: any) -> None:
    """Helper to check if system is initialized, raise if not.

    Args:
        state_manager: SystemStateManager instance

    Raises:
        SystemNotInitializedError: If system is not initialized
    """
    if not state_manager.is_initialized():
        raise SystemNotInitializedError()


def require_debugger_started(debugger: any) -> None:
    """Helper to check if debugger is started, raise if not.

    Args:
        debugger: Debugger instance

    Raises:
        DebuggerNotStartedError: If debugger is not started
    """
    if debugger is None:
        raise DebuggerNotStartedError()
