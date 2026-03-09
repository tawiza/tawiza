"""
TAJINE Learning Module - Continuous Improvement Pipeline.

Implements automated fine-tuning for TAJINE agent based on:
- User feedback (explicit positive/negative)
- Success traces (implicit from task completion)
- Preference pairs (for DPO training)

Components:
- DataCollector: Gathers training data from interactions
- LLMJudgeCurator: Filters and validates training data using LLM-as-Judge
- TAJINEFineTuner: Orchestrates the complete fine-tuning pipeline

Training Methods:
- SFT (Supervised Fine-Tuning): From success examples
- DPO (Direct Preference Optimization): From preference pairs
- GRPO (Group Relative Policy Optimization): For reasoning improvement

Integration:
- Uses Oumi.ai for training orchestration
- Supports Unsloth for accelerated training
- Integrates with Langfuse for training telemetry
"""

from src.infrastructure.agents.tajine.learning.curator import (
    CuratedDataset,
    CurationResult,
    LLMJudgeCurator,
)
from src.infrastructure.agents.tajine.learning.data_collector import (
    DataCollector,
    Interaction,
    PreferencePair,
    SuccessTrace,
    TrainingData,
)
from src.infrastructure.agents.tajine.learning.expert_router import (
    ExpertDomain,
    MixLoRAConfig,
    RoutingResult,
    TerritorialExpertRouter,
    get_expert_router,
)
from src.infrastructure.agents.tajine.learning.fine_tuner import (
    EvaluationResult,
    FineTuneConfig,
    FineTuneResult,
    TAJINEFineTuner,
    TrainingMethod,
)
from src.infrastructure.agents.tajine.learning.oumi_bridge import (
    OumiModelEvaluator,
    OumiTrainingBridge,
)

__all__ = [
    # Data Collection
    "DataCollector",
    "Interaction",
    "PreferencePair",
    "SuccessTrace",
    "TrainingData",
    # Curation
    "LLMJudgeCurator",
    "CurationResult",
    "CuratedDataset",
    # Fine-tuning
    "TAJINEFineTuner",
    "FineTuneConfig",
    "FineTuneResult",
    "TrainingMethod",
    "EvaluationResult",
    # Oumi Training Bridge
    "OumiTrainingBridge",
    "OumiModelEvaluator",
    # Expert Routing (MoE)
    "TerritorialExpertRouter",
    "ExpertDomain",
    "MixLoRAConfig",
    "RoutingResult",
    "get_expert_router",
]
