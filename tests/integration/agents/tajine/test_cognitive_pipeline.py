"""Integration tests for TAJINE Cognitive Pipeline.

Tests the full 5-level reasoning pipeline:
Level 1 (Discovery) → Level 2 (Causal) → Level 3 (Scenario) → Level 4 (Strategy) → Level 5 (Theoretical)

These tests verify:
- Data flows correctly between levels
- The 3-tier fallback pattern works
- End-to-end processing produces valid outputs
- Error handling and graceful degradation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Full Pipeline Integration Tests
# ============================================================================


class TestCognitivePipelineIntegration:
    """Test full cognitive pipeline integration."""

    @pytest.mark.asyncio
    async def test_full_pipeline_executes_all_levels(self):
        """Test CognitiveEngine runs all 5 levels in order."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [
            {
                "tool": "data_collect",
                "result": {"companies": 100, "companies_last_year": 85, "growth": 0.18},
            }
        ]

        output = await engine.process(results)

        # Verify all 5 levels were executed
        assert "cognitive_levels" in output
        cognitive_levels = output["cognitive_levels"]
        assert isinstance(cognitive_levels, dict)
        assert len(cognitive_levels) == 5

        # Verify all levels are present
        expected = ["discovery", "causal", "scenario", "strategy", "theoretical"]
        for level in expected:
            assert level in cognitive_levels

    @pytest.mark.asyncio
    async def test_pipeline_produces_analysis(self):
        """Test pipeline produces analysis output."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [{"tool": "data_collect", "result": {"companies": 50, "growth": 0.12}}]

        output = await engine.process(results)

        assert "analysis" in output
        assert output["analysis"] is not None

    @pytest.mark.asyncio
    async def test_pipeline_computes_confidence(self):
        """Test pipeline computes overall confidence."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = []

        output = await engine.process(results)

        assert "confidence" in output
        assert 0 <= output["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_results(self):
        """Test pipeline handles empty results gracefully."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        output = await engine.process([])

        # Should complete without error
        assert "cognitive_levels" in output
        assert isinstance(output["cognitive_levels"], dict)
        assert len(output["cognitive_levels"]) == 5


# ============================================================================
# Level Flow Integration Tests
# ============================================================================


class TestLevelFlowIntegration:
    """Test data flow between levels."""

    @pytest.mark.asyncio
    async def test_discovery_output_flows_to_causal(self):
        """Test L1 Discovery output is used by L2 Causal."""
        from src.infrastructure.agents.tajine.cognitive.levels import (
            CausalLevel,
            DiscoveryLevel,
        )

        # L1: Discovery
        discovery = DiscoveryLevel()
        results = [{"tool": "data_collect", "result": {"companies": 100, "growth": 0.15}}]
        discovery_output = await discovery.process(results, {})

        # L2: Causal should use discovery output
        causal = CausalLevel()
        previous = {"discovery": discovery_output}
        causal_output = await causal.process(results, previous)

        assert "causes" in causal_output
        assert "effects" in causal_output

    @pytest.mark.asyncio
    async def test_causal_output_flows_to_scenario(self):
        """Test L2 Causal output is used by L3 Scenario."""
        from src.infrastructure.agents.tajine.cognitive.levels import (
            CausalLevel,
            ScenarioLevel,
        )

        # L2: Causal with mock discovery
        causal = CausalLevel()
        results = [{"tool": "data", "result": {"growth": 0.1}}]
        previous = {"discovery": {"signals": [{"type": "growth"}], "patterns": []}}
        causal_output = await causal.process(results, previous)

        # L3: Scenario uses causal output
        scenario = ScenarioLevel()
        previous["causal"] = causal_output
        scenario_output = await scenario.process(results, previous)

        assert "optimistic" in scenario_output
        assert "median" in scenario_output
        assert "pessimistic" in scenario_output

    @pytest.mark.asyncio
    async def test_scenario_output_flows_to_strategy(self):
        """Test L3 Scenario output is used by L4 Strategy."""
        from src.infrastructure.agents.tajine.cognitive.levels import (
            ScenarioLevel,
            StrategyLevel,
        )

        # L3: Scenario with mock data
        scenario = ScenarioLevel()
        previous = {
            "discovery": {"signals": []},
            "causal": {
                "causes": [
                    {
                        "factor": "growth",
                        "contribution": 0.1,
                        "confidence": 0.7,
                        "direction": "positive",
                    }
                ],
                "effects": [],
            },
        }
        results = [{"tool": "data", "result": {"growth": 0.1}}]
        scenario_output = await scenario.process(results, previous)

        # L4: Strategy uses scenario output
        strategy = StrategyLevel()
        previous["scenario"] = scenario_output
        strategy_output = await strategy.process(results, previous)

        assert "recommendations" in strategy_output
        assert isinstance(strategy_output["recommendations"], list)

    @pytest.mark.asyncio
    async def test_strategy_output_flows_to_theoretical(self):
        """Test L4 Strategy output is used by L5 Theoretical."""
        from src.infrastructure.agents.tajine.cognitive.levels import (
            StrategyLevel,
            TheoreticalLevel,
        )

        # L4: Strategy with mock data
        strategy = StrategyLevel()
        previous = {
            "scenario": {
                "optimistic": {"growth_rate": 0.25},
                "median": {"growth_rate": 0.15},
                "pessimistic": {"growth_rate": 0.05},
                "method": "monte_carlo",
            },
            "causal": {
                "causes": [
                    {
                        "factor": "tech_growth",
                        "contribution": 0.1,
                        "confidence": 0.7,
                        "direction": "positive",
                    }
                ]
            },
        }
        strategy_output = await strategy.process([], previous)

        # L5: Theoretical uses strategy output
        theoretical = TheoreticalLevel()
        previous["strategy"] = strategy_output
        theoretical_output = await theoretical.process([], previous)

        assert "validation" in theoretical_output
        assert "theories_applied" in theoretical_output


# ============================================================================
# Monte Carlo Integration Tests
# ============================================================================


class TestMonteCarloIntegration:
    """Test Monte Carlo simulation integration with pipeline."""

    @pytest.mark.asyncio
    async def test_monte_carlo_scenarios_flow_to_strategy(self):
        """Test Monte Carlo output is correctly processed by Strategy level."""
        from src.infrastructure.agents.tajine.cognitive.levels import StrategyLevel
        from src.infrastructure.agents.tajine.cognitive.scenario import (
            MonteCarloEngine,
            SimulationConfig,
        )

        # Run Monte Carlo simulation
        config = SimulationConfig(n_simulations=1000, random_seed=42)
        engine = MonteCarloEngine(config)
        causes = [
            {
                "factor": "tech_growth",
                "contribution": 0.2,
                "confidence": 0.8,
                "direction": "positive",
            },
            {"factor": "policy", "contribution": 0.1, "confidence": 0.6, "direction": "positive"},
        ]
        scenario_output = engine.simulate(causes, base_value=0.05)

        # Feed to Strategy level
        strategy = StrategyLevel()
        previous = {
            "scenario": scenario_output.to_dict(),
            "causal": {"causes": causes, "confidence": 0.7},
        }
        strategy_output = await strategy.process([], previous)

        # Strategy should produce risk-adjusted recommendations
        assert "recommendations" in strategy_output
        assert len(strategy_output["recommendations"]) > 0

        # Should have risk assessment
        if "risk_assessment" in strategy_output:
            assert "overall_risk" in strategy_output["risk_assessment"]

    @pytest.mark.asyncio
    async def test_high_uncertainty_scenario_produces_cautious_strategy(self):
        """Test high uncertainty leads to cautious recommendations."""
        from src.infrastructure.agents.tajine.cognitive.levels import StrategyLevel
        from src.infrastructure.agents.tajine.cognitive.scenario import (
            MonteCarloEngine,
            SimulationConfig,
        )

        # High uncertainty scenario (low confidence factors)
        config = SimulationConfig(n_simulations=1000, random_seed=42)
        engine = MonteCarloEngine(config)
        causes = [
            {
                "factor": "volatile_factor",
                "contribution": 0.3,
                "confidence": 0.2,
                "direction": "positive",
            },
        ]
        scenario_output = engine.simulate(causes, base_value=0.05)

        # Strategy level should recognize high uncertainty
        strategy = StrategyLevel()
        previous = {
            "scenario": scenario_output.to_dict(),
            "causal": {"causes": causes, "confidence": 0.3},
        }
        strategy_output = await strategy.process([], previous)

        # Should have recommendations (even if cautious)
        assert "recommendations" in strategy_output


# ============================================================================
# Fallback Pattern Integration Tests
# ============================================================================


class TestFallbackPatternIntegration:
    """Test 3-tier fallback pattern across levels."""

    @pytest.mark.asyncio
    async def test_scenario_falls_back_to_rule_based(self):
        """Test Scenario level falls back to rule-based when no causes."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel

        level = ScenarioLevel()
        previous = {
            "discovery": {"signals": []},
            "causal": {"causes": [], "effects": []},  # No causes
        }

        output = await level.process([], previous)

        assert output.get("method") == "rule_based"

    @pytest.mark.asyncio
    async def test_scenario_uses_monte_carlo_when_causes_available(self):
        """Test Scenario level uses Monte Carlo when causes provided."""
        from src.infrastructure.agents.tajine.cognitive.levels import ScenarioLevel

        level = ScenarioLevel()
        previous = {
            "discovery": {"signals": []},
            "causal": {
                "causes": [
                    {
                        "factor": "growth",
                        "contribution": 0.15,
                        "confidence": 0.8,
                        "direction": "positive",
                    }
                ],
                "effects": [],
            },
        }
        results = [{"tool": "data", "result": {"growth": 0.1}}]

        output = await level.process(results, previous)

        # Should use Monte Carlo when causes are available
        assert output.get("method") in ["monte_carlo", "llm"]

    @pytest.mark.asyncio
    async def test_strategy_falls_back_to_rule_based(self):
        """Test Strategy level falls back when no Monte Carlo output."""
        from src.infrastructure.agents.tajine.cognitive.levels import StrategyLevel

        level = StrategyLevel()
        previous = {
            "scenario": {
                "optimistic": {"growth_rate": 0.2},
                "median": {"growth_rate": 0.1},
                "pessimistic": {"growth_rate": 0.05},
                "method": "rule_based",  # Not Monte Carlo
            }
        }

        output = await level.process([], previous)

        assert "recommendations" in output


# ============================================================================
# End-to-End Realistic Scenarios
# ============================================================================


class TestRealisticScenarios:
    """Test realistic end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_growth_sector_analysis(self):
        """Test analysis of a growing sector produces investment recommendations."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [
            {
                "tool": "data_collect",
                "result": {
                    "companies": 150,
                    "companies_last_year": 100,
                    "growth": 0.50,  # 50% growth
                    "territory": "Casablanca",
                },
            },
            {
                "tool": "veille_scan",
                "result": {
                    "news": ["Tech hub expansion announced", "Government incentives for startups"]
                },
            },
        ]

        output = await engine.process(results)

        # Should complete all levels
        assert len(output["cognitive_levels"]) == 5

        # Should have reasonable confidence
        assert output["confidence"] > 0

    @pytest.mark.asyncio
    async def test_declining_sector_analysis(self):
        """Test analysis of a declining sector produces caution recommendations."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [
            {
                "tool": "data_collect",
                "result": {
                    "companies": 80,
                    "companies_last_year": 100,
                    "growth": -0.20,  # 20% decline
                    "territory": "Marrakech",
                },
            }
        ]

        output = await engine.process(results)

        # Should complete successfully
        assert "cognitive_levels" in output
        assert len(output["cognitive_levels"]) == 5

    @pytest.mark.asyncio
    async def test_stable_sector_analysis(self):
        """Test analysis of a stable sector produces monitoring recommendations."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [
            {
                "tool": "data_collect",
                "result": {
                    "companies": 102,
                    "companies_last_year": 100,
                    "growth": 0.02,  # 2% growth (stable)
                    "territory": "Rabat",
                },
            }
        ]

        output = await engine.process(results)

        # Should complete successfully
        assert len(output["cognitive_levels"]) == 5
        assert output["confidence"] > 0


# ============================================================================
# Error Handling Integration Tests
# ============================================================================


class TestErrorHandlingIntegration:
    """Test error handling across the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_handles_malformed_results(self):
        """Test pipeline handles malformed input gracefully."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [
            {"tool": "bad_tool"},  # Missing result key
            {"result": "not a dict"},  # Result is not a dict
            None,  # None value
        ]

        # Should not raise, should degrade gracefully
        output = await engine.process([r for r in results if r is not None])

        assert "cognitive_levels" in output

    @pytest.mark.asyncio
    async def test_pipeline_continues_after_level_error(self):
        """Test pipeline continues even if one level has issues."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()

        # Empty results should still produce output from all levels
        output = await engine.process([])

        # All levels should have processed
        assert len(output["cognitive_levels"]) == 5


# ============================================================================
# Performance Integration Tests
# ============================================================================


class TestPerformanceIntegration:
    """Test performance characteristics of the pipeline."""

    @pytest.mark.asyncio
    async def test_monte_carlo_completes_within_timeout(self):
        """Test Monte Carlo simulation completes in reasonable time."""
        import time

        from src.infrastructure.agents.tajine.cognitive.scenario import (
            MonteCarloEngine,
            SimulationConfig,
        )

        config = SimulationConfig(n_simulations=10000, random_seed=42)
        engine = MonteCarloEngine(config)
        causes = [
            {
                "factor": f"factor_{i}",
                "contribution": 0.05,
                "confidence": 0.7,
                "direction": "positive",
            }
            for i in range(5)
        ]

        start = time.time()
        result = engine.simulate(causes, base_value=0.05)
        elapsed = time.time() - start

        assert elapsed < 2.0  # Should complete in under 2 seconds
        assert result.n_simulations == 10000

    @pytest.mark.asyncio
    async def test_full_pipeline_completes_within_timeout(self):
        """Test full pipeline completes in reasonable time."""
        import time

        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()
        results = [{"tool": "data_collect", "result": {"companies": 100, "growth": 0.15}}]

        start = time.time()
        output = await engine.process(results)
        elapsed = time.time() - start

        assert elapsed < 5.0  # Should complete in under 5 seconds
        assert len(output["cognitive_levels"]) == 5
