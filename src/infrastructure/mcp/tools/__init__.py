"""MCP Tools for Tawiza."""

from .browser import register_browser_tools
from .dashboard import register_dashboard_tools
from .granular import register_granular_tools
from .high_level import register_high_level_tools
from .web_search import register_web_search_tools

__all__ = [
    "register_high_level_tools",
    "register_granular_tools",
    "register_browser_tools",
    "register_dashboard_tools",
    "register_web_search_tools",
]
