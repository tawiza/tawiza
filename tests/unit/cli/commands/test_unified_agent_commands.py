"""Tests for Unified Adaptive Agent CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.commands.unified_agent import app
from src.infrastructure.agents.unified import (
    AutonomyLevel,
    TaskRequest,
    TaskResult,
    TaskStatus,
    UnifiedAdaptiveAgent,
)

runner = CliRunner()


class TestUAAStatusCommand:
    """Test uaa status command."""

    def test_status_shows_autonomy_level(self):
        """Should display current autonomy level."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.get_status.return_value = {
                "autonomy_level": "SUPERVISED",
                "autonomy_level_value": 0,
                "trust_score": 0.25,
                "learning_enabled": True,
                "pending_tasks": 0,
                "in_cooldown": False,
            }
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "SUPERVISED" in result.stdout

    def test_status_shows_trust_score(self):
        """Should display trust score."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.get_status.return_value = {
                "autonomy_level": "ASSISTED",
                "trust_score": 0.45,
                "learning_enabled": True,
                "pending_tasks": 2,
                "in_cooldown": False,
            }
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "0.45" in result.stdout or "45" in result.stdout


class TestUAAExecuteCommand:
    """Test uaa execute command."""

    def test_execute_task(self):
        """Should execute a task."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.execute = AsyncMock(
                return_value=TaskResult(
                    task_id="task_123",
                    status=TaskStatus.COMPLETED,
                    output={"success": True, "data": "result"},
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["execute", "Scrape data from example.com"])

            assert result.exit_code == 0
            assert "COMPLETED" in result.stdout or "completed" in result.stdout.lower()

    def test_execute_awaiting_approval(self):
        """Should show awaiting approval status."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.execute = AsyncMock(
                return_value=TaskResult(
                    task_id="task_456",
                    status=TaskStatus.AWAITING_APPROVAL,
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["execute", "Execute dangerous code"])

            assert result.exit_code == 0
            assert "approval" in result.stdout.lower()


class TestUAAApproveCommand:
    """Test uaa approve command."""

    def test_approve_pending_task(self):
        """Should approve a pending task."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.approve = AsyncMock(
                return_value=TaskResult(
                    task_id="task_123",
                    status=TaskStatus.COMPLETED,
                    output={"success": True},
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["approve", "task_123"])

            assert result.exit_code == 0
            mock_agent.approve.assert_called_once_with("task_123")

    def test_approve_nonexistent_task(self):
        """Should handle nonexistent task."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.approve = AsyncMock(
                return_value=TaskResult(
                    task_id="task_999",
                    status=TaskStatus.FAILED,
                    error="Task task_999 not found in pending",
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["approve", "task_999"])

            assert result.exit_code == 0
            assert "not found" in result.stdout.lower() or "failed" in result.stdout.lower()


class TestUAARejectCommand:
    """Test uaa reject command."""

    def test_reject_pending_task(self):
        """Should reject a pending task."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.reject = AsyncMock(
                return_value=TaskResult(
                    task_id="task_123",
                    status=TaskStatus.FAILED,
                    error="Rejected: Too risky",
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["reject", "task_123", "--reason", "Too risky"])

            assert result.exit_code == 0
            mock_agent.reject.assert_called_once()


class TestUAAFeedbackCommand:
    """Test uaa feedback command."""

    def test_positive_feedback(self):
        """Should record positive feedback."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.trust_score = 0.5  # Provide actual float for formatting
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["feedback", "task_123", "positive"])

            assert result.exit_code == 0
            mock_agent.record_feedback.assert_called_once_with(
                task_id="task_123",
                feedback="positive",
                correction=None,
            )

    def test_negative_feedback_with_correction(self):
        """Should record negative feedback with correction."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.trust_score = 0.3  # Provide actual float for formatting
            mock_get.return_value = mock_agent

            result = runner.invoke(
                app,
                [
                    "feedback",
                    "task_123",
                    "negative",
                    "--correction",
                    "Should have clicked the submit button",
                ],
            )

            assert result.exit_code == 0
            mock_agent.record_feedback.assert_called_once_with(
                task_id="task_123",
                feedback="negative",
                correction="Should have clicked the submit button",
            )


class TestUAAStatsCommand:
    """Test uaa stats command."""

    def test_stats_shows_completion_stats(self):
        """Should show task completion statistics."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.get_stats.return_value = {
                "tasks_completed": 42,
                "tasks_failed": 3,
                "tasks_pending": 1,
                "success_rate": 0.93,
                "trust_stats": {
                    "score": 0.75,
                    "level": "AUTONOMOUS",
                },
                "learning_stats": {
                    "examples_collected": 45,
                    "cycles_completed": 2,
                },
            }
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["stats"])

            assert result.exit_code == 0
            assert "42" in result.stdout
            assert "93" in result.stdout or "0.93" in result.stdout


class TestUAALearnCommand:
    """Test uaa learn command."""

    def test_trigger_learning(self):
        """Should trigger learning cycle."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.learning_engine.should_trigger_learning.return_value = True
            mock_agent.learning_engine.run_full_cycle = AsyncMock(
                return_value=MagicMock(
                    state="COMPLETED",
                    metrics=MagicMock(accuracy_before=0.8, accuracy_after=0.85),
                )
            )
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["learn"])

            assert result.exit_code == 0
            mock_agent.learning_engine.run_full_cycle.assert_called_once()

    def test_learn_not_ready(self):
        """Should inform when not ready for learning."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.learning_engine.should_trigger_learning.return_value = False
            mock_agent.learning_engine.get_stats.return_value = {
                "examples_collected": 5,
                "min_examples": 50,
            }
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["learn"])

            assert result.exit_code == 0
            assert "not ready" in result.stdout.lower() or "5" in result.stdout


class TestUAAConfigCommand:
    """Test uaa config command."""

    def test_show_config(self):
        """Should show current configuration."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.config.llm_model = "qwen2.5-coder:7b"
            mock_agent.config.max_concurrent_tasks = 5
            mock_agent.config.default_timeout = 300
            mock_agent.config.trust.metric_weight = 0.4
            mock_agent.config.trust.feedback_weight = 0.35
            mock_agent.config.trust.history_weight = 0.25
            mock_agent.config.trust.error_cooldown = 60
            mock_agent.config.learning.auto_learning_enabled = True
            mock_agent.config.learning.min_examples_for_training = 50
            mock_agent.config.learning.finetune_threshold = 0.8
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["config"])

            assert result.exit_code == 0
            assert "qwen2.5-coder:7b" in result.stdout

    def test_set_autonomy_level(self):
        """Should allow setting autonomy level."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.config.llm_model = "qwen2.5-coder:7b"
            mock_agent.config.max_concurrent_tasks = 5
            mock_agent.config.default_timeout = 300
            mock_agent.config.trust.metric_weight = 0.4
            mock_agent.config.trust.feedback_weight = 0.35
            mock_agent.config.trust.history_weight = 0.25
            mock_agent.config.trust.error_cooldown = 60
            mock_agent.config.learning.auto_learning_enabled = True
            mock_agent.config.learning.min_examples_for_training = 50
            mock_agent.config.learning.finetune_threshold = 0.8
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["config", "--set-level", "AUTONOMOUS"])

            assert result.exit_code == 0


class TestUAAPendingCommand:
    """Test uaa pending command."""

    def test_list_pending_tasks(self):
        """Should list pending tasks."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent._pending_tasks = {
                "task_1": TaskRequest(task_id="task_1", description="First task"),
                "task_2": TaskRequest(task_id="task_2", description="Second task"),
            }
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["pending"])

            assert result.exit_code == 0
            assert "task_1" in result.stdout
            assert "task_2" in result.stdout

    def test_no_pending_tasks(self):
        """Should show message when no pending tasks."""
        with patch("src.cli.commands.unified_agent.get_agent") as mock_get:
            mock_agent = MagicMock()
            mock_agent._pending_tasks = {}
            mock_get.return_value = mock_agent

            result = runner.invoke(app, ["pending"])

            assert result.exit_code == 0
            assert "no pending" in result.stdout.lower() or "empty" in result.stdout.lower()
