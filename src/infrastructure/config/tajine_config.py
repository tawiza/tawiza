# src/infrastructure/config/tajine_config.py
"""Centralized configuration for TAJINE MVP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TajineConfig:
    """Configuration for TAJINE system."""

    # LLM Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:27b"
    ollama_timeout: int = 120

    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Cache Configuration
    sqlite_cache_path: str = "./data/cache/tajine.db"

    # Trust Manager
    trust_persistence_path: str = "./data/trust/"

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> TajineConfig:
        """Load configuration from environment variables."""
        return cls(
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:27b"),
            ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "120")),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            sqlite_cache_path=os.getenv("SQLITE_CACHE_PATH", "./data/cache/tajine.db"),
            trust_persistence_path=os.getenv("TRUST_PERSISTENCE_PATH", "./data/trust/"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    @classmethod
    def from_env_file(cls, path: Path) -> TajineConfig:
        """Load configuration from .env file."""
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()

        return cls.from_env()

    def ensure_directories(self) -> None:
        """Create required directories."""
        Path(self.sqlite_cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.trust_persistence_path).mkdir(parents=True, exist_ok=True)


# Global singleton
_config: TajineConfig | None = None


def get_tajine_config() -> TajineConfig:
    """Get or create the global TAJINE configuration."""
    global _config
    if _config is None:
        env_file = Path(".env.tajine")
        if env_file.exists():
            _config = TajineConfig.from_env_file(env_file)
        else:
            _config = TajineConfig.from_env()
        _config.ensure_directories()
    return _config
