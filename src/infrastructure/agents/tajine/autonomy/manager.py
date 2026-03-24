"""
AutonomyManager - Adaptive autonomy decision engine for TAJINE.

Determines the appropriate level of human oversight for each action based on:
- Trust score (from TrustManager)
- Data confidence (quality of information)
- Action complexity (risk/impact level)

Decision Formula:
    autonomy = trust_score × data_confidence × (1 - complexity × 0.5)

Thresholds:
    >= 0.7 → AUTONOMOUS (act independently)
    >= 0.5 → PROPOSE (show plan, quick approval)
    >= 0.3 → ASK (request decision)
    <  0.3 → ESCALATE (alert supervisor)
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from src.infrastructure.agents.tajine.trust import TrustManager


class AutonomyDecision(Enum):
    """What action the agent should take regarding human oversight."""

    AUTONOMOUS = "autonomous"  # Act independently, notify on completion
    PROPOSE = "propose"  # Show plan, wait for quick approval
    ASK = "ask"  # Present options, request decision
    ESCALATE = "escalate"  # Alert supervisor, pause execution


class OutcomeType(Enum):
    """Types of outcomes that affect trust score."""

    VALIDATED_SUCCESS = "validated_success"  # Human confirmed success
    IMPLICIT_SUCCESS = "implicit_success"  # No complaints = success
    MINOR_FAILURE = "minor_failure"  # Small error, recoverable
    MAJOR_FAILURE = "major_failure"  # Significant failure
    POSITIVE_FEEDBACK = "positive_feedback"  # Explicit positive feedback
    NEGATIVE_FEEDBACK = "negative_feedback"  # Explicit negative feedback


@dataclass
class Action:
    """Represents an action that requires autonomy decision."""

    name: str
    category: str  # 'data_collection', 'analysis', 'recommendation', 'execution'
    description: str = ""
    always_supervised: bool = False  # Force ASK for certain actions
    always_autonomous: bool = False  # Allow autonomous for safe actions
    risk_level: float = 0.5  # 0.0 (safe) to 1.0 (risky)
    reversible: bool = True  # Can the action be undone?

    def __post_init__(self):
        # Validate risk level
        self.risk_level = max(0.0, min(1.0, self.risk_level))


@dataclass
class ActionContext:
    """Context for making an autonomy decision."""

    action: Action
    data_confidence: float  # Quality of input data (0.0 to 1.0)
    complexity: float = 0.5  # Complexity of the task (0.0 to 1.0)
    urgency: float = 0.5  # Time pressure (0.0 to 1.0)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate ranges
        self.data_confidence = max(0.0, min(1.0, self.data_confidence))
        self.complexity = max(0.0, min(1.0, self.complexity))
        self.urgency = max(0.0, min(1.0, self.urgency))


@dataclass
class Outcome:
    """Records the outcome of an action for trust updates."""

    outcome_type: OutcomeType
    action_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: str = ""
    impact_score: float = 1.0  # Multiplier for delta (0.5 = half impact)

    def __post_init__(self):
        self.impact_score = max(0.1, min(2.0, self.impact_score))


class AutonomyManager:
    """
    Gestionnaire d'autonomie adaptative.

    Determines the appropriate level of human oversight for each action
    based on trust, confidence, and complexity.

    Features:
    - Dynamic thresholds based on action category
    - Daily decay to prevent overconfidence
    - Outcome recording for continuous learning
    - Hook for custom decision modifiers
    """

    # Base thresholds for autonomy decisions
    THRESHOLDS = {
        "autonomous": 0.70,
        "propose": 0.50,
        "ask": 0.30,
    }

    # Delta values for different outcome types
    DELTAS = {
        OutcomeType.VALIDATED_SUCCESS: 0.02,
        OutcomeType.IMPLICIT_SUCCESS: 0.005,
        OutcomeType.MINOR_FAILURE: -0.01,
        OutcomeType.MAJOR_FAILURE: -0.10,
        OutcomeType.POSITIVE_FEEDBACK: 0.05,
        OutcomeType.NEGATIVE_FEEDBACK: -0.08,
    }

    # Category-specific threshold adjustments
    CATEGORY_ADJUSTMENTS = {
        "data_collection": 0.1,  # More autonomous for data gathering
        "analysis": 0.05,  # Slightly more autonomous for analysis
        "recommendation": 0.0,  # Standard for recommendations
        "execution": -0.1,  # More cautious for execution
        "financial": -0.15,  # Very cautious for financial actions
        "deletion": -0.2,  # Most cautious for deletions
    }

    # Daily decay rate (applied once per day)
    DAILY_DECAY_RATE = 0.995  # 0.5% decay per day

    def __init__(
        self,
        trust_manager: TrustManager | None = None,
        initial_trust: float = 0.3,
    ):
        """
        Initialize AutonomyManager.

        Args:
            trust_manager: Existing TrustManager or None to create new
            initial_trust: Initial trust score if creating new TrustManager
        """
        self.trust_manager = trust_manager or TrustManager(initial_score=initial_trust)
        self._decision_history: list[dict[str, Any]] = []
        self._outcome_history: list[Outcome] = []
        self._last_decay_date: datetime | None = None
        self._decision_hooks: list[Callable[[ActionContext, float], float]] = []

        logger.info(f"AutonomyManager initialized with trust={self.trust_score:.2f}")

    @property
    def trust_score(self) -> float:
        """Get current trust score from underlying TrustManager."""
        return self.trust_manager.get_trust_score()

    def decide(
        self,
        context: ActionContext,
    ) -> AutonomyDecision:
        """
        Decide the appropriate level of autonomy for an action.

        Formula: autonomy = trust × data_confidence × (1 - complexity × 0.5)

        Args:
            context: ActionContext with action and context information

        Returns:
            AutonomyDecision indicating what the agent should do
        """
        action = context.action

        # Apply daily decay if needed
        self._apply_daily_decay()

        # Handle overrides first
        if action.always_supervised:
            decision = AutonomyDecision.ASK
            logger.debug(f"Action '{action.name}' forced to ASK (always_supervised)")
            self._record_decision(context, decision, "override_supervised")
            return decision

        if action.always_autonomous:
            decision = AutonomyDecision.AUTONOMOUS
            logger.debug(f"Action '{action.name}' forced to AUTONOMOUS (always_autonomous)")
            self._record_decision(context, decision, "override_autonomous")
            return decision

        # Compute autonomy score
        base_score = self._compute_autonomy_score(context)

        # Apply category adjustment
        category_adj = self.CATEGORY_ADJUSTMENTS.get(action.category, 0.0)

        # Apply custom hooks
        for hook in self._decision_hooks:
            try:
                base_score = hook(context, base_score)
            except Exception as e:
                logger.warning(f"Decision hook failed: {e}")

        # Adjust thresholds based on category and reversibility
        thresholds = self._get_adjusted_thresholds(action, category_adj)

        # Make decision
        if base_score >= thresholds["autonomous"]:
            decision = AutonomyDecision.AUTONOMOUS
        elif base_score >= thresholds["propose"]:
            decision = AutonomyDecision.PROPOSE
        elif base_score >= thresholds["ask"]:
            decision = AutonomyDecision.ASK
        else:
            decision = AutonomyDecision.ESCALATE

        logger.debug(
            f"Autonomy decision for '{action.name}': {decision.value} "
            f"(score={base_score:.2f}, trust={self.trust_score:.2f})"
        )

        self._record_decision(context, decision, "computed", base_score)
        return decision

    def _compute_autonomy_score(self, context: ActionContext) -> float:
        """
        Compute the raw autonomy score.

        Formula: trust × data_confidence × (1 - complexity × 0.5)

        Optionally factors in urgency as a slight boost.
        """
        trust = self.trust_score
        data_conf = context.data_confidence
        complexity = context.complexity
        urgency = context.urgency

        # Base formula from design document
        score = trust * data_conf * (1 - complexity * 0.5)

        # Urgency provides a small boost (max +0.05)
        urgency_boost = urgency * 0.05
        score = min(1.0, score + urgency_boost)

        # Factor in action risk level
        risk_penalty = context.action.risk_level * 0.1
        score = max(0.0, score - risk_penalty)

        return score

    def _get_adjusted_thresholds(self, action: Action, category_adj: float) -> dict[str, float]:
        """Get thresholds adjusted for action characteristics."""
        thresholds = dict(self.THRESHOLDS)

        # Lower thresholds if action is reversible (more forgiving)
        if action.reversible:
            for key in thresholds:
                thresholds[key] = max(0.1, thresholds[key] - 0.05)

        # Adjust based on category (e.g., execution requires higher trust)
        for key in thresholds:
            thresholds[key] = max(0.1, min(0.95, thresholds[key] - category_adj))

        return thresholds

    def record_outcome(self, outcome: Outcome) -> None:
        """
        Record an action outcome to update trust score.

        Args:
            outcome: Outcome object describing what happened
        """
        delta = self.DELTAS.get(outcome.outcome_type, 0.0)
        delta * outcome.impact_score

        # Update underlying trust manager based on outcome type
        if outcome.outcome_type in [OutcomeType.VALIDATED_SUCCESS, OutcomeType.IMPLICIT_SUCCESS]:
            self.trust_manager.record_success()
        elif outcome.outcome_type in [OutcomeType.MINOR_FAILURE, OutcomeType.MAJOR_FAILURE]:
            self.trust_manager.record_failure()
        elif outcome.outcome_type == OutcomeType.POSITIVE_FEEDBACK:
            self.trust_manager.record_feedback("positive")
        elif outcome.outcome_type == OutcomeType.NEGATIVE_FEEDBACK:
            self.trust_manager.record_feedback("negative")

        # Additional delta adjustment for our specific outcome types
        # The trust manager already applied its own delta, we just track
        self._outcome_history.append(outcome)

        logger.info(
            f"Recorded outcome: {outcome.outcome_type.value} for '{outcome.action_name}' "
            f"(new trust={self.trust_score:.2f})"
        )

    def _apply_daily_decay(self) -> None:
        """Apply daily decay to prevent trust score from staying too high."""
        today = datetime.now().date()

        if self._last_decay_date is None:
            self._last_decay_date = today
            return

        days_since_decay = (today - self._last_decay_date).days

        if days_since_decay > 0:
            # Apply decay for each day missed
            decay_factor = self.DAILY_DECAY_RATE**days_since_decay
            current_score = self.trust_score
            new_score = current_score * decay_factor

            # Manually update trust manager score via internal access
            self.trust_manager.trust_score = new_score
            self.trust_manager._update_autonomy_level()

            self._last_decay_date = today

            logger.debug(
                f"Applied {days_since_decay}-day decay: {current_score:.3f} → {new_score:.3f}"
            )

    def _record_decision(
        self,
        context: ActionContext,
        decision: AutonomyDecision,
        reason: str,
        score: float | None = None,
    ) -> None:
        """Record a decision for analysis."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": context.action.name,
            "category": context.action.category,
            "decision": decision.value,
            "reason": reason,
            "trust_score": self.trust_score,
            "data_confidence": context.data_confidence,
            "complexity": context.complexity,
            "computed_score": score,
        }
        self._decision_history.append(record)

        # Keep last 1000 decisions
        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-1000:]

    def add_decision_hook(self, hook: Callable[[ActionContext, float], float]) -> None:
        """
        Add a hook to modify autonomy score calculation.

        Hook signature: (context: ActionContext, current_score: float) -> float

        Use cases:
        - Project-specific overrides
        - Time-of-day adjustments
        - User preference integration
        """
        self._decision_hooks.append(hook)
        logger.debug(f"Added decision hook (total: {len(self._decision_hooks)})")

    def get_decision_stats(self) -> dict[str, Any]:
        """Get statistics about recent decisions."""
        if not self._decision_history:
            return {"total_decisions": 0}

        decisions = [d["decision"] for d in self._decision_history]

        return {
            "total_decisions": len(decisions),
            "autonomous_count": decisions.count("autonomous"),
            "propose_count": decisions.count("propose"),
            "ask_count": decisions.count("ask"),
            "escalate_count": decisions.count("escalate"),
            "autonomous_rate": decisions.count("autonomous") / len(decisions),
            "current_trust": self.trust_score,
            "outcomes_recorded": len(self._outcome_history),
        }

    def get_outcome_stats(self) -> dict[str, int]:
        """Get statistics about recorded outcomes."""
        stats = {ot.value: 0 for ot in OutcomeType}
        for outcome in self._outcome_history:
            stats[outcome.outcome_type.value] += 1
        return stats

    def reset_trust(self, new_score: float = 0.3) -> None:
        """
        Reset trust score (use with caution).

        Args:
            new_score: New trust score (default: conservative 0.3)
        """
        self.trust_manager.trust_score = max(0.0, min(1.0, new_score))
        self.trust_manager._update_autonomy_level()
        self._decision_history.clear()
        self._outcome_history.clear()

        logger.warning(f"Trust reset to {new_score}")

    def export_state(self) -> dict[str, Any]:
        """Export manager state for persistence."""
        return {
            "trust_state": self.trust_manager.export_state(),
            "last_decay_date": self._last_decay_date.isoformat() if self._last_decay_date else None,
            "decision_history": self._decision_history[-100:],
            "outcome_history": [
                {
                    "type": o.outcome_type.value,
                    "action": o.action_name,
                    "timestamp": o.timestamp.isoformat(),
                    "details": o.details,
                    "impact": o.impact_score,
                }
                for o in self._outcome_history[-100:]
            ],
        }

    def import_state(self, state: dict[str, Any]) -> None:
        """Import manager state from persistence."""
        if "trust_state" in state:
            self.trust_manager.import_state(state["trust_state"])

        if state.get("last_decay_date"):
            try:
                self._last_decay_date = datetime.fromisoformat(state["last_decay_date"]).date()
            except (ValueError, TypeError):
                self._last_decay_date = None

        self._decision_history = state.get("decision_history", [])

        self._outcome_history = []
        for o in state.get("outcome_history", []):
            try:
                self._outcome_history.append(
                    Outcome(
                        outcome_type=OutcomeType(o["type"]),
                        action_name=o["action"],
                        timestamp=datetime.fromisoformat(o["timestamp"]),
                        details=o.get("details", ""),
                        impact_score=o.get("impact", 1.0),
                    )
                )
            except (KeyError, ValueError):
                continue

        logger.info(f"Imported AutonomyManager state (trust={self.trust_score:.2f})")


# Convenience factory functions
def create_action(name: str, category: str = "analysis", risk: float = 0.5, **kwargs) -> Action:
    """Create an Action with sensible defaults."""
    return Action(name=name, category=category, risk_level=risk, **kwargs)


def create_context(
    action: Action,
    data_confidence: float = 0.7,
    complexity: float = 0.5,
    urgency: float = 0.5,
) -> ActionContext:
    """Create an ActionContext with sensible defaults."""
    return ActionContext(
        action=action,
        data_confidence=data_confidence,
        complexity=complexity,
        urgency=urgency,
    )
