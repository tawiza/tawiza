"""Tool registry for the unified agent."""

import inspect
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union, get_args, get_origin

from loguru import logger


def _get_type_name(annotation: Any) -> str:
    """Get a string representation of a type annotation, handling Union types."""
    if annotation == inspect.Parameter.empty:
        return "any"

    # Handle Union types (including str | None syntax)
    origin = get_origin(annotation)
    if origin is Union or isinstance(annotation, types.UnionType):
        args = get_args(annotation)
        # Filter out NoneType for Optional types
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _get_type_name(non_none_args[0])
        return " | ".join(_get_type_name(a) for a in non_none_args)

    # Handle generic types like List[str], Dict[str, int]
    if origin is not None:
        return getattr(origin, "__name__", str(origin))

    # Handle simple types
    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


class ToolCategory(Enum):
    """Categories of tools available to the agent."""

    BROWSER = "browser"
    ANALYST = "analyst"
    CODER = "coder"
    FILES = "files"
    API = "api"
    ML = "ml"
    CARTO = "carto"
    UTILITY = "utility"
    # Territorial intelligence categories
    DATA = "data"          # Sirene, subventions, public data
    DOCUMENT = "document"  # PDF/HTML extraction and analysis
    GEO = "geo"            # Geolocation and mapping
    STRATEGY = "strategy"  # Network analysis, benchmarks, trends


@dataclass
class Tool:
    """A tool that the agent can use."""

    name: str
    func: Callable
    category: ToolCategory
    description: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Extract params from function signature if not provided
        if not self.params_schema:
            sig = inspect.signature(self.func)
            self.params_schema = {
                name: {
                    "type": _get_type_name(param.annotation),
                    "required": param.default == inspect.Parameter.empty,
                }
                for name, param in sig.parameters.items()
            }


class ToolRegistry:
    """Registry of tools available to the unified agent."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        category: ToolCategory,
        description: str = "",
    ) -> Callable:
        """Decorator to register a tool.

        Usage:
            @registry.register("browser.navigate", ToolCategory.BROWSER)
            async def navigate(url: str) -> dict:
                ...
        """
        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                func=func,
                category=category,
                description=description or func.__doc__ or "",
            )
            self._tools[name] = tool
            logger.debug(f"Registered tool: {name}")
            return func
        return decorator

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: ToolCategory | None = None) -> list[str]:
        """List all tool names, optionally filtered by category."""
        if category:
            return [name for name, tool in self._tools.items() if tool.category == category]
        return list(self._tools.keys())

    async def execute(self, name: str, params: dict[str, Any]) -> Any:
        """Execute a tool by name with given parameters."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        try:
            result = await tool.func(**params)
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            raise

    def get_tools_description(self) -> str:
        """Get a formatted description of all tools for the LLM."""
        lines = ["Available tools:\n"]

        # Group by category
        by_category: dict[ToolCategory, list[Tool]] = {}
        for tool in self._tools.values():
            by_category.setdefault(tool.category, []).append(tool)

        for category in ToolCategory:
            tools = by_category.get(category, [])
            if tools:
                lines.append(f"\n## {category.value.upper()}")
                for tool in tools:
                    params_str = ", ".join(
                        f"{k}: {v['type']}" for k, v in tool.params_schema.items()
                    )
                    lines.append(f"- {tool.name}({params_str}): {tool.description}")

        return "\n".join(lines)
