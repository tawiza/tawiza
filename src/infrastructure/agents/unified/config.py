"""Configuration models for Unified Adaptive Agent."""

from enum import IntEnum

import yaml
from pydantic import BaseModel, Field, model_validator


class AutonomyLevel(IntEnum):
    """Autonomy levels for the agent.

    The agent starts at SUPERVISED and progresses based on trust score.

    Levels:
        SUPERVISED (0): Human validates everything
        ASSISTED (1): Human validates important decisions
        SEMI_AUTONOMOUS (2): Human validates only fine-tuning
        AUTONOMOUS (3): Agent autonomous with alerts
        FULL_AUTONOMOUS (4): Fully autonomous
    """

    SUPERVISED = 0
    ASSISTED = 1
    SEMI_AUTONOMOUS = 2
    AUTONOMOUS = 3
    FULL_AUTONOMOUS = 4


class TrustConfig(BaseModel):
    """Trust manager configuration.

    Controls how trust score is calculated and how autonomy levels progress.
    The three weights must sum to 1.0.
    """

    metrics_weight: float = Field(default=0.4, ge=0, le=1)
    feedback_weight: float = Field(default=0.35, ge=0, le=1)
    history_weight: float = Field(default=0.25, ge=0, le=1)

    level_thresholds: list[float] = Field(
        default=[0.3, 0.5, 0.7, 0.9],
        description="Score thresholds for each autonomy level"
    )

    cooldown_hours: int = Field(default=24, description="Cooldown after major error")
    rollback_on_regression: bool = Field(default=True)

    @model_validator(mode='after')
    def validate_weights_sum(self) -> 'TrustConfig':
        """Ensure weights sum to 1.0."""
        total = self.metrics_weight + self.feedback_weight + self.history_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return self


class ToolConfig(BaseModel):
    """Tool availability configuration.

    Controls which tools are enabled and their settings.
    """

    browser_use_enabled: bool = True
    skyvern_enabled: bool = True
    openmanus_enabled: bool = True
    open_interpreter_enabled: bool = True
    label_studio_enabled: bool = True

    # Tool-specific settings
    browser_headless: bool = True
    interpreter_sandbox: bool = True
    label_studio_url: str = "http://localhost:8080"


class LearningConfig(BaseModel):
    """Learning engine configuration.

    Controls auto-learning, dataset building, and training settings.
    """

    auto_learning_enabled: bool = True
    min_examples_for_training: int = Field(default=100, ge=10)
    max_training_frequency_hours: int = Field(default=24, ge=1)

    # Dataset settings
    default_dataset_format: str = "jsonl"
    active_learning_enabled: bool = True
    uncertainty_threshold: float = Field(default=0.5, ge=0, le=1)

    # Training backends
    llama_factory_enabled: bool = True
    transformer_lab_enabled: bool = True
    llama_factory_config_path: str | None = None


class UnifiedAgentConfig(BaseModel):
    """Main configuration for Unified Adaptive Agent.

    Combines trust, tools, and learning configurations.
    """

    trust: TrustConfig = Field(default_factory=TrustConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)

    # LLM settings
    llm_model: str = "qwen2.5-coder:14b"
    llm_base_url: str = "http://localhost:11434"

    @classmethod
    def from_yaml(cls, path: str) -> "UnifiedAgentConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            UnifiedAgentConfig instance
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save YAML file
        """
        with open(path, 'w') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)
