"""Manus Agent - OpenManus-inspired reasoning agent.

This package provides the ManusAgent implementation, inspired by OpenManus,
with a think-execute reasoning loop and context enrichment capabilities.

The Manus Agent is designed for:
- Browser automation (Playwright)
- Python code execution (sandboxed)
- Bash execution (sandboxed)
- MCP tool integration
- File operations

Key Features:
- Reasoning loop with context enrichment based on tool usage
- Support for tool collection (integrated with ToolRegistry)
- Streaming progress updates
- Proper error handling and logging
"""

from .manus_agent import AgentAction, AgentContext, ManusAgent, create_manus_agent

__all__ = [
    "ManusAgent",
    "AgentContext",
    "AgentAction",
    "create_manus_agent",
]
