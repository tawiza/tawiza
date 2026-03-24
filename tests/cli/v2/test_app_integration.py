"""Tests for CLI v2 app integration with ExperienceController."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.v2.app import app

runner = CliRunner()


class TestAppWelcome:
    """Test welcome screen integration."""

    def test_no_args_shows_welcome(self):
        """tawiza with no args shows welcome screen."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        # Should contain mascot or welcome text
        assert "tawiza" in result.stdout.lower() or "mp" in result.stdout.lower()

    def test_version_flag_shows_version(self):
        """tawiza --version shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.stdout.lower() or "2.0" in result.stdout


class TestAgentCommand:
    """Test agent command integration."""

    @patch("src.cli.v2.commands.simple.agent.agent_command")
    def test_agent_command_calls_handler(self, mock_handler):
        """Agent command delegates to handler."""
        result = runner.invoke(app, ["agent", "test task"])
        mock_handler.assert_called_once()
        # Check task was passed
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["task"] == "test task"

    @patch("src.cli.v2.commands.simple.agent.agent_command")
    def test_agent_with_data_option(self, mock_handler):
        """Agent command passes data option."""
        result = runner.invoke(app, ["agent", "analyze", "-d", "data.csv"])
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["data"] == "data.csv"


class TestStatusCommand:
    """Test status command."""

    @patch("src.cli.v2.commands.simple.status.status_command")
    def test_status_command_works(self, mock_handler):
        """Status command runs without error."""
        result = runner.invoke(app, ["status"])
        mock_handler.assert_called_once()
