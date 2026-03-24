"""TAJINE tools wrapping datasource adapters.

Provides tool wrappers for French open data sources:
- BODACC: Legal announcements (creations, modifications, closures)
- BOAMP: Public procurement opportunities
- BAN: French address geocoding
"""

from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.agents.tools.registry import (
    BaseTool,
    ToolCategory,
    ToolMetadata,
)


class BodaccSearchTool(BaseTool):
    """Search French legal announcements (BODACC).

    BODACC (Bulletin Officiel des Annonces Civiles et Commerciales)
    publishes legal announcements about company events:
    - Creations and registrations
    - Modifications (name, address, capital changes)
    - Closures and liquidations
    """

    def __init__(self):
        """Initialize BodaccSearchTool."""
        self._adapter = None

    def _get_adapter(self):
        """Lazy-load BodaccAdapter."""
        if self._adapter is None:
            from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter

            self._adapter = BodaccAdapter()
        return self._adapter

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="bodacc_search",
            description="Search French legal announcements (BODACC) - company creations, modifications, closures",
            category=ToolCategory.DATA,
            tags=["territorial", "legal", "bodacc", "companies"],
            timeout=60.0,
        )

    async def execute(
        self,
        event_type: str | None = None,
        department: str | None = None,
        siret: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        **kwargs,
    ) -> dict[str, Any]:
        """Search BODACC legal announcements.

        Args:
            event_type: Type of event (creation, modification, radiation)
            department: Department code (e.g., "34")
            siret: SIRET number
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum results

        Returns:
            Dict with success status and results
        """
        logger.info(f"BodaccSearch: dept={department}, type={event_type}")

        try:
            adapter = self._get_adapter()

            params: dict[str, Any] = {"limit": limit}
            if event_type:
                params["type_annonce"] = event_type
            if department:
                params["departement"] = department
            if siret:
                params["siret"] = siret
            if date_from:
                params["date_debut"] = date_from
            if date_to:
                params["date_fin"] = date_to

            results = await adapter.search(params)

            return {
                "success": True,
                "tool": self.metadata.name,
                "data": results,
                "count": len(results) if isinstance(results, list) else results.get("total", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"BodaccSearch failed: {e}")
            return {
                "success": False,
                "tool": self.metadata.name,
                "error": str(e),
            }


class BoampSearchTool(BaseTool):
    """Search French public procurement (BOAMP).

    BOAMP (Bulletin Officiel des Annonces de Marchés Publics)
    publishes public procurement opportunities.
    """

    def __init__(self):
        """Initialize BoampSearchTool."""
        self._adapter = None

    def _get_adapter(self):
        """Lazy-load BoampAdapter."""
        if self._adapter is None:
            from src.infrastructure.datasources.adapters.boamp import BoampAdapter

            self._adapter = BoampAdapter()
        return self._adapter

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="boamp_search",
            description="Search French public procurement opportunities (BOAMP)",
            category=ToolCategory.DATA,
            tags=["territorial", "procurement", "boamp", "public"],
            timeout=60.0,
        )

    async def execute(
        self,
        query: str | None = None,
        cpv_code: str | None = None,
        department: str | None = None,
        limit: int = 50,
        **kwargs,
    ) -> dict[str, Any]:
        """Search BOAMP procurement notices.

        Args:
            query: Search keywords
            cpv_code: CPV classification code
            department: Department code
            limit: Maximum results

        Returns:
            Dict with success status and results
        """
        logger.info(f"BoampSearch: query={query}, dept={department}")

        try:
            adapter = self._get_adapter()

            params: dict[str, Any] = {"limit": limit}
            if query:
                params["q"] = query
            if cpv_code:
                params["cpv"] = cpv_code
            if department:
                params["departement"] = department

            results = await adapter.search(params)

            return {
                "success": True,
                "tool": self.metadata.name,
                "data": results,
                "count": len(results) if isinstance(results, list) else results.get("total", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"BoampSearch failed: {e}")
            return {
                "success": False,
                "tool": self.metadata.name,
                "error": str(e),
            }


class GeocodeTool(BaseTool):
    """Geocode French addresses using BAN.

    BAN (Base Adresse Nationale) is the French national address database.
    Supports forward geocoding (address to coordinates) and reverse geocoding.
    """

    def __init__(self):
        """Initialize GeocodeTool."""
        self._adapter = None

    def _get_adapter(self):
        """Lazy-load BanAdapter."""
        if self._adapter is None:
            from src.infrastructure.datasources.adapters.ban import BanAdapter

            self._adapter = BanAdapter()
        return self._adapter

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="geocode",
            description="Geocode French addresses using BAN (Base Adresse Nationale)",
            category=ToolCategory.DATA,
            tags=["territorial", "geocoding", "ban", "address"],
            timeout=30.0,
        )

    async def execute(
        self,
        address: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Geocode an address or reverse geocode coordinates.

        Args:
            address: Address to geocode
            lat: Latitude for reverse geocoding
            lon: Longitude for reverse geocoding

        Returns:
            Dict with success status and geocoding result
        """
        logger.info(f"Geocode: address={address}, lat={lat}, lon={lon}")

        try:
            adapter = self._get_adapter()

            if address:
                result = await adapter.geocode(address)
            elif lat is not None and lon is not None:
                result = await adapter.reverse(lat, lon)
            else:
                return {
                    "success": False,
                    "tool": self.metadata.name,
                    "error": "Provide either 'address' or both 'lat' and 'lon'",
                }

            return {
                "success": True,
                "tool": self.metadata.name,
                "data": result,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Geocode failed: {e}")
            return {
                "success": False,
                "tool": self.metadata.name,
                "error": str(e),
            }


def get_datasource_tools() -> list[BaseTool]:
    """Get all datasource tools."""
    return [
        BodaccSearchTool(),
        BoampSearchTool(),
        GeocodeTool(),
    ]
