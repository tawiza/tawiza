"""Tool implementations for the unified agent."""

from src.cli.v2.agents.tools.analyst_tools import register_analyst_tools
from src.cli.v2.agents.tools.api_tools import register_api_tools
from src.cli.v2.agents.tools.browser_tools import register_browser_tools
from src.cli.v2.agents.tools.carto_tools import register_carto_tools
from src.cli.v2.agents.tools.coder_tools import register_coder_tools
from src.cli.v2.agents.tools.document_tools import register_document_tools
from src.cli.v2.agents.tools.file_tools import register_file_tools
from src.cli.v2.agents.tools.geo_tools import register_geo_tools

# Territorial intelligence tools
from src.cli.v2.agents.tools.sirene_tools import register_sirene_tools
from src.cli.v2.agents.tools.strategy_tools import register_strategy_tools
from src.cli.v2.agents.tools.subventions_tools import register_subventions_tools
from src.cli.v2.agents.tools.utility_tools import register_utility_tools


def register_all_tools(registry):
    """Register all available tools with the registry."""
    # Core tools
    register_file_tools(registry)
    register_utility_tools(registry)
    register_browser_tools(registry)
    register_analyst_tools(registry)
    register_coder_tools(registry)
    register_api_tools(registry)
    register_carto_tools(registry)

    # Territorial intelligence tools
    register_sirene_tools(registry)
    register_document_tools(registry)
    register_geo_tools(registry)
    register_strategy_tools(registry)
    register_subventions_tools(registry)
