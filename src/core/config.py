"""
Application Configuration
Centralized settings management with pydantic-settings
"""

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration"""

    url: PostgresDsn = Field(
        default="postgresql+asyncpg://tawiza:changeme@localhost:5432/tawiza",
        description="Database connection URL (override via DATABASE_URL env var)",
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max connections overflow")
    echo: bool = Field(default=False, description="Echo SQL queries")

    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=".env", case_sensitive=False)


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration"""

    base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    model_name: str = Field(default="qwen2.5:7b", description="Default model name")
    embedding_model: str = Field(default="nomic-embed-text", description="Embedding model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout: int = Field(default=300, description="Request timeout in seconds")

    model_config = SettingsConfigDict(env_prefix="OLLAMA_", env_file=".env", case_sensitive=False)


class VectorDBSettings(BaseSettings):
    """Vector database configuration"""

    enabled: bool = Field(default=True, description="Enable vector database")
    embedding_dim: int = Field(default=768, description="Embedding dimension")
    chunk_size: int = Field(default=512, description="Document chunk size")
    chunk_overlap: int = Field(default=50, description="Chunk overlap size")

    model_config = SettingsConfigDict(env_prefix="VECTORDB_", env_file=".env", case_sensitive=False)


class RedisSettings(BaseSettings):
    """Redis configuration"""

    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env")


class APISettings(BaseSettings):
    """API configuration"""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    prefix: str = Field(default="/api/v1")
    cors_origins: list = Field(default=["http://localhost:3000", "http://localhost:8000"])

    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env")


class Settings(BaseSettings):
    """Main application settings"""

    app_name: str = Field(default="Tawiza", description="Application name")
    app_env: str = Field(default="development", description="Environment")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    vectordb: VectorDBSettings = Field(default_factory=VectorDBSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    api: APISettings = Field(default_factory=APISettings)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


# Singleton instance
settings = Settings()
