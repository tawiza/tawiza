"""Tests for utility tools."""

import pytest

from src.cli.v2.agents.tools.utility_tools import register_utility_tools
from src.cli.v2.agents.unified.tools import ToolRegistry


class TestUtilityTools:
    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        register_utility_tools(reg)
        return reg

    @pytest.mark.asyncio
    async def test_utility_datetime(self, registry):
        result = await registry.execute("utility.datetime", {"timezone": "UTC"})
        assert result["success"] is True
        assert "datetime" in result
        assert result["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_utility_calculate_add(self, registry):
        result = await registry.execute("utility.calculate", {"expression": "2 + 3"})
        assert result["success"] is True
        assert result["result"] == 5

    @pytest.mark.asyncio
    async def test_utility_calculate_complex(self, registry):
        result = await registry.execute("utility.calculate", {"expression": "2 * 3 + 4"})
        assert result["success"] is True
        assert result["result"] == 10

    @pytest.mark.asyncio
    async def test_utility_calculate_invalid(self, registry):
        result = await registry.execute("utility.calculate", {"expression": "import os"})
        assert result["success"] is False
