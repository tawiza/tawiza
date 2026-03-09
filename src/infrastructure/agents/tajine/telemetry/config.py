"""Telemetry configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class TelemetryConfig:
    """Configuration for TAJINE telemetry."""

    # Langfuse
    langfuse_enabled: bool = field(
        default_factory=lambda: os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
    )
    langfuse_host: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    )
    langfuse_public_key: str | None = field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY")
    )
    langfuse_secret_key: str | None = field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY")
    )

    # Prometheus
    prometheus_enabled: bool = field(
        default_factory=lambda: os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
    )
    prometheus_port: int = field(
        default_factory=lambda: int(os.getenv("PROMETHEUS_PORT", "8000"))
    )

    # Loki
    loki_enabled: bool = field(
        default_factory=lambda: os.getenv("LOKI_ENABLED", "true").lower() == "true"
    )
    loki_url: str = field(
        default_factory=lambda: os.getenv("LOKI_URL", "http://localhost:3100/loki/api/v1/push")
    )

    # General
    service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "tajine-agent")
    )
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        """Create config from environment variables."""
        return cls()
