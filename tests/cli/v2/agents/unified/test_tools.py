"""Tests for tool registry."""

import pytest

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


class TestToolRegistry:
    def test_register_tool(self):
        registry = ToolRegistry()

        @registry.register("test.echo", category=ToolCategory.UTILITY)
        async def echo(message: str) -> str:
            return message

        assert "test.echo" in registry.list_tools()

    def test_get_tool(self):
        registry = ToolRegistry()

        @registry.register("test.hello", category=ToolCategory.UTILITY)
        async def hello() -> str:
            return "Hello"

        tool = registry.get("test.hello")
        assert tool is not None
        assert tool.name == "test.hello"

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        registry = ToolRegistry()

        @registry.register("test.add", category=ToolCategory.UTILITY)
        async def add(a: int, b: int) -> int:
            return a + b

        result = await registry.execute("test.add", {"a": 2, "b": 3})
        assert result == 5

    def test_list_tools_by_category(self):
        registry = ToolRegistry()

        @registry.register("browser.nav", category=ToolCategory.BROWSER)
        async def nav():
            pass

        @registry.register("analyst.stats", category=ToolCategory.ANALYST)
        async def stats():
            pass

        browser_tools = registry.list_tools(category=ToolCategory.BROWSER)
        assert "browser.nav" in browser_tools
        assert "analyst.stats" not in browser_tools

    def test_get_tools_description(self):
        registry = ToolRegistry()

        @registry.register("test.demo", category=ToolCategory.UTILITY, description="A demo tool")
        async def demo():
            pass

        desc = registry.get_tools_description()
        assert "test.demo" in desc
        assert "A demo tool" in desc
