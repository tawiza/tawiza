"""
Causal inference data models.

Dataclasses for representing causal relationships in TAJINE.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CausalHypothesis:
    """A potential cause-effect relationship to test."""
    cause: str           # e.g., "unemployment_rate"
    effect: str          # e.g., "company_creation_rate"
    source: str          # where hypothesis came from (rule, discovery)
    priority: float = 0.5  # 0-1, higher = test first

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "source": self.source,
            "priority": self.priority
        }


@dataclass
class CausalLink:
    """A validated causal relationship."""
    cause: str
    effect: str
    correlation: float   # -1 to 1
    lag_months: int      # optimal lag (0 = instantaneous)
    confidence: float    # 0-1
    evidence: str = ""   # human-readable explanation
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "correlation": self.correlation,
            "lag_months": self.lag_months,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "validated_at": self.validated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CausalLink":
        validated_at = data.get("validated_at")
        if isinstance(validated_at, str):
            validated_at = datetime.fromisoformat(validated_at)
        return cls(
            cause=data["cause"],
            effect=data["effect"],
            correlation=data["correlation"],
            lag_months=data["lag_months"],
            confidence=data["confidence"],
            evidence=data.get("evidence", ""),
            validated_at=validated_at or datetime.now()
        )


@dataclass
class CausalChain:
    """A sequence of causal links forming a path."""
    root_cause: str
    final_effect: str
    links: list[CausalLink] = field(default_factory=list)
    total_confidence: float = 0.0

    def __post_init__(self):
        if self.links and self.total_confidence == 0.0:
            # Product of individual confidences
            self.total_confidence = 1.0
            for link in self.links:
                self.total_confidence *= link.confidence

    def __eq__(self, other: object) -> bool:
        """Compare chains by content, not identity."""
        if not isinstance(other, CausalChain):
            return False
        return (
            self.root_cause == other.root_cause
            and self.final_effect == other.final_effect
            and len(self.links) == len(other.links)
            and all(
                l1.cause == l2.cause and l1.effect == l2.effect
                for l1, l2 in zip(self.links, other.links, strict=False)
            )
        )

    def __hash__(self) -> int:
        """Hash by chain structure for deduplication."""
        link_tuples = tuple((l.cause, l.effect) for l in self.links)
        return hash((self.root_cause, self.final_effect, link_tuples))

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause,
            "final_effect": self.final_effect,
            "chain": [self.root_cause] + [link.effect for link in self.links],
            "links": [link.to_dict() for link in self.links],
            "total_confidence": self.total_confidence
        }
