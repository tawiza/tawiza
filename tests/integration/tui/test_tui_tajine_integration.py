"""Integration tests for TUI-TAJINE connection.

Tests the integration between:
- TUI AgentController
- TAJINEService
- TAJINEAgent (mocked)
- AgentOrchestrator event emission
"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.orchestrator import (
    AgentOrchestrator,
    OrchestratorEvent,
    get_orchestrator,
)


@pytest.fixture
def orchestrator():
    """Create fresh orchestrator for each test."""
    AgentOrchestrator.reset_instance()
    orch = get_orchestrator()
    yield orch
    orch.reset()
    AgentOrchestrator.reset_instance()


class TestTUITAJINEIntegration:
    """Test TUI to TAJINE integration."""

    @pytest.mark.asyncio
    async def test_tajine_service_initialization(self):
        """TAJINEService initializes correctly."""
        from src.cli.v3.tui.services.tajine_service import (
            ProcessingState,
            TAJINEService,
        )

        service = TAJINEService(use_agent=False)  # Use CognitiveEngine directly
        assert service.state == ProcessingState.IDLE
        assert service.last_result is None

    @pytest.mark.asyncio
    async def test_tajine_service_event_emission(self):
        """TAJINEService emits events during processing."""
        from src.cli.v3.tui.services.tajine_service import (
            AnalysisRequest,
            ProcessingEvent,
            TAJINEService,
        )

        service = TAJINEService(use_agent=False)
        events: list[ProcessingEvent] = []

        def capture_event(event: ProcessingEvent):
            events.append(event)

        service.add_event_listener(capture_event)

        # Mock the CognitiveEngine
        with patch.object(service, "_get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_engine.process = AsyncMock(
                return_value={
                    "cognitive_levels": {
                        "discovery": {"signals": [], "confidence": 0.8},
                        "causal": {"causes": [], "confidence": 0.7},
                        "scenario": {"median": {"growth_rate": 0.05}},
                        "strategy": {"recommendations": []},
                        "theoretical": {"summary": "Test"},
                    },
                    "confidence": 0.75,
                }
            )
            mock_get_engine.return_value = mock_engine

            request = AnalysisRequest(query="Test analysis", territory="34", sector="tech")

            result = await service.analyze(request)

            # Should have emitted events
            assert len(events) > 0
            # Should have result
            assert result is not None
            assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_orchestrator_emits_tajine_events(self, orchestrator):
        """AgentOrchestrator emits TAJINE events."""
        events: list[OrchestratorEvent] = []
        orchestrator.subscribe_all(lambda e: events.append(e))

        # Create mock TAJINE agent
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value={"result": "test"})

        # Register as TAJINE agent
        agent_id = orchestrator.register_agent(mock_agent, agent_type="tajine", name="test_tajine")

        # Should have emitted registration event
        assert len(events) >= 1
        reg_event = next(e for e in events if "registered" in e.type)
        assert reg_event.agent_id == agent_id

    @pytest.mark.asyncio
    async def test_tajine_chat_service(self):
        """TAJINEChatService provides conversational interface."""
        from src.cli.v3.tui.services.tajine_service import (
            TAJINEChatService,
            TAJINEService,
        )

        # Create chat service with mocked TAJINE
        tajine_service = TAJINEService(use_agent=False)

        with patch.object(tajine_service, "_get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            mock_engine.process = AsyncMock(
                return_value={
                    "cognitive_levels": {},
                    "confidence": 0.8,
                }
            )
            mock_get_engine.return_value = mock_engine

            chat = TAJINEChatService(tajine_service)

            # Send a message
            response = await chat.send_message("Analyse tech Montpellier")

            # Should have response
            assert response is not None
            assert len(response) > 0

            # Should have history
            assert len(chat.history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_tajine_service_caching(self):
        """TAJINEService caches results."""
        from src.cli.v3.tui.services.tajine_service import (
            AnalysisRequest,
            TAJINEService,
        )

        service = TAJINEService(use_agent=False)

        with patch.object(service, "_get_engine") as mock_get_engine:
            mock_engine = MagicMock()
            call_count = 0

            async def mock_process(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return {"cognitive_levels": {}, "confidence": 0.8}

            mock_engine.process = mock_process
            mock_get_engine.return_value = mock_engine

            request = AnalysisRequest(query="Test", territory="34")

            # First call - should process
            await service.analyze(request, use_cache=True)
            assert call_count == 1

            # Second call - should use cache
            await service.analyze(request, use_cache=True)
            assert call_count == 1  # Still 1

            # Third call without cache - should process again
            await service.analyze(request, use_cache=False)
            assert call_count == 2


class TestTUIAgentController:
    """Test TUI AgentController TAJINE integration."""

    def test_agent_controller_lists_tajine(self):
        """AgentController includes TAJINE in available agents."""
        from src.application.services.agent_orchestrator import (
            get_agent_orchestrator,
        )

        orchestrator = get_agent_orchestrator()
        agents = orchestrator.tui_agents

        # Should have TAJINE
        assert "tajine" in agents
        assert agents["tajine"]["name"] == "TAJINE Agent"
        assert "cognitive" in agents["tajine"]["capabilities"]


class TestEventFlow:
    """Test end-to-end event flow."""

    @pytest.mark.asyncio
    async def test_tajine_to_orchestrator_event_flow(self, orchestrator):
        """Events flow from TAJINE to orchestrator."""
        received_events: list[OrchestratorEvent] = []

        def on_event(event: OrchestratorEvent):
            received_events.append(event)

        orchestrator.subscribe("tajine.cognitive_level", on_event)

        # Emit cognitive level event
        orchestrator.emit(
            OrchestratorEvent(
                type="tajine.cognitive_level",
                agent_id="test_agent",
                data={"level": "discovery", "confidence": 0.85, "signals": ["signal1", "signal2"]},
            )
        )

        # Should have received
        assert len(received_events) == 1
        assert received_events[0].data["level"] == "discovery"
        assert received_events[0].data["confidence"] == 0.85
