"""Configuration management using Pydantic Settings.

This module provides a robust configuration system that:
- Loads from .env files
- Validates configuration values
- Provides type-safe access to settings
- Supports multiple environments (dev, staging, prod)
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from project root
_env_file = Path(__file__).resolve().parents[3] / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    url: PostgresDsn = Field(
        default="postgresql+asyncpg://tawiza:password@localhost:5432/tawiza",
        description="Database connection URL",
        validation_alias="DATABASE_URL",
    )
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=100)
    echo: bool = Field(default=False, description="Echo SQL queries")


class RedisSettings(BaseSettings):
    """Redis configuration."""

    url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
        validation_alias="REDIS_URL",
    )
    max_connections: int = Field(default=50, ge=1)


class MLflowSettings(BaseSettings):
    """MLflow configuration."""

    tracking_uri: str | None = Field(
        default=None,
        description="MLflow tracking server URI (set to enable MLflow)",
    )
    experiment_name: str = Field(default="tawiza-training")
    artifact_location: str | None = Field(
        default="s3://mlflow-artifacts",
        description="Artifact storage location",
    )


class MinIOSettings(BaseSettings):
    """MinIO (S3-compatible) configuration."""

    endpoint: str = Field(default="localhost:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    bucket: str = Field(default="tawiza-models")
    secure: bool = Field(default=False)

    # Additional buckets for specific purposes
    ollama_models_bucket: str = Field(
        default="ollama-models",
        description="Bucket for storing Ollama fine-tuned models",
    )
    mlflow_artifacts_bucket: str = Field(
        default="mlflow-artifacts",
        description="Bucket for MLflow artifacts",
    )


class LabelStudioSettings(BaseSettings):
    """Label Studio configuration."""

    url: str = Field(
        default="http://localhost:8080",
        description="Label Studio URL",
    )
    api_key: str = Field(default="", description="API key")
    project_id: int | None = Field(
        default=None,
        description="Default project ID",
    )


class VLLMSettings(BaseSettings):
    """vLLM inference server configuration."""

    url: str = Field(
        default="http://localhost:8001",
        description="vLLM server URL",
    )
    model_name: str = Field(
        default="meta-llama/Llama-2-7b-chat-hf",
        description="Default model name",
    )
    api_key: str | None = Field(default=None)
    timeout: int = Field(default=60, ge=1, le=300)


class OllamaSettings(BaseSettings):
    """Ollama configuration."""

    url: str = Field(
        default="http://localhost:11434",
        description="Ollama API URL",
    )
    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL (alternative)",
    )
    models_dir: str = Field(
        default="/usr/share/ollama/.ollama/models",
        description="Ollama models directory (for export)",
    )
    timeout: int = Field(default=120, ge=30, le=600)
    max_retries: int = Field(default=3, ge=1, le=10)

    # Connection pooling settings (pour OllamaClient)
    pool_connections: int = Field(
        default=10, ge=1, le=50, description="Number of keep-alive connections in pool"
    )
    pool_maxsize: int = Field(
        default=20, ge=1, le=100, description="Maximum number of connections in pool"
    )
    enable_http2: bool = Field(
        default=True, description="Enable HTTP/2 for connection multiplexing"
    )
    enable_cache: bool = Field(default=True, description="Enable response caching for GET requests")
    cache_ttl: int = Field(
        default=300, ge=60, le=3600, description="Cache TTL in seconds (default: 5 minutes)"
    )


class ROCmSettings(BaseSettings):
    """ROCm (AMD GPU) configuration."""

    path: str = Field(default="/opt/rocm")
    platform: str = Field(default="amd")
    gfx_version: str | None = Field(
        default=None,
        description="GPU architecture version (e.g., '10.3.0')",
    )


class TrainingSettings(BaseSettings):
    """Training configuration."""

    batch_size: int = Field(default=4, ge=1, le=128)
    gradient_accumulation_steps: int = Field(default=4, ge=1)
    learning_rate: float = Field(default=2e-5, gt=0)
    num_epochs: int = Field(default=3, ge=1, le=100)
    max_seq_length: int = Field(default=2048, ge=128, le=8192)
    lora_rank: int = Field(default=8, ge=1, le=256)
    lora_alpha: int = Field(default=16, ge=1, le=512)

    # Directories
    models_dir: str = Field(default="/models")
    data_dir: str = Field(default="/data")
    output_dir: str = Field(default="/output")


class RetrainingSettings(BaseSettings):
    """Automatic retraining configuration."""

    schedule: str = Field(
        default="0 2 * * 0",  # Every Sunday at 2 AM
        description="Cron expression for scheduled retraining",
    )
    min_new_samples: int = Field(
        default=100,
        ge=1,
        description="Minimum new samples to trigger retraining",
    )
    accuracy_threshold: float = Field(
        default=0.85,
        ge=0,
        le=1,
        description="Minimum accuracy threshold",
    )
    drift_threshold: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Data drift threshold",
    )


class DeploymentSettings(BaseSettings):
    """Deployment configuration."""

    canary_traffic_percentage: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Initial canary traffic percentage",
    )
    rollback_error_threshold: float = Field(
        default=0.1,
        ge=0,
        le=1,
        description="Error threshold for automatic rollback",
    )
    deployment_timeout: int = Field(
        default=600,
        ge=60,
        description="Deployment timeout in seconds",
    )


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""

    prometheus_port: int = Field(default=9090, ge=1024, le=65535)
    grafana_port: int = Field(default=3000, ge=1024, le=65535)
    log_level: str = Field(default="INFO")
    sentry_dsn: str | None = Field(default=None)
    enable_profiling: bool = Field(default=False)

    # Progress tracking settings (ProgressTracker)
    progress_cleanup_after: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Cleanup old progress events after N seconds (default: 1 hour)",
    )
    progress_max_events_per_task: int = Field(
        default=1000, ge=100, le=10000, description="Maximum events to store per task"
    )


class SecuritySettings(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    secret_key: str = Field(
        default="change-this-secret-key-in-production-please",
        min_length=32,
        description="Secret key for JWT tokens",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=15, ge=1)
    api_key_header: str = Field(default="X-API-Key")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is not default in production."""
        if v == "change-this-in-production":
            import os

            if os.getenv("APP_ENV") == "production":
                raise ValueError("SECRET_KEY must be changed in production")
        return v


class VectorDBSettings(BaseSettings):
    """Vector database (pgvector) configuration."""

    enabled: bool = Field(default=True, description="Enable vector database features")
    embedding_dim: int = Field(default=768, ge=128, le=4096, description="Embedding dimension")
    embedding_model: str = Field(
        default="nomic-embed-text", description="Ollama model for embeddings"
    )
    chunk_size: int = Field(
        default=512, ge=100, le=2048, description="Document chunk size (tokens)"
    )
    chunk_overlap: int = Field(default=50, ge=0, le=500, description="Chunk overlap size (tokens)")
    search_limit_default: int = Field(
        default=10, ge=1, le=100, description="Default number of search results"
    )
    search_distance_threshold: float = Field(
        default=1.0, ge=0.0, le=2.0, description="Default maximum cosine distance"
    )

    # Phase 3: LitServe optimization
    use_litserve: bool = Field(
        default=False, description="Use LitServe for 2-5x faster embedding generation (Phase 3)"
    )
    litserve_url: str = Field(default="http://localhost:8001", description="LitServe server URL")


class CodeExecutionSettings(BaseSettings):
    """Code execution configuration."""

    e2b_api_key: str | None = Field(
        default=None,
        description="E2B API key for cloud code execution",
    )
    default_backend: str = Field(
        default="auto",
        description="Default execution backend (auto, e2b_cloud, open_interpreter)",
    )
    prefer_cloud: bool = Field(
        default=True,
        description="Prefer cloud execution when both backends available",
    )
    default_timeout: int = Field(
        default=300,
        ge=1,
        le=600,
        description="Default code execution timeout in seconds",
    )


class Settings(BaseSettings):
    """Main application settings.

    This class aggregates all configuration settings and loads them from:
    1. Environment variables
    2. .env file
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Tawiza")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_prefix: str = Field(default="/api/v1")
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])

    # Feature flags
    enable_auto_annotation: bool = Field(default=True)
    enable_active_learning: bool = Field(default=True)
    enable_continuous_learning: bool = Field(default=True)
    enable_canary_deployment: bool = Field(default=True)

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    mlflow: MLflowSettings = Field(default_factory=MLflowSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    label_studio: LabelStudioSettings = Field(default_factory=LabelStudioSettings)
    vllm: VLLMSettings = Field(default_factory=VLLMSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    rocm: ROCmSettings = Field(default_factory=ROCmSettings)
    training: TrainingSettings = Field(default_factory=TrainingSettings)
    retraining: RetrainingSettings = Field(default_factory=RetrainingSettings)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    code_execution: CodeExecutionSettings = Field(default_factory=CodeExecutionSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env.lower() == "development"

    def setup_rocm_env(self) -> None:
        """Setup ROCm environment variables."""
        import os

        os.environ["ROCM_PATH"] = self.rocm.path
        os.environ["HIP_PLATFORM"] = self.rocm.platform

        if self.rocm.gfx_version:
            os.environ["HSA_OVERRIDE_GFX_VERSION"] = self.rocm.gfx_version


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Application settings

    Example:
        >>> from src.infrastructure.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.database.url)
    """
    return Settings()


# Export commonly used settings
settings = get_settings()
