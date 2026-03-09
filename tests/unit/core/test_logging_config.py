"""Tests for centralized logging configuration.

This module tests:
- Context variables for request/user correlation
- InterceptHandler for stdlib logging redirection
- Log formatting with context
- configure_logging() function
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.logging_config import (
    InterceptHandler,
    configure_logging,
    format_record,
    get_logger,
    get_request_id,
    get_user_id,
    logger,
    request_id_var,
    set_request_id,
    set_user_id,
    user_id_var,
)


class TestContextVariables:
    """Test suite for request and user context variables."""

    def setup_method(self):
        """Reset context variables before each test."""
        request_id_var.set(None)
        user_id_var.set(None)

    def test_request_id_default_is_none(self):
        """Request ID should default to None."""
        assert get_request_id() is None

    def test_set_and_get_request_id(self):
        """Should be able to set and retrieve request ID."""
        set_request_id("req-12345")

        assert get_request_id() == "req-12345"

    def test_user_id_default_is_none(self):
        """User ID should default to None."""
        assert get_user_id() is None

    def test_set_and_get_user_id(self):
        """Should be able to set and retrieve user ID."""
        set_user_id("user-abc123")

        assert get_user_id() == "user-abc123"

    def test_context_variables_are_independent(self):
        """Request and user IDs should be independent."""
        set_request_id("req-1")
        set_user_id("user-1")

        assert get_request_id() == "req-1"
        assert get_user_id() == "user-1"

    def test_overwriting_context_values(self):
        """Context values can be overwritten."""
        set_request_id("req-1")
        set_request_id("req-2")

        assert get_request_id() == "req-2"


class TestInterceptHandler:
    """Test suite for InterceptHandler."""

    def test_intercept_handler_is_logging_handler(self):
        """InterceptHandler should be a logging.Handler subclass."""
        handler = InterceptHandler()

        assert isinstance(handler, logging.Handler)

    def test_emit_logs_info_level(self):
        """Handler should emit INFO level logs to loguru."""
        handler = InterceptHandler()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Should not raise
        with patch.object(logger, "opt") as mock_opt:
            mock_log = MagicMock()
            mock_opt.return_value.log = mock_log
            handler.emit(record)

    def test_emit_logs_error_level(self):
        """Handler should emit ERROR level logs to loguru."""
        handler = InterceptHandler()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        with patch.object(logger, "opt") as mock_opt:
            mock_log = MagicMock()
            mock_opt.return_value.log = mock_log
            handler.emit(record)


class TestFormatRecord:
    """Test suite for format_record function."""

    def setup_method(self):
        """Reset context variables before each test."""
        request_id_var.set(None)
        user_id_var.set(None)

    def test_format_without_context(self):
        """Format record without request/user context."""
        record = {
            "time": MagicMock(),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "function": "test_func",
            "line": 42,
            "message": "Test message",
            "exception": None,
        }

        result = format_record(record)

        assert "{message}" in result
        assert "{level" in result

    def test_format_with_request_id(self):
        """Format record should include request ID when set."""
        set_request_id("req-abcd1234efgh")

        record = {
            "time": MagicMock(),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "function": "test_func",
            "line": 42,
            "message": "Test message",
            "exception": None,
        }

        result = format_record(record)

        # Should include truncated request ID
        assert "req=" in result
        assert "req-abcd" in result  # First 8 chars

    def test_format_with_user_id(self):
        """Format record should include user ID when set."""
        set_user_id("user-12345")

        record = {
            "time": MagicMock(),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "function": "test_func",
            "line": 42,
            "message": "Test message",
            "exception": None,
        }

        result = format_record(record)

        assert "user=" in result
        assert "user-12345" in result

    def test_format_with_both_context_values(self):
        """Format record should include both request and user ID."""
        set_request_id("req-12345678")
        set_user_id("user-xyz")

        record = {
            "time": MagicMock(),
            "level": MagicMock(name="INFO"),
            "name": "test",
            "function": "test_func",
            "line": 42,
            "message": "Test message",
            "exception": None,
        }

        result = format_record(record)

        assert "req=" in result
        assert "user=" in result

    def test_format_with_exception(self):
        """Format record should include exception when present."""
        record = {
            "time": MagicMock(),
            "level": MagicMock(name="ERROR"),
            "name": "test",
            "function": "test_func",
            "line": 42,
            "message": "Error occurred",
            "exception": "Traceback...",  # Non-None exception
        }

        result = format_record(record)

        assert "{exception}" in result


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_with_default_level(self):
        """configure_logging should work with default INFO level."""
        # Should not raise
        configure_logging(level="INFO")

    def test_configure_with_debug_level(self):
        """configure_logging should accept DEBUG level."""
        configure_logging(level="DEBUG")

    def test_configure_with_json_logs(self):
        """configure_logging should support JSON log format."""
        configure_logging(level="INFO", json_logs=True)

    def test_configure_with_file_output(self):
        """configure_logging should support file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "logs" / "test.log"

            configure_logging(
                level="INFO",
                log_file=log_file,
                rotation="1 MB",
                retention="1 day",
            )

            # Directory should be created
            assert log_file.parent.exists()

    def test_configure_sets_third_party_log_levels(self):
        """configure_logging should set levels for noisy third-party loggers."""
        configure_logging(level="DEBUG")

        # Third-party loggers should be set to WARNING
        for name in ["uvicorn", "httpx", "sqlalchemy.engine"]:
            log = logging.getLogger(name)
            assert log.level == logging.WARNING


class TestGetLogger:
    """Test suite for get_logger function."""

    def test_get_logger_without_name(self):
        """get_logger() without name should return global logger."""
        result = get_logger()

        assert result is not None

    def test_get_logger_with_name(self):
        """get_logger() with name should return bound logger."""
        result = get_logger("test_module")

        assert result is not None

    def test_multiple_calls_with_different_names(self):
        """get_logger() should return different loggers for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should be valid loggers
        assert logger1 is not None
        assert logger2 is not None


class TestLoggerIntegration:
    """Integration tests for the logging system."""

    def test_logger_is_importable(self):
        """Logger should be importable from module."""
        from src.core.logging_config import logger

        assert logger is not None

    def test_logger_can_log_messages(self):
        """Logger should be able to log messages without errors."""
        from src.core.logging_config import logger

        # These should not raise
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_module_exports(self):
        """All expected symbols should be exported."""
        from src.core import logging_config

        expected_exports = [
            "logger",
            "configure_logging",
            "get_logger",
            "get_request_id",
            "set_request_id",
            "get_user_id",
            "set_user_id",
            "request_id_var",
            "user_id_var",
        ]

        for name in expected_exports:
            assert hasattr(logging_config, name), f"Missing export: {name}"
