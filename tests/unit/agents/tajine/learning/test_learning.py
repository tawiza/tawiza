"""Tests for TAJINE learning module."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.infrastructure.agents.tajine.learning.curator import (
    CuratedDataset,
    CurationResult,
    CurationVerdict,
    LLMJudgeCurator,
)
from src.infrastructure.agents.tajine.learning.data_collector import (
    DataCollector,
    FeedbackType,
    Interaction,
    PreferencePair,
    SuccessTrace,
    TrainingData,
)
from src.infrastructure.agents.tajine.learning.fine_tuner import (
    EvaluationResult,
    FineTuneConfig,
    FineTuneResult,
    TAJINEFineTuner,
    TrainingMethod,
)

# ============================================================================
# DataCollector Tests
# ============================================================================


class TestDataCollector:
    """Tests for DataCollector."""

    @pytest.fixture
    def collector(self):
        """Create a fresh DataCollector."""
        return DataCollector()

    @pytest.fixture
    def sample_interaction(self):
        """Create a sample interaction."""
        return Interaction(
            id="test-001",
            timestamp=datetime.now(),
            query="Quel est le dynamisme économique du département 75?",
            response="Le département 75 (Paris) montre un dynamisme économique fort...",
            context={"department": "75"},
            tools_used=["sirene_query"],
            cognitive_level=3,
            success=True,
            duration_ms=1500.0,
        )

    @pytest.mark.asyncio
    async def test_record_interaction(self, collector, sample_interaction):
        """Test recording an interaction."""
        await collector.record_interaction(sample_interaction)

        stats = await collector.get_stats()
        assert stats["total_interactions"] == 1
        assert stats["total_examples"] == 1

    @pytest.mark.asyncio
    async def test_positive_feedback_creates_trace(self, collector, sample_interaction):
        """Positive feedback should create a success trace."""
        sample_interaction.user_feedback = FeedbackType.POSITIVE
        await collector.record_interaction(sample_interaction)

        stats = await collector.get_stats()
        assert stats["total_examples"] >= 1

    @pytest.mark.asyncio
    async def test_correction_creates_preference(self, collector, sample_interaction):
        """User correction should create a preference pair."""
        sample_interaction.user_correction = "Paris a un dynamisme économique exceptionnel..."
        await collector.record_interaction(sample_interaction)

        stats = await collector.get_stats()
        assert stats["total_preferences"] == 1

    @pytest.mark.asyncio
    async def test_add_preference_manually(self, collector):
        """Test manually adding a preference pair."""
        result = await collector.add_preference(
            instruction="Analyse économique",
            chosen="Réponse améliorée",
            rejected="Réponse originale",
        )

        assert result is True
        stats = await collector.get_stats()
        assert stats["total_preferences"] == 1

    @pytest.mark.asyncio
    async def test_export_training_data(self, collector, sample_interaction):
        """Test exporting collected data."""
        await collector.record_interaction(sample_interaction)
        await collector.add_preference(
            instruction="Test",
            chosen="Good",
            rejected="Bad",
        )

        data = await collector.export()

        assert isinstance(data, TrainingData)
        assert len(data.success_traces) >= 1
        assert len(data.preference_pairs) == 1

    @pytest.mark.asyncio
    async def test_storage_persistence(self, sample_interaction):
        """Test saving and loading from storage."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            storage_path = Path(f.name)

        collector1 = DataCollector(storage_path=storage_path)
        await collector1.record_interaction(sample_interaction)
        await collector1._save_to_storage()

        collector2 = DataCollector(storage_path=storage_path)
        stats = await collector2.get_stats()

        assert stats["total_interactions"] == 1

        # Cleanup
        storage_path.unlink()


class TestSuccessTrace:
    """Tests for SuccessTrace."""

    def test_to_training_format(self):
        """Test conversion to training format."""
        trace = SuccessTrace(
            instruction="Analyse le département 75",
            input_context="Données SIRENE disponibles",
            output="Le département 75...",
            reasoning="J'ai analysé les données...",
        )

        fmt = trace.to_training_format()

        assert "instruction" in fmt
        assert "output" in fmt
        assert "Analyse le département 75" in fmt["instruction"]
        assert "SIRENE" in fmt["instruction"]


class TestPreferencePair:
    """Tests for PreferencePair."""

    def test_to_training_format(self):
        """Test conversion to DPO format."""
        pair = PreferencePair(
            instruction="Question économique",
            input_context="",
            chosen="Bonne réponse",
            rejected="Mauvaise réponse",
        )

        fmt = pair.to_training_format()

        assert fmt["prompt"] == "Question économique"
        assert fmt["chosen"] == "Bonne réponse"
        assert fmt["rejected"] == "Mauvaise réponse"


# ============================================================================
# LLMJudgeCurator Tests
# ============================================================================


class TestLLMJudgeCurator:
    """Tests for LLMJudgeCurator."""

    @pytest.fixture
    def curator(self):
        """Create curator without LLM (heuristic mode)."""
        return LLMJudgeCurator()

    def test_heuristic_curate_good_trace(self, curator):
        """Good trace should be accepted."""
        trace = SuccessTrace(
            instruction="Analyse le dynamisme économique du département 75",
            input_context="Département: 75",
            output="Le département 75 montre un dynamisme économique exceptionnel avec une concentration d'entreprises innovantes.",
            reasoning="J'ai analysé les indicateurs...",
        )

        result = curator._heuristic_curate_trace(trace)

        assert result.verdict == CurationVerdict.ACCEPT
        assert result.quality_score >= 0.7

    def test_heuristic_curate_short_trace(self, curator):
        """Short trace should be rejected or reviewed."""
        trace = SuccessTrace(
            instruction="x",
            input_context="",
            output="Ok",
        )

        result = curator._heuristic_curate_trace(trace)

        assert result.verdict in [CurationVerdict.REJECT, CurationVerdict.NEEDS_REVIEW]
        assert len(result.issues) > 0

    def test_heuristic_curate_valid_preference(self, curator):
        """Valid preference pair should be accepted."""
        pair = PreferencePair(
            instruction="Analyse économique du département 75",
            input_context="",
            chosen="Analyse détaillée avec données SIRENE montrant une croissance de 15%",
            rejected="Je ne sais pas analyser ce département",
            margin=1.0,
        )

        result = curator._heuristic_curate_preference(pair)

        assert result.verdict == CurationVerdict.ACCEPT

    def test_heuristic_curate_identical_preference(self, curator):
        """Identical chosen/rejected should be rejected."""
        pair = PreferencePair(
            instruction="Test",
            input_context="",
            chosen="Same response",
            rejected="Same response",
        )

        result = curator._heuristic_curate_preference(pair)

        assert result.verdict == CurationVerdict.REJECT
        assert "identical" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_filter_training_data(self, curator):
        """Test filtering a complete dataset."""
        data = TrainingData(
            success_traces=[
                SuccessTrace(
                    instruction="Bonne question sur le département 33",
                    input_context="",
                    output="Le département 33 (Gironde) présente des caractéristiques économiques intéressantes...",
                ),
                SuccessTrace(
                    instruction="x",
                    input_context="",
                    output="y",
                ),
            ],
            preference_pairs=[
                PreferencePair(
                    instruction="Compare les départements",
                    input_context="",
                    chosen="Analyse comparative détaillée montrant les différences clés",
                    rejected="Ils sont différents",
                ),
            ],
        )

        curated = await curator.filter(data)

        assert isinstance(curated, CuratedDataset)
        # At least the good trace should be kept
        assert len(curated.success_traces) >= 1
        assert curated.curation_stats["accepted_traces"] >= 1


# ============================================================================
# TAJINEFineTuner Tests
# ============================================================================


class TestTAJINEFineTuner:
    """Tests for TAJINEFineTuner."""

    @pytest.fixture
    def finetuner(self):
        """Create a TAJINEFineTuner without backends."""
        return TAJINEFineTuner(current_model="test-model")

    @pytest.mark.asyncio
    async def test_collect_feedback(self, finetuner):
        """Test collecting feedback from interaction."""
        interaction = Interaction(
            id="test-001",
            timestamp=datetime.now(),
            query="Test query",
            response="Test response",
            success=True,
        )

        await finetuner.collect_feedback(interaction)
        status = await finetuner.get_status()

        assert status["data_stats"]["total_interactions"] == 1

    @pytest.mark.asyncio
    async def test_check_trigger_no_data(self, finetuner):
        """No trigger with insufficient data."""
        trigger = await finetuner.check_trigger()
        assert trigger is None

    @pytest.mark.asyncio
    async def test_check_trigger_dpo(self, finetuner):
        """DPO trigger when enough preferences."""
        for i in range(55):
            await finetuner.data_collector.add_preference(
                instruction=f"Question {i}",
                chosen=f"Good answer {i}",
                rejected=f"Bad answer {i}",
            )

        trigger = await finetuner.check_trigger()
        assert trigger == TrainingMethod.DPO

    def test_record_trust(self, finetuner):
        """Test recording trust history."""
        for i in range(10):
            finetuner.record_trust(0.5 + i * 0.01)

        status = finetuner._trust_history
        assert len(status) == 10

    def test_record_performance(self, finetuner):
        """Test recording performance history."""
        finetuner.record_performance(0.7)
        finetuner.record_performance(0.75)

        assert len(finetuner._performance_history) == 2

    @pytest.mark.asyncio
    async def test_mock_finetune(self, finetuner):
        """Test mock fine-tuning (no backend)."""
        # Add some data
        for i in range(10):
            interaction = Interaction(
                id=f"test-{i}",
                timestamp=datetime.now(),
                query=f"Question économique {i}",
                response=f"Réponse détaillée sur l'économie territoriale {i}",
                success=True,
            )
            await finetuner.collect_feedback(interaction)

        result = await finetuner.run_finetune(method=TrainingMethod.SFT)

        assert result.status == "deployed"
        assert result.improvement > 0
        assert result.method_used == TrainingMethod.SFT

    @pytest.mark.asyncio
    async def test_get_status(self, finetuner):
        """Test getting fine-tuner status."""
        status = await finetuner.get_status()

        assert "current_model" in status
        assert "pending_trigger" in status
        assert "data_stats" in status
        assert status["current_model"] == "test-model"

    def test_save_load_state(self, finetuner):
        """Test state persistence."""
        finetuner.record_trust(0.7)
        finetuner.record_performance(0.8)
        finetuner.current_model = "updated-model"

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            state_path = Path(f.name)

        finetuner.save_state(state_path)

        new_finetuner = TAJINEFineTuner()
        new_finetuner.load_state(state_path)

        assert new_finetuner.current_model == "updated-model"
        assert len(new_finetuner._trust_history) == 1
        assert len(new_finetuner._performance_history) == 1

        state_path.unlink()


class TestFineTuneConfig:
    """Tests for FineTuneConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FineTuneConfig()

        assert config.lora_rank == 64
        assert config.lora_alpha == 128
        assert config.batch_size == 4
        assert config.epochs == 2
        assert config.method == TrainingMethod.SFT

    def test_to_dict(self):
        """Test config serialization."""
        config = FineTuneConfig(
            lora_rank=32,
            method=TrainingMethod.DPO,
        )

        d = config.to_dict()

        assert d["lora_rank"] == 32
        assert d["method"] == "dpo"


class TestTrainingData:
    """Tests for TrainingData."""

    def test_has_preferences(self):
        """Test has_preferences property."""
        data_no_pref = TrainingData()
        assert data_no_pref.has_preferences is False

        data_with_pref = TrainingData(preference_pairs=[PreferencePair("q", "", "a", "b")])
        assert data_with_pref.has_preferences is True

    def test_reasoning_heavy(self):
        """Test reasoning_heavy property."""
        traces_no_reason = [
            SuccessTrace("q1", "", "a1"),
            SuccessTrace("q2", "", "a2"),
        ]
        data_light = TrainingData(success_traces=traces_no_reason)
        assert data_light.reasoning_heavy is False

        traces_with_reason = [
            SuccessTrace("q1", "", "a1", reasoning="Because..."),
            SuccessTrace("q2", "", "a2", reasoning="Due to..."),
        ]
        data_heavy = TrainingData(success_traces=traces_with_reason)
        assert data_heavy.reasoning_heavy is True

    def test_get_stats(self):
        """Test stats generation."""
        data = TrainingData(
            success_traces=[SuccessTrace("q", "", "a")],
            preference_pairs=[PreferencePair("q", "", "a", "b")],
        )

        stats = data.get_stats()

        assert stats["success_traces"] == 1
        assert stats["preference_pairs"] == 1
        assert stats["has_preferences"] is True
