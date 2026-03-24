"""Debate system orchestrating multi-agent validation.

This module provides the DebateSystem class that orchestrates multiple
validation agents in sequence to assess data quality and reliability.

Standard pipeline (3 agents):
    Chercheur -> Critique -> Vérificateur

Extended pipeline (6 agents):
    Chercheur -> SourceRanker -> Critique -> FactChecker -> Vérificateur -> Synthèse
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from src.domain.debate.agents import (
    AgentMessage,
    ChercheurAgent,
    CritiqueAgent,
    FactCheckerAgent,
    LLMProvider,
    SourceRankerAgent,
    SynthesisAgent,
    VerificateurAgent,
)


class DebateMode(Enum):
    """Debate mode determining which agents participate."""

    STANDARD = "standard"  # 3 agents: Chercheur, Critique, Vérificateur
    EXTENDED = "extended"  # 6 agents: All agents including fact-checking


@dataclass
class DebateResult:
    """Result of the multi-agent debate."""

    query: str
    timestamp: datetime
    messages: list[AgentMessage] = field(default_factory=list)
    final_confidence: float = 0.0
    verdict: str = ""
    issues: list[str] = field(default_factory=list)
    duration_ms: float = 0

    @property
    def is_high_confidence(self) -> bool:
        """Check if result has high confidence."""
        return self.final_confidence >= 80

    @property
    def is_valid(self) -> bool:
        """Check if result is valid (confidence >= 40)."""
        return self.final_confidence >= 40

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "final_confidence": self.final_confidence,
            "verdict": self.verdict,
            "is_high_confidence": self.is_high_confidence,
            "is_valid": self.is_valid,
            "issues": self.issues,
            "duration_ms": self.duration_ms,
            "debate_rounds": [
                {
                    "agent": m.agent,
                    "role": m.role,
                    "confidence": m.confidence,
                    "content": m.content,
                }
                for m in self.messages
            ],
        }


class DebateSystem:
    """Multi-agent debate system for data validation.

    The debate follows this flow in standard mode:
    1. Chercheur (Researcher) - Analyzes collected data
    2. Critique (Critic) - Questions and validates findings
    3. Vérificateur (Verifier) - Cross-validates and provides verdict

    Extended mode adds:
    - SourceRanker: After Chercheur, ranks source reliability
    - FactChecker: After Critique, verifies claims
    - Synthesis: After Vérificateur, creates summary

    Example:
        # Standard mode (3 agents)
        debate = DebateSystem()
        result = await debate.validate(
            query="startup IA Lille",
            data={"results": [...], "sources": [...]}
        )

        # Extended mode (6 agents)
        debate = DebateSystem(mode=DebateMode.EXTENDED)
        result = await debate.validate(
            query="startup IA Lille",
            data={"results": [...], "sources": [...]}
        )

        print(f"Confidence: {result.final_confidence}%")
        print(f"Verdict: {result.verdict}")
    """

    def __init__(
        self,
        mode: DebateMode = DebateMode.STANDARD,
        llm: LLMProvider | None = None,
    ):
        """Initialize debate system with agents.

        Args:
            mode: Debate mode (STANDARD or EXTENDED)
            llm: Optional LLM provider for all agents
        """
        self.mode = mode
        self._llm = llm

        # Core agents (always active)
        self.chercheur = ChercheurAgent(llm=llm)
        self.critique = CritiqueAgent(llm=llm)
        self.verificateur = VerificateurAgent(llm=llm)

        # Extended agents (only in EXTENDED mode)
        self.source_ranker = SourceRankerAgent(llm=llm)
        self.fact_checker = FactCheckerAgent(llm=llm)
        self.synthesis = SynthesisAgent(llm=llm)

    async def validate(
        self,
        query: str,
        data: dict[str, Any],
        mode: DebateMode | None = None,
    ) -> DebateResult:
        """Run multi-agent debate on data.

        Args:
            query: Original search query
            data: Data to validate (results, sources, etc.)
            mode: Override the default mode for this validation

        Returns:
            DebateResult with final confidence and verdict
        """
        active_mode = mode or self.mode
        start_time = datetime.utcnow()
        messages: list[AgentMessage] = []

        logger.info(f"Starting {active_mode.value} debate for query: {query}")

        # Round 1: Chercheur analyzes data
        chercheur_msg = await self.chercheur.process(data, messages)
        messages.append(chercheur_msg)
        logger.debug(f"Chercheur: confidence={chercheur_msg.confidence}")

        # Extended: Source ranking after research
        if active_mode == DebateMode.EXTENDED:
            source_ranker_msg = await self.source_ranker.process(data, messages)
            messages.append(source_ranker_msg)
            logger.debug(f"SourceRanker: confidence={source_ranker_msg.confidence}")

        # Round 2: Critique questions findings
        critique_msg = await self.critique.process(data, messages)
        messages.append(critique_msg)
        logger.debug(f"Critique: confidence={critique_msg.confidence}")

        # Extended: Fact checking after critique
        if active_mode == DebateMode.EXTENDED:
            fact_checker_msg = await self.fact_checker.process(data, messages)
            messages.append(fact_checker_msg)
            logger.debug(f"FactChecker: confidence={fact_checker_msg.confidence}")

        # Round 3: Vérificateur provides assessment
        verificateur_msg = await self.verificateur.process(data, messages)
        messages.append(verificateur_msg)
        logger.debug(f"Vérificateur: confidence={verificateur_msg.confidence}")

        # Extended: Final synthesis
        final_msg = verificateur_msg
        if active_mode == DebateMode.EXTENDED:
            synthesis_msg = await self.synthesis.process(data, messages)
            messages.append(synthesis_msg)
            logger.debug(f"Synthesis: confidence={synthesis_msg.confidence}")
            final_msg = synthesis_msg

        # Extract final verdict
        verdict_lines = final_msg.content.split("\n")
        verdict = verdict_lines[0] if verdict_lines else "Verdict indéterminé"

        # Collect all issues
        all_issues = []
        for msg in messages:
            all_issues.extend(msg.issues)
        unique_issues = list(dict.fromkeys(all_issues))  # Preserve order, remove dupes

        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        result = DebateResult(
            query=query,
            timestamp=start_time,
            messages=messages,
            final_confidence=final_msg.confidence,
            verdict=verdict,
            issues=unique_issues,
            duration_ms=duration_ms,
        )

        logger.info(
            f"Debate completed ({active_mode.value}): confidence={result.final_confidence}%, "
            f"issues={len(result.issues)}, agents={len(messages)}, duration={duration_ms:.0f}ms"
        )

        return result

    async def quick_validate(
        self,
        data: dict[str, Any],
    ) -> tuple[float, str]:
        """Quick validation without full debate tracking.

        Args:
            data: Data to validate

        Returns:
            Tuple of (confidence, verdict)
        """
        result = await self.validate("quick_validation", data)
        return float(result.final_confidence), result.verdict
