"""Tests for CLI error handling module.

This module tests:
- Error codes and severity levels
- ErrorInfo dataclass
- TawizaError exception hierarchy
- ErrorHandler display and logging
- Decorators (handle_errors, retry_on_error)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.cli.errors import (
    AgentError,
    AgentNotFoundError,
    ConfigError,
    ConfigNotFoundError,
    ConnectionError,
    # Error codes and severity
    ErrorCode,
    # Handler
    ErrorHandler,
    # Error info
    ErrorInfo,
    ErrorSeverity,
    FileError,
    GPUError,
    GPUNotAvailableError,
    InvalidPathError,
    # Exception hierarchy
    TawizaError,
    NetworkError,
    PathTraversalError,
    ServiceUnavailableError,
    SystemAlreadyInitializedError,
    SystemError,
    SystemNotInitializedError,
    get_error_handler,
    # Decorators
    handle_errors,
    retry_on_error,
)


class TestErrorCode:
    """Test suite for ErrorCode enum."""

    def test_error_codes_are_strings(self):
        """Error codes should be string-based enum values."""
        assert ErrorCode.UNKNOWN.value == "E1000"
        assert ErrorCode.INVALID_INPUT.value == "E1001"
        assert ErrorCode.TIMEOUT.value == "E1003"

    def test_config_error_codes(self):
        """Configuration error codes should be in 1100 range."""
        assert ErrorCode.CONFIG_LOAD_FAILED.value == "E1100"
        assert ErrorCode.CONFIG_NOT_FOUND.value == "E1103"

    def test_system_error_codes(self):
        """System error codes should be in 1200 range."""
        assert ErrorCode.SYSTEM_NOT_INITIALIZED.value == "E1200"
        assert ErrorCode.SYSTEM_INIT_FAILED.value == "E1202"

    def test_gpu_error_codes(self):
        """GPU error codes should be in 1300 range."""
        assert ErrorCode.GPU_NOT_AVAILABLE.value == "E1300"
        assert ErrorCode.GPU_MEMORY_ERROR.value == "E1302"

    def test_network_error_codes(self):
        """Network error codes should be in 1400 range."""
        assert ErrorCode.CONNECTION_FAILED.value == "E1400"
        assert ErrorCode.SERVICE_UNAVAILABLE.value == "E1401"

    def test_agent_error_codes(self):
        """Agent error codes should be in 1500 range."""
        assert ErrorCode.AGENT_START_FAILED.value == "E1500"
        assert ErrorCode.AGENT_NOT_FOUND.value == "E1503"

    def test_model_error_codes(self):
        """Model error codes should be in 1600 range."""
        assert ErrorCode.MODEL_NOT_FOUND.value == "E1600"
        assert ErrorCode.INFERENCE_FAILED.value == "E1602"

    def test_file_error_codes(self):
        """File error codes should be in 1700 range."""
        assert ErrorCode.FILE_NOT_FOUND.value == "E1700"
        assert ErrorCode.PATH_TRAVERSAL.value == "E1703"


class TestErrorSeverity:
    """Test suite for ErrorSeverity enum."""

    def test_severity_levels(self):
        """Should have standard severity levels."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestErrorInfo:
    """Test suite for ErrorInfo dataclass."""

    def test_basic_creation(self):
        """ErrorInfo should be created with required fields."""
        info = ErrorInfo(
            code=ErrorCode.UNKNOWN,
            message="Test error",
        )

        assert info.code == ErrorCode.UNKNOWN
        assert info.message == "Test error"
        assert info.severity == ErrorSeverity.MEDIUM  # Default
        assert info.details == {}
        assert info.suggestions == []
        assert info.exception is None
        assert isinstance(info.timestamp, datetime)

    def test_creation_with_all_fields(self):
        """ErrorInfo should accept all optional fields."""
        exc = ValueError("test")
        info = ErrorInfo(
            code=ErrorCode.INVALID_INPUT,
            message="Invalid value",
            severity=ErrorSeverity.HIGH,
            details={"field": "name", "value": ""},
            suggestions=["Provide a non-empty name"],
            exception=exc,
        )

        assert info.severity == ErrorSeverity.HIGH
        assert info.details["field"] == "name"
        assert len(info.suggestions) == 1
        assert info.exception is exc

    def test_to_dict(self):
        """ErrorInfo should convert to dictionary."""
        info = ErrorInfo(
            code=ErrorCode.TIMEOUT,
            message="Operation timed out",
            details={"timeout": 30},
        )

        result = info.to_dict()

        assert result["code"] == "E1003"
        assert result["message"] == "Operation timed out"
        assert result["severity"] == "medium"
        assert result["details"]["timeout"] == 30
        assert "timestamp" in result


class TestTawizaError:
    """Test suite for TawizaError base exception."""

    def test_basic_creation(self):
        """TawizaError should be created with message."""
        error = TawizaError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.code == ErrorCode.UNKNOWN
        assert error.severity == ErrorSeverity.MEDIUM

    def test_creation_with_code(self):
        """TawizaError should accept custom error code."""
        error = TawizaError(
            "Connection failed",
            code=ErrorCode.CONNECTION_FAILED,
        )

        assert error.code == ErrorCode.CONNECTION_FAILED

    def test_creation_with_severity(self):
        """TawizaError should accept custom severity."""
        error = TawizaError(
            "Critical failure",
            severity=ErrorSeverity.CRITICAL,
        )

        assert error.severity == ErrorSeverity.CRITICAL

    def test_creation_with_details(self):
        """TawizaError should accept details dictionary."""
        error = TawizaError(
            "File error",
            details={"path": "/tmp/file.txt"},
        )

        assert error.info.details["path"] == "/tmp/file.txt"

    def test_creation_with_suggestions(self):
        """TawizaError should accept suggestions list."""
        error = TawizaError(
            "Config missing",
            suggestions=["Run init first"],
        )

        assert "Run init first" in error.info.suggestions

    def test_is_exception(self):
        """TawizaError should be a valid Exception."""
        error = TawizaError("Test")

        assert isinstance(error, Exception)

        with pytest.raises(TawizaError):
            raise error


class TestConfigErrors:
    """Test suite for configuration errors."""

    def test_config_error(self):
        """ConfigError should have config error code."""
        error = ConfigError("Invalid config")

        assert error.code == ErrorCode.CONFIG_VALIDATION_FAILED

    def test_config_not_found_error(self):
        """ConfigNotFoundError should include path and suggestions."""
        error = ConfigNotFoundError("/path/to/config.yaml")

        assert error.code == ErrorCode.CONFIG_NOT_FOUND
        assert "/path/to/config.yaml" in str(error)
        assert len(error.info.suggestions) > 0


class TestSystemErrors:
    """Test suite for system errors."""

    def test_system_not_initialized_error(self):
        """SystemNotInitializedError should have appropriate code and severity."""
        error = SystemNotInitializedError()

        assert error.code == ErrorCode.SYSTEM_NOT_INITIALIZED
        assert error.severity == ErrorSeverity.HIGH
        assert len(error.info.suggestions) > 0

    def test_system_already_initialized_error(self):
        """SystemAlreadyInitializedError should mention --force."""
        error = SystemAlreadyInitializedError()

        assert error.code == ErrorCode.SYSTEM_ALREADY_INITIALIZED
        assert "--force" in str(error.info.suggestions)


class TestGPUErrors:
    """Test suite for GPU errors."""

    def test_gpu_not_available_error_default(self):
        """GPUNotAvailableError should have default message."""
        error = GPUNotAvailableError()

        assert error.code == ErrorCode.GPU_NOT_AVAILABLE
        assert "GPU" in str(error)

    def test_gpu_not_available_error_with_reason(self):
        """GPUNotAvailableError should include reason."""
        error = GPUNotAvailableError("No ROCm drivers")

        assert "No ROCm drivers" in str(error)


class TestNetworkErrors:
    """Test suite for network errors."""

    def test_service_unavailable_error(self):
        """ServiceUnavailableError should include service and URL."""
        error = ServiceUnavailableError("Ollama", "http://localhost:11434")

        assert error.code == ErrorCode.SERVICE_UNAVAILABLE
        assert error.info.details["service"] == "Ollama"
        assert error.info.details["url"] == "http://localhost:11434"

    def test_connection_error(self):
        """ConnectionError should include URL."""
        error = ConnectionError("http://api.example.com", "Connection refused")

        assert error.code == ErrorCode.CONNECTION_FAILED
        assert "http://api.example.com" in str(error)
        assert "Connection refused" in str(error)


class TestAgentErrors:
    """Test suite for agent errors."""

    def test_agent_not_found_error(self):
        """AgentNotFoundError should include agent name."""
        error = AgentNotFoundError("data_analyst")

        assert error.code == ErrorCode.AGENT_NOT_FOUND
        assert error.info.details["agent"] == "data_analyst"


class TestFileErrors:
    """Test suite for file errors."""

    def test_path_traversal_error(self):
        """PathTraversalError should have high severity."""
        error = PathTraversalError("../../../etc/passwd")

        assert error.code == ErrorCode.PATH_TRAVERSAL
        assert error.severity == ErrorSeverity.HIGH

    def test_invalid_path_error(self):
        """InvalidPathError should include path and reason."""
        error = InvalidPathError("/invalid/path", "Contains illegal characters")

        assert error.code == ErrorCode.INVALID_PATH
        assert "/invalid/path" in str(error)


class TestErrorHandler:
    """Test suite for ErrorHandler."""

    def test_initialization(self):
        """ErrorHandler should initialize with empty history."""
        handler = ErrorHandler()

        assert handler.get_history() == []

    def test_handle_tawiza_error(self):
        """Should handle TawizaError correctly."""
        handler = ErrorHandler()
        error = TawizaError("Test error", code=ErrorCode.UNKNOWN)

        with patch.object(handler, "_display_error"):
            handler.handle(error, exit_on_critical=False)

        history = handler.get_history()
        assert len(history) == 1
        assert history[0].code == ErrorCode.UNKNOWN

    def test_handle_error_info(self):
        """Should handle ErrorInfo directly."""
        handler = ErrorHandler()
        info = ErrorInfo(
            code=ErrorCode.TIMEOUT,
            message="Timeout occurred",
        )

        with patch.object(handler, "_display_error"):
            handler.handle(info, exit_on_critical=False)

        history = handler.get_history()
        assert len(history) == 1
        assert history[0].code == ErrorCode.TIMEOUT

    def test_handle_generic_exception(self):
        """Should wrap generic exceptions."""
        handler = ErrorHandler()
        error = ValueError("Invalid value")

        with patch.object(handler, "_display_error"):
            handler.handle(error, exit_on_critical=False)

        history = handler.get_history()
        assert len(history) == 1
        assert history[0].code == ErrorCode.UNKNOWN

    def test_clear_history(self):
        """Should clear error history."""
        handler = ErrorHandler()
        handler._error_history.append(ErrorInfo(code=ErrorCode.UNKNOWN, message="Test"))

        handler.clear_history()

        assert handler.get_history() == []


class TestGetErrorHandler:
    """Test suite for get_error_handler function."""

    def test_returns_handler(self):
        """get_error_handler should return an ErrorHandler instance."""
        handler = get_error_handler()

        assert isinstance(handler, ErrorHandler)

    def test_singleton_pattern(self):
        """get_error_handler should return the same instance."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()

        assert handler1 is handler2


class TestRetryOnErrorDecorator:
    """Test suite for retry_on_error decorator."""

    def test_no_retry_on_success(self):
        """Should not retry when function succeeds."""
        call_count = 0

        @retry_on_error(max_retries=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Should retry on failure."""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = failing_func()

        assert result == "success"
        assert call_count == 3

    def test_exhaust_retries(self):
        """Should raise after exhausting retries."""
        call_count = 0

        @retry_on_error(max_retries=2, delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries


class TestExceptionHierarchy:
    """Test suite for exception class hierarchy."""

    def test_config_errors_inherit_from_tawiza_error(self):
        """Config errors should inherit from TawizaError."""
        errors = [
            ConfigError("test"),
            ConfigNotFoundError("/path"),
        ]

        for error in errors:
            assert isinstance(error, TawizaError)
            assert isinstance(error, Exception)

    def test_system_errors_inherit_from_tawiza_error(self):
        """System errors should inherit from TawizaError."""
        errors = [
            SystemError("test"),
            SystemNotInitializedError(),
            SystemAlreadyInitializedError(),
        ]

        for error in errors:
            assert isinstance(error, TawizaError)

    def test_network_errors_inherit_from_tawiza_error(self):
        """Network errors should inherit from TawizaError."""
        errors = [
            NetworkError("test"),
            ServiceUnavailableError("svc", "url"),
            ConnectionError("url"),
        ]

        for error in errors:
            assert isinstance(error, TawizaError)

    def test_gpu_errors_inherit_from_tawiza_error(self):
        """GPU errors should inherit from TawizaError."""
        error = GPUNotAvailableError()

        assert isinstance(error, GPUError)
        assert isinstance(error, TawizaError)

    def test_agent_errors_inherit_from_tawiza_error(self):
        """Agent errors should inherit from TawizaError."""
        error = AgentNotFoundError("agent")

        assert isinstance(error, AgentError)
        assert isinstance(error, TawizaError)

    def test_file_errors_inherit_from_tawiza_error(self):
        """File errors should inherit from TawizaError."""
        errors = [
            FileError("test"),
            PathTraversalError("path"),
            InvalidPathError("path"),
        ]

        for error in errors:
            assert isinstance(error, TawizaError)
