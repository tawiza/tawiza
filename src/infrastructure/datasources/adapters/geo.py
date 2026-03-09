"""API Geo adapter - French administrative divisions (communes, EPCI, departments, regions)."""

from datetime import datetime
from typing import Any

import httpx

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class GeoAdapter(BaseAdapter):
    """Adapter for API Geo (geo.api.gouv.fr).

    API Documentation: https://geo.api.gouv.fr/

    Provides free access to French administrative divisions:
    - Communes (municipalities)
    - EPCI (intercommunalités)
    - Départements
    - Régions

    No authentication required.
    """

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialize the Geo adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
        """
        if config is None:
            config = AdapterConfig(
                name="geo",
                base_url="https://geo.api.gouv.fr",
                rate_limit=100,  # Generous rate limit
                cache_ttl=86400,  # 24h - admin data is stable
            )
        super().__init__(config)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search communes, EPCI, or departments.

        Args:
            query: Search parameters
                - type: 'communes', 'epci', 'departements', 'regions'
                - nom: Name to search
                - code: INSEE code
                - codePostal: Postal code
                - codeDepartement: Department code
                - codeRegion: Region code
                - lat/lon: Coordinates for reverse geocoding
                - fields: Fields to return (default: all)
                - limit: Max results (default 25)

        Returns:
            List of administrative entities
        """
        entity_type = query.get("type", "communes")
        params = {}

        # Build search params
        if nom := query.get("nom"):
            params["nom"] = nom
        if code := query.get("code"):
            params["code"] = code
        if code_postal := query.get("codePostal"):
            params["codePostal"] = code_postal
        if code_dept := query.get("codeDepartement"):
            params["codeDepartement"] = code_dept
        if code_region := query.get("codeRegion"):
            params["codeRegion"] = code_region

        # Coordinates for reverse lookup
        if lat := query.get("lat"):
            params["lat"] = lat
        if lon := query.get("lon"):
            params["lon"] = lon

        # Fields to return
        fields = query.get("fields", "nom,code,population,departement,region,codesPostaux,centre")
        params["fields"] = fields

        # Limit
        if limit := query.get("limit"):
            params["limit"] = limit

        try:
            response = await self._client.get(
                f"{self.config.base_url}/{entity_type}",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            # Handle both list and single results
            if isinstance(data, dict):
                data = [data]

            return [self._transform_result(r, entity_type) for r in data]

        except httpx.HTTPError as e:
            self._log_error("search", e)
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get commune by INSEE code.

        Args:
            id: INSEE code (5 digits for commune, 2-3 for dept)

        Returns:
            Entity data or None
        """
        # Determine entity type from code length
        if len(id) == 5:
            entity_type = "communes"
        elif len(id) <= 3:
            entity_type = "departements"
        else:
            entity_type = "communes"

        try:
            response = await self._client.get(
                f"{self.config.base_url}/{entity_type}/{id}",
                params={"fields": "nom,code,population,departement,region,codesPostaux,centre,contour"},
            )
            response.raise_for_status()
            data = response.json()
            return self._transform_result(data, entity_type)

        except httpx.HTTPError as e:
            self._log_error("get_by_id", e)
            return None

    async def get_communes_by_department(self, code_dept: str) -> list[dict[str, Any]]:
        """Get all communes in a department.

        Args:
            code_dept: Department code (e.g., '75', '69')

        Returns:
            List of communes
        """
        return await self.search({
            "type": "communes",
            "codeDepartement": code_dept,
            "fields": "nom,code,population,codesPostaux,centre",
        })

    async def get_epci_by_department(self, code_dept: str) -> list[dict[str, Any]]:
        """Get all EPCI (intercommunalités) in a department.

        Args:
            code_dept: Department code

        Returns:
            List of EPCI
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/departements/{code_dept}/epci",
                params={"fields": "nom,code,population"},
            )
            response.raise_for_status()
            data = response.json()
            return [self._transform_result(r, "epci") for r in data]
        except httpx.HTTPError as e:
            self._log_error("get_epci_by_department", e)
            return []

    async def reverse_geocode(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Find commune from coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Commune data or None
        """
        results = await self.search({
            "type": "communes",
            "lat": lat,
            "lon": lon,
            "fields": "nom,code,population,departement,region",
        })
        return results[0] if results else None

    async def geocode(self, address: str) -> dict[str, Any] | None:
        """Geocode an address using BAN (Base Adresse Nationale).

        Args:
            address: Address string to geocode

        Returns:
            Geocoded address with coordinates or None
        """
        try:
            response = await self._client.get(
                "https://api-adresse.data.gouv.fr/search/",
                params={"q": address, "limit": 1},
            )
            response.raise_for_status()
            data = response.json()

            if features := data.get("features", []):
                feature = features[0]
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [])

                return {
                    "source": "ban",
                    "label": props.get("label"),
                    "housenumber": props.get("housenumber"),
                    "street": props.get("street"),
                    "postcode": props.get("postcode"),
                    "city": props.get("city"),
                    "citycode": props.get("citycode"),  # INSEE code
                    "context": props.get("context"),  # Dept, Region
                    "score": props.get("score"),
                    "geo": {
                        "lat": coords[1] if len(coords) > 1 else None,
                        "lon": coords[0] if len(coords) > 0 else None,
                    },
                }
            return None

        except httpx.HTTPError as e:
            self._log_error("geocode", e)
            return None

    async def get_all_departments(self) -> list[dict[str, Any]]:
        """Get all French departments.

        Returns:
            List of departments with codes and names
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/departements",
                params={"fields": "nom,code,codeRegion"},
            )
            response.raise_for_status()
            data = response.json()
            return [self._transform_result(r, "departements") for r in data]
        except httpx.HTTPError as e:
            self._log_error("get_all_departments", e)
            return []

    async def get_all_regions(self) -> list[dict[str, Any]]:
        """Get all French regions.

        Returns:
            List of regions
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/regions",
                params={"fields": "nom,code"},
            )
            response.raise_for_status()
            data = response.json()
            return [self._transform_result(r, "regions") for r in data]
        except httpx.HTTPError as e:
            self._log_error("get_all_regions", e)
            return []

    async def health_check(self) -> bool:
        """Check if API Geo is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/communes",
                params={"nom": "Paris", "limit": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """API Geo doesn't support incremental sync."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="API Geo doesn't support incremental sync",
        )

    def _transform_result(self, result: dict, entity_type: str) -> dict[str, Any]:
        """Transform API result to standard format."""
        base = {
            "source": "geo",
            "type": entity_type,
            "code": result.get("code"),
            "nom": result.get("nom"),
        }

        # Add population if available
        if "population" in result:
            base["population"] = result["population"]

        # Add postal codes for communes
        if codes_postaux := result.get("codesPostaux"):
            base["codes_postaux"] = codes_postaux

        # Add geographic center
        if centre := result.get("centre"):
            if isinstance(centre, dict) and "coordinates" in centre:
                base["geo"] = {
                    "lat": centre["coordinates"][1],
                    "lon": centre["coordinates"][0],
                }

        # Add contour if requested
        if contour := result.get("contour"):
            base["contour"] = contour

        # Add department/region info
        if dept := result.get("departement"):
            base["departement"] = dept if isinstance(dept, dict) else {"code": dept}
        if region := result.get("region"):
            base["region"] = region if isinstance(region, dict) else {"code": region}
        if code_region := result.get("codeRegion"):
            base["code_region"] = code_region

        base["raw"] = result
        return base
