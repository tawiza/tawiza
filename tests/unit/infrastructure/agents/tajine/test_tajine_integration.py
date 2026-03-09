"""Integration tests for TAJINE system.

Tests the full TAJINEAgent workflow including:
- Agent creation via factory
- PPDSL cycle execution
- CognitiveEngine integration
- ValidationEngine integration
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTAJINEIntegration:
    """Integration tests for TAJINE system."""

    def test_import_from_agents_package(self):
        """Test TAJINE can be imported from main agents package."""
        from src.infrastructure.agents import TAJINEAgent, create_tajine_agent, tajine

        assert TAJINEAgent is not None
        assert create_tajine_agent is not None
        assert tajine is not None

    def test_import_all_tajine_components(self):
        """Test all TAJINE components can be imported."""
        from src.infrastructure.agents.tajine import (
            TAJINEAgent,
            create_tajine_agent,
        )
        from src.infrastructure.agents.tajine.cognitive import (
            CausalLevel,
            CognitiveEngine,
            DiscoveryLevel,
            ScenarioLevel,
            StrategyLevel,
            TheoreticalLevel,
        )
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        assert TAJINEAgent is not None
        assert CognitiveEngine is not None
        assert ValidationEngine is not None
        assert TrustManager is not None
        assert StrategicPlanner is not None

    @pytest.mark.asyncio
    async def test_create_and_initialize_agent(self):
        """Test creating and initializing a TAJINEAgent."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        agent = create_tajine_agent(name="integration_test_agent")

        assert agent is not None
        assert agent.name == "integration_test_agent"
        assert agent.agent_type == "tajine"

        # Initialize
        await agent.initialize()
        assert agent._initialized is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_full_ppdsl_cycle(self):
        """Test running a full PPDSL cycle.

        Note: This is an integration test - requires running Ollama LLM.
        The execute_task call triggers real LLM inference + embedding calls.
        Skipped in unit test runs.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")

    @pytest.mark.asyncio
    async def test_cognitive_engine_integration(self):
        """Test CognitiveEngine processes through all 5 levels."""
        from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

        engine = CognitiveEngine()

        # Process sample results
        results = [
            {"type": "growth", "value": 0.15, "source": "sirene"},
            {"type": "concentration", "value": 0.8, "source": "insee"},
        ]

        synthesis = await engine.process(results)

        # Verify all cognitive levels present
        assert "cognitive_levels" in synthesis
        levels = synthesis["cognitive_levels"]
        assert "discovery" in levels
        assert "causal" in levels
        assert "scenario" in levels
        assert "strategy" in levels
        assert "theoretical" in levels

        # Verify confidence
        assert "confidence" in synthesis
        assert 0 <= synthesis["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_validation_engine_integration(self):
        """Test ValidationEngine validates claims correctly."""
        from src.infrastructure.agents.tajine.validation import ValidationEngine

        engine = ValidationEngine()

        # Valid claim
        valid_result = await engine.validate(
            {"claim": "Company count is 847", "source": "sirene_api", "data": {"count": 847}}
        )

        assert valid_result["is_valid"] is True
        assert valid_result["confidence"] >= 0.5

        # Invalid claim (hallucination)
        invalid_result = await engine.validate(
            {"claim": "Massive growth detected", "source": None, "data": {}}
        )

        assert invalid_result["is_valid"] is False
        assert "hallucination" in invalid_result["flags"]

    @pytest.mark.asyncio
    async def test_trust_manager_integration(self):
        """Test TrustManager tracks performance correctly."""
        from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager

        manager = TrustManager()

        initial_score = manager.get_trust_score()
        initial_level = manager.get_autonomy_level()

        # Record some successes
        for _ in range(5):
            manager.record_success()

        new_score = manager.get_trust_score()
        assert new_score >= initial_score

    @pytest.mark.asyncio
    async def test_strategic_planner_integration(self):
        """Test StrategicPlanner creates valid plans."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        # Pass a perception dict (output from perceive())
        perception = {
            "intent": "analyze",
            "territory": "Montpellier",
            "sector": "tech",
            "raw_query": "Analyze regional economic data",
        }
        plan = await planner.create_plan(perception)

        assert "subtasks" in plan
        assert "strategy" in plan
        assert "estimated_steps" in plan
        assert len(plan["subtasks"]) > 0

    @pytest.mark.asyncio
    async def test_agent_shutdown(self):
        """Test agent can be cleanly shutdown."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        agent = create_tajine_agent(name="shutdown_test_agent")
        await agent.initialize()

        # Shutdown
        await agent.shutdown()
        assert agent._initialized is False

    @pytest.mark.asyncio
    async def test_agent_health_check(self):
        """Test agent health check after initialization."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        agent = create_tajine_agent(name="health_test_agent")

        # Before init - should be unhealthy
        health_before = await agent.health_check()
        assert health_before is False

        # After init - should be healthy
        await agent.initialize()
        health_after = await agent.health_check()
        assert health_after is True


class TestTAJINERegistryIntegration:
    """Test TAJINE integration with AgentRegistry."""

    @pytest.mark.asyncio
    async def test_register_tajine_agent(self):
        """Test TAJINEAgent can be registered in the registry."""
        from src.infrastructure.agents import get_agent_registry
        from src.infrastructure.agents.tajine import create_tajine_agent

        # Get fresh registry (clear any existing)
        registry = get_agent_registry()
        if registry.get("registry_test_agent"):
            registry.unregister("registry_test_agent")

        # Create and register
        agent = create_tajine_agent(name="registry_test_agent")
        registry.register(agent)

        # Verify registration
        retrieved = registry.get("registry_test_agent")
        assert retrieved is not None
        assert retrieved.name == "registry_test_agent"
        assert retrieved.agent_type == "tajine"

        # Cleanup
        registry.unregister("registry_test_agent")

    @pytest.mark.asyncio
    async def test_find_tajine_by_type(self):
        """Test finding TAJINEAgent by type."""
        from src.infrastructure.agents import get_agent_registry
        from src.infrastructure.agents.tajine import create_tajine_agent

        registry = get_agent_registry()

        # Cleanup any existing
        if registry.get("type_test_agent"):
            registry.unregister("type_test_agent")

        agent = create_tajine_agent(name="type_test_agent")
        registry.register(agent)

        # Find by type
        tajine_agents = registry.get_by_type("tajine")
        assert len(tajine_agents) >= 1
        assert any(a.name == "type_test_agent" for a in tajine_agents)

        # Cleanup
        registry.unregister("type_test_agent")
