"""Camel AI Tools for Tawiza territorial intelligence.

Provides FunctionTool wrappers for existing Tawiza capabilities:
- Territorial: Sirene, Geo, Subventions
- Browser: OpenManus web automation
- Analysis: Report generation, data export
"""

from camel.toolkits import FunctionTool

from .analysis_tools import (
    ANALYSIS_TOOLS,
    analyze_data,
    export_csv,
    generate_report,
    get_analysis_tools,
)
from .browser_tools import (
    BROWSER_TOOLS,
    browser_click,
    browser_extract,
    browser_fill_form,
    browser_navigate,
    browser_search,
    get_browser_tools,
)
from .territorial_tools import (
    GEO_TOOLS,
    SIRENE_TOOLS,
    SUBVENTIONS_TOOLS,
    aides_search,
    geo_locate,
    geo_map,
    geo_search_commune,
    get_territorial_tools,
    sirene_get,
    sirene_search,
    subventions_by_theme,
)


def get_all_tools() -> list[FunctionTool]:
    """Get all Tawiza tools as Camel FunctionTools.

    Returns:
        List of all available FunctionTool instances
    """
    return get_territorial_tools() + get_browser_tools() + get_analysis_tools()


# Grouped exports for convenience
ALL_TOOLS = get_all_tools()

__all__ = [
    # Main getters
    "get_all_tools",
    "get_territorial_tools",
    "get_browser_tools",
    "get_analysis_tools",
    # Tool groups
    "ALL_TOOLS",
    "SIRENE_TOOLS",
    "GEO_TOOLS",
    "SUBVENTIONS_TOOLS",
    "BROWSER_TOOLS",
    "ANALYSIS_TOOLS",
    # Individual functions (for direct use)
    "sirene_search",
    "sirene_get",
    "geo_locate",
    "geo_map",
    "geo_search_commune",
    "aides_search",
    "subventions_by_theme",
    "browser_navigate",
    "browser_extract",
    "browser_fill_form",
    "browser_click",
    "browser_search",
    "generate_report",
    "export_csv",
    "analyze_data",
]
