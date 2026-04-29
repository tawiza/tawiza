"""Tests for TrustManager - Adaptive autonomy management.

Tests the trust scoring system including:
- Trust score calculation
- Autonomy level transitions
- Time-decay of records
- Tool-specific trust tracking
- Performance metrics
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestTrustManagerImports:
    """Test TrustManager can be imported."""

    def test_import_trust_manager(self):
        """Test TrustManager can be imported."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        assert TrustManager is not None

    def test_import_autonomy_level(self):
        """Test AutonomyLevel enum can be imported."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel

        assert AutonomyLevel is not None

    def test_import_trust_record(self):
        """Test TrustRecord can be imported."""
        from src.infrastructure.agents.tajine.trust import TrustRecord

        assert TrustRecord is not None

    def test_import_from_package(self):
        """Test imports from tajine package."""
        from src.infrastructure.agents.tajine import AutonomyLevel, TrustManager

        assert TrustManager is not None
        assert AutonomyLevel is not None


class TestAutonomyLevels:
    """Test AutonomyLevel enum."""

    def test_autonomy_levels_exist(self):
        """Test all expected autonomy levels exist."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel

        assert hasattr(AutonomyLevel, "SUPERVISED")
        assert hasattr(AutonomyLevel, "ASSISTED")
        assert hasattr(AutonomyLevel, "SEMI_AUTONOMOUS")
        assert hasattr(AutonomyLevel, "AUTONOMOUS")
        assert hasattr(AutonomyLevel, "FULL_AUTONOMOUS")

    def test_autonomy_levels_ordered(self):
        """Test autonomy levels have increasing values."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel

        assert AutonomyLevel.SUPERVISED.value < AutonomyLevel.ASSISTED.value
        assert AutonomyLevel.ASSISTED.value < AutonomyLevel.SEMI_AUTONOMOUS.value
        assert AutonomyLevel.SEMI_AUTONOMOUS.value < AutonomyLevel.AUTONOMOUS.value
        assert AutonomyLevel.AUTONOMOUS.value < AutonomyLevel.FULL_AUTONOMOUS.value


class TestTrustManagerCreation:
    """Test TrustManager instantiation."""

    def test_create_default(self):
        """Test creating TrustManager with defaults."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        assert manager is not None
        assert manager.trust_score == 0.5

    def test_create_with_initial_score(self):
        """Test creating with custom initial score."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.75)

        assert manager.trust_score == 0.75

    def test_initial_autonomy_level(self):
        """Test initial autonomy level matches score."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager(initial_score=0.5)
        assert manager.autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS

        # 0.2 is below ASSISTED threshold (0.25), so should be SUPERVISED
        manager_low = TrustManager(initial_score=0.2)
        assert manager_low.autonomy_level == AutonomyLevel.SUPERVISED

        # 0.3 should be ASSISTED (>= 0.25 and < 0.5)
        manager_assisted = TrustManager(initial_score=0.3)
        assert manager_assisted.autonomy_level == AutonomyLevel.ASSISTED

    def test_empty_records_on_creation(self):
        """Test records list is empty on creation."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        assert len(manager.records) == 0


class TestTrustScoreUpdates:
    """Test trust score update mechanisms."""

    def test_record_success_increases_score(self):
        """Test success increases trust score."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)
        initial = manager.trust_score

        manager.record_success()

        assert manager.trust_score > initial

    def test_record_failure_decreases_score(self):
        """Test failure decreases trust score."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)
        initial = manager.trust_score

        manager.record_failure()

        assert manager.trust_score < initial

    def test_success_and_failure_have_impact(self):
        """Test both success and failure have impact on trust score."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager1 = TrustManager(initial_score=0.5)
        manager2 = TrustManager(initial_score=0.5)

        manager1.record_success()
        success_delta = manager1.trust_score - 0.5

        manager2.record_failure()
        failure_delta = 0.5 - manager2.trust_score

        # Both should have impact
        assert abs(success_delta) > 0
        assert abs(failure_delta) > 0

    def test_score_bounded_at_zero(self):
        """Test trust score cannot go below 0."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.05)

        # Multiple failures
        for _ in range(10):
            manager.record_failure()

        assert manager.trust_score >= 0.0

    def test_score_bounded_at_one(self):
        """Test trust score cannot exceed 1."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.95)

        # Multiple successes
        for _ in range(10):
            manager.record_success()

        assert manager.trust_score <= 1.0


class TestFeedbackProcessing:
    """Test user feedback handling."""

    def test_positive_feedback_increases_score(self):
        """Test positive feedback increases trust."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)
        initial = manager.trust_score

        manager.record_feedback("positive")

        assert manager.trust_score > initial

    def test_negative_feedback_decreases_score(self):
        """Test negative feedback decreases trust."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)
        initial = manager.trust_score

        manager.record_feedback("negative")

        assert manager.trust_score < initial

    def test_neutral_feedback_no_change(self):
        """Test neutral feedback doesn't change score."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)
        initial = manager.trust_score

        manager.record_feedback("neutral")

        assert manager.trust_score == initial

    def test_feedback_variations_recognized(self):
        """Test various feedback strings are recognized."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        # Positive variants
        for feedback in ["positive", "good", "excellent", "POSITIVE", "Good"]:
            manager = TrustManager(initial_score=0.5)
            manager.record_feedback(feedback)
            assert manager.trust_score > 0.5, f"'{feedback}' should be positive"

        # Negative variants
        for feedback in ["negative", "bad", "poor", "NEGATIVE", "Bad"]:
            manager = TrustManager(initial_score=0.5)
            manager.record_feedback(feedback)
            assert manager.trust_score < 0.5, f"'{feedback}' should be negative"


class TestAutonomyLevelTransitions:
    """Test autonomy level changes based on trust."""

    def test_low_trust_supervised(self):
        """Test low trust results in SUPERVISED."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager(initial_score=0.1)

        assert manager.autonomy_level == AutonomyLevel.SUPERVISED

    def test_medium_trust_semi_autonomous(self):
        """Test medium trust results in SEMI_AUTONOMOUS."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager(initial_score=0.6)

        assert manager.autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS

    def test_high_trust_full_autonomous(self):
        """Test high trust results in FULL_AUTONOMOUS."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager(initial_score=0.95)

        assert manager.autonomy_level == AutonomyLevel.FULL_AUTONOMOUS

    def test_autonomy_level_updates_on_score_change(self):
        """Test autonomy level updates when score changes."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager(initial_score=0.5)
        assert manager.autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS

        # Multiple failures should decrease level
        for _ in range(10):
            manager.record_failure()

        assert manager.autonomy_level.value < AutonomyLevel.SEMI_AUTONOMOUS.value


class TestTrustRecords:
    """Test trust record tracking."""

    def test_success_creates_record(self):
        """Test success creates a record."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_success()

        assert len(manager.records) == 1
        assert manager.records[0].event_type == "success"

    def test_failure_creates_record(self):
        """Test failure creates a record."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_failure()

        assert len(manager.records) == 1
        assert manager.records[0].event_type == "failure"

    def test_feedback_creates_record(self):
        """Test feedback creates a record with details."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_feedback("excellent")

        assert len(manager.records) == 1
        assert manager.records[0].event_type == "feedback"
        assert manager.records[0].details == "excellent"

    def test_record_has_timestamp(self):
        """Test records have timestamps."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        before = datetime.now()
        manager = TrustManager()
        manager.record_success()
        after = datetime.now()

        assert before <= manager.records[0].timestamp <= after


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    def test_success_count_tracked(self):
        """Test success count is tracked."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_success()
        manager.record_success()
        manager.record_success()

        assert manager.success_count == 3

    def test_failure_count_tracked(self):
        """Test failure count is tracked."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_failure()
        manager.record_failure()

        assert manager.failure_count == 2

    def test_get_success_rate(self):
        """Test success rate calculation."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_success()
        manager.record_success()
        manager.record_success()
        manager.record_failure()

        rate = manager.get_success_rate()

        assert rate == 0.75  # 3/4

    def test_success_rate_zero_when_no_tasks(self):
        """Test success rate is 0 when no tasks."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        rate = manager.get_success_rate()

        assert rate == 0.0

    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_success()
        manager.record_failure()

        metrics = manager.get_metrics()

        assert "trust_score" in metrics
        assert "autonomy_level" in metrics
        assert "success_count" in metrics
        assert "failure_count" in metrics
        assert "success_rate" in metrics


class TestToolSpecificTrust:
    """Test tool-specific trust tracking."""

    def test_record_tool_success(self):
        """Test recording success for specific tool."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_tool_outcome("data_collect", success=True)

        tool_trust = manager.get_tool_trust("data_collect")
        assert tool_trust > 0.5

    def test_record_tool_failure(self):
        """Test recording failure for specific tool."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_tool_outcome("veille_scan", success=False)

        tool_trust = manager.get_tool_trust("veille_scan")
        assert tool_trust < 0.5

    def test_unknown_tool_default_trust(self):
        """Test unknown tool returns default trust."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        tool_trust = manager.get_tool_trust("unknown_tool")
        assert tool_trust == 0.5  # Default

    def test_tool_trust_independent(self):
        """Test each tool has independent trust."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()
        manager.record_tool_outcome("data_collect", success=True)
        manager.record_tool_outcome("data_collect", success=True)
        manager.record_tool_outcome("veille_scan", success=False)

        assert manager.get_tool_trust("data_collect") > manager.get_tool_trust("veille_scan")


class TestTimeDecay:
    """Test time-based decay of trust records."""

    def test_recent_records_weighted_more(self):
        """Test recent records have more weight."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.5)

        # Old failure (should decay)
        with patch("src.infrastructure.agents.tajine.trust.datetime") as mock_dt:
            mock_dt.now.return_value = datetime.now() - timedelta(days=30)
            manager.record_failure()

        # Recent success
        manager.record_success()

        # With decay, recent success should dominate
        # Score should be closer to 0.5 than without decay
        assert manager.trust_score >= 0.45

    def test_get_effective_trust_with_decay(self):
        """Test effective trust calculation with decay."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        # This tests that the method exists and returns a value
        effective = manager.get_effective_trust(decay_days=7)

        assert 0.0 <= effective <= 1.0


class TestTAJINEAgentIntegration:
    """Test integration with TAJINEAgent."""

    def test_agent_has_trust_manager(self):
        """Test TAJINEAgent has trust_manager property."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert hasattr(agent, "trust_manager")
        assert agent.trust_manager is not None

    @pytest.mark.asyncio
    async def test_learn_updates_trust_on_success(self):
        """Test learn() updates trust on success."""
        from src.infrastructure.agents.tajine import TAJINEAgent
        from src.infrastructure.agents.tajine.trust import TrustManager

        agent = TAJINEAgent()
        # Reset to a score that can increase
        agent._trust_manager = TrustManager(initial_score=0.5)
        initial_score = agent.trust_manager.get_trust_score()

        await agent.learn({"success": True})

        assert agent.trust_manager.get_trust_score() > initial_score

    @pytest.mark.asyncio
    async def test_learn_updates_trust_on_failure(self):
        """Test learn() updates trust on failure."""
        from src.infrastructure.agents.tajine import TAJINEAgent
        from src.infrastructure.agents.tajine.trust import TrustManager

        agent = TAJINEAgent()
        # Reset to a score that can decrease, so the test does not depend
        # on the persisted state in data/tajine/trust.json (which may
        # already be at the 0.0 floor from previous runs)
        agent._trust_manager = TrustManager(initial_score=0.5)
        initial_score = agent.trust_manager.get_trust_score()

        await agent.learn({"success": False})

        assert agent.trust_manager.get_trust_score() < initial_score

    @pytest.mark.asyncio
    async def test_learn_processes_feedback(self):
        """Test learn() processes user feedback."""
        from src.infrastructure.agents.tajine import TAJINEAgent
        from src.infrastructure.agents.tajine.trust import TrustManager

        agent = TAJINEAgent()
        # Reset to a score that can increase
        agent._trust_manager = TrustManager(initial_score=0.5)
        initial_score = agent.trust_manager.get_trust_score()

        await agent.learn({"success": True, "user_feedback": "excellent"})

        # Both success and positive feedback should increase
        assert agent.trust_manager.get_trust_score() > initial_score + 0.03


class TestTrustPersistence:
    """Test trust state persistence."""

    def test_export_state(self):
        """Test exporting trust state."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager(initial_score=0.7)
        manager.record_success()
        manager.record_failure()

        state = manager.export_state()

        assert "trust_score" in state
        assert "autonomy_level" in state
        assert "success_count" in state
        assert "failure_count" in state
        assert "records" in state

    def test_import_state(self):
        """Test importing trust state."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        state = {
            "trust_score": 0.8,
            "autonomy_level": "AUTONOMOUS",
            "success_count": 10,
            "failure_count": 2,
            "tool_trust": {
                "data_collect": {"trust_score": 0.9, "success_count": 5, "failure_count": 1}
            },
            "records": [],
        }

        manager = TrustManager()
        manager.import_state(state)

        assert manager.trust_score == 0.8
        assert manager.autonomy_level == AutonomyLevel.AUTONOMOUS
        assert manager.success_count == 10
        assert manager.get_tool_trust("data_collect") == 0.9
