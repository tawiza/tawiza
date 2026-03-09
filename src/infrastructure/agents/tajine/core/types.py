"""TAJINE Core Types - Shared dataclasses for the algorithm."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EvaluationDecision(Enum):
    """Decision after evaluating data."""
    ACCEPT = "accept"      # Score >= 0.7
    VERIFY = "verify"      # 0.4 <= Score < 0.7
    REJECT = "reject"      # Score < 0.4


class AutonomyDecision(Enum):
    """Level of autonomy for an action."""
    AUTONOMOUS = "autonomous"  # Act without asking
    PROPOSE = "propose"        # Show plan, wait for quick OK
    ASK = "ask"               # Ask for decision
    ESCALATE = "escalate"     # Alert supervisor


@dataclass
class HuntContext:
    """Context for a data hunt operation."""
    query: str
    territory: str
    mode: str = "normal"  # normal | question | combler
    kg_state: dict | None = None
    max_sources: int = 3
    timeout_seconds: int = 30


@dataclass
class RawData:
    """Raw data fetched from a source."""
    source: str
    content: dict[str, Any]
    url: str
    fetched_at: datetime
    quality_hint: float = 0.5  # 0.0 - 1.0


@dataclass
class EvaluationResult:
    """Result of evaluating data on 3 dimensions."""
    reliability: float      # Source credibility (0.0 - 1.0)
    coherence: float        # KG consistency (0.0 - 1.0)
    alpha: float            # Predictive power (0.0 - 1.0)
    composite_score: float = field(init=False)
    decision: EvaluationDecision = field(init=False)

    # Weights for composite score
    W_RELIABILITY: float = field(default=0.4, repr=False)
    W_COHERENCE: float = field(default=0.3, repr=False)
    W_ALPHA: float = field(default=0.3, repr=False)

    def __post_init__(self):
        """Compute composite score and decision."""
        self.composite_score = (
            self.reliability ** self.W_RELIABILITY *
            self.coherence ** self.W_COHERENCE *
            self.alpha ** self.W_ALPHA
        )
        if self.composite_score >= 0.7:
            self.decision = EvaluationDecision.ACCEPT
        elif self.composite_score >= 0.4:
            self.decision = EvaluationDecision.VERIFY
        else:
            self.decision = EvaluationDecision.REJECT


@dataclass
class ScoredData:
    """Data with evaluation score attached."""
    raw: RawData
    evaluation: EvaluationResult
    validated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Scenario:
    """A prospective scenario."""
    name: str               # optimiste | median | pessimiste
    value: float            # Projected value
    probability: float      # 0.0 - 1.0
    description: str = ""
    confidence_interval: tuple[float, float] = field(default=(0.0, 0.0))


@dataclass
class Recommendation:
    """An actionable recommendation."""
    title: str
    description: str
    impact: float           # 0.0 - 1.0
    effort: float           # 0.0 - 1.0
    priority: float = field(init=False)
    stakeholder: str = ""
    timeline: str = ""

    def __post_init__(self):
        """Compute priority = impact / effort."""
        self.priority = self.impact / max(self.effort, 0.01)


@dataclass
class TheoryMatch:
    """A theory matching the analysis context."""
    theory_id: str
    theory_name: str
    similarity: float       # 0.0 - 1.0
    explanation: str
    applicable_insights: list[str] = field(default_factory=list)


@dataclass
class AnalysisContext:
    """Context accumulated during cognitive analysis."""
    data: list[ScoredData]
    query: str
    territory: str = ""
    signals: list[dict] = field(default_factory=list)
    causal_effects: list[dict] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    theory_matches: list[TheoryMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, warning: str):
        """Add a warning to the context."""
        self.warnings.append(warning)


@dataclass
class AnalysisResult:
    """Final result of cognitive analysis."""
    context: AnalysisContext
    summary: str
    confidence: float
    depth_reached: int      # 1-5 cognitive levels
    processing_time_ms: int
