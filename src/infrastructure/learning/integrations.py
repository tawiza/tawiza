"""Learning Engine Integrations - Label Studio & LLaMA-Factory.

Connects the UAA Learning Engine with existing annotation and training infrastructure.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from .active_learning import ActiveLearningManager, AnnotationCandidate
from .dataset_builder import DatasetBuilder, DatasetExample, DatasetFormat


@dataclass
class LabelStudioConfig:
    """Configuration for Label Studio integration."""

    url: str = "http://localhost:8080"
    api_key: str = ""
    project_id: int | None = None

    # Labeling config for instruction/output pairs
    labeling_config: str = """
    <View>
      <Header value="Instruction"/>
      <Text name="instruction" value="$instruction"/>
      <Header value="Output (Agent Response)"/>
      <TextArea name="output" value="$output" editable="true"/>
      <Header value="Quality Rating"/>
      <Rating name="quality" toName="instruction" maxRating="5"/>
      <Header value="Correction (if needed)"/>
      <TextArea name="correction" toName="instruction" editable="true"/>
    </View>
    """


@dataclass
class LlamaFactoryConfig:
    """Configuration for LLaMA-Factory integration."""

    base_model: str = "qwen2.5-coder:7b"
    output_dir: str = "models/uaa-finetuned"
    use_lora: bool = True
    lora_rank: int = 16
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-5


class LabelStudioIntegration:
    """Integrates UAA with Label Studio for annotation.

    Creates annotation projects, imports tasks from the active learning
    queue, and exports completed annotations as training data.
    """

    def __init__(
        self,
        config: LabelStudioConfig | None = None,
        dataset_builder: DatasetBuilder | None = None,
        active_learning: ActiveLearningManager | None = None,
    ):
        self.config = config or LabelStudioConfig()
        self.dataset_builder = dataset_builder or DatasetBuilder()
        self.active_learning = active_learning or ActiveLearningManager()
        self._adapter = None

    async def _get_adapter(self):
        """Get or create Label Studio adapter."""
        if self._adapter is None:
            try:
                from src.infrastructure.config.settings import get_settings
                from src.infrastructure.ml.label_studio.label_studio_adapter import (
                    LabelStudioAdapter,
                )

                settings = get_settings()
                self._adapter = LabelStudioAdapter(settings)
            except Exception as e:
                logger.warning(f"Could not initialize Label Studio adapter: {e}")
                self._adapter = None
        return self._adapter

    async def create_annotation_project(
        self,
        project_name: str = "UAA Training Data",
    ) -> int | None:
        """Create a Label Studio project for UAA annotations.

        Args:
            project_name: Name for the annotation project

        Returns:
            Project ID or None if failed
        """
        adapter = await self._get_adapter()
        if not adapter:
            logger.warning("Label Studio not available, skipping project creation")
            return None

        try:
            project_id = await adapter.create_project(
                project_name=project_name,
                labeling_config=self.config.labeling_config,
            )
            self.config.project_id = project_id
            logger.info(f"Created Label Studio project: {project_id}")
            return project_id
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None

    async def push_candidates_for_annotation(
        self,
        max_candidates: int = 50,
    ) -> int:
        """Push high-priority candidates to Label Studio for annotation.

        Args:
            max_candidates: Maximum candidates to push

        Returns:
            Number of tasks imported
        """
        adapter = await self._get_adapter()
        if not adapter or not self.config.project_id:
            logger.warning("Label Studio not configured")
            return 0

        # Get candidates from active learning queue
        candidates = self.active_learning.get_top_candidates(max_candidates)

        if not candidates:
            logger.info("No candidates in queue")
            return 0

        # Convert to Label Studio tasks
        tasks = []
        for candidate in candidates:
            tasks.append(
                {
                    "data": {
                        "instruction": candidate.instruction,
                        "output": candidate.output,
                        "task_id": candidate.task_id,
                        "uncertainty": candidate.uncertainty_score,
                    },
                }
            )

        try:
            task_ids = await adapter.import_tasks(
                project_id=self.config.project_id,
                tasks=tasks,
            )
            logger.info(f"Imported {len(task_ids)} tasks to Label Studio")
            return len(task_ids)
        except Exception as e:
            logger.error(f"Failed to import tasks: {e}")
            return 0

    async def pull_completed_annotations(self) -> list[DatasetExample]:
        """Pull completed annotations from Label Studio.

        Returns:
            List of dataset examples from annotations
        """
        adapter = await self._get_adapter()
        if not adapter or not self.config.project_id:
            logger.warning("Label Studio not configured")
            return []

        try:
            annotations = await adapter.export_annotations(
                project_id=self.config.project_id,
                format_type="JSON",
            )

            examples = []
            for ann in annotations:
                # Extract instruction and corrected output
                instruction = ann.get("data", {}).get("instruction", "")

                # Get the corrected output if available, otherwise original
                correction = ""
                quality = 0

                for result in ann.get("annotations", [{}])[0].get("result", []):
                    if result.get("from_name") == "correction":
                        correction = result.get("value", {}).get("text", [""])[0]
                    elif result.get("from_name") == "quality":
                        quality = result.get("value", {}).get("rating", 0)

                output = correction if correction else ann.get("data", {}).get("output", "")

                if instruction and output and quality >= 3:  # Only include quality >= 3
                    example = DatasetExample(
                        instruction=instruction,
                        output=output,
                        input="",
                        task_id=ann.get("data", {}).get("task_id", ""),
                    )
                    examples.append(example)
                    self.dataset_builder.add_example(example)

            logger.info(f"Pulled {len(examples)} quality annotations")
            return examples

        except Exception as e:
            logger.error(f"Failed to export annotations: {e}")
            return []


class LlamaFactoryIntegration:
    """Integrates UAA with LLaMA-Factory for fine-tuning.

    Uses the dataset built from annotations to fine-tune the model.
    """

    def __init__(
        self,
        config: LlamaFactoryConfig | None = None,
        dataset_builder: DatasetBuilder | None = None,
    ):
        self.config = config or LlamaFactoryConfig()
        self.dataset_builder = dataset_builder or DatasetBuilder()
        self._adapter = None

    async def _get_adapter(self):
        """Get or create LLaMA-Factory adapter."""
        if self._adapter is None:
            try:
                from src.infrastructure.config.settings import get_settings
                from src.infrastructure.ml.llama_factory.llama_factory_adapter import (
                    LlamaFactoryAdapter,
                )

                settings = get_settings()
                self._adapter = LlamaFactoryAdapter(settings)
            except Exception as e:
                logger.warning(f"Could not initialize LLaMA-Factory adapter: {e}")
                self._adapter = None
        return self._adapter

    async def prepare_dataset(
        self,
        output_path: str | None = None,
        format: DatasetFormat = DatasetFormat.ALPACA,
    ) -> str:
        """Prepare dataset for LLaMA-Factory training.

        Args:
            output_path: Where to save the dataset
            format: Dataset format (Alpaca recommended for LLaMA-Factory)

        Returns:
            Path to the saved dataset
        """
        if output_path is None:
            output_path = f"data/uaa_training_{format.value}.json"

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        saved_path = self.dataset_builder.save(str(path), format)
        logger.info(
            f"Prepared dataset: {saved_path} ({self.dataset_builder.stats.total_examples} examples)"
        )

        return saved_path

    async def train(
        self,
        dataset_path: str,
        model_name: str = "uaa-finetuned",
    ) -> dict[str, Any]:
        """Train model using LLaMA-Factory.

        Args:
            dataset_path: Path to training dataset
            model_name: Name for the fine-tuned model

        Returns:
            Training result with metrics
        """
        adapter = await self._get_adapter()

        hyperparameters = {
            "finetuning_type": "lora" if self.config.use_lora else "full",
            "lora_rank": self.config.lora_rank,
            "num_train_epochs": self.config.num_epochs,
            "per_device_train_batch_size": self.config.batch_size,
            "learning_rate": self.config.learning_rate,
            "fp16": True,
            "logging_steps": 10,
            "save_steps": 100,
        }

        if adapter:
            try:
                run_id = await adapter.train(
                    model_name=model_name,
                    base_model=self.config.base_model,
                    dataset_path=dataset_path,
                    output_dir=self.config.output_dir,
                    hyperparameters=hyperparameters,
                )
                logger.info(f"Training completed: {run_id}")
                return {
                    "success": True,
                    "run_id": run_id,
                    "output_dir": self.config.output_dir,
                }
            except Exception as e:
                logger.error(f"Training failed: {e}")
                return {"success": False, "error": str(e)}
        else:
            # Fallback: use the learning engine's training adapter
            from .training_adapters import LlamaFactoryAdapter as SimpleAdapter

            simple_adapter = SimpleAdapter()
            result = await simple_adapter.train(
                dataset_path=dataset_path,
                output_dir=self.config.output_dir,
            )

            return {
                "success": result.success,
                "run_id": result.run_id,
                "output_dir": result.model_path,
                "metrics": result.metrics,
            }


class UnifiedLearningPipeline:
    """Unified pipeline connecting annotation → training → deployment.

    Orchestrates the full learning cycle:
    1. Collect interactions from UAA execution
    2. Prioritize candidates with active learning
    3. Push to Label Studio for human annotation
    4. Pull validated annotations
    5. Train with LLaMA-Factory
    6. Deploy and update trust score

    Example:
        pipeline = UnifiedLearningPipeline()

        # Add interactions from UAA
        pipeline.record_interaction("task_1", "Search for X", "Found Y")

        # Push candidates for annotation
        await pipeline.push_for_annotation(max_candidates=50)

        # After annotation, pull and train
        await pipeline.pull_and_train()
    """

    def __init__(
        self,
        label_studio_config: LabelStudioConfig | None = None,
        llama_factory_config: LlamaFactoryConfig | None = None,
    ):
        self.dataset_builder = DatasetBuilder()
        self.active_learning = ActiveLearningManager()

        self.label_studio = LabelStudioIntegration(
            config=label_studio_config,
            dataset_builder=self.dataset_builder,
            active_learning=self.active_learning,
        )

        self.llama_factory = LlamaFactoryIntegration(
            config=llama_factory_config,
            dataset_builder=self.dataset_builder,
        )

        self._training_count = 0

    def record_interaction(
        self,
        task_id: str,
        instruction: str,
        output: str,
        feedback: str | None = None,
    ) -> None:
        """Record an interaction for potential training.

        Args:
            task_id: Task identifier
            instruction: User instruction/query
            output: Agent output/response
            feedback: Optional feedback (positive/negative)
        """
        # Add to dataset builder (for immediate positive feedback)
        if feedback == "positive":
            example = DatasetExample(
                instruction=instruction,
                output=output,
                task_id=task_id,
            )
            self.dataset_builder.add_example(example)

        # Add to active learning queue (for prioritization)
        candidate = AnnotationCandidate(
            task_id=task_id,
            instruction=instruction,
            output=output,
        )
        self.active_learning.add_candidate(candidate)

    async def push_for_annotation(self, max_candidates: int = 50) -> int:
        """Push high-priority candidates to Label Studio.

        Args:
            max_candidates: Maximum to push

        Returns:
            Number pushed
        """
        return await self.label_studio.push_candidates_for_annotation(max_candidates)

    async def pull_annotations(self) -> int:
        """Pull completed annotations from Label Studio.

        Returns:
            Number of examples added
        """
        examples = await self.label_studio.pull_completed_annotations()
        return len(examples)

    async def train(self, model_name: str | None = None) -> dict[str, Any]:
        """Train model with current dataset.

        Args:
            model_name: Name for the model

        Returns:
            Training result
        """
        if self.dataset_builder.stats.total_examples < 10:
            return {
                "success": False,
                "error": f"Need at least 10 examples, have {self.dataset_builder.stats.total_examples}",
            }

        self._training_count += 1
        model_name = model_name or f"uaa-v{self._training_count}"

        # Prepare dataset
        dataset_path = await self.llama_factory.prepare_dataset()

        # Train
        result = await self.llama_factory.train(dataset_path, model_name)

        return result

    async def pull_and_train(self, model_name: str | None = None) -> dict[str, Any]:
        """Pull annotations and train in one step.

        Args:
            model_name: Name for the model

        Returns:
            Training result
        """
        # Pull annotations
        num_pulled = await self.pull_annotations()
        logger.info(f"Pulled {num_pulled} new annotations")

        # Train
        return await self.train(model_name)

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "examples_collected": self.dataset_builder.stats.total_examples,
            "candidates_queued": len(self.active_learning._queue),
            "training_runs": self._training_count,
            "dataset_stats": {
                "total": self.dataset_builder.stats.total_examples,
                "avg_instruction_len": self.dataset_builder.stats.avg_instruction_length,
                "avg_output_len": self.dataset_builder.stats.avg_output_length,
            },
        }
