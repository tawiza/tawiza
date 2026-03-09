"""Learning Engine - Orchestrates the self-improvement cycle."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from loguru import logger

from .active_learning import ActiveLearningManager
from .dataset_builder import DatasetBuilder, DatasetFormat


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class LearningState(StrEnum):
    """States of the learning cycle."""

    IDLE = "idle"
    COLLECTING = "collecting"
    PREPARING = "preparing"
    ANNOTATING = "annotating"
    TRAINING = "training"
    EVALUATING = "evaluating"


@dataclass
class LearningCycle:
    """Represents a single learning cycle.

    Tracks the progress through: COLLECT → PREPARE → ANNOTATE → TRAIN → EVALUATE
    """

    id: str
    state: LearningState = LearningState.IDLE
    examples_collected: int = 0
    examples_target: int = 100
    examples_annotated: int = 0
    dataset_path: str | None = None
    model_path: str | None = None
    run_id: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """Calculate progress percentage."""
        if self.examples_target == 0:
            return 0.0
        return min(1.0, self.examples_collected / self.examples_target)

    @property
    def duration_seconds(self) -> float:
        """Calculate cycle duration in seconds."""
        end = self.completed_at or utc_now()
        return (end - self.started_at).total_seconds()


@dataclass
class LearningMetrics:
    """Metrics from a learning cycle."""

    accuracy_before: float = 0.0
    accuracy_after: float = 0.0
    examples_trained: int = 0
    training_time_seconds: float = 0.0
    model_size_mb: float = 0.0

    @property
    def accuracy_improvement(self) -> float:
        """Calculate accuracy improvement."""
        return self.accuracy_after - self.accuracy_before

    @property
    def is_regression(self) -> bool:
        """Check if model regressed."""
        return self.accuracy_after < self.accuracy_before


class LearningEngine:
    """Orchestrates the self-improvement learning cycle.

    Manages the flow: COLLECT → PREPARE → ANNOTATE → TRAIN → EVALUATE → UPDATE

    Example:
        engine = LearningEngine()
        engine.record_interaction("task_1", "Question?", "Answer", feedback="positive")

        if engine.should_trigger_learning():
            cycle = await engine.run_full_cycle()
    """

    def __init__(
        self,
        min_examples: int = 100,
        auto_train: bool = True,
        dataset_builder: DatasetBuilder | None = None,
        active_learning: ActiveLearningManager | None = None,
        trust_manager: Any | None = None,
        output_dir: str = "/tmp/learning_engine",
    ):
        """Initialize learning engine.

        Args:
            min_examples: Minimum examples before triggering training
            auto_train: Whether to auto-trigger training
            dataset_builder: Custom dataset builder
            active_learning: Custom active learning manager
            trust_manager: Trust manager for updating autonomy
            output_dir: Directory for output files
        """
        self.min_examples = min_examples
        self.auto_train = auto_train
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Components
        self.dataset_builder = dataset_builder or DatasetBuilder()
        self.active_learning = active_learning or ActiveLearningManager()
        self.trust_manager = trust_manager

        # State
        self._state = LearningState.IDLE
        self._current_cycle: LearningCycle | None = None
        self._cycle_history: list[LearningCycle] = []
        self._training_adapter: Any | None = None

        logger.info(f"LearningEngine initialized with min_examples={min_examples}")

    @property
    def state(self) -> LearningState:
        """Current engine state."""
        return self._state

    @property
    def current_cycle(self) -> LearningCycle | None:
        """Current active cycle."""
        return self._current_cycle

    def record_interaction(
        self,
        task_id: str,
        instruction: str,
        output: str,
        input: str = "",
        feedback: str | None = None,
        uncertainty: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an interaction for learning.

        Args:
            task_id: Unique task identifier
            instruction: The instruction/question
            output: The generated output
            input: Optional additional input
            feedback: Human feedback (positive/negative)
            uncertainty: Model uncertainty (0-1)
            metadata: Additional metadata
        """
        # Add to dataset
        self.dataset_builder.add(
            instruction=instruction,
            input=input,
            output=output,
            source="interaction",
            feedback=feedback,
            metadata={"task_id": task_id, **(metadata or {})},
        )

        # Add to active learning if uncertain
        if uncertainty is not None and uncertainty > 0.3:
            self.active_learning.add_candidate(
                id=task_id,
                instruction=instruction,
                output=output,
                uncertainty_score=uncertainty,
            )

        logger.debug(f"Recorded interaction {task_id}, total: {len(self.dataset_builder.examples)}")

    def should_trigger_learning(self) -> bool:
        """Check if learning should be triggered.

        Returns:
            True if conditions are met for learning
        """
        if not self.auto_train:
            return False

        if self._state != LearningState.IDLE:
            return False

        return len(self.dataset_builder.examples) >= self.min_examples

    async def start_cycle(self) -> LearningCycle:
        """Start a new learning cycle.

        Returns:
            The new LearningCycle
        """
        if self._current_cycle is not None:
            logger.warning("Cycle already in progress")
            return self._current_cycle

        cycle = LearningCycle(
            id=str(uuid.uuid4())[:8],
            state=LearningState.PREPARING,
            examples_collected=len(self.dataset_builder.examples),
            examples_target=self.min_examples,
        )

        self._current_cycle = cycle
        self._state = LearningState.PREPARING

        logger.info(f"Started learning cycle {cycle.id}")
        return cycle

    async def prepare_dataset(self, cycle: LearningCycle) -> str:
        """Prepare dataset for training.

        Args:
            cycle: The current cycle

        Returns:
            Path to prepared dataset
        """
        cycle.state = LearningState.PREPARING
        self._state = LearningState.PREPARING

        # Filter to positive feedback only for training
        filtered = self.dataset_builder.filter(feedback="positive")

        # If not enough positive, use all
        if len(filtered.examples) < self.min_examples // 2:
            filtered = self.dataset_builder

        # Deduplicate
        filtered.deduplicate()

        # Export dataset
        dataset_path = str(self.output_dir / f"dataset_{cycle.id}.jsonl")
        filtered.export(dataset_path, format=DatasetFormat.JSONL)

        cycle.dataset_path = dataset_path
        logger.info(f"Prepared dataset at {dataset_path}")

        return dataset_path

    async def train_model(self, cycle: LearningCycle) -> dict[str, Any]:
        """Train model on prepared dataset.

        Args:
            cycle: The current cycle

        Returns:
            Training result
        """
        cycle.state = LearningState.TRAINING
        self._state = LearningState.TRAINING

        if self._training_adapter is None:
            logger.warning("No training adapter configured")
            return {}

        result = await self._training_adapter.train(
            dataset_path=cycle.dataset_path,
            output_dir=str(self.output_dir / f"model_{cycle.id}"),
        )

        cycle.run_id = result.get("run_id")
        cycle.model_path = result.get("model_path")
        cycle.metrics = result.get("metrics", {})

        logger.info(f"Training completed: {result}")
        return result

    async def evaluate_model(self, cycle: LearningCycle) -> LearningMetrics:
        """Evaluate trained model.

        Args:
            cycle: The current cycle

        Returns:
            Evaluation metrics
        """
        cycle.state = LearningState.EVALUATING
        self._state = LearningState.EVALUATING

        if self._training_adapter is None:
            logger.warning("No training adapter configured")
            return LearningMetrics()

        eval_result = await self._training_adapter.evaluate(
            model_path=cycle.model_path,
        )

        metrics = LearningMetrics(
            accuracy_before=cycle.metrics.get("accuracy", 0.0),
            accuracy_after=eval_result.get("accuracy", 0.0),
            examples_trained=cycle.examples_collected,
        )

        logger.info(f"Evaluation: {metrics.accuracy_improvement:+.2%} improvement")
        return metrics

    async def run_full_cycle(self) -> LearningCycle:
        """Run a complete learning cycle.

        Returns:
            Completed cycle
        """
        cycle = await self.start_cycle()

        try:
            await self.prepare_dataset(cycle)
            await self.train_model(cycle)
            await self.evaluate_model(cycle)

            # Update trust if available
            if self.trust_manager is not None:
                # This would update trust based on metrics
                pass

            cycle.state = LearningState.IDLE
            cycle.completed_at = utc_now()

            logger.info(f"Completed learning cycle {cycle.id}")

        except Exception as e:
            cycle.error = str(e)
            cycle.state = LearningState.IDLE
            logger.error(f"Cycle {cycle.id} failed: {e}")

        finally:
            self._cycle_history.append(cycle)
            self._current_cycle = None
            self._state = LearningState.IDLE

        return cycle

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "current_state": self._state.value,
            "examples_collected": len(self.dataset_builder.examples),
            "annotation_queue_size": len(self.active_learning.queue),
            "cycles_completed": len(self._cycle_history),
            "min_examples": self.min_examples,
            "auto_train": self.auto_train,
        }

    def get_cycle_history(self) -> list[LearningCycle]:
        """Get history of completed cycles.

        Returns:
            List of cycles
        """
        return self._cycle_history.copy()

    def set_training_adapter(self, adapter: Any) -> None:
        """Set the training adapter.

        Args:
            adapter: Training adapter (e.g., LLaMAFactoryAdapter)
        """
        self._training_adapter = adapter
        logger.info(f"Set training adapter: {type(adapter).__name__}")
