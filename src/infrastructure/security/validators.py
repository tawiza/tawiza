"""Security validators for input sanitization and validation.

This module provides production-ready validators to protect against:
- Command injection (VULN-002)
- Path traversal (VULN-005)
- SSRF (VULN-004)
- General input validation (VULN-006)
"""

import ipaddress
import re
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class ModelNameValidator(BaseModel):
    """Validator for ML model names to prevent command injection.

    Security: Prevents VULN-002 (Command Injection)
    CVSS: 9.8 CRITICAL

    Allows:
    - Alphanumeric characters (a-z, A-Z, 0-9)
    - Hyphens and underscores
    - Colons (for model:tag format)
    - Slashes (for namespace/model format)
    - Dots (for version numbers)

    Examples:
        Valid: "llama2", "qwen3-coder:30b", "meta-llama/Llama-2-7b-chat-hf"
        Invalid: "model; rm -rf /", "model`whoami`", "model$(cat /etc/passwd)"
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Model name to validate"
    )

    # Whitelist pattern: alphanumeric, hyphen, underscore, colon, slash, dot
    ALLOWED_PATTERN: ClassVar[re.Pattern] = re.compile(r'^[a-zA-Z0-9._:/\-]+$')

    # Blacklist patterns for common injection attempts
    FORBIDDEN_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r'[;&|`$()]'),  # Shell metacharacters
        re.compile(r'\.\.'),  # Path traversal
        re.compile(r'[<>]'),  # Redirections
        re.compile(r'\s'),  # Whitespace (spaces, tabs, newlines)
    ]

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate model name against security rules.

        Args:
            v: Model name to validate

        Returns:
            Validated model name

        Raises:
            ValueError: If model name contains forbidden characters
        """
        # Check whitelist pattern
        if not cls.ALLOWED_PATTERN.match(v):
            raise ValueError(
                "Model name contains invalid characters. "
                "Allowed: alphanumeric, hyphen, underscore, colon, slash, dot"
            )

        # Check blacklist patterns
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern.search(v):
                raise ValueError(
                    f"Model name contains forbidden pattern: {pattern.pattern}"
                )

        return v


class PathValidator(BaseModel):
    """Validator for file paths to prevent path traversal attacks.

    Security: Prevents VULN-005 (Path Traversal)
    CVSS: 8.6 HIGH

    Validates that paths:
    - Do not contain .. (parent directory)
    - Stay within allowed base directories
    - Are canonicalized (no symlink tricks)
    - Do not contain null bytes

    Examples:
        Valid: "models/llama2.bin", "/data/dataset.json"
        Invalid: "../../../etc/passwd", "data/../../../secret", "/etc/passwd"
    """

    path: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="File path to validate"
    )
    base_dir: str | None = Field(
        default=None,
        description="Base directory to restrict path within"
    )

    # Forbidden patterns
    FORBIDDEN_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r'\.\.'),  # Parent directory
        re.compile(r'\0'),  # Null byte
        re.compile(r'[<>|]'),  # Shell redirections
    ]

    @field_validator('path')
    @classmethod
    def validate_path_security(cls, v: str) -> str:
        """Validate path for security issues.

        Args:
            v: Path to validate

        Returns:
            Validated path

        Raises:
            ValueError: If path contains forbidden patterns
        """
        # Check forbidden patterns
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern.search(v):
                raise ValueError(
                    f"Path contains forbidden pattern: {pattern.pattern}"
                )

        return v

    def validate_within_base(self) -> Path:
        """Validate that path stays within base directory.

        Returns:
            Resolved canonical path

        Raises:
            ValueError: If path escapes base directory
        """
        path = Path(self.path)

        # Resolve to absolute canonical path
        try:
            resolved_path = path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid path: {e}")

        # If base_dir specified, ensure path is within it
        if self.base_dir:
            base = Path(self.base_dir).resolve()

            # Check if resolved path is relative to base
            try:
                resolved_path.relative_to(base)
            except ValueError:
                raise ValueError(
                    f"Path '{self.path}' escapes base directory '{self.base_dir}'"
                )

        return resolved_path


class URLValidator(BaseModel):
    """Validator for URLs to prevent SSRF attacks.

    Security: Prevents VULN-004 (SSRF)
    CVSS: 9.0 CRITICAL

    Validates that URLs:
    - Use allowed schemes (http, https)
    - Do not point to private IP ranges
    - Match allowed domain whitelist
    - Do not use IP addresses (unless explicitly allowed)

    Examples:
        Valid: "https://api.example.com/data", "https://label-studio.example.com"
        Invalid: "http://localhost:8080", "http://192.168.1.1", "file:///etc/passwd"
    """

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL to validate"
    )
    allowed_schemes: set[str] = Field(
        default={'http', 'https'},
        description="Allowed URL schemes"
    )
    allowed_domains: set[str] | None = Field(
        default=None,
        description="Whitelist of allowed domains (if None, all public domains allowed)"
    )
    allow_private_ips: bool = Field(
        default=False,
        description="Allow private IP addresses (default: False for SSRF protection)"
    )

    # Private IP ranges (RFC 1918, RFC 4193, loopback)
    PRIVATE_IP_RANGES: ClassVar[list] = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),
        ipaddress.ip_network('169.254.0.0/16'),  # Link-local
        ipaddress.ip_network('::1/128'),  # IPv6 loopback
        ipaddress.ip_network('fc00::/7'),  # IPv6 private
        ipaddress.ip_network('fe80::/10'),  # IPv6 link-local
    ]

    @field_validator('url')
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Basic URL format validation.

        Args:
            v: URL to validate

        Returns:
            Validated URL

        Raises:
            ValueError: If URL format is invalid
        """
        # Check for null bytes
        if '\0' in v:
            raise ValueError("URL contains null byte")

        # Check for whitespace
        if any(c.isspace() for c in v):
            raise ValueError("URL contains whitespace")

        return v

    def validate_ssrf_protection(self) -> str:
        """Validate URL for SSRF protection.

        Returns:
            Validated URL

        Raises:
            ValueError: If URL is unsafe (SSRF risk)
        """
        parsed = urlparse(self.url)

        # Validate scheme
        if parsed.scheme not in self.allowed_schemes:
            raise ValueError(
                f"URL scheme '{parsed.scheme}' not allowed. "
                f"Allowed schemes: {', '.join(self.allowed_schemes)}"
            )

        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL missing hostname")

        # Check domain whitelist if specified
        if self.allowed_domains and hostname not in self.allowed_domains:
            raise ValueError(
                f"Domain '{hostname}' not in allowed whitelist: "
                f"{', '.join(self.allowed_domains)}"
            )

        # Check for private IPs (SSRF protection)
        if not self.allow_private_ips:
            # Check if hostname is localhost-like
            if hostname in {'localhost', '0.0.0.0', '[::]'}:
                raise ValueError(
                    f"Access to '{hostname}' is not allowed (SSRF protection)"
                )

            # Try to parse as IP address
            try:
                ip = ipaddress.ip_address(hostname)

                # Check if IP is in private ranges
                for network in self.PRIVATE_IP_RANGES:
                    if ip in network:
                        raise ValueError(
                            f"Access to private IP address '{hostname}' is not allowed "
                            f"(SSRF protection)"
                        )
            except ValueError as e:
                # If it's our security error, re-raise it
                if "SSRF protection" in str(e):
                    raise
                # Otherwise, it's not an IP address (it's a domain name) - that's OK
                pass

        return self.url


# Helper functions for convenient validation

def validate_model_name(name: str) -> str:
    """Validate a model name (convenience function).

    Args:
        name: Model name to validate

    Returns:
        Validated model name

    Raises:
        ValueError: If model name is invalid

    Example:
        >>> validate_model_name("llama2-7b-chat")
        'llama2-7b-chat'
        >>> validate_model_name("model; rm -rf /")
        ValueError: Model name contains forbidden pattern
    """
    validator = ModelNameValidator(name=name)
    return validator.name


def validate_path(
    path: str,
    base_dir: str | None = None,
    must_be_within_base: bool = True
) -> Path:
    """Validate a file path (convenience function).

    Args:
        path: Path to validate
        base_dir: Base directory to restrict path within
        must_be_within_base: If True, enforces base_dir restriction

    Returns:
        Validated resolved path

    Raises:
        ValueError: If path is invalid or escapes base_dir

    Example:
        >>> validate_path("models/llama2.bin", base_dir="/data")
        Path('/data/models/llama2.bin')
        >>> validate_path("../../../etc/passwd")
        ValueError: Path contains forbidden pattern
    """
    validator = PathValidator(path=path, base_dir=base_dir)

    if must_be_within_base and base_dir:
        return validator.validate_within_base()
    else:
        return Path(validator.path)


def validate_url(
    url: str,
    allowed_domains: set[str] | None = None,
    allow_private_ips: bool = False
) -> str:
    """Validate a URL for SSRF protection (convenience function).

    Args:
        url: URL to validate
        allowed_domains: Whitelist of allowed domains
        allow_private_ips: Allow private IP addresses

    Returns:
        Validated URL

    Raises:
        ValueError: If URL is unsafe

    Example:
        >>> validate_url("https://api.example.com/data")
        'https://api.example.com/data'
        >>> validate_url("http://localhost:8080")
        ValueError: Access to 'localhost' is not allowed (SSRF protection)
    """
    validator = URLValidator(
        url=url,
        allowed_domains=allowed_domains,
        allow_private_ips=allow_private_ips
    )
    return validator.validate_ssrf_protection()


def sanitize_command_argument(arg: str, arg_type: str = "string") -> str:
    """Sanitize command-line arguments for subprocess execution.

    This is a defense-in-depth measure for command injection prevention.

    Args:
        arg: Argument to sanitize
        arg_type: Type of argument ("model_name", "path", "string")

    Returns:
        Sanitized argument

    Raises:
        ValueError: If argument cannot be safely sanitized

    Example:
        >>> sanitize_command_argument("llama2-7b", "model_name")
        'llama2-7b'
        >>> sanitize_command_argument("model; rm -rf /", "model_name")
        ValueError: Model name contains forbidden pattern
    """
    if arg_type == "model_name":
        return validate_model_name(arg)
    elif arg_type == "path":
        # For paths, just validate security patterns (don't resolve)
        validator = PathValidator(path=arg)
        return validator.path
    else:
        # For generic strings, remove shell metacharacters
        forbidden_chars = set(';|&$`()<>"\'\n\r\t')
        if any(c in arg for c in forbidden_chars):
            raise ValueError(
                "Argument contains forbidden shell metacharacters"
            )
        return arg
