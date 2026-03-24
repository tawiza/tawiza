"""Tests for core exceptions hierarchy.

This module tests:
- Base TawizaException
- System initialization exceptions
- Configuration exceptions
- Agent exceptions
- Task exceptions
- Resource exceptions
- Security exceptions
- External service exceptions
- Model exceptions
- Convenience functions
"""

import pytest

from src.core.exceptions import (
    # Agents
    AgentError,
    AgentExecutionError,
    AgentNotAvailableError,
    AgentTimeoutError,
    CommandInjectionError,
    ConfigurationCorruptedError,
    # Configuration
    ConfigurationNotFoundError,
    # Debugging
    DebugError,
    DebuggerAlreadyRunningError,
    DebuggerNotStartedError,
    DiskSpaceExhaustedError,
    DockerNotAvailableError,
    # External Services
    ExternalServiceError,
    GPUNotAvailableError,
    InsecureConfigurationError,
    InvalidConfigurationError,
    MemoryExhaustedError,
    MLflowServiceError,
    # Models
    ModelError,
    ModelLoadError,
    ModelNotFoundError,
    TawizaConfigurationError,
    # Base
    TawizaException,
    TawizaResourceError,
    TawizaValidationError,
    OllamaServiceError,
    PathTraversalError,
    PythonVersionError,
    # Resources
    ResourceExhaustedError,
    ROCmNotInstalledError,
    # Security
    SecurityError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    SystemAlreadyInitializedError,
    SystemInitializationError,
    # System
    SystemNotInitializedError,
    # Requirements
    SystemRequirementError,
    TaskAlreadyRunningError,
    # Tasks
    TaskError,
    TaskNotCancellableError,
    TaskNotCompletedError,
    TaskNotFoundError,
    require_debugger_started,
    # Convenience
    require_system_initialized,
)


class TestTawizaException:
    """Test suite for base TawizaException."""

    def test_basic_creation(self):
        """Should create exception with message."""
        exc = TawizaException("Something went wrong")

        assert exc.message == "Something went wrong"
        assert str(exc) == "Something went wrong"

    def test_creation_with_details(self):
        """Should create exception with details."""
        exc = TawizaException("Error", details={"key": "value"})

        assert exc.details["key"] == "value"

    def test_default_details_empty(self):
        """Default details should be empty dict."""
        exc = TawizaException("Error")

        assert exc.details == {}

    def test_is_exception(self):
        """Should be a valid Exception."""
        exc = TawizaException("Test")

        assert isinstance(exc, Exception)

    def test_can_be_raised(self):
        """Should be raisable."""
        with pytest.raises(TawizaException):
            raise TawizaException("Test error")


class TestSystemInitializationExceptions:
    """Test suite for system initialization exceptions."""

    def test_system_not_initialized_default(self):
        """SystemNotInitializedError should have default message."""
        exc = SystemNotInitializedError()

        assert "not initialized" in exc.message.lower()

    def test_system_not_initialized_with_operation(self):
        """SystemNotInitializedError should include operation."""
        exc = SystemNotInitializedError("start_agent")

        assert "start_agent" in exc.message

    def test_system_already_initialized(self):
        """SystemAlreadyInitializedError should mention force=True."""
        exc = SystemAlreadyInitializedError()

        assert "force=True" in exc.message

    def test_system_initialization_error(self):
        """SystemInitializationError should be creatable."""
        exc = SystemInitializationError("Failed to init", details={"stage": "gpu"})

        assert "Failed to init" in exc.message
        assert exc.details["stage"] == "gpu"


class TestSystemRequirementExceptions:
    """Test suite for system requirement exceptions."""

    def test_python_version_error(self):
        """PythonVersionError should include version info."""
        exc = PythonVersionError(
            current_version=(3, 8, 10),
            required_version=(3, 10, 0),
        )

        assert "3.8" in exc.message
        assert "3.10" in exc.message
        assert exc.details["current_version"] == (3, 8, 10)
        assert exc.details["required_version"] == (3, 10, 0)

    def test_docker_not_available_default(self):
        """DockerNotAvailableError should have default message."""
        exc = DockerNotAvailableError()

        assert "Docker" in exc.message

    def test_docker_not_available_with_reason(self):
        """DockerNotAvailableError should include reason."""
        exc = DockerNotAvailableError("daemon not running")

        assert "daemon not running" in exc.message

    def test_gpu_not_available_default(self):
        """GPUNotAvailableError should have default message."""
        exc = GPUNotAvailableError()

        assert "GPU" in exc.message

    def test_gpu_not_available_with_reason(self):
        """GPUNotAvailableError should include reason."""
        exc = GPUNotAvailableError("No compatible devices")

        assert "No compatible devices" in exc.message

    def test_rocm_not_installed(self):
        """ROCmNotInstalledError should mention ROCm."""
        exc = ROCmNotInstalledError()

        assert "ROCm" in exc.message


class TestConfigurationExceptions:
    """Test suite for configuration exceptions."""

    def test_configuration_not_found(self):
        """ConfigurationNotFoundError should include path."""
        exc = ConfigurationNotFoundError("/path/to/config.yaml")

        assert "/path/to/config.yaml" in exc.message
        assert exc.details["config_path"] == "/path/to/config.yaml"

    def test_configuration_corrupted(self):
        """ConfigurationCorruptedError should include path and reason."""
        exc = ConfigurationCorruptedError(
            "/path/to/config.yaml",
            "Invalid YAML syntax",
        )

        assert "/path/to/config.yaml" in exc.message
        assert "Invalid YAML syntax" in exc.message

    def test_invalid_configuration(self):
        """InvalidConfigurationError should include field info."""
        exc = InvalidConfigurationError(
            field="port",
            value=-1,
            reason="must be positive",
        )

        assert "port" in exc.message
        assert exc.details["field"] == "port"
        assert exc.details["value"] == -1


class TestAgentExceptions:
    """Test suite for agent exceptions."""

    def test_agent_not_available(self):
        """AgentNotAvailableError should include agent type."""
        exc = AgentNotAvailableError("BrowserAgent")

        assert "BrowserAgent" in exc.message
        assert exc.details["agent_type"] == "BrowserAgent"

    def test_agent_execution_error(self):
        """AgentExecutionError should include all info."""
        exc = AgentExecutionError(
            agent_type="DataAnalyst",
            task_id="task-123",
            reason="Out of memory",
        )

        assert "DataAnalyst" in exc.message
        assert "task-123" in exc.message
        assert "Out of memory" in exc.message
        assert exc.details["task_id"] == "task-123"

    def test_agent_timeout_error(self):
        """AgentTimeoutError should include timeout info."""
        exc = AgentTimeoutError(
            agent_type="CodeGenerator",
            task_id="task-456",
            timeout=300,
        )

        assert "CodeGenerator" in exc.message
        assert "300" in exc.message
        assert exc.details["timeout"] == 300


class TestTaskExceptions:
    """Test suite for task exceptions."""

    def test_task_not_found(self):
        """TaskNotFoundError should include task ID."""
        exc = TaskNotFoundError("task-abc")

        assert "task-abc" in exc.message
        assert exc.details["task_id"] == "task-abc"

    def test_task_not_completed(self):
        """TaskNotCompletedError should include status."""
        exc = TaskNotCompletedError("task-def", "running")

        assert "task-def" in exc.message
        assert "running" in exc.message
        assert exc.details["status"] == "running"

    def test_task_not_cancellable(self):
        """TaskNotCancellableError should include status."""
        exc = TaskNotCancellableError("task-ghi", "completed")

        assert "task-ghi" in exc.message
        assert "completed" in exc.message

    def test_task_already_running(self):
        """TaskAlreadyRunningError should include task ID."""
        exc = TaskAlreadyRunningError("task-jkl")

        assert "task-jkl" in exc.message
        assert "already running" in exc.message.lower()


class TestResourceExceptions:
    """Test suite for resource exceptions."""

    def test_resource_exhausted(self):
        """ResourceExhaustedError should include resource info."""
        exc = ResourceExhaustedError("cpu", 95.5, 80.0)

        assert "cpu" in exc.message
        assert "95.5" in exc.message
        assert exc.details["usage"] == 95.5
        assert exc.details["limit"] == 80.0

    def test_memory_exhausted(self):
        """MemoryExhaustedError should be ResourceExhaustedError."""
        exc = MemoryExhaustedError(92.0, 85.0)

        assert isinstance(exc, ResourceExhaustedError)
        assert "memory" in exc.message.lower()

    def test_disk_space_exhausted(self):
        """DiskSpaceExhaustedError should be ResourceExhaustedError."""
        exc = DiskSpaceExhaustedError(98.0, 90.0)

        assert isinstance(exc, ResourceExhaustedError)
        assert "disk" in exc.message.lower()


class TestSecurityExceptions:
    """Test suite for security exceptions."""

    def test_insecure_configuration(self):
        """InsecureConfigurationError should include issue."""
        exc = InsecureConfigurationError("SECRET_KEY not set in production")

        assert "SECRET_KEY" in exc.message
        assert exc.details["issue"] == "SECRET_KEY not set in production"

    def test_path_traversal(self):
        """PathTraversalError should include attempted path."""
        exc = PathTraversalError("../../../etc/passwd")

        assert "../../../etc/passwd" in exc.message
        assert exc.details["attempted_path"] == "../../../etc/passwd"

    def test_command_injection(self):
        """CommandInjectionError should include attempted command."""
        exc = CommandInjectionError("; rm -rf /")

        assert "; rm -rf /" in exc.message
        assert exc.details["attempted_command"] == "; rm -rf /"


class TestDebugExceptions:
    """Test suite for debugging exceptions."""

    def test_debugger_not_started(self):
        """DebuggerNotStartedError should mention how to start."""
        exc = DebuggerNotStartedError()

        assert "debug start" in exc.message.lower()

    def test_debugger_already_running(self):
        """DebuggerAlreadyRunningError should have appropriate message."""
        exc = DebuggerAlreadyRunningError()

        assert "already running" in exc.message.lower()


class TestExternalServiceExceptions:
    """Test suite for external service exceptions."""

    def test_service_unavailable_default(self):
        """ServiceUnavailableError should include service name."""
        exc = ServiceUnavailableError("Redis")

        assert "Redis" in exc.message
        assert exc.details["service"] == "Redis"

    def test_service_unavailable_with_reason(self):
        """ServiceUnavailableError should include reason."""
        exc = ServiceUnavailableError("Redis", "Connection refused")

        assert "Redis" in exc.message
        assert "Connection refused" in exc.message

    def test_service_timeout(self):
        """ServiceTimeoutError should include timeout."""
        exc = ServiceTimeoutError("MLflow", 30)

        assert "MLflow" in exc.message
        assert "30" in exc.message
        assert exc.details["timeout"] == 30

    def test_ollama_service_error(self):
        """OllamaServiceError should be ExternalServiceError."""
        exc = OllamaServiceError("Model not found")

        assert isinstance(exc, ExternalServiceError)
        assert "Ollama" in exc.message
        assert exc.details["service"] == "ollama"

    def test_mlflow_service_error(self):
        """MLflowServiceError should be ExternalServiceError."""
        exc = MLflowServiceError("Tracking server unreachable")

        assert isinstance(exc, ExternalServiceError)
        assert "MLflow" in exc.message
        assert exc.details["service"] == "mlflow"


class TestModelExceptions:
    """Test suite for model exceptions."""

    def test_model_not_found(self):
        """ModelNotFoundError should include model name."""
        exc = ModelNotFoundError("llama-7b")

        assert "llama-7b" in exc.message
        assert exc.details["model_name"] == "llama-7b"

    def test_model_load_error(self):
        """ModelLoadError should include name and reason."""
        exc = ModelLoadError("mistral-7b", "CUDA out of memory")

        assert "mistral-7b" in exc.message
        assert "CUDA out of memory" in exc.message
        assert exc.details["reason"] == "CUDA out of memory"


class TestExceptionHierarchy:
    """Test suite for exception class hierarchy."""

    def test_config_errors_inherit_from_base(self):
        """Configuration errors should inherit from TawizaException."""
        errors = [
            TawizaConfigurationError("test"),
            ConfigurationNotFoundError("/path"),
            ConfigurationCorruptedError("/path", "reason"),
            InvalidConfigurationError("field", "value", "reason"),
        ]

        for exc in errors:
            assert isinstance(exc, TawizaException)

    def test_resource_errors_inherit_from_base(self):
        """Resource errors should inherit from TawizaException."""
        errors = [
            TawizaResourceError("test"),
            ResourceExhaustedError("cpu", 90, 80),
            MemoryExhaustedError(90, 80),
            DiskSpaceExhaustedError(90, 80),
        ]

        for exc in errors:
            assert isinstance(exc, TawizaException)

    def test_agent_errors_inherit_from_base(self):
        """Agent errors should inherit from TawizaException."""
        errors = [
            AgentError("test"),
            AgentNotAvailableError("Agent"),
            AgentExecutionError("Agent", "task", "reason"),
            AgentTimeoutError("Agent", "task", 30),
        ]

        for exc in errors:
            assert isinstance(exc, TawizaException)

    def test_security_errors_inherit_from_base(self):
        """Security errors should inherit from TawizaException."""
        errors = [
            SecurityError("test"),
            InsecureConfigurationError("issue"),
            PathTraversalError("path"),
            CommandInjectionError("cmd"),
        ]

        for exc in errors:
            assert isinstance(exc, TawizaException)


class TestConvenienceFunctions:
    """Test suite for convenience functions."""

    def test_require_system_initialized_when_initialized(self):
        """Should not raise when system is initialized."""

        class MockManager:
            def is_initialized(self):
                return True

        # Should not raise
        require_system_initialized(MockManager())

    def test_require_system_initialized_when_not_initialized(self):
        """Should raise when system is not initialized."""

        class MockManager:
            def is_initialized(self):
                return False

        with pytest.raises(SystemNotInitializedError):
            require_system_initialized(MockManager())

    def test_require_debugger_started_when_started(self):
        """Should not raise when debugger is started."""

        class MockDebugger:
            pass

        # Should not raise
        require_debugger_started(MockDebugger())

    def test_require_debugger_started_when_not_started(self):
        """Should raise when debugger is None."""
        with pytest.raises(DebuggerNotStartedError):
            require_debugger_started(None)
