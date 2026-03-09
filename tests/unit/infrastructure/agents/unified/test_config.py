"""Tests for Unified Agent configuration."""

import pytest

from src.infrastructure.agents.unified.config import (
    AutonomyLevel,
    LearningConfig,
    ToolConfig,
    TrustConfig,
    UnifiedAgentConfig,
)


class TestAutonomyLevel:
    """Test autonomy level enum."""

    def test_autonomy_levels_exist(self):
        """Should have 5 autonomy levels."""
        assert AutonomyLevel.SUPERVISED.value == 0
        assert AutonomyLevel.ASSISTED.value == 1
        assert AutonomyLevel.SEMI_AUTONOMOUS.value == 2
        assert AutonomyLevel.AUTONOMOUS.value == 3
        assert AutonomyLevel.FULL_AUTONOMOUS.value == 4


class TestTrustConfig:
    """Test trust configuration."""

    def test_default_weights(self):
        """Should have correct default weights."""
        config = TrustConfig()
        assert config.metrics_weight == 0.4
        assert config.feedback_weight == 0.35
        assert config.history_weight == 0.25
        assert config.metrics_weight + config.feedback_weight + config.history_weight == 1.0

    def test_custom_weights(self):
        """Should accept custom weights."""
        config = TrustConfig(metrics_weight=0.5, feedback_weight=0.3, history_weight=0.2)
        assert config.metrics_weight == 0.5

    def test_level_thresholds(self):
        """Should have correct level thresholds."""
        config = TrustConfig()
        assert config.level_thresholds == [0.3, 0.5, 0.7, 0.9]

    def test_invalid_weights_sum(self):
        """Should reject weights that don't sum to 1.0."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            TrustConfig(metrics_weight=0.5, feedback_weight=0.5, history_weight=0.5)


class TestToolConfig:
    """Test tool configuration."""

    def test_default_tools_enabled(self):
        """Should have all tools enabled by default."""
        config = ToolConfig()
        assert config.browser_use_enabled is True
        assert config.skyvern_enabled is True
        assert config.openmanus_enabled is True
        assert config.open_interpreter_enabled is True
        assert config.label_studio_enabled is True

    def test_disable_specific_tool(self):
        """Should allow disabling specific tools."""
        config = ToolConfig(skyvern_enabled=False)
        assert config.skyvern_enabled is False
        assert config.browser_use_enabled is True


class TestLearningConfig:
    """Test learning configuration."""

    def test_default_learning_config(self):
        """Should have correct defaults."""
        config = LearningConfig()
        assert config.auto_learning_enabled is True
        assert config.min_examples_for_training == 100
        assert config.max_training_frequency_hours == 24
        assert config.active_learning_enabled is True

    def test_min_examples_validation(self):
        """Should reject min_examples below 10."""
        with pytest.raises(ValueError):
            LearningConfig(min_examples_for_training=5)


class TestUnifiedAgentConfig:
    """Test unified agent configuration."""

    def test_default_config(self):
        """Should create valid default config."""
        config = UnifiedAgentConfig()
        assert isinstance(config.trust, TrustConfig)
        assert isinstance(config.tools, ToolConfig)
        assert isinstance(config.learning, LearningConfig)

    def test_llm_settings(self):
        """Should have LLM settings."""
        config = UnifiedAgentConfig()
        assert config.llm_model == "qwen2.5-coder:14b"
        assert config.llm_base_url == "http://localhost:11434"

    def test_from_yaml(self, tmp_path):
        """Should load config from YAML file."""
        yaml_content = """
trust:
  metrics_weight: 0.5
  feedback_weight: 0.3
  history_weight: 0.2
tools:
  browser_use_enabled: true
  skyvern_enabled: false
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = UnifiedAgentConfig.from_yaml(str(config_file))
        assert config.trust.metrics_weight == 0.5
        assert config.tools.skyvern_enabled is False

    def test_to_yaml(self, tmp_path):
        """Should save config to YAML file."""
        config = UnifiedAgentConfig()
        config_file = tmp_path / "output.yaml"

        config.to_yaml(str(config_file))

        assert config_file.exists()
        content = config_file.read_text()
        assert "trust:" in content
