"""Tool Registry - Dynamic tool management for agents.

Provides a centralized registry for managing tools that agents can use,
enabling dynamic tool discovery, loading, and execution.
"""

import asyncio
import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Optional

from loguru import logger


class ToolCategory(StrEnum):
    """Categories of tools available to agents."""

    WEB = "web"              # Web scraping, API calls
    DATA = "data"            # Data processing, analysis
    FILE = "file"            # File operations
    CODE = "code"            # Code generation, execution
    SEARCH = "search"        # Search engines, databases
    COMMUNICATION = "comm"   # Email, notifications
    ML = "ml"                # Machine learning operations
    BROWSER = "browser"      # Browser automation
    CUSTOM = "custom"        # User-defined tools


@dataclass
class ToolMetadata:
    """Metadata describing a tool."""

    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = "system"
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = False
    rate_limit: int | None = None  # calls per minute
    timeout: float = 30.0  # seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "requires_auth": self.requires_auth,
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
        }


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""

    name: str
    type: str  # "string", "int", "float", "bool", "list", "dict"
    description: str
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None  # Allowed values


class BaseTool(ABC):
    """Base class for all tools.

    Tools are reusable capabilities that agents can invoke.
    Each tool has metadata, parameters, and an execute method.

    Example:
        >>> class WebSearchTool(BaseTool):
        ...     @property
        ...     def metadata(self):
        ...         return ToolMetadata(
        ...             name="web_search",
        ...             description="Search the web",
        ...             category=ToolCategory.SEARCH
        ...         )
        ...
        ...     async def execute(self, query: str) -> Dict:
        ...         # Perform search
        ...         return {"results": [...]}
    """

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        pass

    @property
    def parameters(self) -> list[ToolParameter]:
        """Get tool parameters from execute method signature."""
        sig = inspect.signature(self.execute)
        params = []

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            # Determine type
            type_hint = param.annotation
            if type_hint == inspect.Parameter.empty or type_hint == str:
                param_type = "string"
            elif type_hint == int:
                param_type = "int"
            elif type_hint == float:
                param_type = "float"
            elif type_hint == bool:
                param_type = "bool"
            elif type_hint in (list, list):
                param_type = "list"
            elif type_hint in (dict, dict):
                param_type = "dict"
            else:
                param_type = "any"

            params.append(ToolParameter(
                name=name,
                type=param_type,
                description=f"Parameter: {name}",
                required=param.default == inspect.Parameter.empty,
                default=None if param.default == inspect.Parameter.empty else param.default,
            ))

        return params

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result
        """
        pass

    async def validate(self, **kwargs) -> bool:
        """Validate parameters before execution.

        Override this method to add custom validation.

        Returns:
            True if valid, False otherwise
        """
        return True

    def to_function_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-style function schema for LLM tool use."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type if param.type != "any" else "string",
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class FunctionTool(BaseTool):
    """Wrapper to create a tool from a function.

    Example:
        >>> async def search_web(query: str) -> dict:
        ...     return {"results": []}
        >>>
        >>> tool = FunctionTool(
        ...     func=search_web,
        ...     name="web_search",
        ...     description="Search the web",
        ...     category=ToolCategory.SEARCH
        ... )
    """

    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        category: ToolCategory = ToolCategory.CUSTOM,
        **metadata_kwargs
    ):
        self._func = func
        self._metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            **metadata_kwargs
        )

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, **kwargs) -> Any:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self._func):
            return await self._func(**kwargs)
        else:
            return self._func(**kwargs)


class ToolRegistry:
    """Central registry for managing tools.

    Provides tool registration, discovery, and execution with:
    - Dynamic tool loading
    - Category-based filtering
    - Rate limiting support
    - Execution with timeout

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(WebSearchTool())
        >>> tool = registry.get("web_search")
        >>> result = await registry.execute("web_search", query="python")
    """

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls) -> "ToolRegistry":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: dict[str, BaseTool] = {}
            cls._instance._call_counts: dict[str, list[float]] = {}
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same name exists
        """
        name = tool.metadata.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")

        self._tools[name] = tool
        self._call_counts[name] = []
        logger.info(f"Registered tool: {name} ({tool.metadata.category.value})")

    def register_function(
        self,
        func: Callable,
        name: str,
        description: str,
        category: ToolCategory = ToolCategory.CUSTOM,
        **kwargs
    ) -> None:
        """Register a function as a tool.

        Convenience method for registering simple functions.
        """
        tool = FunctionTool(func, name, description, category, **kwargs)
        self.register(tool)

    def unregister(self, name: str) -> BaseTool | None:
        """Unregister a tool."""
        tool = self._tools.pop(name, None)
        if tool:
            self._call_counts.pop(name, None)
            logger.info(f"Unregistered tool: {name}")
        return tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(
        self,
        category: ToolCategory | None = None,
        tags: list[str] | None = None
    ) -> list[BaseTool]:
        """List tools with optional filtering.

        Args:
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of matching tools
        """
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.metadata.category == category]

        if tags:
            tools = [
                t for t in tools
                if any(tag in t.metadata.tags for tag in tags)
            ]

        return tools

    def get_schemas(
        self,
        names: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get function schemas for LLM tool use.

        Args:
            names: Specific tool names, or None for all

        Returns:
            List of OpenAI-style function schemas
        """
        if names:
            tools = [self._tools[n] for n in names if n in self._tools]
        else:
            tools = list(self._tools.values())

        return [t.to_function_schema() for t in tools]

    def _check_rate_limit(self, name: str) -> bool:
        """Check if tool is within rate limit."""
        tool = self._tools.get(name)
        if not tool or not tool.metadata.rate_limit:
            return True

        import time
        now = time.time()
        minute_ago = now - 60

        # Clean old calls
        self._call_counts[name] = [
            t for t in self._call_counts[name]
            if t > minute_ago
        ]

        return len(self._call_counts[name]) < tool.metadata.rate_limit

    async def execute(
        self,
        name: str,
        **kwargs
    ) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            RuntimeError: If rate limited or validation fails
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        # Check rate limit
        if not self._check_rate_limit(name):
            raise RuntimeError(f"Tool '{name}' is rate limited")

        # Validate
        if not await tool.validate(**kwargs):
            raise RuntimeError(f"Validation failed for tool '{name}'")

        # Track call
        import time
        self._call_counts[name].append(time.time())

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=tool.metadata.timeout
            )
            logger.debug(f"Tool executed: {name}")
            return result
        except TimeoutError:
            raise RuntimeError(f"Tool '{name}' timed out after {tool.metadata.timeout}s")

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._call_counts.clear()
        logger.info("Cleared all tools from registry")


# Global registry
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
