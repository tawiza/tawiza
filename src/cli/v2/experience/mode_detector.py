"""Mode detector - analyzes tasks and picks interaction mode."""

import re
from dataclasses import dataclass
from enum import Enum


class InteractionMode(Enum):
    """Available interaction modes."""
    QUICK = "quick"              # Simple, instant response
    AUTONOMOUS = "autonomous"    # Multi-step, agent handles it
    SUPERVISED = "supervised"    # Human-in-the-loop for risky ops
    CONVERSATIONAL = "conversational"  # Exploratory dialogue


@dataclass
class DetectionResult:
    """Result of mode detection."""
    mode: InteractionMode
    confidence: float  # 0.0 to 1.0
    reasoning: str
    suggested_tools: list[str] = None

    def __post_init__(self):
        if self.suggested_tools is None:
            self.suggested_tools = []


class ModeDetector:
    """Analyzes user input to determine interaction mode."""

    # Patterns for different modes
    QUICK_PATTERNS = [
        r"^status$",
        r"^what (time|date|version)",  # Specific quick queries
        r"^when (is|was|will)",
        r"^where (is|are)",
        r"^who (is|are)",
        r"^how (much|many)",
        r"^(show|list|get|check)\s",
        r"^(time|date|version)$",
    ]

    AUTONOMOUS_PATTERNS = [
        r"analyze.*(and|then)",
        r"create.*report",
        r"summarize.*and",
        r"find.*and.*fix",
        r"scrape.*and",
        r"process.*files?",
    ]

    SUPERVISED_PATTERNS = [
        r"refactor",
        r"delete|remove",
        r"modify|change|update.*code",
        r"rewrite",
        r"deploy",
        r"push|commit",
    ]

    CONVERSATIONAL_PATTERNS = [
        r"not sure",
        r"how (should|do|can) (i|we)",
        r"what('s| is) the best",
        r"help me (understand|figure|decide)",
        r"explore",
        r"^(help|explain)$",
    ]

    def detect(self, task: str) -> DetectionResult:
        """Detect the appropriate interaction mode for a task.

        Args:
            task: The user's task description

        Returns:
            DetectionResult with mode, confidence, and reasoning
        """
        task_lower = task.lower().strip()

        # Check patterns in priority order
        for pattern in self.QUICK_PATTERNS:
            if re.search(pattern, task_lower):
                return DetectionResult(
                    mode=InteractionMode.QUICK,
                    confidence=0.9,
                    reasoning="Simple query or status check detected",
                )

        for pattern in self.SUPERVISED_PATTERNS:
            if re.search(pattern, task_lower):
                return DetectionResult(
                    mode=InteractionMode.SUPERVISED,
                    confidence=0.85,
                    reasoning="Task involves code changes or risky operations",
                )

        for pattern in self.AUTONOMOUS_PATTERNS:
            if re.search(pattern, task_lower):
                return DetectionResult(
                    mode=InteractionMode.AUTONOMOUS,
                    confidence=0.8,
                    reasoning="Multi-step task that agent can handle autonomously",
                )

        for pattern in self.CONVERSATIONAL_PATTERNS:
            if re.search(pattern, task_lower):
                return DetectionResult(
                    mode=InteractionMode.CONVERSATIONAL,
                    confidence=0.75,
                    reasoning="Exploratory or unclear task needing dialogue",
                )

        # Default: autonomous for tasks, conversational for short inputs
        if len(task_lower.split()) <= 3:
            return DetectionResult(
                mode=InteractionMode.QUICK,
                confidence=0.5,
                reasoning="Short input, assuming quick query",
            )

        return DetectionResult(
            mode=InteractionMode.AUTONOMOUS,
            confidence=0.6,
            reasoning="Default to autonomous for task-like input",
        )
