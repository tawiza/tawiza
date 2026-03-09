"""Agent Tools - Dynamic tool management for agents.

This module provides a centralized registry for managing tools that agents can use,
enabling dynamic tool discovery, loading, and execution.

Main components:
- BaseTool: Abstract base class for all tools
- FunctionTool: Wrapper to create tools from functions
- ToolRegistry: Central registry for tool management
- ToolCategory: Categories for organizing tools
- ToolMetadata: Metadata describing a tool

Example:
    >>> from src.infrastructure.agents.tools import (
    ...     ToolRegistry,
    ...     FunctionTool,
    ...     ToolCategory,
    ...     get_tool_registry,
    ... )
    >>>
    >>> # Create and register a tool
    >>> async def search_web(query: str) -> dict:
    ...     return {"results": []}
    >>>
    >>> registry = get_tool_registry()
    >>> registry.register_function(
    ...     search_web,
    ...     name="web_search",
    ...     description="Search the web",
    ...     category=ToolCategory.SEARCH,
    ... )
    >>>
    >>> # Execute the tool
    >>> result = await registry.execute("web_search", query="python")
"""

from src.infrastructure.agents.tools.registry import (
    BaseTool,
    FunctionTool,
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolRegistry,
    get_tool_registry,
)

__all__ = [
    "BaseTool",
    "FunctionTool",
    "ToolCategory",
    "ToolMetadata",
    "ToolParameter",
    "ToolRegistry",
    "get_tool_registry",
]
