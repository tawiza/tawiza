"""Tests for ManusAgent.

Tests the Manus reasoning agent with think-execute loop.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestManusAgentBasic:
    """Basic tests for ManusAgent class."""

    def test_manus_agent_imports(self):
        """Should import ManusAgent and create_manus_agent."""
        from src.infrastructure.agents.manus import ManusAgent, create_manus_agent

        assert ManusAgent is not None
        assert create_manus_agent is not None

    @pytest.mark.asyncio
    async def test_create_manus_agent(self):
        """Should create ManusAgent with correct configuration."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent(
            model="qwen3-coder:30b",
            ollama_host="http://localhost:11434",
        )

        assert agent is not None
        assert agent.model == "qwen3-coder:30b"

    @pytest.mark.asyncio
    async def test_agent_has_required_methods(self):
        """Should have all required methods."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()

        # Core methods
        assert hasattr(agent, "execute_task")
        assert hasattr(agent, "think")
        assert hasattr(agent, "reasoning_loop")
        assert hasattr(agent, "get_capabilities")

        # Task management
        assert hasattr(agent, "get_task_status")
        assert hasattr(agent, "get_task_result")
        assert hasattr(agent, "list_tasks")
        assert hasattr(agent, "cancel_task")


class TestManusAgentConfiguration:
    """Tests for ManusAgent configuration."""

    @pytest.mark.asyncio
    async def test_default_model(self):
        """Should use default model when not specified."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()

        assert agent.model is not None
        assert len(agent.model) > 0

    @pytest.mark.asyncio
    async def test_custom_ollama_host(self):
        """Should accept custom Ollama host."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent(ollama_host="http://custom:11434")

        assert agent is not None

    @pytest.mark.asyncio
    async def test_max_iterations_config(self):
        """Should accept max iterations config."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent(max_iterations=20)

        assert agent.max_iterations == 20


class TestManusAgentCapabilities:
    """Tests for ManusAgent capabilities."""

    @pytest.mark.asyncio
    async def test_get_capabilities_returns_dict(self):
        """Should return capabilities as dict."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()
        capabilities = agent.get_capabilities()

        assert isinstance(capabilities, dict)

    @pytest.mark.asyncio
    async def test_capabilities_include_info(self):
        """Should include useful info in capabilities."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()
        capabilities = agent.get_capabilities()

        # Should have some info
        assert len(capabilities) > 0


class TestManusAgentToolRegistry:
    """Tests for ManusAgent tool registry integration."""

    @pytest.mark.asyncio
    async def test_set_tool_registry(self):
        """Should allow setting tool registry."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()

        # Should have method to set tool registry
        assert hasattr(agent, "set_tool_registry")

    @pytest.mark.asyncio
    async def test_agent_has_execute_tool(self):
        """Should have _execute_tool method."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()

        assert hasattr(agent, "_execute_tool")


class TestManusAgentExecution:
    """Tests for ManusAgent task execution."""

    @pytest.mark.asyncio
    async def test_execute_task_interface(self):
        """Should have execute_task that accepts dict."""
        import inspect

        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()
        sig = inspect.signature(agent.execute_task)

        # Should accept task_config parameter
        params = list(sig.parameters.keys())
        assert len(params) >= 1

    @pytest.mark.asyncio
    async def test_execute_action_method(self):
        """Should have execute_action method."""
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent()

        assert hasattr(agent, "execute_action")
