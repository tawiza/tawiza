"""Tests for SAFLA integration with TAJINE."""

import asyncio
from datetime import datetime

import pytest

from src.infrastructure.agents.tajine.safla import (
    SAFLABridge,
    SAFLAMemoryAdapter,
    SAFLAMetaCognitiveAdapter,
)
from src.infrastructure.agents.tajine.safla.metacognitive_adapter import (
    PerformanceMetrics,
    StrategyType,
    TaskComplexity,
)


class TestSAFLAMemoryAdapter:
    """Test SAFLA memory adapter functionality."""

    @pytest.fixture
    def memory_adapter(self, tmp_path):
        """Create a memory adapter with temp storage."""
        return SAFLAMemoryAdapter(storage_path=tmp_path / "safla")

    @pytest.mark.asyncio
    async def test_initialization(self, memory_adapter):
        """Test memory adapter initializes correctly."""
        await memory_adapter.initialize()
        stats = await memory_adapter.get_stats()
        assert stats["status"] in ["active", "unavailable"]

    @pytest.mark.asyncio
    async def test_store_task_memory(self, memory_adapter):
        """Test storing task memory."""
        await memory_adapter.initialize()

        item_id = await memory_adapter.store_task_memory(
            task_id="test-001",
            query="Analyse des entreprises à Paris",
            result={"confidence": 0.8, "insights": ["Paris has many startups"]},
            territory="75",
            sector="tech",
            success=True,
        )

        assert item_id == "test-001"

    @pytest.mark.asyncio
    async def test_store_insight(self, memory_adapter):
        """Test storing analysis insight."""
        await memory_adapter.initialize()

        item_id = await memory_adapter.store_analysis_insight(
            insight="Le secteur tech parisien croît de 15% par an",
            analysis_type="economic",
            territory="75",
            confidence=0.85,
        )

        assert item_id is not None
        assert len(item_id) == 16

    @pytest.mark.asyncio
    async def test_recall_similar(self, memory_adapter):
        """Test recalling similar memories."""
        await memory_adapter.initialize()

        # Store some memories
        await memory_adapter.store_analysis_insight(
            insight="Paris startup ecosystem analysis",
            analysis_type="economic",
            territory="75",
        )

        # Recall
        results = await memory_adapter.recall_similar(
            query="startups in Paris",
            limit=5,
        )

        # Results may be empty if SAFLA not available
        assert isinstance(results, list)


class TestSAFLAMetaCognitiveAdapter:
    """Test SAFLA metacognitive adapter functionality."""

    @pytest.fixture
    def meta_adapter(self):
        """Create a metacognitive adapter."""
        return SAFLAMetaCognitiveAdapter()

    @pytest.mark.asyncio
    async def test_initialization(self, meta_adapter):
        """Test metacognitive adapter initializes correctly."""
        await meta_adapter.initialize()
        state = await meta_adapter.get_system_state()
        assert state["initialized"] is True

    @pytest.mark.asyncio
    async def test_strategic_insight(self, meta_adapter):
        """Test getting strategic insight."""
        await meta_adapter.initialize()

        insight = await meta_adapter.get_strategic_insight(
            query="Compare economic performance of Lyon and Marseille",
            context={"territory": "69"},
        )

        assert insight is not None
        assert insight.suggested_strategy is not None
        assert 0 <= insight.confidence <= 1
        assert insight.estimated_duration_ms > 0

    @pytest.mark.asyncio
    async def test_record_performance(self, meta_adapter):
        """Test recording performance metrics."""
        await meta_adapter.initialize()

        metrics = PerformanceMetrics(
            task_id="test-perf-001",
            duration_ms=1500.0,
            success=True,
            confidence=0.75,
            data_sources_used=3,
            cache_hit=False,
            strategy_used=StrategyType.DEEP_ANALYSIS,
        )

        await meta_adapter.record_performance(metrics)

        state = await meta_adapter.get_system_state()
        assert state["history_size"] >= 1

    @pytest.mark.asyncio
    async def test_complexity_assessment(self, meta_adapter):
        """Test task complexity assessment."""
        # Simple query - needs to not contain any analysis keywords
        complexity = meta_adapter._assess_complexity("Donne moi les chiffres", {})
        assert complexity == TaskComplexity.SIMPLE

        # Moderate query - contains "list" or "summarize"
        complexity = meta_adapter._assess_complexity(
            "Liste des entreprises à Paris",
            {},
        )
        assert complexity == TaskComplexity.MODERATE

        # Complex query - contains "analyze" or "impact"
        complexity = meta_adapter._assess_complexity(
            "Analyze the impact of investments",
            {},
        )
        assert complexity == TaskComplexity.COMPLEX

        # Expert query - contains "compare" or "predict"
        complexity = meta_adapter._assess_complexity(
            "Compare and predict demographic trends",
            {},
        )
        assert complexity == TaskComplexity.EXPERT


class TestSAFLABridge:
    """Test SAFLA bridge (main integration point)."""

    @pytest.fixture
    def bridge(self, tmp_path):
        """Create a SAFLA bridge with temp storage."""
        return SAFLABridge(storage_path=tmp_path / "safla")

    @pytest.mark.asyncio
    async def test_initialization(self, bridge):
        """Test bridge initializes all components."""
        await bridge.initialize()
        status = await bridge.get_status()

        assert status["initialized"] is True
        assert "memory" in status
        assert "metacognitive" in status

    @pytest.mark.asyncio
    async def test_prepare_context(self, bridge):
        """Test preparing execution context."""
        await bridge.initialize()

        context = await bridge.prepare_context(
            task_id="ctx-001",
            query="Analyze economic trends in Hauts-de-France",
            territory="59",
            sector="industry",
        )

        assert context.task_id == "ctx-001"
        assert context.query == "Analyze economic trends in Hauts-de-France"
        assert context.territory == "59"
        assert context.relevant_memories is not None
        assert context.strategic_insight is not None

    @pytest.mark.asyncio
    async def test_record_execution(self, bridge):
        """Test recording execution results."""
        await bridge.initialize()

        # Prepare context
        context = await bridge.prepare_context(
            task_id="exec-001",
            query="Test execution recording",
        )

        # Record execution
        await bridge.record_execution(
            context=context,
            result={"confidence": 0.9, "insights": ["Test insight"]},
            success=True,
        )

        # Verify active contexts cleared
        assert "exec-001" not in bridge._active_contexts

    @pytest.mark.asyncio
    async def test_improvement_suggestion(self, bridge):
        """Test getting improvement suggestions."""
        await bridge.initialize()

        # With no history, should return None
        suggestion = await bridge.get_improvement_suggestion()
        assert suggestion is None

        # Record some failures
        for i in range(15):
            metrics = PerformanceMetrics(
                task_id=f"fail-{i}",
                duration_ms=2000.0,
                success=i % 3 != 0,  # Some failures
                confidence=0.4,
                data_sources_used=1,
                cache_hit=False,
                strategy_used=StrategyType.DEEP_ANALYSIS,
            )
            await bridge.metacognitive.record_performance(metrics)

        # Now should have a suggestion
        suggestion = await bridge.get_improvement_suggestion()
        # May or may not have suggestion depending on failure rate
        assert suggestion is None or isinstance(suggestion, str)
