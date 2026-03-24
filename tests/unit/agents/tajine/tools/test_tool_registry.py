"""Tests for TAJINE tool registry."""

import pytest


class TestTajineToolRegistry:
    """Test TAJINE tool registry functions."""

    def test_get_tajine_tools_returns_all(self):
        """Should return all TAJINE tools."""
        from src.infrastructure.agents.tajine.tools import get_tajine_tools

        tools = get_tajine_tools()

        # Should have datasource tools (3) + territorial tools (4) = 7
        assert len(tools) >= 7

        tool_names = [t.metadata.name for t in tools]
        # Datasource tools
        assert "bodacc_search" in tool_names
        assert "boamp_search" in tool_names
        assert "geocode" in tool_names
        # Territorial tools
        assert "data_collect" in tool_names
        assert "sirene_query" in tool_names

    def test_get_tool_by_name_found(self):
        """Should return tool when name matches."""
        from src.infrastructure.agents.tajine.tools import get_tool_by_name

        tool = get_tool_by_name("bodacc_search")

        assert tool is not None
        assert tool.metadata.name == "bodacc_search"

    def test_get_tool_by_name_not_found(self):
        """Should return None for unknown tool."""
        from src.infrastructure.agents.tajine.tools import get_tool_by_name

        tool = get_tool_by_name("nonexistent_tool")

        assert tool is None

    def test_all_tools_have_metadata(self):
        """All tools should have valid metadata."""
        from src.infrastructure.agents.tajine.tools import get_tajine_tools

        tools = get_tajine_tools()

        for tool in tools:
            assert hasattr(tool, "metadata")
            assert tool.metadata.name is not None
            assert tool.metadata.description is not None
            assert tool.metadata.category is not None
