"""Tests for AgentRegistry.

Tests the centralized agent management functionality including
registration, discovery, lifecycle management, and health monitoring.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.ports.agent_ports import IAgent
from src.infrastructure.agents.registry import AgentRegistry, get_agent_registry


class MockAgent(IAgent):
    """Mock agent for testing."""

    def __init__(self, name: str, agent_type: str = "test"):
        self._name = name
        self._agent_type = agent_type
        self._initialized = False
        self._healthy = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return self._agent_type

    async def initialize(self) -> None:
        self._initialized = True

    async def health_check(self) -> bool:
        return self._healthy

    async def shutdown(self) -> None:
        self._initialized = False


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def setup_method(self):
        """Reset registry before each test."""
        # Clear singleton state
        AgentRegistry._instance = None

    def test_singleton_pattern(self):
        """Registry should be a singleton."""
        registry1 = AgentRegistry()
        registry2 = AgentRegistry()
        assert registry1 is registry2

    def test_get_agent_registry_function(self):
        """get_agent_registry should return singleton."""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()
        assert registry1 is registry2

    def test_register_agent(self):
        """Should register an agent successfully."""
        registry = AgentRegistry()
        agent = MockAgent("test-agent")

        registry.register(agent)

        assert "test-agent" in registry.list_names()
        assert registry.get("test-agent") is agent

    def test_register_duplicate_raises(self):
        """Should raise error when registering duplicate name."""
        registry = AgentRegistry()
        agent1 = MockAgent("duplicate")
        agent2 = MockAgent("duplicate")

        registry.register(agent1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(agent2)

    def test_unregister_agent(self):
        """Should unregister an agent."""
        registry = AgentRegistry()
        agent = MockAgent("to-remove")
        registry.register(agent)

        removed = registry.unregister("to-remove")

        assert removed is agent
        assert "to-remove" not in registry.list_names()

    def test_unregister_nonexistent_returns_none(self):
        """Unregistering nonexistent agent should return None."""
        registry = AgentRegistry()

        result = registry.unregister("nonexistent")

        assert result is None

    def test_get_agent(self):
        """Should retrieve agent by name."""
        registry = AgentRegistry()
        agent = MockAgent("my-agent")
        registry.register(agent)

        retrieved = registry.get("my-agent")

        assert retrieved is agent

    def test_get_nonexistent_returns_none(self):
        """Getting nonexistent agent should return None."""
        registry = AgentRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_get_by_type(self):
        """Should find agents by type."""
        registry = AgentRegistry()
        agent1 = MockAgent("web-1", "web")
        agent2 = MockAgent("web-2", "web")
        agent3 = MockAgent("ml-1", "ml")

        registry.register(agent1)
        registry.register(agent2)
        registry.register(agent3)

        web_agents = registry.get_by_type("web")

        assert len(web_agents) == 2
        assert agent1 in web_agents
        assert agent2 in web_agents
        assert agent3 not in web_agents

    def test_list_names(self):
        """Should list all agent names."""
        registry = AgentRegistry()
        registry.register(MockAgent("a"))
        registry.register(MockAgent("b"))
        registry.register(MockAgent("c"))

        names = registry.list_names()

        assert set(names) == {"a", "b", "c"}

    def test_list_types(self):
        """Should list unique agent types."""
        registry = AgentRegistry()
        registry.register(MockAgent("a", "web"))
        registry.register(MockAgent("b", "web"))
        registry.register(MockAgent("c", "ml"))

        types = registry.list_types()

        assert set(types) == {"web", "ml"}

    def test_agents_property_returns_copy(self):
        """agents property should return a copy."""
        registry = AgentRegistry()
        agent = MockAgent("test")
        registry.register(agent)

        agents = registry.agents
        agents["new"] = MockAgent("new")

        assert "new" not in registry.list_names()

    def test_clear(self):
        """Should clear all agents."""
        registry = AgentRegistry()
        registry.register(MockAgent("a"))
        registry.register(MockAgent("b"))

        registry.clear()

        assert len(registry.list_names()) == 0


class TestAgentRegistryAsync:
    """Async tests for AgentRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        AgentRegistry._instance = None

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        """Should initialize all registered agents."""
        registry = AgentRegistry()
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        registry.register(agent1)
        registry.register(agent2)

        results = await registry.initialize_all()

        assert results == {"agent1": True, "agent2": True}
        assert agent1._initialized
        assert agent2._initialized

    @pytest.mark.asyncio
    async def test_initialize_all_handles_failure(self):
        """Should handle initialization failures gracefully."""
        registry = AgentRegistry()
        agent1 = MockAgent("good")
        agent2 = MockAgent("bad")
        agent2.initialize = AsyncMock(side_effect=Exception("Init failed"))
        registry.register(agent1)
        registry.register(agent2)

        results = await registry.initialize_all()

        assert results["good"] is True
        assert results["bad"] is False

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """Should shutdown all registered agents."""
        registry = AgentRegistry()
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")
        agent1._initialized = True
        agent2._initialized = True
        registry.register(agent1)
        registry.register(agent2)

        results = await registry.shutdown_all()

        assert results == {"agent1": True, "agent2": True}
        assert not agent1._initialized
        assert not agent2._initialized

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Should check health of all agents."""
        registry = AgentRegistry()
        healthy = MockAgent("healthy")
        unhealthy = MockAgent("unhealthy")
        unhealthy._healthy = False
        registry.register(healthy)
        registry.register(unhealthy)

        results = await registry.health_check_all()

        assert results["healthy"] is True
        assert results["unhealthy"] is False

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Should return comprehensive status."""
        registry = AgentRegistry()
        agent1 = MockAgent("web-agent", "web")
        agent2 = MockAgent("ml-agent", "ml")
        agent2._healthy = False
        registry.register(agent1)
        registry.register(agent2)

        status = await registry.get_status()

        assert status["total_agents"] == 2
        assert status["healthy_agents"] == 1
        assert status["unhealthy_agents"] == 1
        assert "web-agent" in status["agents"]
        assert status["agents"]["web-agent"]["type"] == "web"
        assert status["agents"]["web-agent"]["healthy"] is True
        assert status["agents"]["ml-agent"]["healthy"] is False
