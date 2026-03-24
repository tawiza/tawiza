"""Tests for Tool Registry.

Tests the unified tool registry that manages all agent tools.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.tools.agent_tools import (
    AgentTool,
    AgentToolFactory,
    create_unified_registry,
)
from src.infrastructure.tools.base import ToolResult


class MockAgent:
    """Mock agent for testing."""

    async def execute_task(self, task_config):
        return {"success": True, "result": "done"}


class MockAgentFail:
    """Mock agent that fails."""

    async def execute_task(self, task_config):
        raise Exception("Agent failed")


class TestAgentTool:
    """Tests for AgentTool class."""

    def test_init_basic(self):
        """Should initialize with required parameters."""
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="test_tool",
            tool_description="A test tool",
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool._agent_class == MockAgent

    def test_init_with_config(self):
        """Should accept agent config."""
        config = {"timeout": 30}
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="test_tool",
            tool_description="Test",
            agent_config=config,
        )

        assert tool._agent_config == config

    def test_init_with_custom_schema(self):
        """Should accept custom parameters schema."""
        schema = {"type": "object", "properties": {"query": {"type": "string"}}}
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="search_tool",
            tool_description="Search tool",
            custom_parameters_schema=schema,
        )

        assert tool.parameters_schema == schema

    def test_default_parameters_schema(self):
        """Should have default schema with task and context."""
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="test",
            tool_description="Test",
        )

        schema = tool.parameters_schema
        assert "properties" in schema
        assert "task" in schema["properties"]
        assert "context" in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Should execute agent and return success result."""
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="test_tool",
            tool_description="Test",
        )

        result = await tool.execute(task="test task")

        assert result.success is True
        assert result.output == {"success": True, "result": "done"}
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        """Should pass context to agent."""

        class ContextAgent:
            async def execute_task(self, task_config):
                return {"received_context": task_config.get("context")}

        tool = AgentTool(
            agent_class=ContextAgent,
            tool_name="context_tool",
            tool_description="Test",
        )

        result = await tool.execute(task="test", context={"key": "value"})

        assert result.success is True
        assert result.output["received_context"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """Should catch and return exceptions as errors."""
        tool = AgentTool(
            agent_class=MockAgentFail,
            tool_name="fail_tool",
            tool_description="Test",
        )

        result = await tool.execute(task="test")

        assert result.success is False
        assert "Agent failed" in result.error

    def test_lazy_agent_creation(self):
        """Should create agent instance lazily."""
        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="lazy_tool",
            tool_description="Test",
        )

        # Agent not created yet
        assert tool._agent_instance is None

        # Get agent creates instance
        agent = tool._get_agent()
        assert agent is not None
        assert tool._agent_instance is not None

        # Same instance returned
        agent2 = tool._get_agent()
        assert agent is agent2


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self):
        """Should create success result."""
        result = ToolResult(
            success=True,
            output={"key": "value"},
            execution_time_ms=150,
        )

        assert result.success is True
        assert result.output == {"key": "value"}
        assert result.error is None
        assert result.execution_time_ms == 150

    def test_failure_result(self):
        """Should create failure result with error."""
        result = ToolResult(
            success=False,
            error="Something went wrong",
            execution_time_ms=50,
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Something went wrong"

    def test_result_with_metadata(self):
        """Should store metadata."""
        result = ToolResult(
            success=True,
            output="data",
            metadata={"agent_class": "TestAgent"},
            execution_time_ms=100,
        )

        assert result.metadata == {"agent_class": "TestAgent"}


class TestAgentToolFactory:
    """Tests for AgentToolFactory."""

    def test_init(self):
        """Should initialize with registry."""
        factory = AgentToolFactory()

        assert factory.registry is not None

    def test_register_tool(self):
        """Should register a tool via factory."""
        factory = AgentToolFactory()

        tool = AgentTool(
            agent_class=MockAgent,
            tool_name="test_tool",
            tool_description="Test",
        )

        factory.registry.register(tool, category="test")

        tools = factory.registry.list_tools()
        assert "test_tool" in tools

    def test_register_advanced_agents_method_exists(self):
        """Should have register_advanced_agents method."""
        factory = AgentToolFactory()
        assert hasattr(factory, "register_advanced_agents")


class TestCreateUnifiedRegistry:
    """Tests for create_unified_registry factory function."""

    @patch("src.infrastructure.tools.agent_tools.AgentToolFactory")
    def test_creates_registry(self, mock_factory_class):
        """Should create and return a registry."""
        mock_factory = MagicMock()
        mock_factory_class.return_value = mock_factory
        mock_factory.register_advanced_agents.return_value = ["agent1", "agent2"]
        mock_factory.register_camel_agents.return_value = ["camel1"]
        mock_factory._registry = MagicMock()

        registry = create_unified_registry(include_advanced=True, include_camel=True)

        mock_factory.register_advanced_agents.assert_called_once()
        mock_factory.register_camel_agents.assert_called_once()

    @patch("src.infrastructure.tools.agent_tools.AgentToolFactory")
    def test_excludes_advanced_when_disabled(self, mock_factory_class):
        """Should not register advanced agents when disabled."""
        mock_factory = MagicMock()
        mock_factory_class.return_value = mock_factory
        mock_factory._registry = MagicMock()

        create_unified_registry(include_advanced=False, include_camel=True)

        mock_factory.register_advanced_agents.assert_not_called()
        mock_factory.register_camel_agents.assert_called_once()

    @patch("src.infrastructure.tools.agent_tools.AgentToolFactory")
    def test_excludes_camel_when_disabled(self, mock_factory_class):
        """Should not register CAMEL agents when disabled."""
        mock_factory = MagicMock()
        mock_factory_class.return_value = mock_factory
        mock_factory._registry = MagicMock()

        create_unified_registry(include_advanced=True, include_camel=False)

        mock_factory.register_advanced_agents.assert_called_once()
        mock_factory.register_camel_agents.assert_not_called()
