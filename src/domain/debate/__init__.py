"""Multi-agent debate system for data validation.

This module provides a multi-agent system for validating data quality:

Standard Mode (3 agents):
    - ChercheurAgent: Analyzes and summarizes data
    - CritiqueAgent: Identifies issues and validates
    - VerificateurAgent: Cross-validates and provides verdict

Extended Mode (6 agents):
    - All standard agents plus:
    - SourceRankerAgent: Ranks sources by reliability
    - FactCheckerAgent: Verifies claims against authoritative sources
    - SynthesisAgent: Creates comprehensive final summary

Example:
    from src.domain.debate import DebateSystem, DebateMode

    # Standard debate
    debate = DebateSystem()
    result = await debate.validate("query", data)

    # Extended debate with all agents
    debate = DebateSystem(mode=DebateMode.EXTENDED)
    result = await debate.validate("query", data)
"""

from src.domain.debate.agents import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    ChercheurAgent,
    CritiqueAgent,
    FactCheckerAgent,
    LLMProvider,
    SourceRankerAgent,
    SynthesisAgent,
    VerificateurAgent,
)
from src.domain.debate.debate_system import DebateMode, DebateResult, DebateSystem

__all__ = [
    # Core types
    "AgentMessage",
    "AgentRole",
    "BaseAgent",
    "LLMProvider",
    # Standard agents
    "ChercheurAgent",
    "CritiqueAgent",
    "VerificateurAgent",
    # Extended agents
    "FactCheckerAgent",
    "SourceRankerAgent",
    "SynthesisAgent",
    # System
    "DebateMode",
    "DebateResult",
    "DebateSystem",
]
