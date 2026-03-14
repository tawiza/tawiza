"""Geolocation and mapping tools.

Uses:
- API Adresse (BAN) for French addresses - fast, no rate limit for reasonable use
- Nominatim as fallback for international addresses
"""

import asyncio
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry

# French address API - fast and free
BAN_API_URL = "https://api-adresse.data.gouv.fr"

# Nominatim fallback for international
NOMINATIM_URL = "https://nominatim.openstreetmap.org"


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def register_geo_tools(registry: ToolRegistry) -> None:
    """Register geolocation and mapping tools."""

    async def geo_locate(address: str) -> dict[str, Any]:
        """Geocode a French address to get coordinates.

        Uses the official API Adresse (BAN) - fast and reliable for France.

        Args:
            address: French address string (e.g., "10 rue de la Paix, Paris")

        Returns:
            Dict with lat, lon, formatted address, and place details
        """
        try:
            params = {
                "q": address,
                "limit": 1,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BAN_API_URL}/search", params=params)
                response.raise_for_status()
                data = response.json()

                features = data.get("features", [])
                if not features:
                    return {"success": False, "error": f"Address not found: {address}"}

                feature = features[0]
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [0, 0])

                return {
                    "success": True,
                    "query": address,
                    "lat": coords[1],
                    "lon": coords[0],
                    "formatted_address": props.get("label"),
                    "score": props.get("score"),
                    "type": props.get("type"),  # housenumber, street, municipality
                    "address_details": {
                        "numero": props.get("housenumber"),
                        "rue": props.get("street"),
                        "code_postal": props.get("postcode"),
                        "commune": props.get("city"),
                        "context": props.get("context"),  # "59, Nord, Hauts-de-France"
                    },
                }

        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"Geocoding API error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_reverse(lat: float, lon: float) -> dict[str, Any]:
        """Reverse geocode coordinates to get French address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dict with address details
        """
        try:
            params = {
                "lat": lat,
                "lon": lon,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BAN_API_URL}/reverse", params=params)
                response.raise_for_status()
                data = response.json()

                features = data.get("features", [])
                if not features:
                    return {"success": False, "error": f"No address found at {lat}, {lon}"}

                feature = features[0]
                props = feature.get("properties", {})

                return {
                    "success": True,
                    "lat": lat,
                    "lon": lon,
                    "formatted_address": props.get("label"),
                    "address_details": {
                        "numero": props.get("housenumber"),
                        "rue": props.get("street"),
                        "code_postal": props.get("postcode"),
                        "commune": props.get("city"),
                        "context": props.get("context"),
                    },
                }

        except Exception as e:
            logger.error(f"Reverse geocoding failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_distance(
        point1: dict[str, float],
        point2: dict[str, float],
    ) -> dict[str, Any]:
        """Calculate distance between two points.

        Args:
            point1: Dict with 'lat' and 'lon' keys
            point2: Dict with 'lat' and 'lon' keys

        Returns:
            Dict with distance in km
        """
        try:
            lat1 = point1.get("lat")
            lon1 = point1.get("lon")
            lat2 = point2.get("lat")
            lon2 = point2.get("lon")

            if None in [lat1, lon1, lat2, lon2]:
                return {"success": False, "error": "Both points must have 'lat' and 'lon' keys"}

            distance_km = _haversine_distance(lat1, lon1, lat2, lon2)

            return {
                "success": True,
                "point1": point1,
                "point2": point2,
                "distance_km": round(distance_km, 2),
            }

        except Exception as e:
            logger.error(f"Distance calculation failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_search_commune(
        commune: str,
        code_postal: str | None = None,
    ) -> dict[str, Any]:
        """Search for a French commune (city) and get its details.

        Args:
            commune: City name (e.g., "Lille", "Roubaix")
            code_postal: Optional postal code to disambiguate

        Returns:
            Dict with commune details including population, department, region
        """
        try:
            # Use geo.api.gouv.fr for commune data
            params = {"nom": commune, "limit": 5}
            if code_postal:
                params["codePostal"] = code_postal

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://geo.api.gouv.fr/communes",
                    params=params,
                )
                response.raise_for_status()
                communes = response.json()

                if not communes:
                    return {"success": False, "error": f"Commune not found: {commune}"}

                results = []
                for c in communes:
                    results.append(
                        {
                            "nom": c.get("nom"),
                            "code_insee": c.get("code"),
                            "code_postal": c.get("codesPostaux", [None])[0],
                            "population": c.get("population"),
                            "departement": c.get("codeDepartement"),
                            "region": c.get("codeRegion"),
                            "centre": {
                                "lat": c.get("centre", {}).get("coordinates", [0, 0])[1],
                                "lon": c.get("centre", {}).get("coordinates", [0, 0])[0],
                            }
                            if c.get("centre")
                            else None,
                        }
                    )

                return {
                    "success": True,
                    "query": commune,
                    "communes": results,
                    "count": len(results),
                }

        except Exception as e:
            logger.error(f"Commune search failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_batch_locate(addresses: list[str]) -> dict[str, Any]:
        """Geocode multiple French addresses efficiently.

        Args:
            addresses: List of address strings (max 50)

        Returns:
            Dict with results for each address
        """
        try:
            if len(addresses) > 50:
                return {"success": False, "error": "Maximum 50 addresses per batch"}

            results = []
            for addr in addresses:
                result = await geo_locate(addr)
                results.append(
                    {
                        "address": addr,
                        "success": result.get("success"),
                        "lat": result.get("lat"),
                        "lon": result.get("lon"),
                        "formatted": result.get("formatted_address"),
                        "error": result.get("error"),
                    }
                )
                # Small delay to be nice to API
                await asyncio.sleep(0.05)

            success_count = sum(1 for r in results if r["success"])

            return {
                "success": True,
                "total": len(addresses),
                "geocoded": success_count,
                "failed": len(addresses) - success_count,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Batch geocoding failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_map(
        locations: list[dict[str, Any]],
        output_path: str | None = None,
        title: str = "Carte",
        zoom_start: int = 6,
    ) -> dict[str, Any]:
        """Generate an interactive HTML map with markers.

        Args:
            locations: List of dicts with 'lat', 'lon', and optionally 'name', 'type', 'popup'
            output_path: Where to save the HTML file (default: ./outputs/maps/)
            title: Map title
            zoom_start: Initial zoom level (1-18)

        Returns:
            Dict with file path and map info
        """
        try:
            import folium
            from folium.plugins import MarkerCluster
        except ImportError:
            return {"success": False, "error": "folium not installed. Run: pip install folium"}

        try:
            if not locations:
                return {"success": False, "error": "No locations provided"}

            # Filter valid locations
            valid_locs = [loc for loc in locations if loc.get("lat") and loc.get("lon")]
            if not valid_locs:
                return {"success": False, "error": "No valid coordinates in locations"}

            # Calculate center
            lats = [loc["lat"] for loc in valid_locs]
            lons = [loc["lon"] for loc in valid_locs]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

            # Create map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=zoom_start,
                tiles="OpenStreetMap",
            )

            # Add title
            title_html = f"""
                <div style="position: fixed; top: 10px; left: 50px; z-index: 1000;
                     background-color: white; padding: 10px; border-radius: 5px;
                     box-shadow: 0 2px 5px rgba(0,0,0,0.2); font-family: Arial;">
                    <h3 style="margin: 0; color: #333;">{title}</h3>
                    <small style="color: #666;">{len(valid_locs)} acteurs</small>
                </div>
            """
            m.get_root().html.add_child(folium.Element(title_html))

            # Use marker cluster for many points (lower threshold for better UX)
            if len(valid_locs) > 15:
                marker_cluster = MarkerCluster(
                    name="Entreprises",
                    show_coverage_on_hover=True,
                    spiderfyOnMaxZoom=True,
                ).add_to(m)
                target = marker_cluster
            else:
                target = m

            # Color mapping
            color_map = {
                "startup": "blue",
                "entreprise": "green",
                "laboratoire": "purple",
                "incubateur": "orange",
                "cluster": "red",
                "association": "gray",
                "enriched": "darkgreen",
                "default": "blue",
            }

            # Add legend
            legend_html = """
            <div style="position: fixed; bottom: 20px; left: 20px; z-index: 1000;
                 background-color: white; padding: 12px 15px; border-radius: 8px;
                 box-shadow: 0 2px 10px rgba(0,0,0,0.15); font-family: Arial; font-size: 12px;">
                <b style="font-size: 13px;">Légende</b><br>
                <i class="fa fa-map-marker" style="color: green;"></i> Entreprise<br>
                <i class="fa fa-map-marker" style="color: darkgreen;"></i> Enrichie (web)<br>
                <i class="fa fa-map-marker" style="color: blue;"></i> Startup<br>
                <i class="fa fa-map-marker" style="color: purple;"></i> Laboratoire<br>
                <i class="fa fa-map-marker" style="color: orange;"></i> Incubateur
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))

            # Add markers
            for loc in valid_locs:
                name = loc.get("name", loc.get("nom", "Inconnu"))
                actor_type = loc.get("type", "default")

                # Check if enriched (has website)
                is_enriched = bool(loc.get("url") or loc.get("website"))
                if is_enriched:
                    color = "darkgreen"
                else:
                    color = loc.get("color") or color_map.get(actor_type, "blue")

                # Build popup
                popup_parts = [f"<b style='font-size: 14px;'>{name}</b>"]
                if loc.get("type") and loc.get("type") != "entreprise":
                    popup_parts.append(f"<i style='color: #666;'>{loc['type']}</i>")
                if loc.get("activite") or loc.get("libelle_activite"):
                    activite = loc.get("activite") or loc.get("libelle_activite")
                    popup_parts.append(f"<span style='color: #555;'>📋 {activite[:50]}</span>")
                if loc.get("commune") or loc.get("adresse", {}).get("commune"):
                    commune = loc.get("commune") or loc.get("adresse", {}).get("commune")
                    popup_parts.append(f"📍 {commune}")
                if loc.get("effectif"):
                    popup_parts.append(f"👥 {loc['effectif']} employés")

                # Add website link if available
                website = loc.get("url") or loc.get("website")
                if website:
                    popup_parts.append(
                        f"<a href='{website}' target='_blank' style='color: #007bff;'>🌐 Site web</a>"
                    )

                # Add description if available
                description = loc.get("description")
                if description:
                    short_desc = (
                        description[:100] + "..." if len(description) > 100 else description
                    )
                    popup_parts.append(f"<small style='color: #777;'>{short_desc}</small>")

                # Add technologies if available
                technologies = loc.get("technologies")
                if technologies and isinstance(technologies, list) and len(technologies) > 0:
                    tech_str = ", ".join(technologies[:5])  # Limit to 5
                    popup_parts.append(f"<small style='color: #0066cc;'>💻 {tech_str}</small>")

                # Add enrichment quality if available
                quality = loc.get("quality")
                if quality and quality > 0:
                    quality_pct = int(quality * 100)
                    quality_color = (
                        "#28a745"
                        if quality_pct >= 50
                        else "#ffc107"
                        if quality_pct >= 30
                        else "#dc3545"
                    )
                    popup_parts.append(
                        f"<small style='color: {quality_color};'>📊 Qualité: {quality_pct}%</small>"
                    )

                popup_html = "<br>".join(popup_parts)

                # Use different icons based on type
                icon_name = "building" if actor_type == "entreprise" else "info-sign"

                folium.Marker(
                    location=[loc["lat"], loc["lon"]],
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=name,
                    icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
                ).add_to(target)

            # Determine output path
            if not output_path:
                output_dir = Path("./outputs/maps")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_title = "".join(c if c.isalnum() else "_" for c in title)[:30]
                output_path = str(output_dir / f"{timestamp}_{safe_title}.html")

            # Save map
            m.save(output_path)
            abs_path = str(Path(output_path).absolute())

            return {
                "success": True,
                "file_path": abs_path,
                "title": title,
                "markers": len(valid_locs),
                "center": {"lat": center_lat, "lon": center_lon},
            }

        except Exception as e:
            logger.error(f"Map generation failed: {e}")
            return {"success": False, "error": str(e)}

    async def geo_find_nearby(
        center: dict[str, float],
        radius_km: float,
        locations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Find locations within a radius of a center point.

        Args:
            center: Dict with 'lat' and 'lon'
            radius_km: Search radius in kilometers
            locations: List of locations to filter

        Returns:
            Dict with nearby locations sorted by distance
        """
        try:
            center_lat = center.get("lat")
            center_lon = center.get("lon")

            if not center_lat or not center_lon:
                return {"success": False, "error": "Center must have 'lat' and 'lon'"}

            nearby = []

            for loc in locations:
                loc_lat = loc.get("lat")
                loc_lon = loc.get("lon")

                if not loc_lat or not loc_lon:
                    continue

                distance = _haversine_distance(center_lat, center_lon, loc_lat, loc_lon)

                if distance <= radius_km:
                    nearby.append(
                        {
                            **loc,
                            "distance_km": round(distance, 2),
                        }
                    )

            # Sort by distance
            nearby.sort(key=lambda x: x["distance_km"])

            return {
                "success": True,
                "center": center,
                "radius_km": radius_km,
                "found": len(nearby),
                "total_checked": len(locations),
                "nearby": nearby,
            }

        except Exception as e:
            logger.error(f"Find nearby failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["geo.locate"] = Tool(
        name="geo.locate",
        func=geo_locate,
        category=ToolCategory.GEO,
        description="Geocode French address to lat/lon. Uses API Adresse (BAN) - fast and accurate.",
    )

    registry._tools["geo.reverse"] = Tool(
        name="geo.reverse",
        func=geo_reverse,
        category=ToolCategory.GEO,
        description="Get French address from lat/lon coordinates.",
    )

    registry._tools["geo.distance"] = Tool(
        name="geo.distance",
        func=geo_distance,
        category=ToolCategory.GEO,
        description="Calculate distance in km between two points.",
    )

    registry._tools["geo.search_commune"] = Tool(
        name="geo.search_commune",
        func=geo_search_commune,
        category=ToolCategory.GEO,
        description="Search French commune/city. Returns population, department, region, coordinates.",
    )

    registry._tools["geo.batch_locate"] = Tool(
        name="geo.batch_locate",
        func=geo_batch_locate,
        category=ToolCategory.GEO,
        description="Geocode multiple French addresses (max 50).",
    )

    registry._tools["geo.map"] = Tool(
        name="geo.map",
        func=geo_map,
        category=ToolCategory.GEO,
        description="Generate interactive HTML map with markers. Auto-clusters for many points.",
    )

    registry._tools["geo.find_nearby"] = Tool(
        name="geo.find_nearby",
        func=geo_find_nearby,
        category=ToolCategory.GEO,
        description="Find locations within radius of a point. Returns sorted by distance.",
    )

    logger.debug("Registered 7 geo tools")
