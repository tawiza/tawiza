"""Bridge adapter to connect OumiAdapter to TAJINEFineTuner.

This module provides the OumiTrainingBridge that adapts the OumiAdapter
interface to match the TrainingBackend protocol expected by TAJINEFineTuner.

The bridge handles:
- Converting CuratedDataset to JSONL files
- Adapting FineTuneConfig to OumiTrainingConfig
- Extracting model path from TrainingResult
"""

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.infrastructure.learning.oumi_adapter import (
    OumiAdapter,
    OumiTrainingConfig,
)

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.learning.curator import CuratedDataset
    from src.infrastructure.agents.tajine.learning.fine_tuner import (
        EvaluationResult,
        FineTuneConfig,
        TrainingMethod,
    )


class OumiTrainingBridge:
    """Bridge to adapt OumiAdapter to TrainingBackend protocol.

    This class implements the TrainingBackend protocol expected by TAJINEFineTuner
    while internally delegating to OumiAdapter for actual training.

    Example:
        adapter = OumiAdapter(oumi_path="/opt/oumi")
        bridge = OumiTrainingBridge(adapter)

        # Now bridge can be used as TrainingBackend
        fine_tuner = TAJINEFineTuner(training_backend=bridge)
    """

    def __init__(
        self,
        oumi_adapter: OumiAdapter,
        output_dir: Path | None = None,
        territory_code: str | None = None,
    ):
        """Initialize the Oumi training bridge.

        Args:
            oumi_adapter: The underlying OumiAdapter instance
            output_dir: Directory for output models (default: ./models/tajine)
            territory_code: Optional territory code for specialization (e.g., "75")
        """
        self.adapter = oumi_adapter
        self.output_dir = Path(output_dir) if output_dir else Path("./models/tajine")
        self.territory_code = territory_code
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"OumiTrainingBridge initialized (output_dir={self.output_dir})")

    async def train(
        self,
        base_model: str,
        dataset: "CuratedDataset",
        config: "FineTuneConfig",
    ) -> str:
        """Train and return new model name/path.

        Implements the TrainingBackend protocol by:
        1. Exporting CuratedDataset to JSONL file
        2. Creating OumiTrainingConfig from FineTuneConfig
        3. Calling OumiAdapter.train()
        4. Returning the output model path

        Args:
            base_model: Base model name (e.g., "qwen3.5:27b")
            dataset: Curated training dataset
            config: Fine-tuning configuration

        Returns:
            Path to the trained model
        """
        # Generate unique run ID
        run_id = str(uuid.uuid4())[:8]
        run_dir = self.output_dir / f"run-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export dataset to JSONL
        dataset_path = await self._export_dataset(dataset, run_dir, config.method)
        logger.info(f"Exported dataset to {dataset_path}")

        # 2. Create Oumi config
        oumi_config = self._create_oumi_config(base_model, config)
        logger.info(
            f"Created Oumi config: method={config.method.value if config.method else 'sft'}"
        )

        # 3. Call Oumi training
        try:
            result = await self.adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(run_dir / "output"),
                config=oumi_config,
            )

            if result.success:
                model_path = result.model_path or str(run_dir / "output" / "final_model")
                logger.info(f"Training succeeded: {model_path}")
                return model_path
            else:
                raise RuntimeError(f"Training failed: {result.error}")

        except Exception as e:
            logger.error(f"Oumi training failed: {e}")
            raise

    async def _export_dataset(
        self,
        dataset: "CuratedDataset",
        output_dir: Path,
        method: "TrainingMethod | None",
    ) -> Path:
        """Export CuratedDataset to JSONL file.

        Args:
            dataset: The curated dataset
            output_dir: Directory to write the file
            method: Training method (determines format)

        Returns:
            Path to the exported JSONL file
        """
        from src.infrastructure.agents.tajine.learning.fine_tuner import TrainingMethod

        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine format based on method
        is_dpo = method == TrainingMethod.DPO if method else False

        if is_dpo and dataset.preference_pairs:
            # DPO format
            output_path = output_dir / "train_dpo.jsonl"
            with open(output_path, "w", encoding="utf-8") as f:
                for pair in dataset.preference_pairs:
                    line = json.dumps(pair.to_training_format(), ensure_ascii=False)
                    f.write(line + "\n")
            logger.info(f"Exported {len(dataset.preference_pairs)} DPO pairs")
        else:
            # SFT format (default)
            output_path = output_dir / "train_sft.jsonl"
            with open(output_path, "w", encoding="utf-8") as f:
                for trace in dataset.success_traces:
                    line = json.dumps(trace.to_training_format(), ensure_ascii=False)
                    f.write(line + "\n")
            logger.info(f"Exported {len(dataset.success_traces)} SFT traces")

        return output_path

    def _create_oumi_config(
        self,
        base_model: str,
        config: "FineTuneConfig",
    ) -> OumiTrainingConfig:
        """Create OumiTrainingConfig from FineTuneConfig.

        Args:
            base_model: Base model name
            config: TAJINEFineTuner config

        Returns:
            OumiTrainingConfig for training
        """
        from src.infrastructure.agents.tajine.learning.fine_tuner import TrainingMethod

        # Map training method
        method_map = {
            TrainingMethod.SFT: "sft",
            TrainingMethod.DPO: "dpo",
            TrainingMethod.GRPO: "grpo",
        }
        training_type = method_map.get(config.method, "sft") if config.method else "sft"

        return OumiTrainingConfig(
            base_model=base_model,
            training_type=training_type,
            # Oumi settings
            use_coalm=True,
            coalm_agents=4,
            # Territory specialization
            territory_code=self.territory_code,
            territory_specialization=self.territory_code is not None,
            include_insee_context=True,
            include_sirene_context=True,
            # Training settings
            use_unsloth=True,
            quantization="4bit",
            learning_rate=config.learning_rate,
            num_epochs=config.epochs,
            lora_rank=config.lora_rank,
            lora_alpha=config.lora_alpha,
        )


class OumiModelEvaluator:
    """Evaluator that uses Oumi for model evaluation.

    Replaces mock evaluation with real model evaluation using
    OumiAdapter's evaluate method.

    Adapts between two EvaluationResult formats:
    - OumiAdapter returns: accuracy, perplexity, loss, f1_score, custom_metrics
    - TAJINEFineTuner expects: model_name, score, metrics dict
    """

    def __init__(self, oumi_adapter: OumiAdapter):
        """Initialize evaluator.

        Args:
            oumi_adapter: OumiAdapter instance for evaluation
        """
        self.adapter = oumi_adapter

    async def evaluate(self, model_name: str) -> "EvaluationResult":
        """Evaluate a model and return score.

        Args:
            model_name: Model to evaluate (path or name)

        Returns:
            EvaluationResult with computed global score
        """
        from src.infrastructure.agents.tajine.learning.fine_tuner import (
            EvaluationResult as TAJINEEvalResult,
        )

        try:
            # Call Oumi evaluation with territorial metrics
            oumi_result = await self.adapter.evaluate(
                model_path=model_name,
                eval_dataset_path=None,
                include_territorial_metrics=True,
            )

            # Compute global score from individual metrics
            # Weighted average: accuracy (40%), f1 (40%), perplexity penalty (20%)
            perplexity_score = max(0.0, 1.0 - (oumi_result.perplexity / 100.0))
            global_score = (
                0.4 * oumi_result.accuracy + 0.4 * oumi_result.f1_score + 0.2 * perplexity_score
            )
            global_score = min(1.0, max(0.0, global_score))  # Clamp to [0, 1]

            # Build metrics dict
            metrics = {
                "accuracy": oumi_result.accuracy,
                "f1_score": oumi_result.f1_score,
                "perplexity": oumi_result.perplexity,
                "loss": oumi_result.loss,
            }
            # Add custom territorial metrics
            if oumi_result.custom_metrics:
                metrics.update(oumi_result.custom_metrics)

            return TAJINEEvalResult(
                model_name=model_name,
                score=global_score,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"Evaluation failed for {model_name}: {e}")
            # Return a minimal result on failure
            return TAJINEEvalResult(
                model_name=model_name,
                score=0.0,
                metrics={"error": str(e)},
            )
