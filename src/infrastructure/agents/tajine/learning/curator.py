"""
LLMJudgeCurator - Filters and validates training data using LLM-as-Judge.

Uses an LLM to:
- Score quality of success traces
- Validate preference pairs
- Filter out low-quality or harmful examples
- Ensure training data aligns with TAJINE's objectives
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from loguru import logger

from src.infrastructure.agents.tajine.learning.data_collector import (
    PreferencePair,
    SuccessTrace,
    TrainingData,
)


def _to_str(value: str | dict | Any) -> str:
    """Convert value to string safely, handling dict and other types."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        import json
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value) if value else ""


class CurationVerdict(Enum):
    """Verdict from LLM judge."""
    ACCEPT = "accept"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


@dataclass
class CurationResult:
    """Result of curating a single example."""
    verdict: CurationVerdict
    quality_score: float  # 0.0 - 1.0
    reasoning: str
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class CuratedDataset:
    """A curated dataset ready for training."""
    success_traces: list[SuccessTrace]
    preference_pairs: list[PreferencePair]
    curation_stats: dict[str, Any]
    curated_at: datetime = field(default_factory=datetime.now)

    @property
    def has_preferences(self) -> bool:
        return len(self.preference_pairs) > 0

    @property
    def reasoning_heavy(self) -> bool:
        """Check if curated data has significant reasoning content."""
        reasoning_count = sum(
            1 for t in self.success_traces if t.reasoning is not None
        )
        return reasoning_count > len(self.success_traces) * 0.5

    def get_stats(self) -> dict[str, Any]:
        return {
            **self.curation_stats,
            "curated_traces": len(self.success_traces),
            "curated_pairs": len(self.preference_pairs),
            "has_preferences": self.has_preferences,
            "reasoning_heavy": self.reasoning_heavy,
        }


class LLMProvider(Protocol):
    """Protocol for LLM providers used in curation."""

    async def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt."""
        ...


class LLMJudgeCurator:
    """
    Uses LLM-as-Judge pattern to curate training data.

    Quality Criteria:
    - Relevance: Response addresses the query appropriately
    - Correctness: Information is accurate (for territorial data)
    - Completeness: Response provides sufficient detail
    - Clarity: Response is clear and well-structured
    - Safety: No harmful or misleading content
    """

    # Quality thresholds
    ACCEPT_THRESHOLD = 0.7
    REVIEW_THRESHOLD = 0.4

    # Prompt templates
    TRACE_EVALUATION_PROMPT = """You are evaluating a training example for a territorial intelligence AI assistant.

INSTRUCTION: {instruction}

CONTEXT: {context}

RESPONSE: {response}

Evaluate this example on the following criteria (0.0 to 1.0 each):
1. Relevance: Does the response address the question appropriately?
2. Correctness: Is the information accurate for French territorial/economic data?
3. Completeness: Does it provide sufficient detail?
4. Clarity: Is it well-structured and clear?
5. Safety: Is it free of harmful or misleading content?

Respond in JSON format:
{{
    "relevance": 0.0-1.0,
    "correctness": 0.0-1.0,
    "completeness": 0.0-1.0,
    "clarity": 0.0-1.0,
    "safety": 0.0-1.0,
    "overall": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "verdict": "accept" | "reject" | "needs_review",
    "reasoning": "explanation"
}}"""

    PREFERENCE_EVALUATION_PROMPT = """You are validating a preference pair for DPO training.

INSTRUCTION: {instruction}

CONTEXT: {context}

CHOSEN RESPONSE: {chosen}

REJECTED RESPONSE: {rejected}

Evaluate whether the preference is valid:
1. Is the chosen response genuinely better than the rejected one?
2. Are both responses reasonable attempts at answering?
3. Is the quality difference significant enough for training?

Respond in JSON format:
{{
    "preference_valid": true | false,
    "quality_margin": 0.0-1.0,
    "chosen_issues": ["issue1"],
    "rejected_issues": ["issue1"],
    "verdict": "accept" | "reject" | "needs_review",
    "reasoning": "explanation"
}}"""

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        accept_threshold: float = 0.7,
        review_threshold: float = 0.4,
    ):
        """
        Initialize LLMJudgeCurator.

        Args:
            llm_provider: LLM to use for judging (optional, uses heuristics if None)
            accept_threshold: Minimum score to accept
            review_threshold: Minimum score to consider for review
        """
        self.llm_provider = llm_provider
        self.accept_threshold = accept_threshold
        self.review_threshold = review_threshold

        logger.info("LLMJudgeCurator initialized")

    async def filter(self, data: TrainingData) -> CuratedDataset:
        """
        Filter and curate training data.

        Args:
            data: Raw training data

        Returns:
            CuratedDataset with validated examples
        """
        logger.info(f"Curating {len(data.success_traces)} traces, {len(data.preference_pairs)} pairs")

        curated_traces = []
        curated_pairs = []
        stats = {
            "input_traces": len(data.success_traces),
            "input_pairs": len(data.preference_pairs),
            "accepted_traces": 0,
            "rejected_traces": 0,
            "review_traces": 0,
            "accepted_pairs": 0,
            "rejected_pairs": 0,
        }

        # Curate success traces
        for trace in data.success_traces:
            result = await self._curate_trace(trace)

            if result.verdict == CurationVerdict.ACCEPT:
                trace.quality_score = result.quality_score
                curated_traces.append(trace)
                stats["accepted_traces"] += 1
            elif result.verdict == CurationVerdict.NEEDS_REVIEW:
                # For now, include with lower quality score
                trace.quality_score = result.quality_score * 0.8
                curated_traces.append(trace)
                stats["review_traces"] += 1
            else:
                stats["rejected_traces"] += 1

        # Curate preference pairs
        for pair in data.preference_pairs:
            result = await self._curate_preference(pair)

            if result.verdict == CurationVerdict.ACCEPT:
                curated_pairs.append(pair)
                stats["accepted_pairs"] += 1
            else:
                stats["rejected_pairs"] += 1

        logger.info(f"Curation complete: {stats['accepted_traces']} traces, {stats['accepted_pairs']} pairs accepted")

        return CuratedDataset(
            success_traces=curated_traces,
            preference_pairs=curated_pairs,
            curation_stats=stats,
        )

    async def _curate_trace(self, trace: SuccessTrace) -> CurationResult:
        """Curate a single success trace."""
        if self.llm_provider:
            return await self._llm_curate_trace(trace)
        else:
            return self._heuristic_curate_trace(trace)

    async def _curate_preference(self, pair: PreferencePair) -> CurationResult:
        """Curate a single preference pair."""
        if self.llm_provider:
            return await self._llm_curate_preference(pair)
        else:
            return self._heuristic_curate_preference(pair)

    async def _llm_curate_trace(self, trace: SuccessTrace) -> CurationResult:
        """Use LLM to evaluate a trace."""
        prompt = self.TRACE_EVALUATION_PROMPT.format(
            instruction=trace.instruction,
            context=trace.input_context or "None",
            response=trace.output,
        )

        try:
            response = await self.llm_provider.generate(prompt)
            result = self._parse_trace_evaluation(response)
            return result
        except Exception as e:
            logger.warning(f"LLM curation failed, using heuristics: {e}")
            return self._heuristic_curate_trace(trace)

    async def _llm_curate_preference(self, pair: PreferencePair) -> CurationResult:
        """Use LLM to evaluate a preference pair."""
        prompt = self.PREFERENCE_EVALUATION_PROMPT.format(
            instruction=pair.instruction,
            context=pair.input_context or "None",
            chosen=pair.chosen,
            rejected=pair.rejected,
        )

        try:
            response = await self.llm_provider.generate(prompt)
            result = self._parse_preference_evaluation(response)
            return result
        except Exception as e:
            logger.warning(f"LLM curation failed, using heuristics: {e}")
            return self._heuristic_curate_preference(pair)

    def _parse_trace_evaluation(self, response: str) -> CurationResult:
        """Parse LLM response for trace evaluation."""
        import json

        try:
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                verdict_str = data.get("verdict", "needs_review")
                verdict = CurationVerdict(verdict_str)

                return CurationResult(
                    verdict=verdict,
                    quality_score=data.get("overall", 0.5),
                    reasoning=data.get("reasoning", ""),
                    issues=data.get("issues", []),
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # Fallback
        return CurationResult(
            verdict=CurationVerdict.NEEDS_REVIEW,
            quality_score=0.5,
            reasoning="Failed to parse LLM evaluation",
        )

    def _parse_preference_evaluation(self, response: str) -> CurationResult:
        """Parse LLM response for preference evaluation."""
        import json

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                verdict_str = data.get("verdict", "needs_review")
                verdict = CurationVerdict(verdict_str)

                return CurationResult(
                    verdict=verdict,
                    quality_score=data.get("quality_margin", 0.5),
                    reasoning=data.get("reasoning", ""),
                    issues=data.get("chosen_issues", []) + data.get("rejected_issues", []),
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return CurationResult(
            verdict=CurationVerdict.NEEDS_REVIEW,
            quality_score=0.5,
            reasoning="Failed to parse LLM evaluation",
        )

    def _heuristic_curate_trace(self, trace: SuccessTrace) -> CurationResult:
        """Use heuristics to evaluate a trace (no LLM)."""
        issues = []
        score = 1.0

        # Length checks
        if len(trace.instruction) < 10:
            issues.append("Instruction too short")
            score -= 0.3

        if len(trace.output) < 20:
            issues.append("Output too short")
            score -= 0.2

        if len(trace.output) > 5000:
            issues.append("Output very long, may contain noise")
            score -= 0.1

        # Content checks - safely convert to string for dict outputs
        instruction_str = _to_str(trace.instruction)
        output_str = _to_str(trace.output)

        if not instruction_str.strip():
            issues.append("Empty instruction")
            score -= 0.5

        if not output_str.strip():
            issues.append("Empty output")
            score -= 0.5

        # French territorial keywords bonus
        territorial_keywords = ["département", "région", "entreprise", "siret", "insee", "économique"]
        has_territorial = any(kw in output_str.lower() for kw in territorial_keywords)
        if has_territorial:
            score += 0.1

        # Reasoning bonus
        if trace.reasoning:
            score += 0.1

        score = max(0.0, min(1.0, score))

        if score >= self.accept_threshold:
            verdict = CurationVerdict.ACCEPT
        elif score >= self.review_threshold:
            verdict = CurationVerdict.NEEDS_REVIEW
        else:
            verdict = CurationVerdict.REJECT

        return CurationResult(
            verdict=verdict,
            quality_score=score,
            reasoning=f"Heuristic evaluation (score={score:.2f})",
            issues=issues,
        )

    def _heuristic_curate_preference(self, pair: PreferencePair) -> CurationResult:
        """Use heuristics to evaluate a preference pair (no LLM)."""
        issues = []
        score = 1.0

        # Basic validity
        if not pair.chosen or not pair.rejected:
            return CurationResult(
                verdict=CurationVerdict.REJECT,
                quality_score=0.0,
                reasoning="Missing chosen or rejected response",
                issues=["Incomplete pair"],
            )

        # Convert to strings safely
        chosen_str = _to_str(pair.chosen)
        rejected_str = _to_str(pair.rejected)

        # Length difference
        chosen_len = len(chosen_str)
        rejected_len = len(rejected_str)

        if chosen_len < rejected_len * 0.5:
            issues.append("Chosen response much shorter than rejected")
            score -= 0.2

        # Identical check
        if chosen_str.strip() == rejected_str.strip():
            return CurationResult(
                verdict=CurationVerdict.REJECT,
                quality_score=0.0,
                reasoning="Chosen and rejected are identical",
                issues=["Identical responses"],
            )

        # Margin consideration
        if pair.margin < 0.5:
            issues.append("Low preference margin")
            score -= 0.1

        score = max(0.0, min(1.0, score))

        if score >= self.accept_threshold:
            verdict = CurationVerdict.ACCEPT
        elif score >= self.review_threshold:
            verdict = CurationVerdict.NEEDS_REVIEW
        else:
            verdict = CurationVerdict.REJECT

        return CurationResult(
            verdict=verdict,
            quality_score=score,
            reasoning=f"Heuristic evaluation (score={score:.2f})",
            issues=issues,
        )
