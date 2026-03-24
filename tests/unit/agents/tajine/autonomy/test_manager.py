"""Tests for AutonomyManager."""

from datetime import datetime, timedelta

import pytest

from src.infrastructure.agents.tajine.autonomy.manager import (
    Action,
    ActionContext,
    AutonomyDecision,
    AutonomyManager,
    Outcome,
    OutcomeType,
    create_action,
    create_context,
)
from src.infrastructure.agents.tajine.trust import TrustManager


class TestAutonomyDecisionBasics:
    """Test basic autonomy decision making."""

    def test_low_trust_escalates(self):
        """Low trust score should escalate to human."""
        manager = AutonomyManager(initial_trust=0.1)
        action = create_action("test_action")
        context = create_context(action, data_confidence=0.5, complexity=0.5)

        decision = manager.decide(context)

        assert decision == AutonomyDecision.ESCALATE

    def test_high_trust_autonomous(self):
        """High trust with good data should be autonomous."""
        manager = AutonomyManager(initial_trust=0.9)
        action = create_action("test_action", risk=0.2)
        context = create_context(action, data_confidence=0.9, complexity=0.3)

        decision = manager.decide(context)

        assert decision == AutonomyDecision.AUTONOMOUS

    def test_medium_trust_proposes(self):
        """Medium-high trust with good data should propose."""
        manager = AutonomyManager(initial_trust=0.7)
        action = create_action("test_action", risk=0.2)  # Low risk
        context = create_context(action, data_confidence=0.8, complexity=0.3)

        decision = manager.decide(context)

        # score ~= 0.7 * 0.8 * (1 - 0.3*0.5) - 0.2*0.1 + 0.025 = 0.44
        assert decision in [AutonomyDecision.ASK, AutonomyDecision.PROPOSE]

    def test_always_supervised_overrides(self):
        """always_supervised flag should force ASK."""
        manager = AutonomyManager(initial_trust=0.95)
        action = Action(
            name="sensitive_action",
            category="financial",
            always_supervised=True,
        )
        context = create_context(action, data_confidence=1.0, complexity=0.0)

        decision = manager.decide(context)

        assert decision == AutonomyDecision.ASK

    def test_always_autonomous_overrides(self):
        """always_autonomous flag should force AUTONOMOUS."""
        manager = AutonomyManager(initial_trust=0.1)
        action = Action(
            name="safe_action",
            category="data_collection",
            always_autonomous=True,
        )
        context = create_context(action, data_confidence=0.3, complexity=0.9)

        decision = manager.decide(context)

        assert decision == AutonomyDecision.AUTONOMOUS


class TestAutonomyScore:
    """Test autonomy score calculation."""

    def test_formula_applies_correctly(self):
        """Verify: autonomy = trust × data_confidence × (1 - complexity × 0.5)."""
        manager = AutonomyManager(initial_trust=0.8)
        action = create_action("test", risk=0.0)  # No risk penalty

        # trust=0.8, data=0.5, complexity=0.4
        # score = 0.8 × 0.5 × (1 - 0.4 × 0.5) = 0.8 × 0.5 × 0.8 = 0.32
        context = create_context(action, data_confidence=0.5, complexity=0.4)
        score = manager._compute_autonomy_score(context)

        # Should be around 0.32 (with minor urgency boost of 0.025)
        assert 0.30 < score < 0.40

    def test_complexity_reduces_score(self):
        """Higher complexity should reduce autonomy score."""
        manager = AutonomyManager(initial_trust=0.8)
        action = create_action("test", risk=0.0)

        context_low = create_context(action, data_confidence=0.8, complexity=0.2)
        context_high = create_context(action, data_confidence=0.8, complexity=0.8)

        score_low = manager._compute_autonomy_score(context_low)
        score_high = manager._compute_autonomy_score(context_high)

        assert score_low > score_high

    def test_risk_level_reduces_score(self):
        """Higher risk should reduce autonomy score."""
        manager = AutonomyManager(initial_trust=0.8)

        action_low_risk = create_action("safe", risk=0.1)
        action_high_risk = create_action("risky", risk=0.9)

        context_low = create_context(action_low_risk, data_confidence=0.8)
        context_high = create_context(action_high_risk, data_confidence=0.8)

        score_low = manager._compute_autonomy_score(context_low)
        score_high = manager._compute_autonomy_score(context_high)

        assert score_low > score_high


class TestCategoryAdjustments:
    """Test category-based threshold adjustments."""

    def test_data_collection_more_autonomous(self):
        """Data collection should have lower thresholds (more autonomous)."""
        manager = AutonomyManager(initial_trust=0.75)

        action_data = create_action("fetch_data", category="data_collection", risk=0.2)
        action_exec = create_action("execute", category="execution", risk=0.2)

        context_data = create_context(action_data, data_confidence=0.85, complexity=0.3)
        context_exec = create_context(action_exec, data_confidence=0.85, complexity=0.3)

        decision_data = manager.decide(context_data)
        decision_exec = manager.decide(context_exec)

        # Data collection gets +0.1 category adjustment, execution gets -0.1
        # So data_collection should be more autonomous
        autonomy_order = ["escalate", "ask", "propose", "autonomous"]
        assert autonomy_order.index(decision_data.value) >= autonomy_order.index(
            decision_exec.value
        )

    def test_financial_more_cautious(self):
        """Financial actions should have higher thresholds (more cautious)."""
        manager = AutonomyManager(initial_trust=0.7)

        action_normal = create_action("analyze", category="analysis")
        action_financial = create_action("transfer", category="financial")

        context_normal = create_context(action_normal, data_confidence=0.8)
        context_financial = create_context(action_financial, data_confidence=0.8)

        decision_normal = manager.decide(context_normal)
        decision_financial = manager.decide(context_financial)

        # Financial should be more cautious (lower autonomy)
        autonomy_order = ["escalate", "ask", "propose", "autonomous"]
        assert autonomy_order.index(decision_financial.value) <= autonomy_order.index(
            decision_normal.value
        )


class TestOutcomeRecording:
    """Test outcome recording and trust updates."""

    def test_success_increases_trust(self):
        """Validated success should increase trust."""
        manager = AutonomyManager(initial_trust=0.5)
        initial_trust = manager.trust_score

        outcome = Outcome(
            outcome_type=OutcomeType.VALIDATED_SUCCESS,
            action_name="test_action",
        )
        manager.record_outcome(outcome)

        assert manager.trust_score > initial_trust

    def test_failure_decreases_trust(self):
        """Major failure should decrease trust."""
        manager = AutonomyManager(initial_trust=0.5)
        initial_trust = manager.trust_score

        outcome = Outcome(
            outcome_type=OutcomeType.MAJOR_FAILURE,
            action_name="test_action",
        )
        manager.record_outcome(outcome)

        assert manager.trust_score < initial_trust

    def test_outcome_history_tracked(self):
        """Outcomes should be tracked in history."""
        manager = AutonomyManager(initial_trust=0.5)

        for i in range(5):
            manager.record_outcome(
                Outcome(
                    outcome_type=OutcomeType.IMPLICIT_SUCCESS,
                    action_name=f"action_{i}",
                )
            )

        stats = manager.get_outcome_stats()
        assert stats["implicit_success"] == 5


class TestDailyDecay:
    """Test daily decay mechanism."""

    def test_decay_applied_after_days(self):
        """Trust should decay after days pass."""
        manager = AutonomyManager(initial_trust=0.9)

        # Simulate days passing
        manager._last_decay_date = (datetime.now() - timedelta(days=5)).date()
        initial_trust = manager.trust_score

        # Trigger decay by calling decide
        action = create_action("test")
        context = create_context(action)
        manager.decide(context)

        # Trust should have decayed
        assert manager.trust_score < initial_trust

    def test_no_decay_same_day(self):
        """No decay should occur on the same day."""
        manager = AutonomyManager(initial_trust=0.9)
        manager._last_decay_date = datetime.now().date()
        initial_trust = manager.trust_score

        action = create_action("test")
        context = create_context(action)
        manager.decide(context)

        assert manager.trust_score == initial_trust


class TestDecisionHooks:
    """Test custom decision hooks."""

    def test_hook_can_modify_score(self):
        """Custom hooks should be able to modify the score."""
        manager = AutonomyManager(initial_trust=0.5)

        # Hook that always boosts score
        def boost_hook(context: ActionContext, score: float) -> float:
            return min(1.0, score + 0.3)

        manager.add_decision_hook(boost_hook)

        action = create_action("test")
        context = create_context(action, data_confidence=0.5, complexity=0.5)

        # With boost, should be more autonomous
        decision = manager.decide(context)
        assert decision in [AutonomyDecision.AUTONOMOUS, AutonomyDecision.PROPOSE]


class TestStatePersistence:
    """Test state export and import."""

    def test_export_import_roundtrip(self):
        """State should survive export/import cycle."""
        manager = AutonomyManager(initial_trust=0.7)

        # Record some outcomes
        manager.record_outcome(
            Outcome(
                outcome_type=OutcomeType.VALIDATED_SUCCESS,
                action_name="test1",
            )
        )
        manager.record_outcome(
            Outcome(
                outcome_type=OutcomeType.MINOR_FAILURE,
                action_name="test2",
            )
        )

        # Make some decisions
        action = create_action("test")
        context = create_context(action)
        manager.decide(context)

        # Export
        state = manager.export_state()

        # Import to new manager
        new_manager = AutonomyManager(initial_trust=0.3)
        new_manager.import_state(state)

        # Verify state matches
        assert abs(new_manager.trust_score - manager.trust_score) < 0.01
        assert len(new_manager._outcome_history) == len(manager._outcome_history)


class TestConvenienceFunctions:
    """Test factory functions."""

    def test_create_action_defaults(self):
        """create_action should apply sensible defaults."""
        action = create_action("my_action")

        assert action.name == "my_action"
        assert action.category == "analysis"
        assert action.risk_level == 0.5
        assert action.reversible is True

    def test_create_context_defaults(self):
        """create_context should apply sensible defaults."""
        action = create_action("test")
        context = create_context(action)

        assert context.data_confidence == 0.7
        assert context.complexity == 0.5
        assert context.urgency == 0.5


class TestDecisionStats:
    """Test decision statistics."""

    def test_stats_track_decisions(self):
        """Decision stats should track all decision types."""
        manager = AutonomyManager(initial_trust=0.5)

        # Make various decisions
        for trust in [0.1, 0.4, 0.6, 0.9]:
            manager.trust_manager.trust_score = trust
            manager.trust_manager._update_autonomy_level()
            action = create_action("test")
            context = create_context(action, data_confidence=0.7)
            manager.decide(context)

        stats = manager.get_decision_stats()

        assert stats["total_decisions"] == 4
        assert "autonomous_rate" in stats
        assert "current_trust" in stats
