# tests/unit/config/test_tajine_config.py
"""Tests for TAJINE configuration loader."""

import os
from pathlib import Path

import pytest


class TestTajineConfig:
    """Test TAJINE configuration loading."""

    def test_load_from_env_file(self, tmp_path: Path):
        """Should load config from .env file."""
        # Create temp env file
        env_file = tmp_path / ".env.tajine"
        env_file.write_text("OLLAMA_HOST=http://test:11434\nOLLAMA_MODEL=test-model\n")

        from src.infrastructure.config.tajine_config import TajineConfig

        config = TajineConfig.from_env_file(env_file)

        assert config.ollama_host == "http://test:11434"
        assert config.ollama_model == "test-model"

    def test_default_values(self):
        """Should use defaults when env vars missing."""
        from src.infrastructure.config.tajine_config import TajineConfig

        config = TajineConfig()

        assert config.ollama_host == "http://localhost:11434"
        assert config.ollama_model == "qwen3:14b"
        assert config.neo4j_uri == "bolt://localhost:7687"

    def test_neo4j_config(self):
        """Should load Neo4j configuration."""
        from src.infrastructure.config.tajine_config import TajineConfig

        os.environ["NEO4J_URI"] = "bolt://neo4j-server:7687"
        os.environ["NEO4J_USER"] = "admin"
        os.environ["NEO4J_PASSWORD"] = "secret"

        try:
            config = TajineConfig.from_env()

            assert config.neo4j_uri == "bolt://neo4j-server:7687"
            assert config.neo4j_user == "admin"
            assert config.neo4j_password == "secret"
        finally:
            # Cleanup
            del os.environ["NEO4J_URI"]
            del os.environ["NEO4J_USER"]
            del os.environ["NEO4J_PASSWORD"]
