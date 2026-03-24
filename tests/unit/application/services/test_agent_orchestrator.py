"""Unit tests for AgentOrchestrator.

Tests the TUI agent integration including:
- Agent initialization
- Task execution with events
- Ollama fallback behavior
- Event streaming
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.agent_orchestrator import (
    AgentOrchestrator,
    TaskEvent,
    TaskEventType,
    get_agent_orchestrator,
    initialize_orchestrator,
)


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator class."""

    def test_singleton_pattern(self):
        """Test that get_agent_orchestrator returns singleton."""
        orch1 = get_agent_orchestrator()
        orch2 = get_agent_orchestrator()
        assert orch1 is orch2

    def test_initialization(self):
        """Test basic orchestrator initialization."""
        orch = AgentOrchestrator()

        # Check Tawiza agents
        assert len(orch.tawiza_agents) == 9
        assert "tawiza-analyst" in orch.tawiza_agents

        # Check TUI agents
        assert len(orch.tui_agents) == 7
        assert "manus" in orch.tui_agents
        assert "general" in orch.tui_agents

    def test_tui_agent_info(self):
        """Test getting TUI agent info."""
        orch = AgentOrchestrator()

        manus_info = orch.get_tui_agent_info("manus")
        assert manus_info is not None
        assert manus_info["name"] == "Manus Agent"
        assert "reasoning" in manus_info["capabilities"]

        unknown_info = orch.get_tui_agent_info("unknown")
        assert unknown_info is None

    def test_list_tui_agents(self):
        """Test listing all TUI agents."""
        orch = AgentOrchestrator()
        agents = orch.list_tui_agents()

        assert len(agents) == 7
        agent_ids = [a["id"] for a in agents]
        assert "manus" in agent_ids
        assert "browser" in agent_ids
        assert "research" in agent_ids

    def test_is_tawiza_agent(self):
        """Test Tawiza agent detection."""
        orch = AgentOrchestrator()

        assert orch.is_tawiza_agent("tawiza-analyst") is True
        assert orch.is_tawiza_agent("tawiza-data") is True
        assert orch.is_tawiza_agent("general") is False
        assert orch.is_tawiza_agent("qwen3.5:27b") is False


class TestTaskEvent:
    """Tests for TaskEvent dataclass."""

    def test_event_creation(self):
        """Test creating a TaskEvent."""
        event = TaskEvent(type=TaskEventType.STARTED, task_id="test-123", data={"agent": "manus"})

        assert event.type == TaskEventType.STARTED
        assert event.task_id == "test-123"
        assert event.data["agent"] == "manus"
        assert event.timestamp is not None

    def test_event_to_dict(self):
        """Test TaskEvent serialization."""
        event = TaskEvent(
            type=TaskEventType.PROGRESS, task_id="test-456", data={"step": 1, "total": 3}
        )

        d = event.to_dict()
        assert d["type"] == "progress"
        assert d["task_id"] == "test-456"
        assert d["step"] == 1


class TestAgentInitialization:
    """Tests for agent initialization."""

    @pytest.mark.asyncio
    async def test_initialize_agents(self):
        """Test that initialize_agents loads agents."""
        orch = AgentOrchestrator()
        results = await orch.initialize_agents()

        # Should have results for all agent types
        assert "manus" in results
        assert "browser" in results
        assert "research" in results
        assert "coder" in results
        assert "data" in results
        assert "general" in results

        # General should always be True
        assert results["general"] is True

    @pytest.mark.asyncio
    async def test_agents_loaded(self):
        """Test that real agents are loaded."""
        orch = AgentOrchestrator()
        await orch.initialize_agents()

        # Check agents are in _real_agents
        assert "manus" in orch._real_agents or results.get("manus") is False

    @pytest.mark.asyncio
    async def test_double_initialization(self):
        """Test that double init is safe."""
        orch = AgentOrchestrator()
        results1 = await orch.initialize_agents()
        results2 = await orch.initialize_agents()

        # Second call should return existing agents (possibly subset)
        # All agents from second call should be in first call
        for key in results2.keys():
            assert key in results1


class TestTaskExecution:
    """Tests for task execution."""

    @pytest.mark.asyncio
    async def test_execute_task_yields_events(self):
        """Test that execute_task yields events."""
        orch = AgentOrchestrator()

        events = []
        async for event in orch.execute_task(
            task_id="test-exec", agent_type="general", prompt="Say hi", context={}
        ):
            events.append(event)
            # Limit for quick test
            if len(events) >= 5:
                break

        # Should have at least started event
        assert len(events) >= 1
        assert events[0].type == TaskEventType.STARTED

    @pytest.mark.asyncio
    async def test_event_types_in_execution(self):
        """Test that various event types are emitted."""
        orch = AgentOrchestrator()

        event_types = set()
        async for event in orch.execute_task(
            task_id="test-types", agent_type="general", prompt="One word", context={}
        ):
            event_types.add(event.type)

        # Should include these basic types
        assert TaskEventType.STARTED in event_types
        assert TaskEventType.COMPLETED in event_types or TaskEventType.ERROR in event_types

    @pytest.mark.asyncio
    async def test_fallback_to_ollama(self):
        """Test that unknown agents fall back to Ollama."""
        orch = AgentOrchestrator()

        events = []
        async for event in orch.execute_task(
            task_id="test-fallback",
            agent_type="general",  # No real agent for this
            prompt="Hi",
            context={},
        ):
            events.append(event)
            if len(events) >= 3:
                break

        # Should work via Ollama fallback
        assert len(events) >= 1


class TestEventCallback:
    """Tests for event callback functionality."""

    @pytest.mark.asyncio
    async def test_set_event_callback(self):
        """Test setting event callback."""
        orch = AgentOrchestrator()

        callback_events = []

        async def callback(event):
            callback_events.append(event)

        orch.set_event_callback(callback)

        # Emit an event
        event = TaskEvent(type=TaskEventType.THINKING, task_id="cb-test", data={"content": "test"})
        await orch._emit_event(event)

        assert len(callback_events) == 1
        assert callback_events[0].task_id == "cb-test"

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callback errors are handled."""
        orch = AgentOrchestrator()

        async def bad_callback(event):
            raise ValueError("Callback error")

        orch.set_event_callback(bad_callback)

        # Should not raise
        event = TaskEvent(type=TaskEventType.ERROR, task_id="err-test", data={})
        await orch._emit_event(event)  # Should handle gracefully


class TestModelSelection:
    """Tests for model selection."""

    @pytest.mark.asyncio
    async def test_get_best_model(self):
        """Test best model selection."""
        orch = AgentOrchestrator()
        model = await orch._get_best_model()

        # Should return a model name
        assert isinstance(model, str)
        assert len(model) > 0

    @pytest.mark.asyncio
    async def test_get_best_model_fallback(self):
        """Test model selection fallback."""
        orch = AgentOrchestrator()
        orch.ollama_url = "http://invalid:11434"  # Invalid URL

        model = await orch._get_best_model()

        # Should return default
        assert model == "qwen3.5:27b"
