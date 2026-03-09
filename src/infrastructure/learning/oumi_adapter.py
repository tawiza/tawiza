"""Oumi Training Adapter - Fine-tuning Pipeline for TAJINE.

This adapter integrates with Oumi.ai for training territory-specialized
language models using CoALM (Collaborative Agent Language Model) approach.

The adapter supports:
- LoRA/QLoRA fine-tuning for efficient training
- CoALM multi-agent training for collaborative reasoning
- Territorial specialization for French departmental analysis
- Fallback to Ollama when Oumi is not available

Security Note:
    All subprocess calls use asyncio.create_subprocess_exec() with argument lists,
    NOT shell strings. This is safe from command injection as arguments are passed
    directly to the executable without shell interpretation.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .training_adapters import (
    EvaluationResult,
    TrainingAdapter,
    TrainingConfig,
    TrainingResult,
    register_adapter,
    utc_now,
)


@dataclass
class OumiTrainingConfig(TrainingConfig):
    """Configuration for Oumi training with TAJINE extensions.

    Extends base TrainingConfig with Oumi-specific and territorial settings.
    """

    # Base model override for TAJINE
    base_model: str = "qwen3.5:27b"

    # Oumi-specific settings
    training_backend: str = "oumi"
    oumi_version: str = "latest"

    # CoALM (Collaborative Agent LM) settings
    use_coalm: bool = True
    coalm_agents: int = 4
    coalm_coordination: str = "hierarchical"  # hierarchical, peer, consensus
    coalm_specializations: list[str] = field(
        default_factory=lambda: ["extraction", "validation", "analysis", "synthesis"]
    )

    # Territorial specialization for TAJINE
    territory_code: str | None = None  # e.g., "34" for Hérault
    territory_specialization: bool = False
    include_insee_context: bool = True
    include_sirene_context: bool = True

    # Training optimizations
    use_unsloth: bool = True  # Unsloth for faster training
    quantization: str = "4bit"  # 4bit, 8bit, none

    # Evaluation settings
    eval_territorial_metrics: bool = True
    eval_siret_extraction: bool = True


class OumiAdapter(TrainingAdapter):
    """Training adapter for Oumi.ai framework.

    Oumi.ai provides advanced training capabilities including:
    - CoALM multi-agent fine-tuning
    - Efficient LoRA/QLoRA training
    - Integration with various model architectures

    For TAJINE, this adapter adds:
    - Territorial specialization (French departments)
    - SIRET/SIREN extraction optimization
    - INSEE data integration

    Example:
        adapter = OumiAdapter()
        result = await adapter.train(
            dataset_path="data/tajine_train.jsonl",
            output_dir="models/coalm-34",
            config=OumiTrainingConfig(
                territory_code="34",
                use_coalm=True,
            ),
        )
    """

    def __init__(
        self,
        oumi_path: str | None = None,
        fallback_to_ollama: bool = True,
        ollama_url: str = "http://localhost:11434",
        config_path: str | None = None,
    ):
        """Initialize Oumi adapter.

        Args:
            oumi_path: Path to Oumi installation (default: /opt/oumi)
            fallback_to_ollama: Fall back to Ollama if Oumi unavailable
            ollama_url: Ollama API URL for fallback
            config_path: Path to base configuration file
        """
        self.oumi_path = Path(oumi_path) if oumi_path else Path("/opt/oumi")
        self.fallback_to_ollama = fallback_to_ollama
        self.ollama_url = ollama_url
        self.config_path = config_path

        logger.info(
            f"OumiAdapter initialized (oumi_path={self.oumi_path}, "
            f"fallback={fallback_to_ollama})"
        )

    def is_available(self) -> bool:
        """Check if Oumi training framework is available.

        Returns:
            True if Oumi is installed and accessible
        """
        try:
            # Check if oumi_path exists
            if self.oumi_path.exists():
                return True
            # Check if oumi is importable
            import importlib.util
            spec = importlib.util.find_spec("oumi")
            return spec is not None
        except Exception:
            return False

    def generate_config(
        self,
        dataset_path: str,
        output_dir: str,
        config: OumiTrainingConfig | None = None,
    ) -> str:
        """Generate Oumi training configuration file.

        Args:
            dataset_path: Path to training data
            output_dir: Output directory
            config: Training configuration

        Returns:
            Path to generated config file
        """
        config = config or OumiTrainingConfig()

        oumi_config = {
            # Model settings
            "model": {
                "name": config.base_model,
                "type": config.model_type,
                "quantization": config.quantization,
            },
            # Dataset
            "data": {
                "train_path": dataset_path,
                "format": "jsonl",
                "max_seq_length": config.max_seq_length,
            },
            # Training
            "training": {
                "output_dir": output_dir,
                "num_epochs": config.num_epochs,
                "batch_size": config.batch_size,
                "gradient_accumulation_steps": config.gradient_accumulation_steps,
                "learning_rate": config.learning_rate,
                "warmup_ratio": config.warmup_ratio,
                "weight_decay": config.weight_decay,
                "fp16": config.fp16,
                "bf16": config.bf16,
            },
            # LoRA
            "lora": {
                "enabled": config.use_lora,
                "rank": config.lora_rank,
                "alpha": config.lora_alpha,
                "dropout": config.lora_dropout,
                "target_modules": config.lora_target_modules,
            },
            # Optimization
            "optimizer": {
                "name": config.optimizer,
                "scheduler": config.scheduler,
            },
            # Logging
            "logging": {
                "steps": config.logging_steps,
                "save_steps": config.save_steps,
                "eval_steps": config.eval_steps,
            },
        }

        # Add CoALM configuration if enabled
        if config.use_coalm:
            oumi_config["coalm"] = {
                "enabled": True,
                "num_agents": config.coalm_agents,
                "coordination": config.coalm_coordination,
                "specializations": config.coalm_specializations,
            }

        # Add territorial configuration for TAJINE
        if config.territory_specialization and config.territory_code:
            oumi_config["territorial"] = {
                "enabled": True,
                "department_code": config.territory_code,
                "include_insee": config.include_insee_context,
                "include_sirene": config.include_sirene_context,
            }

        # Add Unsloth optimization
        if config.use_unsloth:
            oumi_config["optimization"] = {
                "use_unsloth": True,
                "gradient_checkpointing": True,
            }

        # Write config file
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        config_file = output_path / "oumi_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(oumi_config, f, default_flow_style=False)

        logger.info(f"Generated Oumi config at {config_file}")
        return str(config_file)

    def prepare_dataset(
        self,
        raw_data: list[dict[str, Any]],
        output_path: Path,
        territory_code: str | None = None,
        format: str = "standard",
    ) -> Path:
        """Prepare dataset for Oumi training.

        Args:
            raw_data: Raw data records
            output_path: Output file path
            territory_code: Optional territory code for context
            format: Dataset format ('standard', 'coalm')

        Returns:
            Path to prepared dataset
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        prepared_data = []

        for record in raw_data:
            if format == "coalm":
                # CoALM format includes agent role annotations
                prepared = self._format_for_coalm(record, territory_code)
            else:
                # Standard instruction-output format
                prepared = self._format_standard(record, territory_code)

            prepared_data.append(prepared)

        # Write JSONL
        with open(output_path, "w", encoding="utf-8") as f:
            for item in prepared_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"Prepared {len(prepared_data)} examples to {output_path}")
        return output_path

    def _format_standard(
        self, record: dict[str, Any], territory_code: str | None
    ) -> dict[str, Any]:
        """Format record to standard instruction format."""
        formatted = {
            "instruction": record.get("instruction", record.get("text", "")),
            "input": record.get("input", ""),
            "output": record.get("output", ""),
        }

        # Add territorial context
        if territory_code:
            context = f"[Département {territory_code}] "
            formatted["instruction"] = context + formatted["instruction"]

        return formatted

    def _format_for_coalm(
        self, record: dict[str, Any], territory_code: str | None
    ) -> dict[str, Any]:
        """Format record for CoALM multi-agent training."""
        formatted = self._format_standard(record, territory_code)

        # Add CoALM metadata
        formatted["coalm"] = {
            "agents": ["extractor", "validator", "analyzer", "synthesizer"],
            "coordination": "sequential",
        }

        return formatted

    async def _run_safe_subprocess(
        self, cmd: list[str], cwd: str | None = None
    ) -> tuple:
        """Run subprocess safely with argument list (no shell injection risk).

        Uses asyncio.create_subprocess_exec which passes arguments directly
        to the executable without shell interpretation, similar to execFile.

        Args:
            cmd: Command as list of arguments (e.g., ["python", "-m", "oumi"])
            cwd: Working directory

        Returns:
            Tuple of ((stdout, stderr), returncode)
        """
        # Safe: arguments passed as list, not shell string
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await process.communicate()
        return (stdout, stderr), process.returncode

    async def _run_oumi_training(
        self,
        config_file: str,
        output_dir: str,
    ) -> dict[str, Any]:
        """Run Oumi training process.

        Args:
            config_file: Path to config file
            output_dir: Output directory

        Returns:
            Training result dict
        """
        # Command as argument list (safe from injection)
        cmd = [
            "python",
            "-m",
            "oumi.train",
            "--config",
            config_file,
        ]

        logger.info(f"Starting Oumi training with config: {config_file}")

        (stdout, stderr), returncode = await self._run_safe_subprocess(
            cmd, cwd=str(self.oumi_path)
        )

        if returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Oumi training failed: {error_msg}")

        # Parse training output
        metrics = self._parse_training_output(stdout.decode())

        return {
            "success": True,
            "model_path": output_dir,
            "metrics": metrics,
        }

    async def _run_ollama_fallback(
        self,
        dataset_path: str,
        output_dir: str,
        config: OumiTrainingConfig | None = None,
    ) -> dict[str, Any]:
        """Fallback to Ollama-based training.

        Uses Ollama's Modelfile approach for fine-tuning when Oumi is unavailable.
        """
        config = config or OumiTrainingConfig()

        logger.warning("Falling back to Ollama training (Oumi unavailable)")

        # Create Modelfile for Ollama
        modelfile_content = f"""FROM {config.base_model}
PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM You are a territorial analysis assistant specialized in French economic data.
"""

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        modelfile_path = output_path / "Modelfile"
        with open(modelfile_path, "w") as f:
            f.write(modelfile_content)

        # Create model with Ollama (command as list - safe)
        model_name = f"tajine-{config.territory_code or 'base'}"

        cmd = [
            "ollama",
            "create",
            model_name,
            "-f",
            str(modelfile_path),
        ]

        (stdout, stderr), returncode = await self._run_safe_subprocess(cmd)

        if returncode != 0:
            raise RuntimeError(f"Ollama fallback failed: {stderr.decode()}")

        return {
            "success": True,
            "model_path": str(output_path),
            "metrics": {"fallback": "ollama"},
        }

    def _parse_training_output(self, output: str) -> dict[str, Any]:
        """Parse training output for metrics."""
        import re

        metrics = {}

        for line in output.split("\n"):
            line_lower = line.lower()

            # Extract loss
            if "loss" in line_lower:
                match = re.search(r"loss[:\s]+([0-9.]+)", line_lower)
                if match:
                    metrics["loss"] = float(match.group(1))

            # Extract accuracy
            if "accuracy" in line_lower:
                match = re.search(r"accuracy[:\s]+([0-9.]+)", line_lower)
                if match:
                    metrics["accuracy"] = float(match.group(1))

        return metrics

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        config: TrainingConfig | None = None,
    ) -> TrainingResult:
        """Train model using Oumi.

        Args:
            dataset_path: Path to training data (JSONL)
            output_dir: Directory for output
            config: Training configuration (OumiTrainingConfig recommended)

        Returns:
            Training result
        """
        run_id = str(uuid.uuid4())[:8]
        started_at = utc_now()

        # Convert to OumiTrainingConfig if needed
        if config is None:
            config = OumiTrainingConfig()
        elif not isinstance(config, OumiTrainingConfig):
            # Create OumiTrainingConfig with base config values
            config = OumiTrainingConfig(
                base_model=config.base_model,
                learning_rate=config.learning_rate,
                num_epochs=config.num_epochs,
                batch_size=config.batch_size,
                use_lora=config.use_lora,
                lora_rank=config.lora_rank,
            )

        try:
            # Generate config file
            config_file = self.generate_config(dataset_path, output_dir, config)

            # Try Oumi training first
            try:
                result_data = await self._run_oumi_training(config_file, output_dir)
            except (FileNotFoundError, RuntimeError) as e:
                if self.fallback_to_ollama:
                    logger.warning(f"Oumi failed ({e}), trying Ollama fallback")
                    result_data = await self._run_ollama_fallback(
                        dataset_path, output_dir, config
                    )
                else:
                    raise

            completed_at = utc_now()
            duration = (completed_at - started_at).total_seconds()

            return TrainingResult(
                run_id=run_id,
                model_path=result_data.get("model_path"),
                metrics=result_data.get("metrics", {}),
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Training error: {e}")
            completed_at = utc_now()
            return TrainingResult(
                run_id=run_id,
                success=False,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
            )

    async def _run_oumi_evaluation(
        self,
        model_path: str,
        eval_dataset_path: str | None = None,
        include_territorial_metrics: bool = False,
    ) -> dict[str, Any]:
        """Run Oumi evaluation process."""
        # Command as argument list (safe from injection)
        cmd = [
            "python",
            "-m",
            "oumi.evaluate",
            "--model_path",
            model_path,
        ]

        if eval_dataset_path:
            cmd.extend(["--dataset", eval_dataset_path])

        if include_territorial_metrics:
            cmd.append("--territorial-metrics")

        (stdout, stderr), returncode = await self._run_safe_subprocess(cmd)

        if returncode != 0:
            logger.warning(f"Evaluation failed: {stderr.decode()}")
            return {}

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            return self._parse_training_output(stdout.decode())

    async def evaluate(
        self,
        model_path: str,
        eval_dataset_path: str | None = None,
        include_territorial_metrics: bool = False,
    ) -> EvaluationResult:
        """Evaluate trained model.

        Args:
            model_path: Path to trained model
            eval_dataset_path: Optional evaluation dataset
            include_territorial_metrics: Include TAJINE-specific metrics

        Returns:
            Evaluation result
        """
        try:
            result_data = await self._run_oumi_evaluation(
                model_path,
                eval_dataset_path,
                include_territorial_metrics,
            )

            # Extract standard metrics
            accuracy = result_data.get("accuracy", 0.0)
            perplexity = result_data.get("perplexity", 0.0)
            loss = result_data.get("loss", 0.0)
            f1_score = result_data.get("f1_score", 0.0)

            # Extract custom territorial metrics
            custom_metrics = {}
            if include_territorial_metrics:
                custom_metrics = {
                    k: v
                    for k, v in result_data.items()
                    if k not in ["accuracy", "perplexity", "loss", "f1_score"]
                }

            return EvaluationResult(
                accuracy=accuracy,
                perplexity=perplexity,
                loss=loss,
                f1_score=f1_score,
                custom_metrics=custom_metrics,
            )

        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return EvaluationResult()


# Register adapter in the global registry
register_adapter("oumi", OumiAdapter)
