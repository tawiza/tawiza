"""BAN adapter - French national address database for geocoding."""

from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter


class BanAdapter(BaseAdapter):
    """Adapter for Base Adresse Nationale API.

    API Documentation: https://adresse.data.gouv.fr/api-doc/adresse

    Provides:
    - Geocoding (address -> coordinates)
    - Reverse geocoding (coordinates -> address)
    - INSEE code lookup
    """

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                name="ban",
                base_url="https://api-adresse.data.gouv.fr",
                rate_limit=50,
                cache_ttl=2592000,  # 30 days - addresses are very stable
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Geocode an address.

        Args:
            query: Search parameters
                - address: Full address string
                - postcode: Filter by postal code
                - city: Filter by city name
                - limit: Max results (default 5)

        Returns:
            List of geocoded results
        """
        params = {"limit": query.get("limit", 5)}

        if address := query.get("address"):
            params["q"] = address
        if postcode := query.get("postcode"):
            params["postcode"] = postcode
        if city := query.get("city"):
            params["city"] = city

        try:
            response = await self._client.get(
                f"{self.config.base_url}/search/",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [self._transform_feature(f) for f in data.get("features", [])]

        except httpx.HTTPError as e:
            logger.error(f"BAN search failed: {e}")
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Reverse geocode coordinates.

        Args:
            id: Coordinates as "lat,lon" string

        Returns:
            Address data or None
        """
        try:
            lat, lon = id.split(",")

            response = await self._client.get(
                f"{self.config.base_url}/reverse/",
                params={"lat": lat.strip(), "lon": lon.strip()},
            )
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            if features:
                return self._transform_feature(features[0])
            return None

        except (ValueError, httpx.HTTPError) as e:
            logger.error(f"BAN reverse geocode failed: {e}")
            return None

    async def health_check(self) -> bool:
        """Check if BAN API is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/search/",
                params={"q": "Paris", "limit": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def geocode(self, address: str) -> dict[str, Any] | None:
        """Convenience method for geocoding a single address."""
        results = await self.search({"address": address, "limit": 1})
        return results[0] if results else None

    async def reverse(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Convenience method for reverse geocoding."""
        return await self.get_by_id(f"{lat},{lon}")

    def _transform_feature(self, feature: dict) -> dict[str, Any]:
        """Transform GeoJSON feature to standard format."""
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])

        # Parse context for department and region
        context = props.get("context", "")
        context_parts = [p.strip() for p in context.split(",")]
        departement = context_parts[0] if context_parts else None
        region = context_parts[-1] if len(context_parts) > 1 else None

        return {
            "source": "ban",
            "label": props.get("label"),
            "housenumber": props.get("housenumber"),
            "street": props.get("street"),
            "postcode": props.get("postcode"),
            "city": props.get("city"),
            "commune": props.get("city"),
            "code_insee": props.get("citycode"),
            "departement": departement,
            "region": region,
            "lon": coords[0],
            "lat": coords[1],
            "score": props.get("score"),
            "type": props.get("type"),  # housenumber, street, municipality
            "raw": feature,
        }
