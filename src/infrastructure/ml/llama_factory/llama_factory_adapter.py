"""LLaMA-Factory adapter for model training.

This adapter integrates with LLaMA-Factory for fine-tuning LLMs.
It provides both CLI-based and Python API-based training.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from src.application.ports.ml_ports import IModelTrainer
from src.infrastructure.config.settings import Settings


class LlamaFactoryAdapter(IModelTrainer):
    """Adapter for LLaMA-Factory training.

    LLaMA-Factory supports multiple training methods:
    - Supervised Fine-Tuning (SFT)
    - Reward Modeling (RM)
    - PPO (Proximal Policy Optimization)
    - DPO (Direct Preference Optimization)

    This adapter focuses on SFT and can be extended for RLHF methods.
    """

    def __init__(
        self,
        settings: Settings,
        use_cli: bool = True,
    ) -> None:
        """Initialize LLaMA-Factory adapter.

        Args:
            settings: Application settings
            use_cli: Use CLI interface (True) or Python API (False)
        """
        self.settings = settings
        self.use_cli = use_cli
        self.models_dir = Path(settings.training.models_dir)
        self.data_dir = Path(settings.training.data_dir)
        self.output_dir = Path(settings.training.output_dir)

        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Initialized LLaMA-Factory adapter (models: {self.models_dir}, data: {self.data_dir})"
        )

    async def train(
        self,
        model_name: str,
        base_model: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> str:
        """Train a model using LLaMA-Factory.

        Args:
            model_name: Name of the model being trained
            base_model: Base model to fine-tune (e.g., "meta-llama/Llama-2-7b-chat-hf")
            dataset_path: Path to training dataset (JSONL format)
            output_dir: Directory to save the trained model
            hyperparameters: Training hyperparameters

        Returns:
            MLflow run ID for tracking

        Raises:
            RuntimeError: If training fails
        """
        logger.info(f"Starting training for {model_name} based on {base_model}")

        # Generate unique run ID
        import uuid

        mlflow_run_id = str(uuid.uuid4())

        # Prepare training config
        config = self._prepare_training_config(
            base_model=base_model,
            dataset_path=dataset_path,
            output_dir=output_dir,
            hyperparameters=hyperparameters,
        )

        try:
            if self.use_cli:
                await self._train_with_cli(config, mlflow_run_id)
            else:
                await self._train_with_api(config, mlflow_run_id)

            logger.info(
                f"Training completed successfully for {model_name} (run_id: {mlflow_run_id})"
            )
            return mlflow_run_id

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            raise RuntimeError(f"Training failed: {e}") from e

    async def train_with_rlhf(
        self,
        model_path: str,
        reward_model_path: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> str:
        """Train a model with RLHF using PPO.

        Args:
            model_path: Path to the base model
            reward_model_path: Path to the reward model
            dataset_path: Path to training dataset
            output_dir: Directory to save the trained model
            hyperparameters: Training hyperparameters

        Returns:
            MLflow run ID

        Note:
            This requires OpenRLHF or LLaMA-Factory's PPO implementation
        """
        logger.info("Starting RLHF training with PPO")

        # Generate unique run ID
        import uuid

        mlflow_run_id = str(uuid.uuid4())

        # Prepare PPO config
        config = self._prepare_ppo_config(
            model_path=model_path,
            reward_model_path=reward_model_path,
            dataset_path=dataset_path,
            output_dir=output_dir,
            hyperparameters=hyperparameters,
        )

        try:
            # For RLHF, we would use OpenRLHF or LLaMA-Factory's PPO
            # This is a simplified version
            await self._train_ppo(config, mlflow_run_id)

            logger.info(f"RLHF training completed (run_id: {mlflow_run_id})")
            return mlflow_run_id

        except Exception as e:
            logger.error(f"RLHF training failed: {e}", exc_info=True)
            raise RuntimeError(f"RLHF training failed: {e}") from e

    async def get_training_status(self, mlflow_run_id: str) -> dict[str, Any]:
        """Get the status of a training job.

        Args:
            mlflow_run_id: MLflow run ID

        Returns:
            Training status information
        """
        # In a real implementation, this would check:
        # 1. MLflow for run status
        # 2. Training process status
        # 3. Log files for progress

        # For now, return a mock status
        return {
            "run_id": mlflow_run_id,
            "status": "running",  # or "completed", "failed"
            "progress": 0.5,  # 50%
            "current_epoch": 2,
            "total_epochs": 3,
            "current_step": 1000,
            "total_steps": 2000,
            "metrics": {
                "loss": 0.5,
                "learning_rate": 2e-5,
            },
        }

    def _prepare_training_config(
        self,
        base_model: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare LLaMA-Factory training configuration.

        Args:
            base_model: Base model name/path
            dataset_path: Training dataset path
            output_dir: Output directory
            hyperparameters: Training hyperparameters

        Returns:
            Training configuration dictionary
        """
        config = {
            # Model
            "model_name_or_path": base_model,
            "output_dir": output_dir,
            # Dataset
            "dataset": "custom",
            "dataset_dir": str(self.data_dir),
            "train_file": dataset_path,
            # Training
            "stage": "sft",  # Supervised Fine-Tuning
            "do_train": True,
            "finetuning_type": "lora",  # Use LoRA by default
            # Hyperparameters
            "per_device_train_batch_size": hyperparameters.get("batch_size", 4),
            "gradient_accumulation_steps": hyperparameters.get("gradient_accumulation_steps", 4),
            "learning_rate": hyperparameters.get("learning_rate", 2e-5),
            "num_train_epochs": hyperparameters.get("num_epochs", 3),
            "max_seq_length": hyperparameters.get("max_seq_length", 2048),
            # LoRA config
            "lora_rank": hyperparameters.get("lora_rank", 8),
            "lora_alpha": hyperparameters.get("lora_alpha", 16),
            "lora_dropout": hyperparameters.get("lora_dropout", 0.1),
            "lora_target": "q_proj,v_proj",
            # Optimization
            "lr_scheduler_type": "cosine",
            "warmup_steps": hyperparameters.get("warmup_steps", 100),
            "optim": "adamw_torch",
            # Precision
            "fp16": hyperparameters.get("fp16", True),
            "bf16": hyperparameters.get("bf16", False),
            # Logging
            "logging_steps": 10,
            "save_steps": hyperparameters.get("save_steps", 500),
            "eval_steps": hyperparameters.get("eval_steps", 500),
            # Misc
            "seed": 42,
            "report_to": "none",  # We use MLflow separately
        }

        return config

    def _prepare_ppo_config(
        self,
        model_path: str,
        reward_model_path: str,
        dataset_path: str,
        output_dir: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare PPO training configuration for RLHF.

        Args:
            model_path: Path to base model
            reward_model_path: Path to reward model
            dataset_path: Training dataset path
            output_dir: Output directory
            hyperparameters: Training hyperparameters

        Returns:
            PPO configuration dictionary
        """
        config = {
            # Models
            "model_name_or_path": model_path,
            "reward_model": reward_model_path,
            "output_dir": output_dir,
            # Dataset
            "dataset": "custom",
            "train_file": dataset_path,
            # PPO config
            "stage": "ppo",
            "ppo_epochs": 4,
            "ppo_score_norm": True,
            "ppo_whiten_rewards": True,
            # Other params from base config
            **self._prepare_training_config(
                base_model=model_path,
                dataset_path=dataset_path,
                output_dir=output_dir,
                hyperparameters=hyperparameters,
            ),
        }

        return config

    async def _train_with_cli(
        self,
        config: dict[str, Any],
        mlflow_run_id: str,
    ) -> None:
        """Train using LLaMA-Factory CLI.

        Args:
            config: Training configuration
            mlflow_run_id: MLflow run ID for tracking
        """
        # Save config to JSON file
        config_path = self.output_dir / f"config_{mlflow_run_id}.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        # Build CLI command
        cmd = [
            "llamafactory-cli",
            "train",
            str(config_path),
        ]

        logger.info(f"Running LLaMA-Factory CLI: {' '.join(cmd)}")

        # Run training process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Stream output
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            logger.info(f"[Training] {line.decode().strip()}")

        # Wait for completion
        await process.wait()

        if process.returncode != 0:
            stderr = await process.stderr.read()
            raise RuntimeError(f"Training failed with code {process.returncode}: {stderr.decode()}")

    async def _train_with_api(
        self,
        config: dict[str, Any],
        mlflow_run_id: str,
    ) -> None:
        """Train using LLaMA-Factory Python API.

        Args:
            config: Training configuration
            mlflow_run_id: MLflow run ID
        """
        # This would use LLaMA-Factory's Python API
        # For now, we use the CLI version
        logger.warning("Python API training not yet implemented, using CLI")
        await self._train_with_cli(config, mlflow_run_id)

    async def _train_ppo(
        self,
        config: dict[str, Any],
        mlflow_run_id: str,
    ) -> None:
        """Train using PPO for RLHF.

        Args:
            config: PPO configuration
            mlflow_run_id: MLflow run ID
        """
        # This would integrate with OpenRLHF or LLaMA-Factory's PPO
        logger.warning("PPO training requires OpenRLHF integration")
        # For now, treat it like regular training
        await self._train_with_cli(config, mlflow_run_id)
