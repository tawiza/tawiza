"""
ReflectionOutput - ReAct-inspired reflection system for PPDSL phases.

Implements structured reflection at each cognitive level to:
- Track reasoning process (thinking)
- Identify gaps in analysis
- Suggest improvements
- Recommend retry strategies when confidence is low
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ReflectionOutput:
    """
    Output enriched with ReAct-style reflection.

    Used by cognitive levels to provide structured feedback about
    the quality of analysis and whether refinement is needed.

    Attributes:
        result: The actual result from processing
        thinking: Explicit reasoning trace (ReAct style)
        confidence: Confidence score (0.0-1.0)
        gaps: Identified gaps or missing information
        suggestions: Possible improvements or follow-up actions
        should_retry: Whether retry is recommended
        retry_strategy: How to retry if recommended
    """

    result: Any
    thinking: str = ""
    confidence: float = 0.5
    gaps: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    should_retry: bool = False
    retry_strategy: str | None = None

    def __post_init__(self):
        """Validate and normalize fields."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        if self.confidence < 0.4 and not self.should_retry:
            # Auto-suggest retry for low confidence
            self.should_retry = True
            if not self.retry_strategy:
                self.retry_strategy = "expand_sources"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "result": self.result,
            "thinking": self.thinking,
            "confidence": self.confidence,
            "gaps": self.gaps,
            "suggestions": self.suggestions,
            "should_retry": self.should_retry,
            "retry_strategy": self.retry_strategy,
        }

    @classmethod
    def from_result(
        cls, result: Any, confidence: float = 0.5, thinking: str = ""
    ) -> ReflectionOutput:
        """Create ReflectionOutput from a simple result."""
        return cls(
            result=result,
            thinking=thinking,
            confidence=confidence,
        )

    @classmethod
    def low_confidence(
        cls, result: Any, gaps: list[str], retry_strategy: str = "expand_sources"
    ) -> ReflectionOutput:
        """Create a low-confidence output that recommends retry."""
        return cls(
            result=result,
            confidence=0.3,
            gaps=gaps,
            should_retry=True,
            retry_strategy=retry_strategy,
            thinking=f"Low confidence due to: {', '.join(gaps)}",
        )


# Adaptive thresholds by mode and phase
ADAPTIVE_THRESHOLDS = {
    "rapide": {
        "perceive": 0.5,
        "plan": 0.4,
        "delegate": 0.3,
        "synthesize": 0.5,
        "learn": 0.3,
        "discovery": 0.4,
        "causal": 0.4,
        "scenario": 0.3,
        "strategy": 0.4,
        "theoretical": 0.3,
    },
    "complet": {
        "perceive": 0.7,
        "plan": 0.6,
        "delegate": 0.5,
        "synthesize": 0.7,
        "learn": 0.5,
        "discovery": 0.6,
        "causal": 0.6,
        "scenario": 0.5,
        "strategy": 0.6,
        "theoretical": 0.5,
    },
}


def get_threshold(mode: str, phase: str) -> float:
    """Get confidence threshold for a given mode and phase."""
    mode_thresholds = ADAPTIVE_THRESHOLDS.get(mode.lower(), ADAPTIVE_THRESHOLDS["rapide"])
    return mode_thresholds.get(phase.lower(), 0.5)


def should_retry_phase(reflection: ReflectionOutput, mode: str, phase: str) -> bool:
    """Determine if a phase should be retried based on reflection."""
    threshold = get_threshold(mode, phase)
    return reflection.confidence < threshold or reflection.should_retry


class ReflectionMixin:
    """
    Mixin providing reflection capabilities to cognitive levels.

    Usage:
        class MyLevel(BaseCognitiveLevel, ReflectionMixin):
            async def process(self, results, previous) -> dict:
                # Process data
                output = ...

                # Create reflection
                reflection = self.create_reflection(
                    output,
                    confidence=0.7,
                    thinking="Analyzed X patterns, found Y signals"
                )

                # Return with reflection metadata
                return {
                    **output,
                    'reflection': reflection.to_dict()
                }
    """

    def create_reflection(
        self,
        result: Any,
        confidence: float,
        thinking: str = "",
        gaps: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> ReflectionOutput:
        """Create a ReflectionOutput for the current processing."""
        return ReflectionOutput(
            result=result,
            thinking=thinking,
            confidence=confidence,
            gaps=gaps or [],
            suggestions=suggestions or [],
        )

    def analyze_result_quality(
        self, result: dict[str, Any], mode: str = "rapide"
    ) -> ReflectionOutput:
        """
        Analyze the quality of a result and create appropriate reflection.

        Args:
            result: The processing result to analyze
            mode: Analysis mode ("rapide" or "complet")

        Returns:
            ReflectionOutput with quality assessment
        """
        gaps = []
        suggestions = []
        confidence = 0.5

        # Check for common quality indicators
        if not result:
            gaps.append("Empty result")
            confidence = 0.1

        # Check signals/patterns (for Discovery level)
        signals = result.get("signals", [])
        patterns = result.get("patterns", [])

        if isinstance(signals, list):
            if len(signals) == 0:
                gaps.append("No signals detected")
                suggestions.append("Consider expanding data sources")
            elif len(signals) >= 3:
                confidence += 0.2

        if isinstance(patterns, list):
            if len(patterns) == 0:
                gaps.append("No patterns identified")
            elif len(patterns) >= 2:
                confidence += 0.15

        # Check analysis content (for higher levels)
        if analysis := result.get("analysis"):
            if len(str(analysis)) < 100:
                gaps.append("Analysis is too brief")
                suggestions.append("Request more detailed LLM analysis")
            else:
                confidence += 0.15

        # Check for data sources
        if sources := result.get("sources_used", result.get("data_sources")):
            if len(sources) >= 2:
                confidence += 0.1
            else:
                suggestions.append("Add more data sources for validation")

        # Normalize confidence
        confidence = min(1.0, max(0.0, confidence))

        # Generate thinking trace
        thinking = self._generate_thinking_trace(result, gaps, confidence)

        return ReflectionOutput(
            result=result,
            thinking=thinking,
            confidence=confidence,
            gaps=gaps,
            suggestions=suggestions,
        )

    def _generate_thinking_trace(
        self, result: dict[str, Any], gaps: list[str], confidence: float
    ) -> str:
        """Generate a reasoning trace for the reflection."""
        parts = []

        # Describe what was found
        if signals := result.get("signals"):
            parts.append(f"Found {len(signals)} signals")
        if patterns := result.get("patterns"):
            parts.append(f"Identified {len(patterns)} patterns")
        if analysis := result.get("analysis"):
            parts.append(f"Generated analysis ({len(str(analysis))} chars)")

        # Describe gaps
        if gaps:
            parts.append(f"Gaps: {', '.join(gaps)}")

        # Confidence assessment
        if confidence >= 0.7:
            parts.append("High confidence result")
        elif confidence >= 0.5:
            parts.append("Moderate confidence - some validation needed")
        else:
            parts.append("Low confidence - consider retry")

        return ". ".join(parts) if parts else "Processing completed"
