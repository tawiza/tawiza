"""Training Adapters - Interfaces to training backends."""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


@dataclass
class TrainingConfig:
    """Configuration for model training.

    Compatible with LLaMA-Factory and similar frameworks.
    """

    # Base model
    base_model: str = "qwen2.5-coder:7b"
    model_type: str = "auto"

    # Training hyperparameters
    learning_rate: float = 2e-5
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    warmup_ratio: float = 0.1

    # LoRA settings
    use_lora: bool = True
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: str = "all"

    # Optimization
    optimizer: str = "adamw_torch"
    scheduler: str = "cosine"
    weight_decay: float = 0.01
    fp16: bool = True
    bf16: bool = False

    # Evaluation
    eval_steps: int = 100
    save_steps: int = 100
    logging_steps: int = 10


@dataclass
class TrainingResult:
    """Result from a training run."""

    run_id: str
    model_path: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0


@dataclass
class EvaluationResult:
    """Result from model evaluation."""

    accuracy: float = 0.0
    perplexity: float = 0.0
    loss: float = 0.0
    f1_score: float = 0.0
    custom_metrics: dict[str, Any] = field(default_factory=dict)


class TrainingAdapter(ABC):
    """Abstract base class for training adapters.

    Defines the interface that all training backends must implement.
    """

    @abstractmethod
    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        config: TrainingConfig | None = None,
    ) -> TrainingResult:
        """Train a model on the given dataset.

        Args:
            dataset_path: Path to training data
            output_dir: Directory for output
            config: Training configuration

        Returns:
            Training result
        """
        pass

    @abstractmethod
    async def evaluate(
        self,
        model_path: str,
        eval_dataset_path: str | None = None,
    ) -> EvaluationResult:
        """Evaluate a trained model.

        Args:
            model_path: Path to model
            eval_dataset_path: Optional evaluation dataset

        Returns:
            Evaluation result
        """
        pass


class LlamaFactoryAdapter(TrainingAdapter):
    """Adapter for LLaMA-Factory training framework.

    LLaMA-Factory supports LoRA, QLoRA, and full fine-tuning
    for various LLM architectures.

    Example:
        adapter = LlamaFactoryAdapter()
        result = await adapter.train(
            dataset_path="data/train.jsonl",
            output_dir="models/output",
        )
    """

    def __init__(
        self,
        config_path: str | None = None,
        llamafactory_path: str = "/opt/LLaMA-Factory",
    ):
        """Initialize adapter.

        Args:
            config_path: Path to base config file
            llamafactory_path: Path to LLaMA-Factory installation
        """
        self.config_path = config_path
        self.llamafactory_path = Path(llamafactory_path)

        logger.info("LlamaFactoryAdapter initialized")

    def generate_config(
        self,
        dataset_path: str,
        output_dir: str,
        config: TrainingConfig | None = None,
    ) -> str:
        """Generate LlamaFactory YAML config file.

        Args:
            dataset_path: Path to training data
            output_dir: Output directory
            config: Training configuration

        Returns:
            Path to generated config file
        """
        config = config or TrainingConfig()

        llama_config = {
            # Model
            "model_name_or_path": config.base_model,
            "model_type": config.model_type,

            # Dataset
            "dataset": dataset_path,
            "template": "default",

            # Training
            "output_dir": output_dir,
            "num_train_epochs": config.num_epochs,
            "per_device_train_batch_size": config.batch_size,
            "gradient_accumulation_steps": config.gradient_accumulation_steps,
            "learning_rate": config.learning_rate,
            "warmup_ratio": config.warmup_ratio,
            "max_seq_length": config.max_seq_length,

            # LoRA
            "finetuning_type": "lora" if config.use_lora else "full",
            "lora_rank": config.lora_rank,
            "lora_alpha": config.lora_alpha,
            "lora_dropout": config.lora_dropout,

            # Optimization
            "optim": config.optimizer,
            "lr_scheduler_type": config.scheduler,
            "weight_decay": config.weight_decay,
            "fp16": config.fp16,
            "bf16": config.bf16,

            # Logging
            "logging_steps": config.logging_steps,
            "save_steps": config.save_steps,
            "eval_steps": config.eval_steps,
        }

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        config_file = output_path / "train_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(llama_config, f, default_flow_style=False)

        logger.info(f"Generated config at {config_file}")
        return str(config_file)

    async def _run_subprocess(self, cmd: list[str], cwd: str | None = None):
        """Run a subprocess safely with arguments list.

        Uses create_subprocess_exec which is safe from shell injection
        since arguments are passed as a list, not a shell string.
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        return await process.communicate(), process.returncode

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        config: TrainingConfig | None = None,
    ) -> TrainingResult:
        """Train model using LLaMA-Factory.

        Args:
            dataset_path: Path to training data (JSONL)
            output_dir: Directory for output
            config: Training configuration

        Returns:
            Training result
        """
        run_id = str(uuid.uuid4())[:8]
        started_at = utc_now()

        try:
            # Generate config
            config_file = self.generate_config(dataset_path, output_dir, config)

            # Run LLaMA-Factory training (safe: args passed as list)
            cmd = [
                "python", "-m", "llamafactory.train",
                "--config", config_file,
            ]

            logger.info(f"Starting training run {run_id}")

            (stdout, stderr), returncode = await self._run_subprocess(
                cmd, cwd=str(self.llamafactory_path)
            )

            if returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Training failed: {error_msg}")
                return TrainingResult(
                    run_id=run_id,
                    success=False,
                    error=error_msg,
                    started_at=started_at,
                    completed_at=utc_now(),
                )

            # Parse metrics from output
            metrics = self._parse_training_output(stdout.decode())

            return TrainingResult(
                run_id=run_id,
                model_path=output_dir,
                metrics=metrics,
                success=True,
                started_at=started_at,
                completed_at=utc_now(),
            )

        except Exception as e:
            logger.error(f"Training error: {e}")
            return TrainingResult(
                run_id=run_id,
                success=False,
                error=str(e),
                started_at=started_at,
                completed_at=utc_now(),
            )

    def _parse_training_output(self, output: str) -> dict[str, Any]:
        """Parse training output for metrics.

        Args:
            output: Training stdout

        Returns:
            Extracted metrics
        """
        metrics = {}

        # Look for common patterns
        for line in output.split("\n"):
            if "loss" in line.lower():
                try:
                    # Try to extract loss value
                    import re
                    match = re.search(r"loss[:\s]+([0-9.]+)", line.lower())
                    if match:
                        metrics["loss"] = float(match.group(1))
                except (ValueError, AttributeError):
                    pass

        return metrics

    async def evaluate(
        self,
        model_path: str,
        eval_dataset_path: str | None = None,
    ) -> EvaluationResult:
        """Evaluate model using LLaMA-Factory.

        Args:
            model_path: Path to trained model
            eval_dataset_path: Optional evaluation dataset

        Returns:
            Evaluation result
        """
        try:
            cmd = [
                "python", "-m", "llamafactory.evaluate",
                "--model_path", model_path,
            ]

            if eval_dataset_path:
                cmd.extend(["--dataset", eval_dataset_path])

            (stdout, stderr), returncode = await self._run_subprocess(cmd)

            if returncode != 0:
                logger.warning(f"Evaluation failed: {stderr.decode()}")
                return EvaluationResult()

            # Parse evaluation output
            try:
                result_data = json.loads(stdout.decode())
                return EvaluationResult(
                    accuracy=result_data.get("accuracy", 0.0),
                    perplexity=result_data.get("perplexity", 0.0),
                    loss=result_data.get("loss", 0.0),
                )
            except json.JSONDecodeError:
                logger.warning("Could not parse evaluation output")
                return EvaluationResult()

        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return EvaluationResult()


# Adapter registry
_ADAPTERS: dict[str, type[TrainingAdapter]] = {
    "llama_factory": LlamaFactoryAdapter,
}


def get_available_adapters() -> dict[str, type[TrainingAdapter]]:
    """Get all available training adapters.

    Returns:
        Dictionary of adapter name to class
    """
    return _ADAPTERS.copy()


def create_adapter(name: str, **kwargs) -> TrainingAdapter:
    """Create a training adapter by name.

    Args:
        name: Adapter name
        **kwargs: Adapter constructor arguments

    Returns:
        Instantiated adapter

    Raises:
        ValueError: If adapter not found
    """
    if name not in _ADAPTERS:
        raise ValueError(f"Unknown adapter: {name}. Available: {list(_ADAPTERS.keys())}")

    return _ADAPTERS[name](**kwargs)


def register_adapter(name: str, adapter_class: type[TrainingAdapter]) -> None:
    """Register a new training adapter.

    Args:
        name: Adapter name
        adapter_class: Adapter class
    """
    _ADAPTERS[name] = adapter_class
    logger.info(f"Registered training adapter: {name}")
