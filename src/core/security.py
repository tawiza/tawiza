"""Security utilities for Tawiza-V2.

This module provides security functions to prevent common vulnerabilities:
- Command injection
- Path traversal
- Hardcoded secrets
- Input validation
"""

import os
import re
import secrets
from pathlib import Path
from typing import Any

from loguru import logger

from src.core.constants import (
    APP_ENV_VAR,
    PRODUCTION_ENV,
    SECRET_KEY_ENV_VAR,
    SECRET_KEY_MIN_LENGTH,
)
from src.core.exceptions import (
    CommandInjectionError,
    InsecureConfigurationError,
    PathTraversalError,
)

# ============================================================================
# Secret Management
# ============================================================================


class SecretManager:
    """Secure secret key management.

    Prevents hardcoded secrets by enforcing environment-based configuration.
    """

    @staticmethod
    def get_secret_key() -> str:
        """Get secret key from environment or generate for development.

        Returns:
            Secret key string

        Raises:
            InsecureConfigurationError: If running in production without SECRET_KEY

        Example:
            >>> key = SecretManager.get_secret_key()
            >>> assert len(key) >= 32
        """
        key = os.getenv(SECRET_KEY_ENV_VAR)

        # In production, SECRET_KEY MUST be set
        if os.getenv(APP_ENV_VAR) == PRODUCTION_ENV:
            if not key:
                raise InsecureConfigurationError(
                    f"{SECRET_KEY_ENV_VAR} must be set in production environment"
                )
            if len(key) < SECRET_KEY_MIN_LENGTH:
                raise InsecureConfigurationError(
                    f"{SECRET_KEY_ENV_VAR} must be at least {SECRET_KEY_MIN_LENGTH} characters"
                )

        # In development, generate a secure random key if not set
        if not key:
            logger.warning(
                f"{SECRET_KEY_ENV_VAR} not set, generating temporary key for development"
            )
            key = secrets.token_urlsafe(SECRET_KEY_MIN_LENGTH)

        return key

    @staticmethod
    def generate_secret_key() -> str:
        """Generate a cryptographically secure secret key.

        Returns:
            URL-safe base64 encoded secret key

        Example:
            >>> key = SecretManager.generate_secret_key()
            >>> assert len(key) >= 32
        """
        return secrets.token_urlsafe(SECRET_KEY_MIN_LENGTH)

    @staticmethod
    def validate_secret_key(key: str) -> bool:
        """Validate secret key strength.

        Args:
            key: Secret key to validate

        Returns:
            True if key meets security requirements
        """
        if not key or len(key) < SECRET_KEY_MIN_LENGTH:
            return False

        # Check for common insecure patterns
        insecure_patterns = [
            "change-this",
            "changeme",
            "password",
            "secret",
            "default",
            "1234",
        ]

        key_lower = key.lower()
        return not any(pattern in key_lower for pattern in insecure_patterns)


# ============================================================================
# Path Sanitization
# ============================================================================


def sanitize_path(user_input: str, base_dir: Path | str) -> Path:
    """Sanitize user-provided paths to prevent traversal attacks.

    Args:
        user_input: User-provided path component
        base_dir: Base directory to restrict paths to

    Returns:
        Sanitized absolute path

    Raises:
        PathTraversalError: If path traversal is detected
        ValueError: If input is invalid

    Example:
        >>> base = Path("/app/data")
        >>> safe_path = sanitize_path("file.txt", base)
        >>> assert str(safe_path).startswith(str(base))

        >>> try:
        ...     sanitize_path("../../../etc/passwd", base)
        ... except PathTraversalError:
        ...     print("Attack blocked!")
        Attack blocked!
    """
    if not user_input:
        raise ValueError("Path input cannot be empty")

    # Convert to Path objects
    base_dir = Path(base_dir).resolve()

    # Remove any potentially dangerous characters
    # Allow: alphanumeric, underscore, hyphen, dot, forward slash
    if not re.match(r"^[a-zA-Z0-9_\-./]+$", user_input):
        raise PathTraversalError(f"Path contains invalid characters: {user_input}")

    # Construct the full path
    requested_path = (base_dir / user_input).resolve()

    # Verify the resolved path is still within base_dir
    try:
        requested_path.relative_to(base_dir)
    except ValueError:
        # Path is outside base_dir
        raise PathTraversalError(
            f"Path traversal detected: {user_input} resolves outside {base_dir}"
        )

    logger.debug(f"Path sanitized: {user_input} -> {requested_path}")
    return requested_path


def validate_filename(filename: str) -> str:
    """Validate and sanitize filename.

    Args:
        filename: Filename to validate

    Returns:
        Sanitized filename

    Raises:
        ValueError: If filename is invalid

    Example:
        >>> validate_filename("report.pdf")
        'report.pdf'
        >>> validate_filename("../etc/passwd")
        Traceback (most recent call last):
        ...
        ValueError: Invalid filename
    """
    if not filename:
        raise ValueError("Filename cannot be empty")

    # Remove directory separators
    filename = os.path.basename(filename)

    # Allow only safe characters: alphanumeric, underscore, hyphen, dot
    if not re.match(r"^[a-zA-Z0-9_\-. ]+$", filename):
        raise ValueError(f"Filename contains invalid characters: {filename}")

    # Prevent hidden files
    if filename.startswith("."):
        raise ValueError(f"Hidden files not allowed: {filename}")

    # Prevent excessively long filenames
    if len(filename) > 255:
        raise ValueError(f"Filename too long: {filename}")

    return filename


# ============================================================================
# Command Injection Prevention
# ============================================================================


def sanitize_command_arg(arg: str, allow_special_chars: bool = False) -> str:
    """Sanitize command-line argument to prevent injection.

    Args:
        arg: Command argument to sanitize
        allow_special_chars: Whether to allow some special characters

    Returns:
        Sanitized argument

    Raises:
        CommandInjectionError: If injection attempt is detected

    Example:
        >>> sanitize_command_arg("file.txt")
        'file.txt'
        >>> sanitize_command_arg("file.txt; rm -rf /")
        Traceback (most recent call last):
        ...
        src.core.exceptions.CommandInjectionError: Command injection detected
    """
    if not arg:
        return arg

    # Detect dangerous characters
    dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r", ">", "<"]

    if not allow_special_chars:
        for char in dangerous_chars:
            if char in arg:
                raise CommandInjectionError(f"Dangerous character '{char}' detected in: {arg}")

    # Detect command substitution attempts
    if "$(" in arg or "`" in arg:
        raise CommandInjectionError(f"Command substitution detected in: {arg}")

    return arg


def validate_subprocess_command(command: list[str]) -> list[str]:
    """Validate subprocess command for safety.

    Args:
        command: Command as list of strings

    Returns:
        Validated command

    Raises:
        CommandInjectionError: If command is unsafe
        ValueError: If command is invalid

    Example:
        >>> validate_subprocess_command(["ls", "-la"])
        ['ls', '-la']
        >>> validate_subprocess_command(["sh", "-c", "rm -rf /"])
        Traceback (most recent call last):
        ...
        src.core.exceptions.CommandInjectionError: Shell execution not allowed
    """
    if not command or len(command) == 0:
        raise ValueError("Command cannot be empty")

    # Disallow shell execution
    shell_commands = ["sh", "bash", "zsh", "fish", "cmd", "powershell"]
    if command[0] in shell_commands:
        raise CommandInjectionError(f"Shell execution not allowed: {command[0]}")

    # Validate each argument
    for arg in command:
        sanitize_command_arg(arg, allow_special_chars=True)

    return command


# ============================================================================
# Input Validation
# ============================================================================


def validate_port(port: Any) -> int:
    """Validate port number.

    Args:
        port: Port number to validate

    Returns:
        Validated port number

    Raises:
        ValueError: If port is invalid

    Example:
        >>> validate_port(8080)
        8080
        >>> validate_port(99999)
        Traceback (most recent call last):
        ...
        ValueError: Port must be between 1 and 65535
    """
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"Port must be an integer: {port}")

    if not (1 <= port_int <= 65535):
        raise ValueError(f"Port must be between 1 and 65535: {port}")

    return port_int


def validate_timeout(timeout: Any) -> int:
    """Validate timeout value.

    Args:
        timeout: Timeout in seconds

    Returns:
        Validated timeout

    Raises:
        ValueError: If timeout is invalid
    """
    try:
        timeout_int = int(timeout)
    except (TypeError, ValueError):
        raise ValueError(f"Timeout must be an integer: {timeout}")

    if timeout_int < 0:
        raise ValueError(f"Timeout cannot be negative: {timeout}")

    if timeout_int > 3600:  # 1 hour max
        logger.warning(f"Very long timeout: {timeout_int}s")

    return timeout_int


def sanitize_log_message(message: str, max_length: int = 1000) -> str:
    """Sanitize log message to prevent log injection.

    Args:
        message: Log message to sanitize
        max_length: Maximum message length

    Returns:
        Sanitized message

    Example:
        >>> sanitize_log_message("Normal message")
        'Normal message'
        >>> sanitize_log_message("Line1\\nFAKE LOG: Error")
        'Line1 FAKE LOG: Error'
    """
    if not message:
        return ""

    # Remove newlines to prevent log injection
    message = message.replace("\n", " ").replace("\r", " ")

    # Truncate if too long
    if len(message) > max_length:
        message = message[:max_length] + "..."

    return message


# ============================================================================
# Security Headers
# ============================================================================


def get_security_headers() -> dict[str, str]:
    """Get recommended security headers for web responses.

    Returns:
        Dictionary of security headers

    Example:
        >>> headers = get_security_headers()
        >>> assert 'X-Content-Type-Options' in headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
