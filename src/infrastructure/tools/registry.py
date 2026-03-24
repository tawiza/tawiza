"""
Tool Registry for centralized tool management.

The registry provides:
- Tool registration and discovery
- Schema generation for LLM function calling
- Unified tool execution interface
- Support for both native tools and MCP tools
"""

import logging
from collections import defaultdict
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for managing and executing tools.

    Features:
    - Register native Python tools
    - Register MCP tools from external servers
    - Get OpenAI-compatible schemas for all tools
    - Execute tools by name with parameter validation
    - Category-based organization
    - Tool metadata tracking
    """

    def __init__(self):
        """Initialize empty registry."""
        self._tools: dict[str, BaseTool] = {}
        self._mcp_tools: dict[str, Any] = {}  # MCP tools stored separately
        self._categories: dict[str, list[str]] = defaultdict(list)
        self._metadata: dict[str, dict[str, Any]] = {}

    def register(
        self, tool: BaseTool, category: str = "general", metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Register a native Python tool.

        Args:
            tool: Tool instance to register
            category: Category for organization (e.g., 'code', 'browser', 'file')
            metadata: Additional metadata about the tool

        Raises:
            ValueError: If tool name conflicts with existing tool
        """
        name = tool.name

        if name in self._tools or name in self._mcp_tools:
            raise ValueError(
                f"Tool '{name}' already registered. "
                "Tool names must be unique across native and MCP tools."
            )

        self._tools[name] = tool
        self._categories[category].append(name)
        self._metadata[name] = metadata or {}

        logger.info(
            f"Registered tool '{name}' in category '{category}' (sandbox: {tool.requires_sandbox})"
        )

    def register_mcp(
        self, server_name: str, tool_name: str, tool_schema: dict[str, Any], executor_fn: Any
    ) -> None:
        """
        Register an MCP tool from an external server.

        Args:
            server_name: Name of the MCP server providing this tool
            tool_name: Unique name for the tool
            tool_schema: OpenAI-compatible schema for the tool
            executor_fn: Async function to execute the tool

        Raises:
            ValueError: If tool name conflicts with existing tool
        """
        if tool_name in self._tools or tool_name in self._mcp_tools:
            raise ValueError(
                f"Tool '{tool_name}' already registered. "
                "Tool names must be unique across native and MCP tools."
            )

        self._mcp_tools[tool_name] = {
            "server": server_name,
            "schema": tool_schema,
            "executor": executor_fn,
        }
        self._categories["mcp"].append(tool_name)

        logger.info(f"Registered MCP tool '{tool_name}' from server '{server_name}'")

    def unregister(self, tool_name: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            tool_name: Name of tool to remove

        Returns:
            True if tool was removed, False if not found
        """
        removed = False

        # Remove from native tools
        if tool_name in self._tools:
            del self._tools[tool_name]
            removed = True

        # Remove from MCP tools
        if tool_name in self._mcp_tools:
            del self._mcp_tools[tool_name]
            removed = True

        # Remove from categories
        for _category, tools in self._categories.items():
            if tool_name in tools:
                tools.remove(tool_name)

        # Remove metadata
        if tool_name in self._metadata:
            del self._metadata[tool_name]

        if removed:
            logger.info(f"Unregistered tool '{tool_name}'")
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry")

        return removed

    def get_tool(self, name: str) -> BaseTool | None:
        """
        Get a native tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool exists (native or MCP).

        Args:
            name: Tool name

        Returns:
            True if tool exists
        """
        return name in self._tools or name in self._mcp_tools

    def list_tools(self, category: str | None = None, include_mcp: bool = True) -> list[str]:
        """
        List all registered tool names.

        Args:
            category: Filter by category (None = all categories)
            include_mcp: Whether to include MCP tools

        Returns:
            List of tool names
        """
        if category:
            return self._categories.get(category, [])

        tools = list(self._tools.keys())
        if include_mcp:
            tools.extend(self._mcp_tools.keys())

        return sorted(tools)

    def get_all_schemas(
        self, category: str | None = None, include_mcp: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get OpenAI-compatible schemas for all tools.

        Args:
            category: Filter by category (None = all categories)
            include_mcp: Whether to include MCP tools

        Returns:
            List of tool schemas in OpenAI function calling format
        """
        schemas = []

        # Get tool names based on filters
        tool_names = self.list_tools(category=category, include_mcp=include_mcp)

        # Generate schemas
        for name in tool_names:
            if name in self._tools:
                schemas.append(self._tools[name].to_openai_schema())
            elif name in self._mcp_tools and include_mcp:
                schemas.append(self._mcp_tools[name]["schema"])

        return schemas

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a tool by name with given arguments.

        Args:
            tool_name: Name of tool to execute
            arguments: Parameters for the tool

        Returns:
            ToolResult containing execution outcome
        """
        # Check if tool exists
        if not self.has_tool(tool_name):
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found in registry. "
                f"Available tools: {', '.join(self.list_tools())}",
            )

        try:
            # Execute native tool
            if tool_name in self._tools:
                tool = self._tools[tool_name]

                # Validate input
                validation_error = tool.validate_input(**arguments)
                if validation_error:
                    return ToolResult(
                        success=False, error=f"Input validation failed: {validation_error}"
                    )

                # Execute
                result = await tool.execute(**arguments)
                return result

            # Execute MCP tool
            elif tool_name in self._mcp_tools:
                mcp_tool = self._mcp_tools[tool_name]
                executor = mcp_tool["executor"]

                # Execute via MCP
                result = await executor(**arguments)
                return result

        except Exception as e:
            logger.exception(f"Error executing tool '{tool_name}'")
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
                metadata={"exception_type": type(e).__name__},
            )

    def get_categories(self) -> list[str]:
        """
        Get list of all categories.

        Returns:
            List of category names
        """
        return sorted(self._categories.keys())

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get detailed information about a tool.

        Args:
            tool_name: Name of tool

        Returns:
            Dict with tool info or None if not found
        """
        if tool_name in self._tools:
            tool = self._tools[tool_name]
            return {
                "name": tool.name,
                "description": tool.description,
                "type": "native",
                "requires_sandbox": tool.requires_sandbox,
                "schema": tool.to_openai_schema(),
                "metadata": self._metadata.get(tool_name, {}),
            }
        elif tool_name in self._mcp_tools:
            mcp_tool = self._mcp_tools[tool_name]
            return {
                "name": tool_name,
                "type": "mcp",
                "server": mcp_tool["server"],
                "schema": mcp_tool["schema"],
            }
        else:
            return None

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._mcp_tools.clear()
        self._categories.clear()
        self._metadata.clear()
        logger.info("Registry cleared")

    def __len__(self) -> int:
        """Return total number of registered tools."""
        return len(self._tools) + len(self._mcp_tools)

    def __contains__(self, tool_name: str) -> bool:
        """Check if tool exists using 'in' operator."""
        return self.has_tool(tool_name)

    def __repr__(self) -> str:
        return (
            f"<ToolRegistry(native={len(self._tools)}, "
            f"mcp={len(self._mcp_tools)}, "
            f"categories={len(self._categories)})>"
        )
