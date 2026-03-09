"""
Tool system for Tawiza Agents v2.

This package provides:
- BaseTool: Abstract base class for all tools
- ToolResult: Standardized result container
- ToolRegistry: Central registry for tool discovery and execution
- AgentTool: Wrapper to expose agents as tools
- AgentToolFactory: Factory for registering multiple agents
- create_unified_registry: Create a fully-configured registry
"""

from .agent_tools import AgentTool, AgentToolFactory, create_unified_registry
from .base import BaseTool, ToolResult
from .registry import ToolRegistry

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    # Agent tools
    "AgentTool",
    "AgentToolFactory",
    "create_unified_registry",
]
