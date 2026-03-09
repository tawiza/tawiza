"""
LoRA Fine-Tuner with Unsloth

Efficient fine-tuning using LoRA (Low-Rank Adaptation) and Unsloth for optimized training.

Features:
- QLoRA (Quantized LoRA) for memory efficiency
- Unsloth library for 2x faster training, 70% less memory
- ROCm GPU support for AMD GPUs
- MLflow integration for experiment tracking
- Progress tracking via ProgressTracker
- Automatic checkpoint saving
- Gradient accumulation support

Performance improvements:
- 2x faster training vs standard LoRA
- 70% less VRAM usage
- Support for larger models on consumer GPUs
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    logger.debug(
        "PyTorch not available. Install with: pip install torch"
    )
    TORCH_AVAILABLE = False
    torch = None  # type: ignore

try:
    from unsloth import FastLanguageModel, is_bfloat16_supported
    UNSLOTH_AVAILABLE = True
except ImportError:
    logger.debug(
        "Unsloth not available (optional). Install with: pip install unsloth"
    )
    UNSLOTH_AVAILABLE = False
    # Fallback for when unsloth is not available
    FastLanguageModel = Any  # type: ignore
    def is_bfloat16_supported():
        return False  # type: ignore

try:
    from transformers import TrainingArguments
    from trl import SFTTrainer

    from datasets import Dataset
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.debug(
        "Transformers/TRL not available (optional). Install with: "
        "pip install transformers trl datasets"
    )
    TRANSFORMERS_AVAILABLE = False
    # Fallback types for when transformers is not available
    Dataset = Any  # type: ignore
    TrainingArguments = Any  # type: ignore
    SFTTrainer = Any  # type: ignore

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    logger.warning("MLflow not available for experiment tracking")
    MLFLOW_AVAILABLE = False


@dataclass
class LoRAConfig:
    """
    Configuration for LoRA fine-tuning.

    Attributes:
        r: LoRA rank (typically 16, 32, 64)
        lora_alpha: LoRA scaling factor (typically 2*r)
        lora_dropout: Dropout probability
        target_modules: Modules to apply LoRA to
        use_gradient_checkpointing: Enable gradient checkpointing
        use_4bit: Use 4-bit quantization (QLoRA)
        use_8bit: Use 8-bit quantization
    """
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = None
    use_gradient_checkpointing: bool = True
    use_4bit: bool = True
    use_8bit: bool = False

    def __post_init__(self):
        """Set defaults after initialization."""
        if self.target_modules is None:
            # Default target modules for most LLMs
            self.target_modules = [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ]


@dataclass
class TrainingConfig:
    """
    Configuration for training process.

    Attributes:
        output_dir: Directory to save checkpoints
        num_train_epochs: Number of training epochs
        per_device_train_batch_size: Batch size per device
        gradient_accumulation_steps: Gradient accumulation steps
        learning_rate: Learning rate
        max_seq_length: Maximum sequence length
        warmup_steps: Warmup steps
        logging_steps: Log every N steps
        save_steps: Save checkpoint every N steps
    """
    output_dir: str = "./outputs/lora"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 2048
    warmup_steps: int = 5
    logging_steps: int = 10
    save_steps: int = 100
    fp16: bool = False
    bf16: bool = False
    optim: str = "adamw_8bit"
    weight_decay: float = 0.01
    lr_scheduler_type: str = "linear"
    seed: int = 42


class LoRAFineTuner:
    """
    Fine-tune language models using LoRA with Unsloth optimization.

    Usage:
        config = LoRAConfig(r=16, lora_alpha=32)
        training_config = TrainingConfig(num_train_epochs=3)

        tuner = LoRAFineTuner(
            model_name="unsloth/Qwen2.5-14B-Instruct",
            lora_config=config,
            training_config=training_config
        )

        await tuner.load_model()
        await tuner.train(training_data, validation_data)
        await tuner.save_model("my-finetuned-model")
    """

    def __init__(
        self,
        model_name: str,
        lora_config: LoRAConfig,
        training_config: TrainingConfig,
        mlflow_tracking_uri: str | None = None,
        progress_callback: Callable[[int, dict[str, Any]], None] | None = None
    ):
        """
        Initialize LoRA fine-tuner.

        Args:
            model_name: HuggingFace model name or path
            lora_config: LoRA configuration
            training_config: Training configuration
            mlflow_tracking_uri: MLflow tracking URI
            progress_callback: Callback for progress updates
        """
        if not UNSLOTH_AVAILABLE:
            raise ImportError(
                "Unsloth is required but not installed. "
                "Install with: pip install unsloth"
            )

        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Transformers/TRL required. "
                "Install with: pip install transformers trl datasets"
            )

        self.model_name = model_name
        self.lora_config = lora_config
        self.training_config = training_config
        self.progress_callback = progress_callback

        # Model and tokenizer (loaded later)
        self.model = None
        self.tokenizer = None
        self.trainer = None

        # MLflow setup
        if MLFLOW_AVAILABLE and mlflow_tracking_uri:
            mlflow.set_tracking_uri(mlflow_tracking_uri)
            logger.info(f"MLflow tracking URI: {mlflow_tracking_uri}")

        # Detect GPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cuda":
            logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            logger.warning("No GPU detected, training will be slow")

        # Auto-detect bf16 support
        if is_bfloat16_supported() and not self.training_config.bf16:
            self.training_config.bf16 = True
            self.training_config.fp16 = False
            logger.info("BF16 supported and enabled")

        logger.info(f"LoRAFineTuner initialized for model: {model_name}")

    async def load_model(self, max_seq_length: int | None = None):
        """
        Load model with LoRA adapters using Unsloth.

        Args:
            max_seq_length: Override max sequence length

        Raises:
            RuntimeError: If model loading fails
        """
        try:
            logger.info(f"Loading model: {self.model_name}")

            max_seq = max_seq_length or self.training_config.max_seq_length

            # Load model with Unsloth FastLanguageModel
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.model_name,
                max_seq_length=max_seq,
                dtype=None,  # Auto-detect
                load_in_4bit=self.lora_config.use_4bit,
                load_in_8bit=self.lora_config.use_8bit,
            )

            logger.info("Model loaded successfully")

            # Add LoRA adapters
            self.model = FastLanguageModel.get_peft_model(
                self.model,
                r=self.lora_config.r,
                target_modules=self.lora_config.target_modules,
                lora_alpha=self.lora_config.lora_alpha,
                lora_dropout=self.lora_config.lora_dropout,
                bias="none",
                use_gradient_checkpointing=(
                    "unsloth" if self.lora_config.use_gradient_checkpointing else False
                ),
                random_state=self.training_config.seed,
                use_rslora=False,
                loftq_config=None,
            )

            logger.info(
                f"LoRA adapters added (r={self.lora_config.r}, "
                f"alpha={self.lora_config.lora_alpha})"
            )

            # Print trainable parameters
            trainable_params = sum(
                p.numel() for p in self.model.parameters() if p.requires_grad
            )
            total_params = sum(p.numel() for p in self.model.parameters())
            logger.info(
                f"Trainable params: {trainable_params:,} / {total_params:,} "
                f"({100 * trainable_params / total_params:.2f}%)"
            )

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    def prepare_dataset(
        self,
        data: list[dict[str, str]],
        formatting_func: Callable | None = None
    ) -> Dataset:
        """
        Prepare dataset for training.

        Args:
            data: List of training examples
            formatting_func: Custom formatting function

        Returns:
            Dataset: Prepared dataset

        Example data format:
            [
                {"instruction": "...", "input": "...", "output": "..."},
                {"instruction": "...", "input": "...", "output": "..."},
            ]
        """
        from datasets import Dataset as HFDataset

        # Create dataset
        dataset = HFDataset.from_list(data)

        logger.info(f"Dataset created with {len(dataset)} examples")
        return dataset

    async def train(
        self,
        train_data: list[dict[str, str]],
        eval_data: list[dict[str, str]] | None = None,
        formatting_func: Callable | None = None,
        experiment_name: str = "lora-finetuning"
    ) -> dict[str, Any]:
        """
        Train the model with LoRA.

        Args:
            train_data: Training examples
            eval_data: Validation examples (optional)
            formatting_func: Custom formatting function
            experiment_name: MLflow experiment name

        Returns:
            dict: Training results and metrics
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            # Start MLflow run
            if MLFLOW_AVAILABLE:
                mlflow.set_experiment(experiment_name)
                mlflow.start_run(run_name=f"{self.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

                # Log parameters
                mlflow.log_params({
                    "model_name": self.model_name,
                    "lora_r": self.lora_config.r,
                    "lora_alpha": self.lora_config.lora_alpha,
                    "lora_dropout": self.lora_config.lora_dropout,
                    "learning_rate": self.training_config.learning_rate,
                    "epochs": self.training_config.num_train_epochs,
                    "batch_size": self.training_config.per_device_train_batch_size,
                    "max_seq_length": self.training_config.max_seq_length,
                })

            # Prepare datasets
            logger.info("Preparing datasets...")
            train_dataset = self.prepare_dataset(train_data, formatting_func)
            eval_dataset = self.prepare_dataset(eval_data, formatting_func) if eval_data else None

            # Create training arguments
            training_args = TrainingArguments(
                output_dir=self.training_config.output_dir,
                num_train_epochs=self.training_config.num_train_epochs,
                per_device_train_batch_size=self.training_config.per_device_train_batch_size,
                gradient_accumulation_steps=self.training_config.gradient_accumulation_steps,
                learning_rate=self.training_config.learning_rate,
                warmup_steps=self.training_config.warmup_steps,
                logging_steps=self.training_config.logging_steps,
                save_steps=self.training_config.save_steps,
                fp16=self.training_config.fp16,
                bf16=self.training_config.bf16,
                optim=self.training_config.optim,
                weight_decay=self.training_config.weight_decay,
                lr_scheduler_type=self.training_config.lr_scheduler_type,
                seed=self.training_config.seed,
                logging_dir=f"{self.training_config.output_dir}/logs",
                report_to="mlflow" if MLFLOW_AVAILABLE else "none",
                evaluation_strategy="steps" if eval_dataset else "no",
                eval_steps=self.training_config.save_steps if eval_dataset else None,
                save_total_limit=3,
                load_best_model_at_end=bool(eval_dataset),
            )

            # Create default formatting function if not provided
            if formatting_func is None:
                def default_formatting_func(examples):
                    """Default Alpaca-style formatting."""
                    texts = []
                    for instruction, input_text, output in zip(
                        examples.get("instruction", []),
                        examples.get("input", []),
                        examples.get("output", []), strict=False
                    ):
                        text = f"### Instruction:\n{instruction}\n\n"
                        if input_text:
                            text += f"### Input:\n{input_text}\n\n"
                        text += f"### Response:\n{output}"
                        texts.append(text)
                    return texts

                formatting_func = default_formatting_func

            # Create trainer
            logger.info("Creating trainer...")
            self.trainer = SFTTrainer(
                model=self.model,
                tokenizer=self.tokenizer,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                args=training_args,
                formatting_func=formatting_func,
                max_seq_length=self.training_config.max_seq_length,
                packing=False,
            )

            # Train
            logger.info("Starting training...")
            train_result = self.trainer.train()

            # Log final metrics
            metrics = train_result.metrics
            logger.info(f"Training completed. Final metrics: {metrics}")

            if MLFLOW_AVAILABLE:
                mlflow.log_metrics(metrics)
                mlflow.end_run()

            # Call progress callback
            if self.progress_callback:
                self.progress_callback(100, {
                    "status": "completed",
                    "metrics": metrics
                })

            return {
                "status": "completed",
                "metrics": metrics,
                "model_name": self.model_name,
                "output_dir": self.training_config.output_dir
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            if MLFLOW_AVAILABLE:
                mlflow.end_run(status="FAILED")
            raise

    async def save_model(
        self,
        output_path: str,
        save_method: str = "merged"
    ):
        """
        Save fine-tuned model.

        Args:
            output_path: Path to save model
            save_method: "merged" (full model) or "lora_only" (adapters only)
        """
        if self.model is None:
            raise RuntimeError("No model to save")

        try:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Saving model to: {output_dir}")

            if save_method == "merged":
                # Save merged model (base + LoRA)
                self.model.save_pretrained_merged(
                    str(output_dir),
                    self.tokenizer,
                    save_method="merged_16bit",
                )
                logger.info("Merged model saved (16-bit)")

            elif save_method == "lora_only":
                # Save only LoRA adapters
                self.model.save_pretrained(str(output_dir))
                self.tokenizer.save_pretrained(str(output_dir))
                logger.info("LoRA adapters saved")

            else:
                raise ValueError(f"Unknown save_method: {save_method}")

            # Log to MLflow
            if MLFLOW_AVAILABLE:
                mlflow.log_artifact(str(output_dir))

            return str(output_dir)

        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise

    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the loaded model.

        Returns:
            dict: Model information
        """
        if self.model is None:
            return {"status": "not_loaded"}

        trainable_params = sum(
            p.numel() for p in self.model.parameters() if p.requires_grad
        )
        total_params = sum(p.numel() for p in self.model.parameters())

        return {
            "status": "loaded",
            "model_name": self.model_name,
            "trainable_params": trainable_params,
            "total_params": total_params,
            "trainable_percentage": 100 * trainable_params / total_params,
            "device": self.device,
            "lora_config": {
                "r": self.lora_config.r,
                "lora_alpha": self.lora_config.lora_alpha,
                "lora_dropout": self.lora_config.lora_dropout,
                "target_modules": self.lora_config.target_modules,
            }
        }
