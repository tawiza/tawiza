"""
DataCollector - Collects training data from TAJINE interactions.

Gathers:
- User feedback (explicit positive/negative ratings)
- Success traces (implicit from successful task completion)
- Preference pairs (chosen vs rejected responses)

Data is stored in structured format for downstream curation and training.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class FeedbackType(Enum):
    """Types of user feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CORRECTION = "correction"  # User provided correction


@dataclass
class Interaction:
    """A single TAJINE interaction."""
    id: str
    timestamp: datetime
    query: str  # User's question/request
    response: str | dict[str, Any]  # Agent's response (str or structured dict for training)
    context: dict[str, Any] = field(default_factory=dict)  # Analysis context
    tools_used: list[str] = field(default_factory=list)
    cognitive_level: int = 1  # 1-5
    success: bool = True
    duration_ms: float = 0.0
    user_feedback: FeedbackType | None = None
    user_correction: str | None = None  # If user provided correction

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "response": self.response,
            "context": self.context,
            "tools_used": self.tools_used,
            "cognitive_level": self.cognitive_level,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "user_feedback": self.user_feedback.value if self.user_feedback else None,
            "user_correction": self.user_correction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Interaction":
        feedback = None
        if data.get("user_feedback"):
            feedback = FeedbackType(data["user_feedback"])

        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            query=data["query"],
            response=data["response"],
            context=data.get("context", {}),
            tools_used=data.get("tools_used", []),
            cognitive_level=data.get("cognitive_level", 1),
            success=data.get("success", True),
            duration_ms=data.get("duration_ms", 0.0),
            user_feedback=feedback,
            user_correction=data.get("user_correction"),
        )


@dataclass
class SuccessTrace:
    """A successful interaction trace for SFT training."""
    instruction: str
    input_context: str
    output: str
    reasoning: str | None = None  # Chain of thought if available
    cognitive_level: int = 1
    quality_score: float = 1.0  # 0.0-1.0, assigned by curator

    def to_training_format(self) -> dict[str, str]:
        """Convert to standard instruction-tuning format."""
        if self.input_context:
            prompt = f"{self.instruction}\n\nContext:\n{self.input_context}"
        else:
            prompt = self.instruction

        return {
            "instruction": prompt,
            "output": self.output,
        }


@dataclass
class PreferencePair:
    """A preference pair for DPO training."""
    instruction: str
    input_context: str
    chosen: str  # Preferred response
    rejected: str  # Non-preferred response
    chosen_reason: str | None = None
    rejected_reason: str | None = None
    margin: float = 1.0  # Strength of preference

    def to_training_format(self) -> dict[str, str]:
        """Convert to DPO training format."""
        if self.input_context:
            prompt = f"{self.instruction}\n\nContext:\n{self.input_context}"
        else:
            prompt = self.instruction

        return {
            "prompt": prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
        }


@dataclass
class TrainingData:
    """Container for collected training data."""
    success_traces: list[SuccessTrace] = field(default_factory=list)
    preference_pairs: list[PreferencePair] = field(default_factory=list)
    raw_interactions: list[Interaction] = field(default_factory=list)
    collection_start: datetime | None = None
    collection_end: datetime | None = None

    @property
    def has_preferences(self) -> bool:
        return len(self.preference_pairs) > 0

    @property
    def reasoning_heavy(self) -> bool:
        """Check if data has significant reasoning content."""
        reasoning_count = sum(
            1 for t in self.success_traces if t.reasoning is not None
        )
        return reasoning_count > len(self.success_traces) * 0.5

    def get_stats(self) -> dict[str, Any]:
        return {
            "success_traces": len(self.success_traces),
            "preference_pairs": len(self.preference_pairs),
            "raw_interactions": len(self.raw_interactions),
            "has_preferences": self.has_preferences,
            "reasoning_heavy": self.reasoning_heavy,
            "collection_start": self.collection_start.isoformat() if self.collection_start else None,
            "collection_end": self.collection_end.isoformat() if self.collection_end else None,
        }


class DataCollector:
    """
    Collects training data from TAJINE interactions.

    Features:
    - Automatic extraction of success traces
    - Preference pair creation from corrections
    - Persistent storage with export/import
    - Statistics and triggers for fine-tuning
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        min_examples_trigger: int = 100,
        min_preferences_trigger: int = 50,
    ):
        """
        Initialize DataCollector.

        Args:
            storage_path: Path for persistent storage (optional)
            min_examples_trigger: Minimum examples before triggering fine-tune
            min_preferences_trigger: Minimum preferences before triggering DPO
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.min_examples_trigger = min_examples_trigger
        self.min_preferences_trigger = min_preferences_trigger

        self._interactions: list[Interaction] = []
        self._success_traces: list[SuccessTrace] = []
        self._preference_pairs: list[PreferencePair] = []
        self._collection_start: datetime | None = None
        self._last_export: datetime | None = None

        # Ensure storage directory exists
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured storage directory: {self.storage_path.parent}")

        # Load existing data if available
        if self.storage_path and self.storage_path.exists():
            self._load_from_storage()

        logger.info(f"DataCollector initialized (storage={storage_path})")

    async def record_interaction(self, interaction: Interaction) -> None:
        """
        Record an interaction for potential training use.

        Args:
            interaction: The interaction to record
        """
        if self._collection_start is None:
            self._collection_start = datetime.now()

        self._interactions.append(interaction)

        # Auto-extract success trace if positive outcome
        if interaction.success and interaction.user_feedback != FeedbackType.NEGATIVE:
            trace = self._extract_success_trace(interaction)
            if trace:
                self._success_traces.append(trace)
                logger.debug(f"Extracted success trace from interaction {interaction.id}")

        # Create preference pair if user provided correction
        if interaction.user_correction:
            pair = self._create_preference_pair(interaction)
            if pair:
                self._preference_pairs.append(pair)
                logger.debug(f"Created preference pair from correction in {interaction.id}")

        # Auto-save frequently to prevent data loss on restart
        # Save first interaction immediately to create file, then every 3 interactions
        interaction_count = len(self._interactions)
        if interaction_count == 1 or interaction_count % 3 == 0:
            await self._auto_save()
            logger.info(f"Auto-saved {interaction_count} interactions to storage")

    async def add_preference(
        self,
        instruction: str,
        chosen: str | None,
        rejected: str | None,
        context: str = "",
        margin: float = 1.0,
    ) -> bool:
        """
        Manually add a preference pair.

        Args:
            instruction: The instruction/query
            chosen: Preferred response (or None)
            rejected: Non-preferred response (or None)
            context: Additional context
            margin: Preference strength

        Returns:
            True if pair was added
        """
        if not chosen or not rejected:
            return False

        pair = PreferencePair(
            instruction=instruction,
            input_context=context,
            chosen=chosen,
            rejected=rejected,
            margin=margin,
        )
        self._preference_pairs.append(pair)
        logger.info(f"Added preference pair (total: {len(self._preference_pairs)})")
        return True

    async def add_success_trace(self, interaction: Interaction) -> bool:
        """
        Manually add a success trace from an interaction.

        Args:
            interaction: The successful interaction

        Returns:
            True if trace was added
        """
        trace = self._extract_success_trace(interaction)
        if trace:
            self._success_traces.append(trace)
            logger.info(f"Added success trace (total: {len(self._success_traces)})")
            return True
        return False

    def _extract_success_trace(self, interaction: Interaction) -> SuccessTrace | None:
        """Extract a training-ready success trace from an interaction."""
        if not interaction.query or not interaction.response:
            return None

        # Extract reasoning from context if available
        reasoning = None
        if "reasoning" in interaction.context:
            reasoning = interaction.context["reasoning"]
        elif "chain_of_thought" in interaction.context:
            reasoning = interaction.context["chain_of_thought"]
        # Also check in response if it's a dict
        if isinstance(interaction.response, dict):
            if not reasoning and "reasoning" in interaction.response:
                reasoning = interaction.response.get("reasoning")
            # Look for cognitive reasoning in analysis
            analysis = interaction.response.get("analysis", {})
            if not reasoning and isinstance(analysis, dict):
                cognitive_sig = analysis.get("cognitive_signature", {})
                if isinstance(cognitive_sig, dict):
                    reasoning = cognitive_sig.get("key_insight")

        # Build context string
        context_parts = []
        if "department" in interaction.context:
            context_parts.append(f"Territoire: {interaction.context['department']}")
        if "data_sources" in interaction.context:
            context_parts.append(f"Sources: {', '.join(interaction.context['data_sources'])}")
        # Add cognitive level context
        cognitive_levels = interaction.context.get("cognitive_levels", {})
        if cognitive_levels:
            levels_str = ", ".join(f"{k}: {v.get('summary', 'N/A')}" for k, v in cognitive_levels.items() if isinstance(v, dict))
            if levels_str:
                context_parts.append(f"Niveaux cognitifs: {levels_str}")

        # Convert response to string if it's a dict
        if isinstance(interaction.response, dict):
            # Extract the main analysis text for training
            analysis = interaction.response.get("analysis", {})
            if isinstance(analysis, dict):
                output_text = analysis.get("content") or analysis.get("summary", "")
                # If still empty, try response key
                if not output_text:
                    output_text = analysis.get("response", str(analysis))
            else:
                output_text = str(analysis)
            # Add confidence info
            confidence = interaction.response.get("confidence", 0)
            if confidence and output_text:
                output_text += f"\n\n[Confiance: {confidence:.0%}]"
        else:
            output_text = str(interaction.response)

        if not output_text:
            logger.warning(f"Empty output for interaction {interaction.id}, skipping trace")
            return None

        return SuccessTrace(
            instruction=interaction.query,
            input_context="\n".join(context_parts),
            output=output_text,
            reasoning=reasoning,
            cognitive_level=interaction.cognitive_level,
            quality_score=1.0 if interaction.user_feedback == FeedbackType.POSITIVE else 0.8,
        )

    def _create_preference_pair(self, interaction: Interaction) -> PreferencePair | None:
        """Create a preference pair from an interaction with correction."""
        if not interaction.user_correction:
            return None

        # Build context
        context_parts = []
        if "department" in interaction.context:
            context_parts.append(f"Department: {interaction.context['department']}")

        return PreferencePair(
            instruction=interaction.query,
            input_context="\n".join(context_parts),
            chosen=interaction.user_correction,  # User's correction is preferred
            rejected=interaction.response,  # Original response is rejected
            chosen_reason="User-provided correction",
            rejected_reason="Original response needed improvement",
        )

    async def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        return {
            "new_examples": len(self._success_traces) - self._count_exported_examples(),
            "new_preferences": len(self._preference_pairs) - self._count_exported_preferences(),
            "total_examples": len(self._success_traces),
            "total_preferences": len(self._preference_pairs),
            "total_interactions": len(self._interactions),
            "ready_for_sft": len(self._success_traces) >= self.min_examples_trigger,
            "ready_for_dpo": len(self._preference_pairs) >= self.min_preferences_trigger,
            "collection_start": self._collection_start.isoformat() if self._collection_start else None,
            "last_export": self._last_export.isoformat() if self._last_export else None,
        }

    def _count_exported_examples(self) -> int:
        """Count examples already exported."""
        if self._last_export is None:
            return 0
        return len(list(self._success_traces)) - len(self._success_traces)  # Simplified: return 0 for now

    def _count_exported_preferences(self) -> int:
        """Count preferences already exported."""
        return 0  # Simplified

    async def export(self) -> TrainingData:
        """
        Export collected data for training.

        Returns:
            TrainingData containing all collected examples
        """
        data = TrainingData(
            success_traces=list(self._success_traces),
            preference_pairs=list(self._preference_pairs),
            raw_interactions=list(self._interactions),
            collection_start=self._collection_start,
            collection_end=datetime.now(),
        )

        self._last_export = datetime.now()
        logger.info(f"Exported training data: {data.get_stats()}")

        return data

    async def clear(self, keep_last_n: int = 0) -> None:
        """
        Clear collected data.

        Args:
            keep_last_n: Keep the last N items (0 = clear all)
        """
        if keep_last_n > 0:
            self._interactions = self._interactions[-keep_last_n:]
            self._success_traces = self._success_traces[-keep_last_n:]
            self._preference_pairs = self._preference_pairs[-keep_last_n:]
        else:
            self._interactions.clear()
            self._success_traces.clear()
            self._preference_pairs.clear()

        self._collection_start = None
        logger.info("Cleared collected data")

    async def save(self) -> bool:
        """
        Explicitly save collected data to storage.

        Use this method at shutdown or when you want to ensure data is persisted.

        Returns:
            True if saved successfully
        """
        if not self.storage_path:
            logger.warning("Cannot save: no storage_path configured")
            return False

        try:
            await self._save_to_storage()
            logger.info(
                f"Saved training data: {len(self._interactions)} interactions, "
                f"{len(self._success_traces)} success traces, "
                f"{len(self._preference_pairs)} preference pairs"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save training data: {e}")
            return False

    async def _auto_save(self) -> None:
        """Auto-save to storage if configured."""
        if self.storage_path:
            await self._save_to_storage()

    async def _save_to_storage(self) -> None:
        """Save current data to storage."""
        if not self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "interactions": [i.to_dict() for i in self._interactions[-1000:]],
            "success_traces": [
                {
                    "instruction": t.instruction,
                    "input_context": t.input_context,
                    "output": t.output,
                    "reasoning": t.reasoning,
                    "cognitive_level": t.cognitive_level,
                    "quality_score": t.quality_score,
                }
                for t in self._success_traces
            ],
            "preference_pairs": [
                {
                    "instruction": p.instruction,
                    "input_context": p.input_context,
                    "chosen": p.chosen,
                    "rejected": p.rejected,
                    "margin": p.margin,
                }
                for p in self._preference_pairs
            ],
            "collection_start": self._collection_start.isoformat() if self._collection_start else None,
            "last_export": self._last_export.isoformat() if self._last_export else None,
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(
            f"Saved to {self.storage_path}: "
            f"{len(data['interactions'])} interactions, "
            f"{len(data['success_traces'])} traces"
        )

    def _load_from_storage(self) -> None:
        """Load data from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            self._interactions = [
                Interaction.from_dict(i) for i in data.get("interactions", [])
            ]

            self._success_traces = [
                SuccessTrace(**t) for t in data.get("success_traces", [])
            ]

            self._preference_pairs = [
                PreferencePair(**p) for p in data.get("preference_pairs", [])
            ]

            if data.get("collection_start"):
                self._collection_start = datetime.fromisoformat(data["collection_start"])

            if data.get("last_export"):
                self._last_export = datetime.fromisoformat(data["last_export"])

            logger.info(f"Loaded {len(self._interactions)} interactions from storage")

        except Exception as e:
            logger.warning(f"Failed to load from storage: {e}")


# ============================================================================
# Singleton Instance
# ============================================================================

_collector: DataCollector | None = None


def get_data_collector() -> DataCollector:
    """Get the singleton DataCollector instance.

    Creates a new instance on first call with default storage path.

    Returns:
        The shared DataCollector instance
    """
    global _collector

    if _collector is None:
        storage_path = Path.home() / ".tawiza" / "data" / "training_data.json"
        _collector = DataCollector(storage_path=storage_path)

    return _collector
