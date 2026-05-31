"""Tests for security utilities.

This module tests:
- SecretManager for secret key management
- Path sanitization and validation
- Command injection prevention
- Input validation functions
- Security headers
"""

import os
import re
import tempfile
from pathlib import Path

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


# ============================================================================
# Batch 3 coverage extension (issue #161)
# Edge cases and branches not covered by the suites above.
# Tests document the REAL behavior of src/core/security.py.
# ============================================================================


class TestSecretManagerEdgeCases:
    """Additional edge cases for SecretManager."""

    def setup_method(self):
        self._original_secret = os.environ.get(SECRET_KEY_ENV_VAR)
        self._original_env = os.environ.get(APP_ENV_VAR)
        os.environ.pop(SECRET_KEY_ENV_VAR, None)
        os.environ.pop(APP_ENV_VAR, None)

    def teardown_method(self):
        if self._original_secret is not None:
            os.environ[SECRET_KEY_ENV_VAR] = self._original_secret
        else:
            os.environ.pop(SECRET_KEY_ENV_VAR, None)
        if self._original_env is not None:
            os.environ[APP_ENV_VAR] = self._original_env
        else:
            os.environ.pop(APP_ENV_VAR, None)

    def test_non_production_env_does_not_enforce_key(self):
        """A non-production APP_ENV should still auto-generate a dev key."""
        os.environ[APP_ENV_VAR] = "staging"

        key = SecretManager.get_secret_key()

        assert key is not None
        assert len(key) >= SECRET_KEY_MIN_LENGTH

    def test_non_production_env_with_short_key_is_accepted(self):
        """Outside production, a short provided key is returned as-is (no enforcement)."""
        os.environ[APP_ENV_VAR] = "development"
        os.environ[SECRET_KEY_ENV_VAR] = "short-dev-key"

        key = SecretManager.get_secret_key()

        assert key == "short-dev-key"

    def test_production_key_exactly_min_length_accepted(self):
        """Production key of exactly SECRET_KEY_MIN_LENGTH chars is accepted."""
        os.environ[APP_ENV_VAR] = PRODUCTION_ENV
        os.environ[SECRET_KEY_ENV_VAR] = "k" * SECRET_KEY_MIN_LENGTH

        key = SecretManager.get_secret_key()

        assert len(key) == SECRET_KEY_MIN_LENGTH

    def test_production_missing_key_error_message(self):
        """Production missing key should mention the env var name and 'production'."""
        os.environ[APP_ENV_VAR] = PRODUCTION_ENV

        with pytest.raises(InsecureConfigurationError) as exc_info:
            SecretManager.get_secret_key()

        assert SECRET_KEY_ENV_VAR in str(exc_info.value)

    def test_generate_secret_key_is_url_safe(self):
        """Generated key should only contain URL-safe base64 characters."""
        key = SecretManager.generate_secret_key()

        assert re.match(r"^[A-Za-z0-9_\-]+$", key)

    def test_validate_secret_key_exactly_min_length(self):
        """A secure key of exactly the min length should be accepted."""
        # 32 distinct-ish chars with no insecure substring
        key = "Xq" + "abcdefghijklmnopqrstuvwxyzABCD"
        assert len(key) == SECRET_KEY_MIN_LENGTH
        assert SecretManager.validate_secret_key(key) is True

    def test_validate_secret_key_one_below_min_length(self):
        """A key one char below min length should be rejected."""
        key = "a" * (SECRET_KEY_MIN_LENGTH - 1)
        assert SecretManager.validate_secret_key(key) is False

    def test_validate_secret_key_uppercase_insecure_pattern(self):
        """Insecure pattern matching is case-insensitive."""
        # Long enough but contains 'PASSWORD' (uppercased)
        key = "PASSWORD" + "X" * 30
        assert SecretManager.validate_secret_key(key) is False


class TestSanitizePathEdgeCases:
    """Additional edge cases for sanitize_path."""

    def test_returns_resolved_absolute_path(self):
        """Result must be absolute and within the resolved base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = sanitize_path("a/b/c.txt", base)
            assert result.is_absolute()
            # relative_to does not raise -> inside base
            result.relative_to(base.resolve())

    def test_accepts_string_base_dir(self):
        """base_dir may be passed as a string, not only a Path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_path("file.txt", tmpdir)
            assert result == Path(tmpdir).resolve() / "file.txt"

    def test_current_dir_segments_collapse_inside_base(self):
        """Redundant './' segments are allowed and collapse within base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = sanitize_path("./sub/./file.txt", base)
            assert result == base.resolve() / "sub" / "file.txt"

    def test_traversal_via_valid_chars_blocked(self):
        """'..' uses only allowed chars but must still be blocked by relative_to check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "inner"
            base.mkdir()
            with pytest.raises(PathTraversalError):
                sanitize_path("../escape.txt", base)

    def test_path_traversal_error_carries_details(self):
        """PathTraversalError should carry the attempted path in its details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with pytest.raises(PathTraversalError) as exc_info:
                sanitize_path("file!.txt", base)
            # invalid-character branch
            assert "file!.txt" in str(exc_info.value)


class TestSanitizeCommandArgAllowSpecial:
    """Cover the allow_special_chars branch of sanitize_command_arg."""

    def test_allow_special_chars_permits_pipe(self):
        """With allow_special_chars=True, a pipe is permitted (returned as-is)."""
        arg = "a|b"
        assert sanitize_command_arg(arg, allow_special_chars=True) == arg

    def test_allow_special_chars_permits_semicolon(self):
        """With allow_special_chars=True, a semicolon is permitted."""
        arg = "a;b"
        assert sanitize_command_arg(arg, allow_special_chars=True) == arg

    def test_allow_special_chars_still_blocks_command_substitution(self):
        """Command substitution '$(' is blocked even when special chars allowed."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("$(whoami)", allow_special_chars=True)

    def test_allow_special_chars_still_blocks_backtick(self):
        """Backtick substitution is blocked even when special chars allowed."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("`whoami`", allow_special_chars=True)

    def test_detects_redirection_in(self):
        """Input redirection '<' is a dangerous character."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file < input")

    def test_detects_redirection_out(self):
        """Output redirection '>' is a dangerous character."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file > output")

    def test_detects_carriage_return(self):
        """Carriage return is a dangerous character."""
        with pytest.raises(CommandInjectionError):
            sanitize_command_arg("file\rrm")

    def test_command_injection_error_carries_details(self):
        """CommandInjectionError should reference the offending argument."""
        with pytest.raises(CommandInjectionError) as exc_info:
            sanitize_command_arg("a;b")
        assert "a;b" in str(exc_info.value)


class TestValidateSubprocessCommandEdgeCases:
    """Additional edge cases for validate_subprocess_command."""

    def test_single_element_command(self):
        """A single safe binary is a valid command."""
        assert validate_subprocess_command(["echo"]) == ["echo"]

    def test_args_with_special_chars_allowed(self):
        """Non-shell command whose args contain pipes is allowed (special chars permitted)."""
        cmd = ["grep", "a|b", "file.txt"]
        assert validate_subprocess_command(cmd) == cmd

    def test_command_with_substitution_arg_blocked(self):
        """Even a non-shell binary with a '$(' substitution arg is rejected."""
        with pytest.raises(CommandInjectionError):
            validate_subprocess_command(["echo", "$(rm -rf /)"])

    def test_command_with_backtick_arg_blocked(self):
        """Backtick substitution in an argument is rejected."""
        with pytest.raises(CommandInjectionError):
            validate_subprocess_command(["echo", "`id`"])

    def test_fish_shell_blocked(self):
        """The 'fish' shell is in the blocked list."""
        with pytest.raises(CommandInjectionError):
            validate_subprocess_command(["fish", "-c", "ls"])

    def test_returns_same_list_object(self):
        """The validated command returned is the same list instance passed in."""
        cmd = ["ls", "-la"]
        assert validate_subprocess_command(cmd) is cmd


class TestValidatePortEdgeCases:
    """Additional edge cases for validate_port."""

    def test_boundary_low(self):
        """Port 1 is the inclusive lower bound."""
        assert validate_port(1) == 1

    def test_boundary_high(self):
        """Port 65535 is the inclusive upper bound."""
        assert validate_port(65535) == 65535

    def test_float_string_rejected(self):
        """A float-looking string is not a valid integer port."""
        with pytest.raises(ValueError):
            validate_port("80.5")

    def test_float_truncates(self):
        """A float port is coerced via int() (truncation), documenting real behavior."""
        # int(8080.9) == 8080, within range
        assert validate_port(8080.9) == 8080


class TestValidateTimeoutEdgeCases:
    """Additional edge cases for validate_timeout."""

    def test_zero_timeout_allowed(self):
        """Zero is a valid timeout."""
        assert validate_timeout(0) == 0

    def test_exactly_one_hour_no_warning_returns_value(self):
        """A timeout of exactly 3600 is returned unchanged."""
        assert validate_timeout(3600) == 3600

    def test_over_one_hour_still_returns_value(self):
        """A timeout above 3600 logs a warning but is still returned."""
        assert validate_timeout(7200) == 7200

    def test_none_rejected(self):
        """None cannot be coerced to int and is rejected."""
        with pytest.raises(ValueError):
            validate_timeout(None)

    def test_float_truncates(self):
        """A float timeout is coerced via int(), documenting real behavior."""
        assert validate_timeout(30.7) == 30


class TestSanitizeLogMessageEdgeCases:
    """Additional edge cases for sanitize_log_message."""

    def test_at_max_length_not_truncated(self):
        """A message exactly at max_length is not truncated."""
        msg = "y" * 100
        result = sanitize_log_message(msg, max_length=100)
        assert result == msg
        assert not result.endswith("...")

    def test_one_over_max_length_truncated(self):
        """A message one char over max_length is truncated and suffixed."""
        msg = "z" * 101
        result = sanitize_log_message(msg, max_length=100)
        assert result == "z" * 100 + "..."

    def test_default_max_length_truncation(self):
        """With the default max_length (1000), longer messages are truncated."""
        msg = "a" * 1500
        result = sanitize_log_message(msg)
        assert result == "a" * 1000 + "..."

    def test_mixed_newlines_and_carriage_returns(self):
        """Both \\n and \\r are replaced by spaces."""
        result = sanitize_log_message("a\r\nb\nc\rd")
        assert "\n" not in result and "\r" not in result
        assert result == "a  b c d"


class TestGetSecurityHeadersValues:
    """Verify exact values of selected security headers."""

    def test_hsts_value(self):
        """HSTS header should enable subdomains and a one-year max-age."""
        headers = get_security_headers()
        assert headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )

    def test_csp_default_src_self(self):
        """CSP default-src should be 'self'."""
        headers = get_security_headers()
        assert headers["Content-Security-Policy"] == "default-src 'self'"

    def test_returns_new_dict_each_call(self):
        """Each call returns an independent dict (mutation isolation)."""
        h1 = get_security_headers()
        h2 = get_security_headers()
        h1["X-Frame-Options"] = "MUTATED"
        assert h2["X-Frame-Options"] == "DENY"

    def test_all_values_are_strings(self):
        """All header values must be strings."""
        headers = get_security_headers()
        assert all(isinstance(v, str) for v in headers.values())
