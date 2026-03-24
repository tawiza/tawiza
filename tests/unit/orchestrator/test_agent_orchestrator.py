"""Unit tests for AgentOrchestrator."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.orchestrator import (
    AgentInfo,
    AgentOrchestrator,
    AgentState,
    OrchestratorEvent,
    get_orchestrator,
)
from src.infrastructure.orchestrator.agent_orchestrator import EventType


@pytest.fixture
def orchestrator():
    """Create fresh orchestrator for each test."""
    AgentOrchestrator.reset_instance()
    orch = get_orchestrator()
    yield orch
    orch.reset()
    AgentOrchestrator.reset_instance()


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = Mock()
    agent.run = AsyncMock(return_value={"result": "test"})
    return agent


class TestSingleton:
    """Test singleton pattern."""

    def test_singleton_returns_same_instance(self, orchestrator):
        """Same instance returned each time."""
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2

    def test_reset_instance_creates_new(self, orchestrator):
        """Reset creates new instance."""
        orch1 = get_orchestrator()
        AgentOrchestrator.reset_instance()
        orch2 = get_orchestrator()
        # They are same singleton pattern but reset clears state
        assert orch2._initialized


class TestAgentRegistry:
    """Test agent registration."""

    def test_register_agent(self, orchestrator, mock_agent):
        """Agent can be registered."""
        agent_id = orchestrator.register_agent(mock_agent, agent_type="tajine", name="test_agent")
        assert agent_id is not None
        assert len(agent_id) == 12

    def test_get_agent(self, orchestrator, mock_agent):
        """Registered agent can be retrieved."""
        agent_id = orchestrator.register_agent(mock_agent, "tajine")
        retrieved = orchestrator.get_agent(agent_id)
        assert retrieved is mock_agent

    def test_get_nonexistent_agent(self, orchestrator):
        """Getting nonexistent agent returns None."""
        assert orchestrator.get_agent("nonexistent") is None

    def test_get_agent_info(self, orchestrator, mock_agent):
        """Agent info can be retrieved."""
        agent_id = orchestrator.register_agent(
            mock_agent, agent_type="tajine", name="my_agent", metadata={"key": "value"}
        )
        info = orchestrator.get_agent_info(agent_id)
        assert info is not None
        assert info.agent_type == "tajine"
        assert info.name == "my_agent"
        assert info.metadata == {"key": "value"}
        assert info.state == AgentState.IDLE

    def test_list_agents(self, orchestrator, mock_agent):
        """All agents can be listed."""
        orchestrator.register_agent(mock_agent, "tajine", "agent1")
        orchestrator.register_agent(mock_agent, "manus", "agent2")
        orchestrator.register_agent(mock_agent, "tajine", "agent3")

        agents = orchestrator.list_agents()
        assert len(agents) == 3

    def test_get_agents_by_type(self, orchestrator, mock_agent):
        """Agents can be filtered by type."""
        orchestrator.register_agent(mock_agent, "tajine", "t1")
        orchestrator.register_agent(mock_agent, "manus", "m1")
        orchestrator.register_agent(mock_agent, "tajine", "t2")

        tajine_agents = orchestrator.get_agents_by_type("tajine")
        assert len(tajine_agents) == 2

        manus_agents = orchestrator.get_agents_by_type("manus")
        assert len(manus_agents) == 1

    def test_unregister_agent(self, orchestrator, mock_agent):
        """Agent can be unregistered."""
        agent_id = orchestrator.register_agent(mock_agent, "tajine")
        assert orchestrator.get_agent(agent_id) is not None

        result = orchestrator.unregister_agent(agent_id)
        assert result is True
        assert orchestrator.get_agent(agent_id) is None

    def test_unregister_nonexistent(self, orchestrator):
        """Unregistering nonexistent agent returns False."""
        result = orchestrator.unregister_agent("nonexistent")
        assert result is False


class TestEventBus:
    """Test event bus functionality."""

    def test_subscribe_and_emit(self, orchestrator):
        """Subscribers receive events."""
        received = []

        def callback(event):
            received.append(event)

        orchestrator.subscribe("test.event", callback)
        orchestrator.emit(OrchestratorEvent(type="test.event", data={"key": "value"}))

        assert len(received) == 1
        assert received[0].type == "test.event"
        assert received[0].data == {"key": "value"}

    def test_global_subscriber(self, orchestrator):
        """Global subscribers receive all events."""
        received = []

        def callback(event):
            received.append(event)

        orchestrator.subscribe_all(callback)
        orchestrator.emit(OrchestratorEvent(type="event1"))
        orchestrator.emit(OrchestratorEvent(type="event2"))

        assert len(received) == 2

    def test_unsubscribe(self, orchestrator):
        """Unsubscribed callbacks don't receive events."""
        received = []

        def callback(event):
            received.append(event)

        orchestrator.subscribe("test", callback)
        orchestrator.emit(OrchestratorEvent(type="test"))
        assert len(received) == 1

        orchestrator.unsubscribe("test", callback)
        orchestrator.emit(OrchestratorEvent(type="test"))
        assert len(received) == 1  # Still 1

    def test_event_history(self, orchestrator):
        """Events are recorded in history."""
        orchestrator.emit(OrchestratorEvent(type="event1"))
        orchestrator.emit(OrchestratorEvent(type="event2"))
        orchestrator.emit(OrchestratorEvent(type="event3"))

        history = orchestrator.get_event_history()
        assert len(history) == 3

    def test_event_history_filter_by_type(self, orchestrator):
        """Event history can be filtered by type."""
        orchestrator.emit(OrchestratorEvent(type="type_a"))
        orchestrator.emit(OrchestratorEvent(type="type_b"))
        orchestrator.emit(OrchestratorEvent(type="type_a"))

        history = orchestrator.get_event_history(event_type="type_a")
        assert len(history) == 2

    def test_event_history_filter_by_agent(self, orchestrator):
        """Event history can be filtered by agent."""
        orchestrator.emit(OrchestratorEvent(type="test", agent_id="agent1"))
        orchestrator.emit(OrchestratorEvent(type="test", agent_id="agent2"))
        orchestrator.emit(OrchestratorEvent(type="test", agent_id="agent1"))

        history = orchestrator.get_event_history(agent_id="agent1")
        assert len(history) == 2

    def test_callback_error_doesnt_break_emit(self, orchestrator):
        """Callback errors don't break event emission."""
        received = []

        def bad_callback(event):
            raise ValueError("Intentional error")

        def good_callback(event):
            received.append(event)

        orchestrator.subscribe("test", bad_callback)
        orchestrator.subscribe("test", good_callback)

        # Should not raise
        orchestrator.emit(OrchestratorEvent(type="test"))
        assert len(received) == 1


class TestAgentLifecycle:
    """Test agent lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_agent(self, orchestrator, mock_agent):
        """Agent can be started."""
        agent_id = orchestrator.register_agent(mock_agent, "tajine")

        result = await orchestrator.start_agent(agent_id, task="test task")
        assert result is True

        info = orchestrator.get_agent_info(agent_id)
        assert info.state == AgentState.RUNNING
        assert info.current_task == "test task"

    @pytest.mark.asyncio
    async def test_start_nonexistent_agent(self, orchestrator):
        """Starting nonexistent agent returns False."""
        result = await orchestrator.start_agent("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_agent(self, orchestrator, mock_agent):
        """Agent can be stopped."""
        agent_id = orchestrator.register_agent(mock_agent, "tajine")
        await orchestrator.start_agent(agent_id)

        result = await orchestrator.stop_agent(agent_id)
        assert result is True

        info = orchestrator.get_agent_info(agent_id)
        assert info.state == AgentState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_resume_agent(self, orchestrator, mock_agent):
        """Agent can be paused and resumed."""
        agent_id = orchestrator.register_agent(mock_agent, "tajine")
        await orchestrator.start_agent(agent_id)

        # Pause
        await orchestrator.pause_agent(agent_id)
        info = orchestrator.get_agent_info(agent_id)
        assert info.state == AgentState.PAUSED

        # Resume
        await orchestrator.resume_agent(agent_id)
        info = orchestrator.get_agent_info(agent_id)
        assert info.state == AgentState.RUNNING

    @pytest.mark.asyncio
    async def test_lifecycle_events_emitted(self, orchestrator, mock_agent):
        """Lifecycle events are emitted."""
        events = []
        orchestrator.subscribe_all(lambda e: events.append(e))

        agent_id = orchestrator.register_agent(mock_agent, "tajine")
        await orchestrator.start_agent(agent_id)
        await orchestrator.pause_agent(agent_id)
        await orchestrator.resume_agent(agent_id)
        await orchestrator.stop_agent(agent_id)

        event_types = [e.type for e in events]
        assert EventType.AGENT_REGISTERED.value in event_types
        assert EventType.AGENT_STARTED.value in event_types
        assert EventType.AGENT_PAUSED.value in event_types
        assert EventType.AGENT_RESUMED.value in event_types
        assert EventType.AGENT_STOPPED.value in event_types


class TestOrchestratorEvent:
    """Test OrchestratorEvent dataclass."""

    def test_event_to_dict(self):
        """Event can be serialized to dict."""
        event = OrchestratorEvent(type="test.event", agent_id="agent123", data={"key": "value"})
        d = event.to_dict()

        assert d["type"] == "test.event"
        assert d["agent_id"] == "agent123"
        assert d["data"] == {"key": "value"}
        assert "timestamp" in d
        assert "event_id" in d

    def test_event_auto_generates_id(self):
        """Event auto-generates unique ID."""
        event1 = OrchestratorEvent(type="test")
        event2 = OrchestratorEvent(type="test")
        assert event1.event_id != event2.event_id


class TestAgentInfo:
    """Test AgentInfo dataclass."""

    def test_info_to_dict(self):
        """AgentInfo can be serialized to dict."""
        info = AgentInfo(
            agent_id="test123",
            agent_type="tajine",
            name="Test Agent",
            state=AgentState.RUNNING,
            current_task="analyzing",
        )
        d = info.to_dict()

        assert d["agent_id"] == "test123"
        assert d["agent_type"] == "tajine"
        assert d["name"] == "Test Agent"
        assert d["state"] == "running"
        assert d["current_task"] == "analyzing"


class TestReset:
    """Test reset functionality."""

    def test_reset_clears_state(self, orchestrator, mock_agent):
        """Reset clears all state."""
        orchestrator.register_agent(mock_agent, "tajine")
        orchestrator.emit(OrchestratorEvent(type="test"))

        assert len(orchestrator.list_agents()) == 1
        assert len(orchestrator.get_event_history()) > 0

        orchestrator.reset()

        assert len(orchestrator.list_agents()) == 0
        assert len(orchestrator.get_event_history()) == 0
