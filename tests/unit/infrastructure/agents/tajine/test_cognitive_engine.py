"""Tests for CognitiveEngine - 5-level reasoning system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCognitiveEngineImports:
    """Test imports."""

    def test_import_cognitive_engine(self):
        """Test CognitiveEngine can be imported."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        assert CognitiveEngine is not None

    def test_import_cognitive_levels(self):
        """Test individual levels can be imported."""
        from src.infrastructure.agents.tajine.cognitive.engine import (
            CausalLevel,
            DiscoveryLevel,
            ScenarioLevel,
            StrategyLevel,
            TheoreticalLevel,
        )

        assert all([DiscoveryLevel, CausalLevel, ScenarioLevel, StrategyLevel, TheoreticalLevel])


class TestCognitiveEngineStructure:
    """Test CognitiveEngine structure."""

    def test_engine_has_five_levels(self):
        """Test engine has exactly 5 levels."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()

        assert len(engine.levels) == 5

    def test_levels_are_ordered(self):
        """Test levels are in correct order."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        level_names = [name for name, _ in engine.levels]

        expected = ["discovery", "causal", "scenario", "strategy", "theoretical"]
        assert level_names == expected


class TestDiscoveryLevel:
    """Test Level 1: Discovery."""

    @pytest.mark.asyncio
    async def test_discovery_detects_signals(self):
        """Test discovery level detects weak signals."""
        from src.infrastructure.agents.tajine.cognitive.levels import DiscoveryLevel

        level = DiscoveryLevel()
        results = [
            {"tool": "data_collect", "result": {"companies": 847, "growth": 0.15}},
            {"tool": "veille_scan", "result": {"news": ["AI startup funding +40%"]}},
        ]

        output = await level.process(results, {})

        assert "signals" in output
        assert "patterns" in output
        assert "confidence" in output
        assert 0 <= output["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_discovery_identifies_trends(self):
        """Test discovery identifies growth trends."""
        from src.infrastructure.agents.tajine.cognitive.levels import DiscoveryLevel

        level = DiscoveryLevel()
        results = [
            {
                "tool": "data_collect",
                "result": {
                    "companies": 100,
                    "companies_last_year": 80,
                },
            }
        ]

        output = await level.process(results, {})

        # Should detect growth signal
        assert any("growth" in str(s).lower() for s in output.get("signals", []))


class TestCausalLevel:
    """Test Level 2: Causal Analysis."""

    @pytest.mark.asyncio
    async def test_causal_identifies_factors(self):
        """Test causal level identifies contributing factors."""
        from src.infrastructure.agents.tajine.cognitive.levels import CausalLevel

        level = CausalLevel()
        results = [
            {"tool": "data_collect", "result": {"proximity_university": True}},
        ]
        previous = {"discovery": {"signals": [{"type": "growth"}], "patterns": []}}

        output = await level.process(results, previous)

        assert "causes" in output
        assert "effects" in output


class TestScenarioLevel:
    """Test Level 3: Scenario Generation."""

    @pytest.mark.asyncio
    async def test_scenario_generates_three_scenarios(self):
        """Test scenario level generates optimistic/median/pessimistic."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel

        level = ScenarioLevel()
        results = []
        previous = {"discovery": {"signals": []}, "causal": {"causes": [], "effects": []}}

        output = await level.process(results, previous)

        assert "optimistic" in output
        assert "median" in output
        assert "pessimistic" in output


class TestStrategyLevel:
    """Test Level 4: Strategy Recommendations."""

    @pytest.mark.asyncio
    async def test_strategy_generates_recommendations(self):
        """Test strategy level generates actionable recommendations."""
        from src.infrastructure.agents.tajine.cognitive.levels import StrategyLevel

        level = StrategyLevel()
        results = []
        previous = {"scenario": {"optimistic": {}, "median": {}, "pessimistic": {}}}

        output = await level.process(results, previous)

        assert "recommendations" in output
        assert isinstance(output["recommendations"], list)


class TestTheoreticalLevel:
    """Test Level 5: Theoretical Validation."""

    @pytest.mark.asyncio
    async def test_theoretical_validates_with_theories(self):
        """Test theoretical level validates against known theories."""
        from src.infrastructure.agents.tajine.cognitive.levels import TheoreticalLevel

        level = TheoreticalLevel()
        results = []
        previous = {"strategy": {"recommendations": [{"description": "invest in tech hub"}]}}

        output = await level.process(results, previous)

        assert "validation" in output
        assert "theories_applied" in output


class TestCognitiveEngineProcess:
    """Test full CognitiveEngine.process() method."""

    @pytest.mark.asyncio
    async def test_process_runs_all_levels(self):
        """Test process() runs through all 5 levels."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [{"tool": "data_collect", "result": {"companies": 100}}]

        output = await engine.process(results)

        assert "analysis" in output
        assert "confidence" in output
        assert "cognitive_levels" in output
        assert len(output["cognitive_levels"]) == 5

    @pytest.mark.asyncio
    async def test_process_computes_confidence(self):
        """Test process() computes weighted confidence."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = []

        output = await engine.process(results)

        assert 0 <= output["confidence"] <= 1
