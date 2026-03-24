"""TAJINE Territorial Intelligence Tools.

Provides specialized tools for territorial economic intelligence:
- Data collection (SIRENE, INSEE, company databases)
- Veille (monitoring) and signal detection
- Geographic and sectoral analysis
- Browser automation with screenshot streaming
"""

from src.infrastructure.agents.tajine.tools.browser_tools import (
    BrowserActionTool,
    WebScrapeTool,
    get_browser_tools,
)
from src.infrastructure.agents.tajine.tools.datasource_tools import (
    BoampSearchTool,
    BodaccSearchTool,
    GeocodeTool,
    get_datasource_tools,
)
from src.infrastructure.agents.tajine.tools.territorial import (
    DataCollectTool,
    SireneQueryTool,
    TerritorialAnalysisTool,
    TerritorialTools,
    VeilleScanTool,
    register_territorial_tools,
)
from src.infrastructure.agents.tools.registry import BaseTool


def get_tajine_tools() -> list[BaseTool]:
    """Get all TAJINE tools (datasource + territorial + browser).

    Returns:
        List of all available TAJINE tools
    """
    tools: list[BaseTool] = []

    # Datasource tools (BODACC, BOAMP, BAN)
    tools.extend(get_datasource_tools())

    # Territorial tools (SIRENE, analysis, veille)
    tools.extend(
        [
            DataCollectTool(),
            VeilleScanTool(),
            SireneQueryTool(),
            TerritorialAnalysisTool(),
        ]
    )

    # Browser automation tools
    tools.extend(get_browser_tools())

    return tools


def get_tool_by_name(name: str) -> BaseTool | None:
    """Get a specific tool by name.

    Args:
        name: Tool name to find

    Returns:
        Tool instance or None if not found
    """
    for tool in get_tajine_tools():
        if tool.metadata.name == name:
            return tool
    return None


__all__ = [
    # Functions
    "get_tajine_tools",
    "get_tool_by_name",
    "get_datasource_tools",
    "get_browser_tools",
    # Classes - Territorial
    "TerritorialTools",
    "register_territorial_tools",
    "DataCollectTool",
    "VeilleScanTool",
    "SireneQueryTool",
    "TerritorialAnalysisTool",
    # Classes - Datasources
    "BodaccSearchTool",
    "BoampSearchTool",
    "GeocodeTool",
    # Classes - Browser
    "BrowserActionTool",
    "WebScrapeTool",
]
