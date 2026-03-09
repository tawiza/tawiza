"""Cartography tools for the unified agent (EcoCartographe integration)."""

from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def register_carto_tools(registry: ToolRegistry) -> None:
    """Register cartography tools for ecosystem mapping.

    Note: These are simplified stubs for now. Full EcoCartographe integration
    will be implemented when the service is available.
    """

    async def carto_create_project(name: str, territory: str = "") -> dict[str, Any]:
        """Create a new cartography project."""
        try:
            # Will integrate with EcoCartographe service
            project_id = f"project_{name.lower().replace(' ', '_')}"
            return {
                "success": True,
                "project_id": project_id,
                "name": name,
                "territory": territory,
                "status": "created",
                "note": "Stub implementation - full EcoCartographe integration pending",
            }
        except Exception as e:
            logger.error(f"Carto create project failed: {e}")
            return {"success": False, "error": str(e)}

    async def carto_ingest(project_id: str, sources: list[str]) -> dict[str, Any]:
        """Ingest data sources into a project.

        Args:
            project_id: The project ID to ingest data into
            sources: List of data source paths or URLs (CSV, web pages, etc.)
        """
        try:
            # Will integrate with EcoCartographe service
            return {
                "success": True,
                "project_id": project_id,
                "sources_ingested": len(sources),
                "sources": sources,
                "note": "Stub implementation - full EcoCartographe integration pending",
            }
        except Exception as e:
            logger.error(f"Carto ingest failed: {e}")
            return {"success": False, "error": str(e)}

    async def carto_extract_entities(project_id: str) -> dict[str, Any]:
        """Extract entities using NLP (spaCy).

        Args:
            project_id: The project ID to extract entities from
        """
        try:
            # Will integrate with spaCy NLP
            return {
                "success": True,
                "project_id": project_id,
                "entities_count": 0,
                "entity_types": ["ORGANIZATION", "PERSON", "LOCATION", "EVENT"],
                "note": "Stub implementation - spaCy integration pending",
            }
        except Exception as e:
            logger.error(f"Carto extract entities failed: {e}")
            return {"success": False, "error": str(e)}

    async def carto_generate_map(project_id: str, output_path: str = "map.html") -> dict[str, Any]:
        """Generate an interactive map using Folium.

        Args:
            project_id: The project ID to generate map for
            output_path: Output file path for the HTML map
        """
        try:
            # Will integrate with Folium
            return {
                "success": True,
                "project_id": project_id,
                "output_path": output_path,
                "note": "Stub implementation - Folium integration pending",
            }
        except Exception as e:
            logger.error(f"Carto generate map failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["carto.create_project"] = Tool(
        name="carto.create_project",
        func=carto_create_project,
        category=ToolCategory.CARTO,
        description="Create a new ecosystem mapping project",
    )

    registry._tools["carto.ingest"] = Tool(
        name="carto.ingest",
        func=carto_ingest,
        category=ToolCategory.CARTO,
        description="Ingest data sources (CSV, web) into project",
    )

    registry._tools["carto.extract_entities"] = Tool(
        name="carto.extract_entities",
        func=carto_extract_entities,
        category=ToolCategory.CARTO,
        description="Extract entities using NLP (spaCy) - stub",
    )

    registry._tools["carto.generate_map"] = Tool(
        name="carto.generate_map",
        func=carto_generate_map,
        category=ToolCategory.CARTO,
        description="Generate interactive map (Folium) - stub",
    )

    logger.debug("Registered 4 carto tools")
