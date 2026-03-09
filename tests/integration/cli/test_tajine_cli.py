"""Integration tests for TAJINE CLI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestTajineCLI:
    """Test TAJINE CLI commands."""

    def test_status_command(self):
        """Should show system status."""
        from src.cli.v2.commands.simple.tajine import app

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "TAJINE System Status" in result.stdout or "Configuration" in result.stdout

    def test_analyze_command_help(self):
        """Should show analyze help."""
        from src.cli.v2.commands.simple.tajine import app

        result = runner.invoke(app, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "territorial" in result.stdout.lower() or "query" in result.stdout.lower()

    def test_main_help_shows_subcommands(self):
        """Should show available subcommands in main help."""
        from src.cli.v2.commands.simple.tajine import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "status" in result.stdout.lower()
        assert "analyze" in result.stdout.lower()

    @patch("src.cli.v2.commands.simple.tajine.create_tajine_agent")
    @patch("src.cli.v2.commands.simple.tajine.get_tajine_config")
    def test_analyze_uses_factory_and_config(self, mock_config, mock_create):
        """Should use create_tajine_agent factory and get_tajine_config."""
        from src.cli.v2.commands.simple.tajine import app

        # Mock config
        mock_config_obj = MagicMock()
        mock_config_obj.ollama_model = "qwen3:14b"
        mock_config_obj.ollama_host = "http://localhost:11434"
        mock_config.return_value = mock_config_obj

        # Mock agent creation
        mock_agent = MagicMock()
        mock_agent.execute_task = AsyncMock(
            return_value={
                "status": "completed",
                "result": {"summary": "test"},
                "task_id": "test-123",
                "confidence": 0.8,
                "metadata": {},
            }
        )
        mock_create.return_value = mock_agent

        result = runner.invoke(app, ["analyze", "Test query"])

        # Should call both functions (config may be called multiple times)
        assert mock_config.called, "get_tajine_config should be called"
        assert mock_create.called, "create_tajine_agent should be called"

    @patch("src.cli.v2.commands.simple.tajine.get_tajine_config")
    def test_status_command_shows_config(self, mock_config):
        """Should display configuration in status command."""
        from src.cli.v2.commands.simple.tajine import app
        from src.infrastructure.config.tajine_config import TajineConfig

        # Use real TajineConfig with test values (avoids MagicMock render issues)
        test_config = TajineConfig(
            ollama_host="http://localhost:11434",
            ollama_model="qwen3:14b",
            ollama_timeout=120,
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
            sqlite_cache_path="./data/cache/tajine.db",
            trust_persistence_path="./data/trust/",
            log_level="INFO",
        )
        mock_config.return_value = test_config

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        mock_config.assert_called_once()
        # Should show config info
        assert "qwen3:14b" in result.stdout or "localhost" in result.stdout
