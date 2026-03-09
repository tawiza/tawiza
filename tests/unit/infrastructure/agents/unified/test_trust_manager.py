"""Tests for Trust Manager."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.infrastructure.agents.unified.config import AutonomyLevel, TrustConfig
from src.infrastructure.agents.unified.trust_manager import TrustManager


class TestTrustManagerInit:
    """Test trust manager initialization."""

    def test_initial_level_is_supervised(self):
        """Should start at supervised level."""
        manager = TrustManager()
        assert manager.level == AutonomyLevel.SUPERVISED

    def test_initial_score_is_zero(self):
        """Should start with zero trust score."""
        manager = TrustManager()
        assert manager.score == 0.0

    def test_custom_config(self):
        """Should accept custom config."""
        config = TrustConfig(metrics_weight=0.5, feedback_weight=0.3, history_weight=0.2)
        manager = TrustManager(config)
        assert manager.config.metrics_weight == 0.5


class TestTrustScoreCalculation:
    """Test trust score calculation."""

    def test_calculate_score_all_perfect(self):
        """Should return high score for perfect metrics."""
        manager = TrustManager()
        manager.record_metrics(accuracy=1.0, success_rate=1.0, error_rate=0.0)
        manager.record_feedback(positive=10, negative=0)
        manager.record_history(days_without_incident=30, tasks_completed=100)

        score = manager.calculate_score()
        assert score >= 0.9

    def test_calculate_score_all_bad(self):
        """Should return low score for bad metrics."""
        manager = TrustManager()
        manager.record_metrics(accuracy=0.0, success_rate=0.0, error_rate=1.0)
        manager.record_feedback(positive=0, negative=10)
        manager.record_history(days_without_incident=0, tasks_completed=0)

        score = manager.calculate_score()
        assert score < 0.3

    def test_calculate_score_mixed(self):
        """Should return medium score for mixed metrics."""
        manager = TrustManager()
        manager.record_metrics(accuracy=0.7, success_rate=0.8, error_rate=0.1)
        manager.record_feedback(positive=7, negative=3)
        manager.record_history(days_without_incident=15, tasks_completed=50)

        score = manager.calculate_score()
        assert 0.5 < score < 0.8

    def test_score_with_no_feedback(self):
        """Should use neutral feedback when none recorded."""
        manager = TrustManager()
        manager.record_metrics(accuracy=0.8, success_rate=0.9, error_rate=0.1)
        manager.record_history(days_without_incident=10, tasks_completed=20)

        score = manager.calculate_score()
        # Should still calculate, using 0.5 for feedback
        assert 0.3 < score < 0.8


class TestAutonomyLevelProgression:
    """Test autonomy level changes."""

    def test_level_increases_with_high_score(self):
        """Should increase level when score exceeds threshold."""
        manager = TrustManager()
        manager._score = 0.35  # Above level 1 threshold (0.3)

        manager.update_level()
        assert manager.level == AutonomyLevel.ASSISTED

    def test_level_increases_to_semi_autonomous(self):
        """Should reach semi-autonomous at 0.5+ score."""
        manager = TrustManager()
        manager._score = 0.55

        manager.update_level()
        assert manager.level == AutonomyLevel.SEMI_AUTONOMOUS

    def test_level_increases_to_autonomous(self):
        """Should reach autonomous at 0.7+ score."""
        manager = TrustManager()
        manager._score = 0.75

        manager.update_level()
        assert manager.level == AutonomyLevel.AUTONOMOUS

    def test_level_increases_to_full_autonomous(self):
        """Should reach full autonomous at 0.9+ score."""
        manager = TrustManager()
        manager._score = 0.95

        manager.update_level()
        assert manager.level == AutonomyLevel.FULL_AUTONOMOUS

    def test_level_decreases_on_regression(self):
        """Should decrease level on score regression."""
        config = TrustConfig(rollback_on_regression=True)
        manager = TrustManager(config)
        manager._level = AutonomyLevel.AUTONOMOUS
        manager._score = 0.4  # Below level 3 threshold

        manager.update_level()
        assert manager.level < AutonomyLevel.AUTONOMOUS

    def test_level_stays_on_no_regression_config(self):
        """Should not decrease if rollback disabled."""
        config = TrustConfig(rollback_on_regression=False)
        manager = TrustManager(config)
        manager._level = AutonomyLevel.AUTONOMOUS
        manager._score = 0.4  # Below level 3 threshold

        manager.update_level()
        assert manager.level == AutonomyLevel.AUTONOMOUS


class TestCooldown:
    """Test cooldown mechanism."""

    def test_cooldown_prevents_increase(self):
        """Should not increase level during cooldown."""
        manager = TrustManager()
        manager.trigger_cooldown()
        manager._score = 0.95

        old_level = manager.level
        manager.update_level()
        assert manager.level == old_level

    def test_cooldown_expires(self):
        """Should allow increase after cooldown expires."""
        manager = TrustManager()
        # Set cooldown that has already expired
        manager._cooldown_until = datetime.now(UTC) - timedelta(hours=1)
        manager._score = 0.95

        manager.update_level()
        assert manager.level == AutonomyLevel.FULL_AUTONOMOUS

    def test_is_in_cooldown_property(self):
        """Should correctly report cooldown status."""
        manager = TrustManager()
        assert manager.is_in_cooldown is False

        manager.trigger_cooldown()
        assert manager.is_in_cooldown is True


class TestTaskPermissions:
    """Test task permission checks."""

    def test_supervised_requires_approval_for_all(self):
        """Supervised level should require approval for everything."""
        manager = TrustManager()
        manager._level = AutonomyLevel.SUPERVISED

        assert manager.requires_approval("web_scraping") is True
        assert manager.requires_approval("fine_tuning") is True
        assert manager.requires_approval("annotation") is True
        assert manager.requires_approval("code_execution") is True

    def test_assisted_allows_basic_tasks(self):
        """Assisted level should still need approval for most tasks."""
        manager = TrustManager()
        manager._level = AutonomyLevel.ASSISTED

        # Assisted meets requirement for basic tasks
        assert manager.requires_approval("web_scraping") is False
        assert manager.requires_approval("code_execution") is False
        # But not for higher tasks
        assert manager.requires_approval("annotation") is True

    def test_semi_autonomous_allows_annotation(self):
        """Semi-autonomous should allow annotation."""
        manager = TrustManager()
        manager._level = AutonomyLevel.SEMI_AUTONOMOUS

        assert manager.requires_approval("annotation") is False
        assert manager.requires_approval("dataset_creation") is False
        # But not fine-tuning
        assert manager.requires_approval("fine_tuning") is True

    def test_autonomous_allows_most_tasks(self):
        """Autonomous level should allow most tasks except fine-tuning."""
        manager = TrustManager()
        manager._level = AutonomyLevel.AUTONOMOUS

        assert manager.requires_approval("web_scraping") is False
        assert manager.requires_approval("annotation") is False
        # Fine-tuning still requires approval at level 3
        assert manager.requires_approval("fine_tuning") is True

    def test_full_autonomous_allows_all(self):
        """Full autonomous should allow everything."""
        manager = TrustManager()
        manager._level = AutonomyLevel.FULL_AUTONOMOUS

        assert manager.requires_approval("fine_tuning") is False
        assert manager.requires_approval("model_deployment") is False

    def test_unknown_task_requires_supervised(self):
        """Unknown tasks should require supervised level."""
        manager = TrustManager()
        manager._level = AutonomyLevel.ASSISTED

        # Unknown task defaults to SUPERVISED requirement
        assert manager.requires_approval("unknown_dangerous_task") is False


class TestSerialization:
    """Test serialization to dict."""

    def test_to_dict(self):
        """Should export state to dictionary."""
        manager = TrustManager()
        manager._score = 0.75
        manager._level = AutonomyLevel.AUTONOMOUS

        data = manager.to_dict()

        assert data["level"] == "AUTONOMOUS"
        assert data["level_value"] == 3
        assert data["score"] == 0.75
        assert "metrics" in data
        assert "feedback" in data
        assert "history" in data
        assert "in_cooldown" in data
        assert "last_update" in data
