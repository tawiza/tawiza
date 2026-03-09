"""Tests for Learning Engine."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.learning.active_learning import ActiveLearningManager
from src.infrastructure.learning.dataset_builder import DatasetBuilder
from src.infrastructure.learning.learning_engine import (
    LearningCycle,
    LearningEngine,
    LearningMetrics,
    LearningState,
)


class TestLearningState:
    """Test LearningState enum."""

    def test_states_exist(self):
        """Should have all expected states."""
        assert LearningState.IDLE.value == "idle"
        assert LearningState.COLLECTING.value == "collecting"
        assert LearningState.PREPARING.value == "preparing"
        assert LearningState.ANNOTATING.value == "annotating"
        assert LearningState.TRAINING.value == "training"
        assert LearningState.EVALUATING.value == "evaluating"


class TestLearningCycle:
    """Test LearningCycle dataclass."""

    def test_create_cycle(self):
        """Should create a valid cycle."""
        cycle = LearningCycle(
            id="cycle_1",
            state=LearningState.IDLE,
        )
        assert cycle.id == "cycle_1"
        assert cycle.state == LearningState.IDLE

    def test_cycle_progress(self):
        """Should track progress."""
        cycle = LearningCycle(
            id="cycle_1",
            state=LearningState.COLLECTING,
            examples_collected=50,
            examples_target=100,
        )
        assert cycle.progress == 0.5

    def test_cycle_duration(self):
        """Should calculate duration."""
        cycle = LearningCycle(
            id="cycle_1",
            state=LearningState.TRAINING,
        )
        # Just started, duration should be small
        assert cycle.duration_seconds >= 0


class TestLearningMetrics:
    """Test LearningMetrics dataclass."""

    def test_create_metrics(self):
        """Should create valid metrics."""
        metrics = LearningMetrics(
            accuracy_before=0.75,
            accuracy_after=0.82,
            examples_trained=100,
        )
        assert metrics.accuracy_improvement == pytest.approx(0.07)

    def test_no_regression(self):
        """Should detect regression."""
        metrics = LearningMetrics(
            accuracy_before=0.85,
            accuracy_after=0.80,
            examples_trained=50,
        )
        assert metrics.accuracy_improvement == pytest.approx(-0.05)
        assert metrics.is_regression is True


class TestLearningEngineInit:
    """Test LearningEngine initialization."""

    def test_init_default(self):
        """Should initialize with defaults."""
        engine = LearningEngine()
        assert engine.state == LearningState.IDLE
        assert engine.current_cycle is None

    def test_init_with_config(self):
        """Should accept configuration."""
        engine = LearningEngine(
            min_examples=50,
            auto_train=False,
        )
        assert engine.min_examples == 50
        assert engine.auto_train is False


class TestLearningEngineCollection:
    """Test example collection."""

    def test_record_interaction(self):
        """Should record interaction for learning."""
        engine = LearningEngine()

        engine.record_interaction(
            task_id="task_1",
            instruction="What is AI?",
            output="AI is artificial intelligence.",
            feedback="positive",
        )

        assert len(engine.dataset_builder.examples) == 1

    def test_record_with_uncertainty(self):
        """Should track uncertainty for active learning."""
        engine = LearningEngine()

        engine.record_interaction(
            task_id="task_1",
            instruction="Complex question",
            output="Answer...",
            uncertainty=0.8,
        )

        # Should be added to active learning queue
        assert len(engine.active_learning.queue) == 1

    def test_auto_trigger_at_threshold(self):
        """Should auto-trigger learning at threshold."""
        engine = LearningEngine(min_examples=5, auto_train=True)

        # Record enough examples
        for i in range(5):
            engine.record_interaction(
                task_id=f"task_{i}",
                instruction=f"Question {i}",
                output=f"Answer {i}",
            )

        assert engine.should_trigger_learning()


class TestLearningEngineCycle:
    """Test learning cycle management."""

    @pytest.mark.asyncio
    async def test_start_cycle(self):
        """Should start a new learning cycle."""
        engine = LearningEngine(min_examples=2)

        # Add examples
        engine.record_interaction(task_id="1", instruction="Q1", output="A1")
        engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        cycle = await engine.start_cycle()

        assert cycle is not None
        assert cycle.state == LearningState.PREPARING
        assert engine.current_cycle == cycle

    @pytest.mark.asyncio
    async def test_prepare_dataset(self):
        """Should prepare dataset for training."""
        engine = LearningEngine(min_examples=2)
        engine.record_interaction(task_id="1", instruction="Q", output="A")
        engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        cycle = await engine.start_cycle()
        await engine.prepare_dataset(cycle)

        assert cycle.state == LearningState.PREPARING
        assert cycle.dataset_path is not None

    @pytest.mark.asyncio
    async def test_train_model(self):
        """Should trigger model training."""
        engine = LearningEngine(min_examples=2)

        # Mock the training adapter
        engine._training_adapter = MagicMock()
        engine._training_adapter.train = AsyncMock(
            return_value={
                "run_id": "test_run",
                "model_path": "/models/test",
                "metrics": {"accuracy": 0.85},
            }
        )

        engine.record_interaction(task_id="1", instruction="Q", output="A")
        engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        cycle = await engine.start_cycle()
        await engine.prepare_dataset(cycle)
        await engine.train_model(cycle)

        assert cycle.state == LearningState.TRAINING
        engine._training_adapter.train.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_model(self):
        """Should evaluate trained model."""
        engine = LearningEngine(min_examples=2)

        # Mock adapters
        engine._training_adapter = MagicMock()
        engine._training_adapter.train = AsyncMock(
            return_value={
                "run_id": "test_run",
                "model_path": "/models/test",
                "metrics": {"accuracy": 0.85},
            }
        )
        engine._training_adapter.evaluate = AsyncMock(
            return_value={
                "accuracy": 0.87,
            }
        )

        engine.record_interaction(task_id="1", instruction="Q", output="A")
        engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        cycle = await engine.start_cycle()
        await engine.prepare_dataset(cycle)
        await engine.train_model(cycle)
        metrics = await engine.evaluate_model(cycle)

        assert metrics is not None
        assert "accuracy" in str(metrics)

    @pytest.mark.asyncio
    async def test_complete_cycle(self):
        """Should complete full learning cycle."""
        engine = LearningEngine(min_examples=2)

        # Mock adapters
        engine._training_adapter = MagicMock()
        engine._training_adapter.train = AsyncMock(
            return_value={
                "run_id": "test_run",
                "model_path": "/models/test",
                "metrics": {"accuracy": 0.85},
            }
        )
        engine._training_adapter.evaluate = AsyncMock(
            return_value={
                "accuracy": 0.87,
            }
        )

        engine.record_interaction(task_id="1", instruction="Q", output="A")
        engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        cycle = await engine.run_full_cycle()

        assert cycle.state == LearningState.IDLE
        assert cycle.completed_at is not None


class TestLearningEngineStats:
    """Test statistics and history."""

    def test_get_stats(self):
        """Should return learning statistics."""
        engine = LearningEngine()

        engine.record_interaction(task_id="1", instruction="Q", output="A")

        stats = engine.get_stats()

        assert "examples_collected" in stats
        assert "cycles_completed" in stats
        assert "current_state" in stats

    def test_cycle_history(self):
        """Should maintain cycle history."""
        engine = LearningEngine()

        # Create a completed cycle manually for testing
        cycle = LearningCycle(id="test", state=LearningState.IDLE)
        engine._cycle_history.append(cycle)

        assert len(engine.get_cycle_history()) == 1


class TestLearningEngineIntegration:
    """Test integration with other components."""

    def test_with_trust_manager(self):
        """Should update trust manager after training."""
        from src.infrastructure.agents.unified.trust_manager import TrustManager

        trust_manager = TrustManager()
        engine = LearningEngine(trust_manager=trust_manager)

        # After successful training, trust should be updatable
        assert engine.trust_manager is trust_manager

    def test_with_custom_dataset_builder(self):
        """Should accept custom dataset builder."""
        builder = DatasetBuilder()
        engine = LearningEngine(dataset_builder=builder)

        assert engine.dataset_builder is builder

    def test_with_custom_active_learning(self):
        """Should accept custom active learning manager."""
        al_manager = ActiveLearningManager()
        engine = LearningEngine(active_learning=al_manager)

        assert engine.active_learning is al_manager
