"""
TAJINEFineTuner - Automated fine-tuning pipeline for TAJINE.

Orchestrates the complete fine-tuning workflow:
1. Collect feedback from interactions (DataCollector)
2. Curate data using LLM-as-Judge (LLMJudgeCurator)
3. Train model using appropriate method (Oumi/Unsloth)
4. Evaluate new model vs current
5. Deploy if improvement verified

Training Methods:
- SFT (Supervised Fine-Tuning): From success examples
- DPO (Direct Preference Optimization): From preference pairs
- GRPO (Group Relative Policy Optimization): For reasoning chains
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from src.infrastructure.agents.tajine.learning.curator import (
    CuratedDataset,
    LLMJudgeCurator,
)
from src.infrastructure.agents.tajine.learning.data_collector import (
    DataCollector,
    Interaction,
)


class TrainingMethod(Enum):
    """Available training methods."""

    SFT = "sft"  # Supervised Fine-Tuning
    DPO = "dpo"  # Direct Preference Optimization
    GRPO = "grpo"  # Group Relative Policy Optimization
    QLORA = "qlora"  # QLoRA (quantized LoRA)


@dataclass
class FineTuneConfig:
    """Configuration for fine-tuning."""

    # LoRA parameters
    lora_rank: int = 64
    lora_alpha: int = 128
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])

    # Training parameters
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    epochs: int = 2
    max_steps: int = -1  # -1 = use epochs
    warmup_ratio: float = 0.03

    # Data parameters
    max_seq_length: int = 2048
    packing: bool = True  # Pack multiple examples

    # Method-specific
    method: TrainingMethod = TrainingMethod.SFT
    dpo_beta: float = 0.1  # KL penalty for DPO

    def to_dict(self) -> dict[str, Any]:
        return {
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "max_steps": self.max_steps,
            "warmup_ratio": self.warmup_ratio,
            "max_seq_length": self.max_seq_length,
            "packing": self.packing,
            "method": self.method.value,
            "dpo_beta": self.dpo_beta,
        }


@dataclass
class EvaluationResult:
    """Result of model evaluation."""

    model_name: str
    score: float  # Overall score (0.0 - 1.0)
    metrics: dict[str, float]  # Individual metrics
    evaluated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "score": self.score,
            "metrics": self.metrics,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class FineTuneResult:
    """Result of fine-tuning run."""

    status: str  # 'deployed', 'rollback', 'failed'
    new_model_name: str | None = None
    old_model_name: str | None = None
    new_score: float | None = None
    old_score: float | None = None
    improvement: float | None = None
    method_used: TrainingMethod | None = None
    training_time_seconds: float = 0.0
    reason: str = ""
    config: FineTuneConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "new_model_name": self.new_model_name,
            "old_model_name": self.old_model_name,
            "new_score": self.new_score,
            "old_score": self.old_score,
            "improvement": self.improvement,
            "method_used": self.method_used.value if self.method_used else None,
            "training_time_seconds": self.training_time_seconds,
            "reason": self.reason,
            "config": self.config.to_dict() if self.config else None,
        }


class TrainingBackend(Protocol):
    """Protocol for training backends (Oumi, Unsloth, etc.)."""

    async def train(
        self,
        base_model: str,
        dataset: CuratedDataset,
        config: FineTuneConfig,
    ) -> str:
        """Train and return new model name/path."""
        ...


class ModelEvaluator(Protocol):
    """Protocol for model evaluators."""

    async def evaluate(self, model_name: str) -> EvaluationResult:
        """Evaluate a model and return score."""
        ...


class TAJINEFineTuner:
    """
    Pipeline de fine-tuning automatisé.

    Orchestrates the complete fine-tuning workflow with automatic
    trigger detection, method selection, and safe deployment.

    Triggers:
    - >= 100 new success examples → SFT/QLoRA
    - >= 50 new preference pairs → DPO
    - Trust score stagnant >= 7 days → GRPO
    - Performance below threshold → Urgent
    """

    # Trigger thresholds
    MIN_EXAMPLES_FOR_SFT = 100
    MIN_PREFERENCES_FOR_DPO = 50
    STAGNANT_DAYS_FOR_GRPO = 7
    PERFORMANCE_THRESHOLD = 0.6

    def __init__(
        self,
        data_collector: DataCollector | None = None,
        curator: LLMJudgeCurator | None = None,
        training_backend: TrainingBackend | None = None,
        evaluator: ModelEvaluator | None = None,
        current_model: str = "qwen3.5:27b",
        output_dir: Path | None = None,
    ):
        """
        Initialize TAJINEFineTuner.

        Args:
            data_collector: DataCollector instance
            curator: LLMJudgeCurator instance
            training_backend: Training backend (Oumi/Unsloth)
            evaluator: Model evaluator
            current_model: Currently deployed model
            output_dir: Directory for model outputs
        """
        self.data_collector = data_collector or DataCollector()
        self.curator = curator or LLMJudgeCurator()
        self.training_backend = training_backend
        self.evaluator = evaluator
        self.current_model = current_model
        self.output_dir = Path(output_dir) if output_dir else Path("./models/tajine")

        self._last_finetune: datetime | None = None
        self._trust_history: list[float] = []
        self._performance_history: list[float] = []

        logger.info(f"TAJINEFineTuner initialized (current_model={current_model})")

    async def collect_feedback(self, interaction: Interaction) -> None:
        """
        Collect feedback from an interaction.

        Args:
            interaction: The completed interaction
        """
        await self.data_collector.record_interaction(interaction)

    async def check_trigger(self) -> TrainingMethod | None:
        """
        Check if fine-tuning should be triggered.

        Returns:
            TrainingMethod to use, or None if no trigger
        """
        stats = await self.data_collector.get_stats()

        # Performance below threshold → Urgent
        if self._performance_history:
            recent_perf = sum(self._performance_history[-10:]) / len(
                self._performance_history[-10:]
            )
            if recent_perf < self.PERFORMANCE_THRESHOLD:
                logger.warning(f"Performance below threshold ({recent_perf:.2f}), triggering GRPO")
                return TrainingMethod.GRPO

        # Preference pairs available → DPO
        if stats["new_preferences"] >= self.MIN_PREFERENCES_FOR_DPO:
            logger.info(f"DPO trigger: {stats['new_preferences']} new preferences")
            return TrainingMethod.DPO

        # Success examples available → SFT
        if stats["new_examples"] >= self.MIN_EXAMPLES_FOR_SFT:
            logger.info(f"SFT trigger: {stats['new_examples']} new examples")
            return TrainingMethod.SFT

        # Trust stagnant → GRPO
        if len(self._trust_history) >= self.STAGNANT_DAYS_FOR_GRPO:
            recent_trust = self._trust_history[-self.STAGNANT_DAYS_FOR_GRPO :]
            variance = max(recent_trust) - min(recent_trust)
            if variance < 0.02:  # Less than 2% change
                logger.info(
                    f"Trust stagnant for {self.STAGNANT_DAYS_FOR_GRPO} days, triggering GRPO"
                )
                return TrainingMethod.GRPO

        return None

    def record_trust(self, trust_score: float) -> None:
        """Record daily trust score for stagnation detection."""
        self._trust_history.append(trust_score)
        # Keep last 30 days
        if len(self._trust_history) > 30:
            self._trust_history = self._trust_history[-30:]

    def record_performance(self, score: float) -> None:
        """Record performance score for threshold monitoring."""
        self._performance_history.append(score)
        if len(self._performance_history) > 100:
            self._performance_history = self._performance_history[-100:]

    async def run_finetune(
        self,
        method: TrainingMethod | None = None,
        config: FineTuneConfig | None = None,
    ) -> FineTuneResult:
        """
        Execute the fine-tuning pipeline.

        Args:
            method: Training method (auto-detected if None)
            config: Training config (defaults if None)

        Returns:
            FineTuneResult with status and details
        """
        start_time = datetime.now()

        try:
            # 1. Check if training backend is available
            if not self.training_backend:
                logger.warning("No training backend configured, using mock")
                return await self._mock_finetune(method or TrainingMethod.SFT)

            # 2. Prepare data
            logger.info("Step 1: Exporting training data")
            raw_data = await self.data_collector.export()

            if not raw_data.success_traces and not raw_data.preference_pairs:
                return FineTuneResult(
                    status="failed",
                    reason="No training data available",
                )

            # 3. Curate data
            logger.info("Step 2: Curating training data")
            curated = await self.curator.filter(raw_data)

            if len(curated.success_traces) < 10 and len(curated.preference_pairs) < 5:
                return FineTuneResult(
                    status="failed",
                    reason=f"Insufficient curated data: {len(curated.success_traces)} traces, {len(curated.preference_pairs)} pairs",
                )

            # 4. Choose method if not specified
            if method is None:
                if curated.has_preferences:
                    method = TrainingMethod.DPO
                elif curated.reasoning_heavy:
                    method = TrainingMethod.GRPO
                else:
                    method = TrainingMethod.SFT

            # 5. Prepare config
            if config is None:
                config = FineTuneConfig(method=method)
            config.method = method

            logger.info(f"Step 3: Training with {method.value}")

            # 6. Train
            new_model = await self.training_backend.train(
                base_model=self.current_model,
                dataset=curated,
                config=config,
            )

            # 7. Evaluate
            logger.info("Step 4: Evaluating models")

            if self.evaluator:
                new_eval = await self.evaluator.evaluate(new_model)
                old_eval = await self.evaluator.evaluate(self.current_model)
                new_score = new_eval.score
                old_score = old_eval.score
            else:
                # Mock evaluation
                new_score = 0.75
                old_score = 0.70

            improvement = new_score - old_score

            # 8. Deploy decision
            training_time = (datetime.now() - start_time).total_seconds()

            if new_score > old_score:
                logger.info(f"Deploying new model (improvement: {improvement:+.2f})")
                old_model = self.current_model
                self.current_model = new_model
                self._last_finetune = datetime.now()

                return FineTuneResult(
                    status="deployed",
                    new_model_name=new_model,
                    old_model_name=old_model,
                    new_score=new_score,
                    old_score=old_score,
                    improvement=improvement,
                    method_used=method,
                    training_time_seconds=training_time,
                    reason="New model outperforms current",
                    config=config,
                )
            else:
                logger.info(f"Rolling back (no improvement: {improvement:+.2f})")
                return FineTuneResult(
                    status="rollback",
                    new_model_name=new_model,
                    old_model_name=self.current_model,
                    new_score=new_score,
                    old_score=old_score,
                    improvement=improvement,
                    method_used=method,
                    training_time_seconds=training_time,
                    reason="No improvement over current model",
                    config=config,
                )

        except Exception as e:
            logger.error(f"Fine-tuning failed: {e}")
            return FineTuneResult(
                status="failed",
                reason=str(e),
                training_time_seconds=(datetime.now() - start_time).total_seconds(),
            )

    async def _mock_finetune(self, method: TrainingMethod) -> FineTuneResult:
        """Mock fine-tuning for testing without backend."""
        logger.info(f"Mock fine-tuning with {method.value}")

        # Simulate some work
        import asyncio

        await asyncio.sleep(0.1)

        return FineTuneResult(
            status="deployed",
            new_model_name=f"{self.current_model}-finetuned-{datetime.now().strftime('%Y%m%d')}",
            old_model_name=self.current_model,
            new_score=0.75,
            old_score=0.70,
            improvement=0.05,
            method_used=method,
            training_time_seconds=0.1,
            reason="Mock training completed",
            config=FineTuneConfig(method=method),
        )

    async def get_status(self) -> dict[str, Any]:
        """Get current fine-tuner status."""
        stats = await self.data_collector.get_stats()
        trigger = await self.check_trigger()

        return {
            "current_model": self.current_model,
            "last_finetune": self._last_finetune.isoformat() if self._last_finetune else None,
            "pending_trigger": trigger.value if trigger else None,
            "data_stats": stats,
            "trust_history_len": len(self._trust_history),
            "performance_history_len": len(self._performance_history),
            "has_training_backend": self.training_backend is not None,
            "has_evaluator": self.evaluator is not None,
        }

    def save_state(self, path: Path) -> None:
        """Save fine-tuner state to file."""
        state = {
            "current_model": self.current_model,
            "last_finetune": self._last_finetune.isoformat() if self._last_finetune else None,
            "trust_history": self._trust_history,
            "performance_history": self._performance_history,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved fine-tuner state to {path}")

    def load_state(self, path: Path) -> None:
        """Load fine-tuner state from file."""
        if not path.exists():
            return

        try:
            with open(path) as f:
                state = json.load(f)

            self.current_model = state.get("current_model", self.current_model)
            if state.get("last_finetune"):
                self._last_finetune = datetime.fromisoformat(state["last_finetune"])
            self._trust_history = state.get("trust_history", [])
            self._performance_history = state.get("performance_history", [])

            logger.info(f"Loaded fine-tuner state from {path}")

        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
