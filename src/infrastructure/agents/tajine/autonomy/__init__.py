"""
TAJINE Autonomy Module.

Adaptive autonomy management that determines the appropriate level of
human oversight for each action based on trust, confidence, and complexity.

Components:
- AutonomyManager: Decision engine for action-level autonomy
- AutonomyDecision: What the agent should do (AUTONOMOUS, PROPOSE, ASK, ESCALATE)
- ActionContext: Context for making autonomy decisions

Uses TrustManager from ../trust.py for underlying trust score computation.
"""

from src.infrastructure.agents.tajine.autonomy.manager import (
    Action,
    ActionContext,
    AutonomyDecision,
    AutonomyManager,
    Outcome,
    OutcomeType,
)

__all__ = [
    "AutonomyManager",
    "AutonomyDecision",
    "ActionContext",
    "Action",
    "Outcome",
    "OutcomeType",
]
