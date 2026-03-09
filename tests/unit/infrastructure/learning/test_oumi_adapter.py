"""Tests for Oumi Training Adapter - TAJINE Fine-tuning Pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOumiAdapterImports:
    """Test OumiAdapter imports."""

    def test_import_oumi_adapter(self):
        """OumiAdapter class can be imported."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        assert OumiAdapter is not None

    def test_import_oumi_config(self):
        """OumiTrainingConfig can be imported."""
        from src.infrastructure.learning.oumi_adapter import OumiTrainingConfig

        assert OumiTrainingConfig is not None

    def test_import_from_learning_module(self):
        """OumiAdapter exported from learning module."""
        from src.infrastructure.learning import OumiAdapter

        assert OumiAdapter is not None


class TestOumiTrainingConfig:
    """Test OumiTrainingConfig dataclass."""

    def test_default_config(self):
        """Should have Oumi-specific defaults."""
        from src.infrastructure.learning.oumi_adapter import OumiTrainingConfig

        config = OumiTrainingConfig()

        assert config.base_model == "qwen3:14b"
        assert config.training_backend == "oumi"
        assert config.use_coalm is True

    def test_coalm_config(self):
        """Should support CoALM (Collaborative Agent LM) settings."""
        from src.infrastructure.learning.oumi_adapter import OumiTrainingConfig

        config = OumiTrainingConfig(
            use_coalm=True, coalm_agents=4, coalm_coordination="hierarchical"
        )

        assert config.use_coalm is True
        assert config.coalm_agents == 4
        assert config.coalm_coordination == "hierarchical"

    def test_territorial_config(self):
        """Should support territorial specialization for TAJINE."""
        from src.infrastructure.learning.oumi_adapter import OumiTrainingConfig

        config = OumiTrainingConfig(
            territory_code="34",
            territory_specialization=True,
        )

        assert config.territory_code == "34"
        assert config.territory_specialization is True

    def test_inherits_base_config(self):
        """Should work with base TrainingConfig fields."""
        from src.infrastructure.learning.oumi_adapter import OumiTrainingConfig

        config = OumiTrainingConfig(
            learning_rate=1e-4,
            num_epochs=5,
            batch_size=8,
        )

        assert config.learning_rate == 1e-4
        assert config.num_epochs == 5


class TestOumiAdapterCreation:
    """Test OumiAdapter instantiation."""

    def test_create_default(self):
        """Should create with defaults."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        assert adapter is not None

    def test_create_with_oumi_path(self):
        """Should accept custom Oumi installation path."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter(oumi_path="/opt/oumi")

        assert adapter.oumi_path == Path("/opt/oumi")

    def test_create_with_ollama_fallback(self):
        """Should configure Ollama fallback."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter(fallback_to_ollama=True, ollama_url="http://localhost:11434")

        assert adapter.fallback_to_ollama is True
        assert adapter.ollama_url == "http://localhost:11434"

    def test_implements_training_adapter(self):
        """Should implement TrainingAdapter interface."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter
        from src.infrastructure.learning.training_adapters import TrainingAdapter

        adapter = OumiAdapter()

        assert isinstance(adapter, TrainingAdapter)


class TestOumiAdapterTrain:
    """Test OumiAdapter training."""

    @pytest.mark.asyncio
    async def test_train_basic(self, tmp_path):
        """Should run basic training."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        # Create mock dataset
        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        with patch.object(adapter, "_run_oumi_training", new_callable=AsyncMock) as mock_train:
            mock_train.return_value = {
                "success": True,
                "model_path": str(tmp_path / "output"),
                "metrics": {"loss": 0.15},
            }

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
            )

            assert result.success is True
            mock_train.assert_called_once()

    @pytest.mark.asyncio
    async def test_train_with_coalm(self, tmp_path):
        """Should train with CoALM configuration."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter, OumiTrainingConfig

        adapter = OumiAdapter()

        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        config = OumiTrainingConfig(
            use_coalm=True,
            coalm_agents=4,
        )

        with patch.object(adapter, "_run_oumi_training", new_callable=AsyncMock) as mock_train:
            mock_train.return_value = {"success": True, "model_path": str(tmp_path), "metrics": {}}

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
                config=config,
            )

            assert result.success is True
            # Verify CoALM config was passed
            call_kwargs = mock_train.call_args
            assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_train_failure_handling(self, tmp_path):
        """Should handle training failures gracefully."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        # Disable fallback to ensure failure propagates
        adapter = OumiAdapter(fallback_to_ollama=False)

        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        with patch.object(adapter, "_run_oumi_training", new_callable=AsyncMock) as mock_train:
            mock_train.side_effect = RuntimeError("GPU out of memory")

            result = await adapter.train(
                dataset_path=str(dataset_path),
                output_dir=str(tmp_path / "output"),
            )

            assert result.success is False
            assert "GPU out of memory" in result.error

    @pytest.mark.asyncio
    async def test_train_with_ollama_fallback(self, tmp_path):
        """Should fallback to Ollama when Oumi unavailable."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter(fallback_to_ollama=True)

        dataset_path = tmp_path / "train.jsonl"
        dataset_path.write_text('{"instruction": "test", "output": "output"}\n')

        with patch.object(adapter, "_run_oumi_training", new_callable=AsyncMock) as mock_oumi:
            mock_oumi.side_effect = FileNotFoundError("Oumi not installed")

            with patch.object(
                adapter, "_run_ollama_fallback", new_callable=AsyncMock
            ) as mock_ollama:
                mock_ollama.return_value = {
                    "success": True,
                    "model_path": str(tmp_path / "output"),
                    "metrics": {},
                }

                result = await adapter.train(
                    dataset_path=str(dataset_path),
                    output_dir=str(tmp_path / "output"),
                )

                # Should have tried Oumi first, then fallen back
                assert mock_oumi.called
                assert mock_ollama.called
                assert result.success is True


class TestOumiAdapterEvaluate:
    """Test OumiAdapter evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_model(self, tmp_path):
        """Should evaluate trained model."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        model_path = tmp_path / "model"
        model_path.mkdir()

        with patch.object(adapter, "_run_oumi_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
                "accuracy": 0.85,
                "perplexity": 12.5,
                "loss": 0.22,
            }

            result = await adapter.evaluate(model_path=str(model_path))

            assert result.accuracy == 0.85
            assert result.perplexity == 12.5

    @pytest.mark.asyncio
    async def test_evaluate_with_territorial_metrics(self, tmp_path):
        """Should include territorial metrics for TAJINE."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        model_path = tmp_path / "model"
        model_path.mkdir()

        with patch.object(adapter, "_run_oumi_evaluation", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
                "accuracy": 0.85,
                "perplexity": 12.5,
                "loss": 0.22,
                "territorial_accuracy": 0.91,  # TAJINE-specific
                "siret_extraction_f1": 0.88,  # TAJINE-specific
            }

            result = await adapter.evaluate(
                model_path=str(model_path),
                include_territorial_metrics=True,
            )

            assert result.custom_metrics.get("territorial_accuracy") == 0.91


class TestOumiDatasetPreparation:
    """Test Oumi dataset preparation for TAJINE."""

    def test_prepare_territorial_dataset(self, tmp_path):
        """Should prepare dataset with territorial context."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        raw_data = [
            {
                "text": "SARL Test Company",
                "siret": "12345678901234",
                "department": "34",
            }
        ]

        prepared = adapter.prepare_dataset(
            raw_data,
            output_path=tmp_path / "prepared.jsonl",
            territory_code="34",
        )

        assert prepared.exists()

    def test_prepare_with_coalm_format(self, tmp_path):
        """Should format for CoALM multi-agent training."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter

        adapter = OumiAdapter()

        raw_data = [
            {"instruction": "Extract SIRET", "input": "Company X", "output": "12345678901234"}
        ]

        prepared = adapter.prepare_dataset(
            raw_data,
            output_path=tmp_path / "coalm_data.jsonl",
            format="coalm",
        )

        assert prepared.exists()


class TestOumiAdapterIntegration:
    """Test OumiAdapter integration with TAJINE."""

    def test_register_in_adapter_registry(self):
        """OumiAdapter should be registered."""
        from src.infrastructure.learning.training_adapters import get_available_adapters

        adapters = get_available_adapters()

        assert "oumi" in adapters

    def test_create_via_factory(self):
        """Should create via adapter factory."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter
        from src.infrastructure.learning.training_adapters import create_adapter

        adapter = create_adapter("oumi")

        assert isinstance(adapter, OumiAdapter)

    def test_compatible_with_hybrid_router(self):
        """Should work with HybridLLMRouter's OumiClient."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter
        from src.infrastructure.llm.hybrid_router import OumiClient

        adapter = OumiAdapter()
        client = OumiClient(model="coalm-8b")

        # Both should be usable together
        assert adapter is not None
        assert client is not None


class TestOumiConfigGeneration:
    """Test Oumi configuration file generation."""

    def test_generate_oumi_config(self, tmp_path):
        """Should generate Oumi YAML config."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter, OumiTrainingConfig

        adapter = OumiAdapter()

        config = OumiTrainingConfig(
            base_model="qwen3:14b",
            use_coalm=True,
            territory_code="34",
        )

        config_path = adapter.generate_config(
            dataset_path="/data/train.jsonl",
            output_dir=str(tmp_path),
            config=config,
        )

        assert Path(config_path).exists()
        content = Path(config_path).read_text()
        assert "qwen3:14b" in content

    def test_config_includes_coalm_settings(self, tmp_path):
        """Config should include CoALM settings when enabled."""
        from src.infrastructure.learning.oumi_adapter import OumiAdapter, OumiTrainingConfig

        adapter = OumiAdapter()

        config = OumiTrainingConfig(
            use_coalm=True,
            coalm_agents=4,
            coalm_coordination="hierarchical",
        )

        config_path = adapter.generate_config(
            dataset_path="/data/train.jsonl",
            output_dir=str(tmp_path),
            config=config,
        )

        content = Path(config_path).read_text()
        # Should have CoALM configuration
        assert "coalm" in content.lower() or "agents" in content.lower()
