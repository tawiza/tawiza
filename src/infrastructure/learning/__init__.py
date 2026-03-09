"""Learning Engine - Dataset building and auto-training."""

from .active_learning import (
    ActiveLearningManager,
    AnnotationCandidate,
    PriorityQueue,
    SelectionStrategy,
)
from .dataset_builder import DatasetBuilder, DatasetExample, DatasetFormat, DatasetStats
from .integrations import (
    LabelStudioConfig,
    LabelStudioIntegration,
    LlamaFactoryConfig,
    LlamaFactoryIntegration,
    UnifiedLearningPipeline,
)
from .learning_engine import LearningCycle, LearningEngine, LearningMetrics, LearningState
from .oumi_adapter import OumiAdapter, OumiTrainingConfig
from .training_adapters import (
    EvaluationResult,
    LlamaFactoryAdapter,
    TrainingAdapter,
    TrainingConfig,
    TrainingResult,
    create_adapter,
    get_available_adapters,
)

__all__ = [
    # Core
    "LearningEngine",
    "LearningCycle",
    "LearningState",
    "LearningMetrics",
    # Dataset
    "DatasetBuilder",
    "DatasetExample",
    "DatasetFormat",
    "DatasetStats",
    # Active Learning
    "ActiveLearningManager",
    "AnnotationCandidate",
    "PriorityQueue",
    "SelectionStrategy",
    # Training
    "TrainingAdapter",
    "LlamaFactoryAdapter",
    "OumiAdapter",
    "TrainingConfig",
    "OumiTrainingConfig",
    "TrainingResult",
    "EvaluationResult",
    "create_adapter",
    "get_available_adapters",
    # Integrations
    "LabelStudioConfig",
    "LlamaFactoryConfig",
    "LabelStudioIntegration",
    "LlamaFactoryIntegration",
    "UnifiedLearningPipeline",
]
