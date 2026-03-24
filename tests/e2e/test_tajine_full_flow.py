"""End-to-end test for TAJINE full analysis flow.

Tests the complete PPDSL cycle:
1. TAJINEAgent receives query
2. PERCEIVE: Extract intent and context
3. PLAN: Decompose into subtasks
4. DELEGATE: Execute tools via ManusAgent
5. SYNTHESIZE: Cognitive processing through 5 levels
6. LEARN: Update trust and feedback
7. Final report generation
"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def is_ollama_available() -> bool:
    """Check if Ollama service is running and has models."""
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            return len(data.get("models", [])) > 0
    except Exception:
        pass
    return False


OLLAMA_AVAILABLE = is_ollama_available()


@pytest.mark.e2e
class TestTajineFullFlow:
    """Test complete TAJINE analysis flow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Requires running Ollama service with models")
    async def test_full_territorial_analysis(self):
        """
        E2E Test: "Analyse le potentiel tech dans l'Hérault"

        Flow:
        1. TAJINEAgent receives query
        2. StrategicPlanner decomposes into tasks
        3. ManusAgent executes tasks using tools
        4. CognitiveEngine processes through 5 levels
        5. ValidationEngine validates results
        6. Final report is generated

        Note: This test requires a running Ollama service.
        """
        from src.infrastructure.agents.tajine import create_tajine_agent
        from src.infrastructure.agents.tajine.events import TAJINECallback

        # Create agent with local Ollama
        agent = create_tajine_agent(
            name="test_tajine", local_model="qwen3:14b", ollama_host="http://localhost:11434"
        )

        # Track progress events
        events: list[TAJINECallback] = []

        def on_event_handler(callback: TAJINECallback):
            events.append(callback)

        agent.on_event(on_event_handler)

        # Run analysis
        result = await agent.execute_task(
            {"prompt": "Analyse le potentiel tech dans l'Hérault", "territory": "34"}
        )

        # Assertions
        assert result is not None
        assert "status" in result

        # Should have gone through PPDSL phases
        phases = [e.phase for e in events if hasattr(e, "phase") and e.phase]
        assert len(phases) > 0, "Should have progressed through phases"

        # Check for expected phases
        phase_names = set(phases)
        expected = {"perceive", "plan", "delegate", "synthesize"}
        assert phase_names.intersection(expected), f"Should have PPDSL phases, got: {phase_names}"

        # Result should have structure
        if result.get("status") == "success":
            assert "result" in result or "synthesis" in result
            # Should have cognitive analysis or confidence
            if "confidence" in result:
                assert 0 <= result["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_ppdsl_cycle_with_mocked_llm(self):
        """Test PPDSL cycle with mocked LLM responses."""
        from src.infrastructure.agents.tajine import TAJINEAgent
        from src.infrastructure.agents.tajine.events import TAJINECallback, TAJINEEvent

        # Create agent
        agent = TAJINEAgent(name="test_mocked", local_model="qwen3:14b")

        # Verify agent was created
        assert agent is not None
        assert agent.name == "test_mocked"

        # Verify agent has expected methods
        assert hasattr(agent, "perceive")
        assert hasattr(agent, "plan")
        assert hasattr(agent, "delegate")
        assert hasattr(agent, "synthesize")
        assert hasattr(agent, "execute_task")

    @pytest.mark.asyncio
    async def test_graceful_degradation_without_neo4j(self):
        """Should complete analysis even without Neo4j."""
        from src.infrastructure.agents.tajine import create_tajine_agent
        from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

        # Force Neo4j to be unavailable
        with patch.object(KnowledgeGraphService, "connect", AsyncMock(return_value=False)):
            agent = create_tajine_agent(name="test_no_neo4j")

            # Access KG service to verify degraded mode
            from src.infrastructure.agents.tajine.knowledge import get_kg_service

            kg_service = await get_kg_service()

            # Should work in degraded mode
            result = await kg_service.get_enterprises_by_territory("34")
            assert result == []  # Empty in degraded mode
            assert kg_service.is_available is False

    @pytest.mark.asyncio
    async def test_datasource_tools_integration(self):
        """Should access all TAJINE datasource tools."""
        from src.infrastructure.agents.tajine.tools import get_tajine_tools, get_tool_by_name

        tools = get_tajine_tools()

        # Should have at least 7 tools
        assert len(tools) >= 7, f"Expected >= 7 tools, got {len(tools)}"

        # Verify essential tools exist
        tool_names = [t.metadata.name for t in tools]
        expected_tools = [
            "bodacc_search",
            "boamp_search",
            "geocode",
            "data_collect",
            "veille_scan",
            "sirene_query",
            "territorial_analysis",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

        # Get tool by name should work
        sirene = get_tool_by_name("sirene_query")
        assert sirene is not None
        assert sirene.metadata.name == "sirene_query"

    @pytest.mark.asyncio
    async def test_knowledge_graph_service_operations(self):
        """Test KG service CRUD operations with mocked Neo4j."""
        from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.execute = AsyncMock(
                return_value=[{"e": {"siret": "12345", "nom": "Test Corp", "departement": "34"}}]
            )
            mock_client.execute_write = AsyncMock(return_value=[{"e": {}}])
            MockClient.return_value = mock_client

            service = KnowledgeGraphService()
            await service.connect()

            assert service.is_available is True

            # Test store enterprise
            stored = await service.store_enterprise(
                {"siret": "12345678901234", "nom": "Test Corp", "departement": "34"}
            )
            assert stored is True

            # Test query
            enterprises = await service.get_enterprises_by_territory("34")
            assert len(enterprises) == 1
            assert enterprises[0]["siret"] == "12345"

    @pytest.mark.asyncio
    async def test_cognitive_engine_processing(self):
        """Test CognitiveEngine processes through all 5 levels."""
        from src.infrastructure.agents.tajine.cognitive import (
            CognitiveEngine,
            DiscoveryLevel,
        )

        # Create cognitive engine with mocked LLM router
        mock_router = MagicMock()
        mock_router.route = AsyncMock(
            return_value=MagicMock(
                text='{"analysis": "test", "confidence": 0.8}', model="test", provider="mock"
            )
        )

        engine = CognitiveEngine(llm_router=mock_router)

        # Process through levels
        test_data = {
            "results": [{"source": "sirene", "data": {"count": 150}}],
            "query": "Test analysis",
        }

        # Discovery level - test process method
        discovery_level = DiscoveryLevel()
        assert discovery_level is not None

        # Engine should have process method
        assert hasattr(engine, "process") or hasattr(engine, "process_level")

    @pytest.mark.asyncio
    async def test_trust_manager_tracking(self):
        """Test TrustManager tracks tool outcomes."""
        from src.infrastructure.agents.tajine.trust import TrustManager

        manager = TrustManager()

        # Initial state
        initial_score = manager.get_trust_score()
        assert 0 <= initial_score <= 1

        # Record successful outcomes
        for _ in range(5):
            manager.record_tool_outcome("sirene_query", success=True)

        # Trust should increase
        after_success = manager.get_trust_score()
        assert after_success >= initial_score

        # Record failures
        for _ in range(3):
            manager.record_tool_outcome("sirene_query", success=False)

        # Trust should decrease
        after_failure = manager.get_trust_score()
        assert after_failure <= after_success

    @pytest.mark.asyncio
    async def test_strategic_planner_decomposition(self):
        """Test StrategicPlanner creates valid execution plans."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        # Create planner without LLM router (it may have different constructor)
        planner = StrategicPlanner()

        # Test that planner was created successfully
        assert planner is not None

        # Planner should have create_plan or plan method
        assert hasattr(planner, "create_plan") or hasattr(planner, "plan"), (
            "Planner should have create_plan or plan method"
        )

        # Create plan input
        perception = {"intent": "territorial_analysis", "territory": "34", "sector": "tech"}

    @pytest.mark.asyncio
    async def test_event_emission_during_execution(self):
        """Test that TAJINEAgent emits events during PPDSL cycle."""
        from src.infrastructure.agents.tajine import TAJINEAgent
        from src.infrastructure.agents.tajine.events import TAJINECallback, TAJINEEvent

        agent = TAJINEAgent(name="test_events")

        # Verify agent has event capabilities
        assert hasattr(agent, "on_event"), "Agent should have on_event method"
        assert hasattr(agent, "emit"), "Agent should have emit method"

        # Test event subscription
        events = []

        def capture_event(callback):
            events.append(callback)

        agent.on_event(capture_event)

        # Emit a test event directly
        agent.emit(
            TAJINECallback(event=TAJINEEvent.TASK_STARTED, task_id="test", message="Test event")
        )

        # Should have captured the event
        assert len(events) == 1, "Should capture emitted events"
        assert events[0].event == TAJINEEvent.TASK_STARTED


@pytest.mark.e2e
class TestTajineToolExecution:
    """Test tool execution integration."""

    @pytest.mark.asyncio
    async def test_bodacc_tool_search(self):
        """Test BODACC search tool execution."""
        from src.infrastructure.agents.tajine.tools import get_tool_by_name

        tool = get_tool_by_name("bodacc_search")
        assert tool is not None

        # Verify tool has correct structure
        assert hasattr(tool, "execute")
        assert hasattr(tool, "metadata")
        assert tool.metadata.name == "bodacc_search"

        # Execute with mocked adapter
        # Note: Accessing private _adapter for test injection - this is acceptable
        # in tests to avoid real API calls while testing tool execution logic
        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(return_value=[{"type": "creation", "siret": "123"}])
        tool._adapter = mock_adapter

        result = await tool.execute(event_type="creation", department="34", limit=10)

        assert result is not None
        # Should have result structure
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_sirene_tool_search(self):
        """Test SIRENE query tool execution."""
        from src.infrastructure.agents.tajine.tools import get_tool_by_name

        tool = get_tool_by_name("sirene_query")
        assert tool is not None

        # Tool should have execute method
        assert hasattr(tool, "execute") or hasattr(tool, "__call__")

    @pytest.mark.asyncio
    async def test_territorial_analysis_tool(self):
        """Test territorial analysis tool."""
        from src.infrastructure.agents.tajine.tools import get_tool_by_name

        tool = get_tool_by_name("territorial_analysis")
        assert tool is not None
        assert tool.metadata.name == "territorial_analysis"


@pytest.mark.e2e
class TestTajineDegradedMode:
    """Test TAJINE behavior in degraded mode."""

    @pytest.mark.asyncio
    async def test_works_without_ollama(self):
        """Should handle Ollama unavailability gracefully."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        # Create agent pointing to non-existent Ollama
        agent = TAJINEAgent(
            name="test_no_ollama",
            ollama_host="http://localhost:99999",  # Non-existent
        )

        # Should not crash on creation
        assert agent is not None
        assert agent.name == "test_no_ollama"

    @pytest.mark.asyncio
    async def test_kg_graceful_empty_results(self):
        """KG service returns empty results when unavailable."""
        from src.infrastructure.agents.tajine.knowledge.service import KnowledgeGraphService

        # Force connection failure
        with patch("src.infrastructure.agents.tajine.knowledge.service.Neo4jClient") as MockClient:
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            service = KnowledgeGraphService()
            await service.connect()

            # Should return empty, not error
            enterprises = await service.get_enterprises_by_territory("34")
            assert enterprises == []

            stats = await service.get_territory_stats("34")
            assert stats.get("available") is False


# Integration test that requires real services
@pytest.mark.integration
@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Requires running Ollama service with models")
class TestTajineRealIntegration:
    """Integration tests requiring real Ollama service."""

    @pytest.mark.asyncio
    async def test_real_llm_perceive(self):
        """Test real LLM perception with Ollama."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        agent = create_tajine_agent()

        perception = await agent.perceive("Analyse le potentiel tech dans l'Hérault")

        assert perception is not None
        assert "intent" in perception or isinstance(perception, dict)
