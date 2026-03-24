"""Tests for security utilities.

This module tests:
- SecretManager for secret key management
- Path sanitization and validation
- Command injection prevention
- Input validation functions
- Security headers
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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
from src.core.security import (
    SecretManager,
    get_security_headers,
    sanitize_command_arg,
    sanitize_log_message,
    sanitize_path,
    validate_filename,
    validate_port,
    validate_subprocess_command,
    validate_timeout,
)


class TestSecretManager:
    """Test suite for SecretManager."""

    def setup_method(self):
        """Clear environment before each test."""
        # Save original values
        self._original_secret = os.environ.get(SECRET_KEY_ENV_VAR)
        self._original_env = os.environ.get(APP_ENV_VAR)

        # Clear for tests
        if SECRET_KEY_ENV_VAR in os.environ:
            del os.environ[SECRET_KEY_ENV_VAR]
        if APP_ENV_VAR in os.environ:
            del os.environ[APP_ENV_VAR]

    def teardown_method(self):
        """Restore environment after each test."""
        if self._original_secret is not None:
            os.environ[SECRET_KEY_ENV_VAR] = self._original_secret
        elif SECRET_KEY_ENV_VAR in os.environ:
            del os.environ[SECRET_KEY_ENV_VAR]

        if self._original_env is not None:
            os.environ[APP_ENV_VAR] = self._original_env
        elif APP_ENV_VAR in os.environ:
            del os.environ[APP_ENV_VAR]

    def test_get_secret_key_from_environment(self):
        """Should return key from environment variable."""
        os.environ[SECRET_KEY_ENV_VAR] = "test-secret-key-that-is-long-enough-to-pass"

        key = SecretManager.get_secret_key()

        assert key == "test-secret-key-that-is-long-enough-to-pass"

    def test_get_secret_key_generates_for_development(self):
        """Should generate key in development mode without SECRET_KEY."""
        # No SECRET_KEY set, not in production
        key = SecretManager.get_secret_key()

        assert key is not None
        assert len(key) >= SECRET_KEY_MIN_LENGTH

    def test_get_secret_key_production_requires_key(self):
        """Should raise in production without SECRET_KEY."""
        os.environ[APP_ENV_VAR] = PRODUCTION_ENV

        with pytest.raises(InsecureConfigurationError):
            SecretManager.get_secret_key()

    def test_get_secret_key_production_requires_long_key(self):
        """Should raise in production with short SECRET_KEY."""
        os.environ[APP_ENV_VAR] = PRODUCTION_ENV
        os.environ[SECRET_KEY_ENV_VAR] = "short"

        with pytest.raises(InsecureConfigurationError):
            SecretManager.get_secret_key()

    def test_get_secret_key_production_accepts_long_key(self):
        """Should accept sufficiently long key in production."""
        os.environ[APP_ENV_VAR] = PRODUCTION_ENV
        os.environ[SECRET_KEY_ENV_VAR] = "a" * SECRET_KEY_MIN_LENGTH

        key = SecretManager.get_secret_key()

        assert key == "a" * SECRET_KEY_MIN_LENGTH

    def test_generate_secret_key(self):
        """Should generate cryptographically secure key."""
        key = SecretManager.generate_secret_key()

        assert len(key) >= SECRET_KEY_MIN_LENGTH

    def test_generate_secret_key_unique(self):
        """Generated keys should be unique."""
        keys = [SecretManager.generate_secret_key() for _ in range(10)]

        assert len(set(keys)) == 10

    def test_validate_secret_key_short(self):
        """Should reject short keys."""
        assert SecretManager.validate_secret_key("short") is False

    def test_validate_secret_key_empty(self):
        """Should reject empty keys."""
        assert SecretManager.validate_secret_key("") is False
        assert SecretManager.validate_secret_key(None) is False

    def test_validate_secret_key_insecure_patterns(self):
        """Should reject keys with insecure patterns."""
        insecure_keys = [
            "change-this-secret-key-123456789",
            "changeme-please-this-is-insecure",
            "password-is-not-a-good-secret",
            "my-default-secret-key-for-app",
            "1234567890123456789012345678901234",
        ]

        for key in insecure_keys:
            assert SecretManager.validate_secret_key(key) is False, f"Should reject: {key}"

    def test_validate_secret_key_valid(self):
        """Should accept secure keys."""
        key = SecretManager.generate_secret_key()

        assert SecretManager.validate_secret_key(key) is True


class TestSanitizePath:
    """Test suite for sanitize_path function."""

    def test_valid_path(self):
        """Should accept valid paths within base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "subdir").mkdir()

            result = sanitize_path("subdir/file.txt", base)

            assert result == base / "subdir" / "file.txt"

    def test_simple_filename(self):
        """Should accept simple filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            result = sanitize_path("file.txt", base)

            assert result == base / "file.txt"

    def test_path_traversal_detection(self):
        """Should detect path traversal attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(PathTraversalError):
                sanitize_path("../../../etc/passwd", base)

    def test_absolute_path_escape(self):
        """Should detect absolute path escape attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(PathTraversalError):
                sanitize_path("/etc/passwd", base)

    def test_invalid_characters(self):
        """Should reject invalid characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            invalid_paths = [
                "file;rm -rf /",
                "file|cat /etc/passwd",
                "file$USER",
                "file`whoami`",
            ]

            for path in invalid_paths:
                with pytest.raises(PathTraversalError):
                    sanitize_path(path, base)

    def test_empty_path(self):
        """Should reject empty paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError):
                sanitize_path("", tmpdir)


class TestValidateFilename:
    """Test suite for validate_filename function."""

    def test_valid_filenames(self):
        """Should accept valid filenames."""
        valid_names = [
            "file.txt",
            "my-document.pdf",
            "report_2024.csv",
            "file name with spaces.doc",
        ]

        for name in valid_names:
            result = validate_filename(name)
            assert result == name

    def test_strips_directory(self):
        """Should strip directory components."""
        result = validate_filename("path/to/file.txt")

        assert result == "file.txt"

    def test_rejects_hidden_files(self):
        """Should reject hidden files."""
        with pytest.raises(ValueError):
            validate_filename(".hidden")

    def test_rejects_empty(self):
        """Should reject empty filename."""
        with pytest.raises(ValueError):
            validate_filename("")

    def test_rejects_long_filename(self):
        """Should reject excessively long filenames."""
        with pytest.raises(ValueError):
            validate_filename("a" * 256)

    def test_rejects_special_characters(self):
        """Should reject special characters."""
        invalid_names = [
            "file<script>.txt",
            "file>output.txt",
            "file:stream",
            'file"quotes".txt',
        ]

        for name in invalid_names:
            with pytest.raises(ValueError):
                validate_filename(name)


class TestSanitizeCommandArg:
    """Test suite for sanitize_command_arg function."""

    def test_safe_arguments(self):
        """Should accept safe arguments."""
        safe_args = [
            "file.txt",
            "--verbose",
            "-n",
            "path/to/file",
            "user@host",
        ]

        for arg in safe_args:
            result = sanitize_command_arg(arg)
            assert result == arg

    def test_detects_semicolon(self):
        """Should detect semicolon injection."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file.txt; rm -rf /")

    def test_detects_pipe(self):
        """Should detect pipe injection."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file.txt | cat /etc/passwd")

    def test_detects_ampersand(self):
        """Should detect ampersand injection."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file.txt & rm -rf /")

    def test_detects_dollar(self):
        """Should detect variable expansion."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("$PATH")

    def test_detects_backtick(self):
        """Should detect backtick command substitution."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("`whoami`")

    def test_detects_subshell(self):
        """Should detect subshell command substitution."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("$(whoami)")

    def test_detects_newline(self):
        """Should detect newline injection."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file.txt\nrm -rf /")

    def test_empty_arg(self):
        """Should handle empty argument."""
        assert sanitize_command_arg("") == ""
        assert sanitize_command_arg(None) is None


class TestValidateSubprocessCommand:
    """Test suite for validate_subprocess_command function."""

    def test_valid_command(self):
        """Should accept valid commands."""
        cmd = ["ls", "-la", "/tmp"]

        result = validate_subprocess_command(cmd)

        assert result == cmd

    def test_empty_command(self):
        """Should reject empty commands."""
        with pytest.raises(ValueError):
            validate_subprocess_command([])

    def test_shell_execution_blocked(self):
        """Should block shell execution attempts."""
        shell_commands = [
            ["sh", "-c", "rm -rf /"],
            ["bash", "-c", "cat /etc/passwd"],
            ["zsh", "-c", "echo $PATH"],
            ["cmd", "/c", "del *.*"],
            ["powershell", "-Command", "Remove-Item"],
        ]

        for cmd in shell_commands:
            with pytest.raises(CommandInjectionError):
                validate_subprocess_command(cmd)


class TestValidatePort:
    """Test suite for validate_port function."""

    def test_valid_ports(self):
        """Should accept valid port numbers."""
        valid_ports = [1, 80, 443, 8080, 65535]

        for port in valid_ports:
            result = validate_port(port)
            assert result == port

    def test_string_port(self):
        """Should convert string port to int."""
        assert validate_port("8080") == 8080

    def test_port_zero(self):
        """Should reject port 0."""
        with pytest.raises(ValueError):
            validate_port(0)

    def test_negative_port(self):
        """Should reject negative ports."""
        with pytest.raises(ValueError):
            validate_port(-1)

    def test_port_too_large(self):
        """Should reject ports > 65535."""
        with pytest.raises(ValueError):
            validate_port(65536)

    def test_invalid_type(self):
        """Should reject non-integer types."""
        with pytest.raises(ValueError):
            validate_port("not-a-number")

        with pytest.raises(ValueError):
            validate_port(None)


class TestValidateTimeout:
    """Test suite for validate_timeout function."""

    def test_valid_timeouts(self):
        """Should accept valid timeouts."""
        valid_timeouts = [0, 30, 60, 300, 3600]

        for timeout in valid_timeouts:
            result = validate_timeout(timeout)
            assert result == timeout

    def test_string_timeout(self):
        """Should convert string timeout to int."""
        assert validate_timeout("30") == 30

    def test_negative_timeout(self):
        """Should reject negative timeouts."""
        with pytest.raises(ValueError):
            validate_timeout(-1)

    def test_invalid_type(self):
        """Should reject non-integer types."""
        with pytest.raises(ValueError):
            validate_timeout("not-a-number")


class TestSanitizeLogMessage:
    """Test suite for sanitize_log_message function."""

    def test_normal_message(self):
        """Should pass normal messages through."""
        msg = "Normal log message"

        result = sanitize_log_message(msg)

        assert result == msg

    def test_removes_newlines(self):
        """Should remove newlines to prevent log injection."""
        msg = "Line1\nFAKE LOG: Error\nLine3"

        result = sanitize_log_message(msg)

        assert "\n" not in result
        assert result == "Line1 FAKE LOG: Error Line3"

    def test_removes_carriage_returns(self):
        """Should remove carriage returns."""
        msg = "Line1\rFAKE LOG\r"

        result = sanitize_log_message(msg)

        assert "\r" not in result

    def test_truncates_long_messages(self):
        """Should truncate long messages."""
        msg = "x" * 2000

        result = sanitize_log_message(msg, max_length=100)

        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_empty_message(self):
        """Should handle empty messages."""
        assert sanitize_log_message("") == ""
        assert sanitize_log_message(None) == ""


class TestGetSecurityHeaders:
    """Test suite for get_security_headers function."""

    def test_returns_dict(self):
        """Should return dictionary of headers."""
        headers = get_security_headers()

        assert isinstance(headers, dict)

    def test_content_type_options(self):
        """Should include X-Content-Type-Options."""
        headers = get_security_headers()

        assert headers["X-Content-Type-Options"] == "nosniff"

    def test_frame_options(self):
        """Should include X-Frame-Options."""
        headers = get_security_headers()

        assert headers["X-Frame-Options"] == "DENY"

    def test_xss_protection(self):
        """Should include X-XSS-Protection."""
        headers = get_security_headers()

        assert "X-XSS-Protection" in headers

    def test_hsts(self):
        """Should include HSTS header."""
        headers = get_security_headers()

        assert "Strict-Transport-Security" in headers

    def test_csp(self):
        """Should include Content-Security-Policy."""
        headers = get_security_headers()

        assert "Content-Security-Policy" in headers

    def test_referrer_policy(self):
        """Should include Referrer-Policy."""
        headers = get_security_headers()

        assert "Referrer-Policy" in headers

    def test_permissions_policy(self):
        """Should include Permissions-Policy."""
        headers = get_security_headers()

        assert "Permissions-Policy" in headers
