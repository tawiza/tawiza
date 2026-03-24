"""Tests for TAJINE Tool Registry integration.

Tests the integration of ToolRegistry with TAJINEAgent for
territorial intelligence operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTerritorialToolsImports:
    """Test territorial tools can be imported."""

    def test_import_territorial_tools(self):
        """Test TerritorialTools can be imported."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        assert TerritorialTools is not None

    def test_import_register_territorial_tools(self):
        """Test registration function can be imported."""
        from src.infrastructure.agents.tajine.tools import register_territorial_tools

        assert register_territorial_tools is not None


class TestTerritorialToolsCreation:
    """Test territorial tools creation."""

    def test_create_data_collect_tool(self):
        """Test data_collect tool can be created."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        tool = tools.get_tool("data_collect")

        assert tool is not None
        assert tool.metadata.name == "data_collect"

    def test_create_veille_scan_tool(self):
        """Test veille_scan tool can be created."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        tool = tools.get_tool("veille_scan")

        assert tool is not None
        assert tool.metadata.name == "veille_scan"

    def test_create_sirene_query_tool(self):
        """Test sirene_query tool can be created."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        tool = tools.get_tool("sirene_query")

        assert tool is not None
        assert tool.metadata.name == "sirene_query"


class TestTerritorialToolExecution:
    """Test territorial tool execution."""

    @pytest.mark.asyncio
    async def test_data_collect_returns_companies(self):
        """Test data_collect returns company data."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()

        result = await tools.execute("data_collect", territory="34", sector="tech")

        assert "companies" in result or "count" in result
        assert "source" in result

    @pytest.mark.asyncio
    async def test_veille_scan_returns_signals(self):
        """Test veille_scan returns signals."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()

        result = await tools.execute("veille_scan", keywords=["startup", "tech"])

        assert "signals" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_sirene_query_returns_establishments(self):
        """Test sirene_query returns establishment data."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()

        result = await tools.execute("sirene_query", siren="123456789")

        assert "etablissements" in result or "error" in result


class TestToolRegistryIntegration:
    """Test integration with global ToolRegistry."""

    def test_register_territorial_tools(self):
        """Test territorial tools can be registered globally."""
        from src.infrastructure.agents.tajine.tools import register_territorial_tools
        from src.infrastructure.agents.tools import get_tool_registry

        # Clear registry first
        registry = get_tool_registry()
        initial_count = len(registry.list_tools())

        # Register territorial tools
        register_territorial_tools(registry)

        # Should have more tools now
        new_count = len(registry.list_tools())
        assert new_count > initial_count

    def test_execute_via_registry(self):
        """Test executing territorial tool via registry."""
        from src.infrastructure.agents.tajine.tools import register_territorial_tools
        from src.infrastructure.agents.tools import get_tool_registry

        registry = get_tool_registry()

        # Ensure tools are registered
        if not registry.get("data_collect"):
            register_territorial_tools(registry)

        # Tool should be available
        tool = registry.get("data_collect")
        assert tool is not None


class TestTAJINEAgentToolIntegration:
    """Test TAJINEAgent integration with tools."""

    def test_agent_has_tool_registry(self):
        """Test TAJINEAgent has tool_registry property."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert hasattr(agent, "tool_registry")
        assert agent.tool_registry is not None

    @pytest.mark.asyncio
    async def test_delegate_uses_tools_when_manus_unavailable(self):
        """Test delegate falls back to tool execution."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Force ManusAgent to be unavailable
        with patch.object(agent, "_create_manus_agent", new_callable=AsyncMock, return_value=None):
            result = await agent.delegate(
                {"tool": "data_collect", "params": {"territory": "34", "sector": "tech"}}
            )

            # Should execute via tool registry fallback
            assert result["status"] == "completed"
            assert "result" in result

    @pytest.mark.asyncio
    async def test_delegate_executes_known_tool(self):
        """Test delegate can execute registered tools."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        with patch.object(agent, "_create_manus_agent", new_callable=AsyncMock, return_value=None):
            result = await agent.delegate(
                {"tool": "sirene_query", "params": {"siren": "123456789"}}
            )

            assert result["success"] is True
            assert result["tool"] == "sirene_query"

    @pytest.mark.asyncio
    async def test_delegate_handles_unknown_tool(self):
        """Test delegate handles unknown tool gracefully."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        with patch.object(agent, "_create_manus_agent", new_callable=AsyncMock, return_value=None):
            result = await agent.delegate({"tool": "nonexistent_tool", "params": {}})

            # Should still return a result (fallback stub)
            assert "status" in result


class TestToolSchemas:
    """Test tool schemas for LLM integration."""

    def test_tools_have_function_schemas(self):
        """Test tools can generate OpenAI-style function schemas."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        schemas = tools.get_schemas()

        assert len(schemas) > 0

        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]

    def test_schema_has_parameters(self):
        """Test tool schemas include parameter definitions."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        schemas = tools.get_schemas()

        data_collect_schema = next(
            (s for s in schemas if s["function"]["name"] == "data_collect"), None
        )

        assert data_collect_schema is not None
        assert "parameters" in data_collect_schema["function"]


class TestToolCategories:
    """Test tool categorization."""

    def test_territorial_tools_have_categories(self):
        """Test each tool has a category."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools
        from src.infrastructure.agents.tools import ToolCategory

        tools = TerritorialTools()

        for tool in tools.list_tools():
            assert tool.metadata.category is not None
            assert isinstance(tool.metadata.category, ToolCategory)

    def test_can_filter_by_category(self):
        """Test tools can be filtered by category."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools
        from src.infrastructure.agents.tools import ToolCategory

        tools = TerritorialTools()

        data_tools = tools.list_tools(category=ToolCategory.DATA)
        assert len(data_tools) >= 1
