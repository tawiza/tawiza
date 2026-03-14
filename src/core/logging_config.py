"""Centralized Logging Configuration.

This module provides a unified logging setup using loguru.
All modules should import logger from here instead of using stdlib logging.

Usage:
    from src.core.logging_config import logger

    logger.info("Message")
    logger.debug("Debug info", extra={"user_id": 123})
    logger.error("Error occurred", exc_info=True)

Features:
- Structured logging with JSON output option
- Request ID correlation
- Environment-based log levels
- Log rotation and retention
- Integration with stdlib logging for third-party libs
"""

import logging
import sys
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

# Context variable for request correlation
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context."""
    request_id_var.set(request_id)


def get_user_id() -> str | None:
    """Get current user ID from context."""
    return user_id_var.get()


def set_user_id(user_id: str) -> None:
    """Set user ID in context."""
    user_id_var.set(user_id)


class InterceptHandler(logging.Handler):
    """Intercept stdlib logging and redirect to loguru.

    This ensures third-party libraries using stdlib logging
    are also captured by loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def format_record(record: dict) -> str:
    """Custom format for log records with context."""
    # Add context info
    request_id = get_request_id()
    user_id = get_user_id()

    extra_parts = []
    if request_id:
        extra_parts.append(f"req={request_id[:8]}")
    if user_id:
        extra_parts.append(f"user={user_id}")

    extra_str = f" [{' '.join(extra_parts)}]" if extra_parts else ""

    # Format: TIME | LEVEL | MODULE:LINE | MESSAGE
    format_str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        f"{extra_str} - "
        "<level>{message}</level>\n"
    )

    if record["exception"]:
        format_str += "{exception}\n"

    return format_str


def configure_logging(
    level: str = "INFO",
    json_logs: bool = False,
    log_file: Path | None = None,
    rotation: str = "10 MB",
    retention: str = "1 week",
) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Output logs as JSON (for production)
        log_file: Optional file path for log output
        rotation: When to rotate log files
        retention: How long to keep old log files
    """
    # Remove default handler
    logger.remove()

    # Console handler
    if json_logs:
        logger.add(
            sys.stderr,
            level=level,
            format="{message}",
            serialize=True,  # JSON output
        )
    else:
        logger.add(
            sys.stderr,
            level=level,
            format=format_record,
            colorize=True,
        )

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            level=level,
            format=format_record if not json_logs else "{message}",
            serialize=json_logs,
            rotation=rotation,
            retention=retention,
            compression="gz",
        )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set levels for noisy third-party loggers
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "httpx",
        "httpcore",
        "sqlalchemy.engine",
        "playwright",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logger.info(f"Logging configured: level={level}, json={json_logs}")


def get_logger(name: str = None):
    """Get a logger instance.

    This is provided for compatibility but the global logger is preferred.

    Args:
        name: Optional logger name (for filtering)

    Returns:
        Logger instance bound with the name
    """
    if name:
        return logger.bind(name=name)
    return logger


# Configure with defaults on import
# Can be reconfigured by calling configure_logging() explicitly
configure_logging(level="INFO")

# Export the configured logger
__all__ = [
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
