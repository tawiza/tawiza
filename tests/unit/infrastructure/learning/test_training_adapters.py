"""Tests for Training Adapters."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.learning.training_adapters import (
    EvaluationResult,
    LlamaFactoryAdapter,
    TrainingAdapter,
    TrainingConfig,
    TrainingResult,
)


class TestTrainingConfig:
    """Test TrainingConfig dataclass."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = TrainingConfig()
        assert config.learning_rate == 2e-5
        assert config.num_epochs == 3
        assert config.batch_size == 4
        assert config.gradient_accumulation_steps == 4

    def test_custom_config(self):
        """Should accept custom values."""
        config = TrainingConfig(
            learning_rate=1e-4,
            num_epochs=5,
            batch_size=8,
        )
        assert config.learning_rate == 1e-4
        assert config.num_epochs == 5

    def test_lora_config(self):
        """Should have LoRA settings."""
        config = TrainingConfig()
        assert config.use_lora is True
        assert config.lora_rank == 16
        assert config.lora_alpha == 32


class TestTrainingResult:
    """Test TrainingResult dataclass."""

    def test_create_result(self):
        """Should create valid result."""
        result = TrainingResult(
            run_id="run_123",
            model_path="/models/output",
            metrics={"accuracy": 0.85, "loss": 0.15},
        )
        assert result.run_id == "run_123"
        assert result.metrics["accuracy"] == 0.85

    def test_result_success(self):
        """Should track success status."""
        result = TrainingResult(
            run_id="run_123",
            model_path="/models/output",
            success=True,
        )
        assert result.success is True

    def test_result_failure(self):
        """Should track failure with error."""
        result = TrainingResult(
            run_id="run_123",
            success=False,
            error="Out of memory",
        )
        assert result.success is False
        assert result.error == "Out of memory"


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""

    def test_create_eval_result(self):
        """Should create valid evaluation result."""
        result = EvaluationResult(
            accuracy=0.87,
            perplexity=12.5,
            loss=0.22,
        )
        assert result.accuracy == 0.87
        assert result.perplexity == 12.5


class TestTrainingAdapter:
    """Test base TrainingAdapter interface."""

    def test_is_abstract(self):
        """Should be abstract base class."""
        with pytest.raises(TypeError):
            TrainingAdapter()

    def test_subclass_must_implement_train(self):
        """Subclass must implement train method."""

        class IncompleteAdapter(TrainingAdapter):
            async def evaluate(self, model_path):
                pass

        with pytest.raises(TypeError):
            IncompleteAdapter()


class TestLlamaFactoryAdapter:
    """Test LlamaFactoryAdapter."""

    def test_init(self):
        """Should initialize with config path."""
        adapter = LlamaFactoryAdapter(config_path="/path/to/config.yaml")
        assert adapter.config_path == "/path/to/config.yaml"

    def test_init_default_config(self):
        """Should use default config if not provided."""
        adapter = LlamaFactoryAdapter()
        assert adapter.config_path is None

    @pytest.mark.asyncio
    async def test_train_basic(self, tmp_path):
        """Should run basic training."""
        adapter = LlamaFactoryAdapter()

        # Create mock dataset
        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        # Mock subprocess
        with patch("asyncio.create_subprocess_exec") as mock_proc:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Training complete", b""))
            mock_proc.return_value = mock_process

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_train_with_config(self, tmp_path):
        """Should use custom training config."""
        adapter = LlamaFactoryAdapter()

        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        config = TrainingConfig(
            learning_rate=1e-4,
            num_epochs=5,
        )

        with patch("asyncio.create_subprocess_exec") as mock_proc:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Done", b""))
            mock_proc.return_value = mock_process

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
                config=config,
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_train_failure(self, tmp_path):
        """Should handle training failure."""
        adapter = LlamaFactoryAdapter()

        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        with patch("asyncio.create_subprocess_exec") as mock_proc:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"CUDA OOM"))
            mock_proc.return_value = mock_process

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
            )

            assert result.success is False
            assert "CUDA OOM" in result.error

    @pytest.mark.asyncio
    async def test_evaluate_model(self, tmp_path):
        """Should evaluate trained model."""
        adapter = LlamaFactoryAdapter()

        model_path = tmp_path / "model"
        model_path.mkdir()

        with patch("asyncio.create_subprocess_exec") as mock_proc:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(b'{"accuracy": 0.85, "perplexity": 10.5}', b"")
            )
            mock_proc.return_value = mock_process

            result = await adapter.evaluate(model_path=str(model_path))

            assert result.accuracy == 0.85

    def test_generate_config(self, tmp_path):
        """Should generate LlamaFactory config file."""
        adapter = LlamaFactoryAdapter()

        config = TrainingConfig(
            base_model="qwen2.5-coder:7b",
            learning_rate=2e-5,
            num_epochs=3,
        )

        config_path = adapter.generate_config(
            dataset_path="/data/train.jsonl",
            output_dir=str(tmp_path),
            config=config,
        )

        assert Path(config_path).exists()
        content = Path(config_path).read_text()
        assert "qwen2.5-coder:7b" in content


class TestAdapterDiscovery:
    """Test adapter discovery and factory."""

    def test_get_available_adapters(self):
        """Should list available adapters."""
        from src.infrastructure.learning.training_adapters import get_available_adapters

        adapters = get_available_adapters()

        assert "llama_factory" in adapters
        assert isinstance(adapters["llama_factory"], type)

    def test_create_adapter(self):
        """Should create adapter by name."""
        from src.infrastructure.learning.training_adapters import create_adapter

        adapter = create_adapter("llama_factory")

        assert isinstance(adapter, LlamaFactoryAdapter)

    def test_create_unknown_adapter(self):
        """Should raise for unknown adapter."""
        from src.infrastructure.learning.training_adapters import create_adapter

        with pytest.raises(ValueError, match="Unknown adapter"):
            create_adapter("unknown_adapter")
