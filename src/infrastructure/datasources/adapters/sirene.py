"""INSEE Sirene adapter - Official French enterprise registry."""

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class SireneAdapter(BaseAdapter):
    """Adapter for INSEE Sirene API (api.insee.fr).

    API Documentation: https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee

    Note: Uses the free "Sirene - Données ouvertes" API which doesn't require authentication.
    Alternative endpoint via recherche-entreprises.api.gouv.fr for simpler access.
    """

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialise l'adapter Sirene.

        Args:
            config: Configuration de l'adapter. Si None, utilise les
                valeurs par défaut pour l'API recherche-entreprises.
        """
        if config is None:
            config = AdapterConfig(
                name="sirene",
                base_url="https://recherche-entreprises.api.gouv.fr",
                rate_limit=30,
                cache_ttl=604800,  # 7 days - enterprise data is stable
            )
        super().__init__(config)

    # NAF division to section mapping (for partial code search)
    NAF_DIVISION_TO_SECTION = {
        "62": "J",  # IT / Programming
        "63": "J",  # Information services
        "58": "J",  # Publishing
        "59": "J",  # Film/TV production
        "60": "J",  # Broadcasting
        "61": "J",  # Telecommunications
        "71": "M",  # Architecture/Engineering
        "72": "M",  # R&D
        "73": "M",  # Advertising
        "74": "M",  # Other professional
        "69": "M",  # Legal/Accounting
        "70": "M",  # Management consulting
        "41": "F",  # Construction of buildings
        "42": "F",  # Civil engineering
        "43": "F",  # Specialized construction
        "45": "G",  # Wholesale/retail trade vehicles
        "46": "G",  # Wholesale trade
        "47": "G",  # Retail trade
        "10": "C",  # Food products
        "25": "C",  # Fabricated metal products
        "26": "C",  # Computer/electronic products
        "27": "C",  # Electrical equipment
        "28": "C",  # Machinery
    }

    async def search(self, query: dict[str, Any]) -> dict[str, Any]:
        """Search enterprises in Sirene.

        Args:
            query: Search parameters
                - nom: Company name
                - siret: SIRET number
                - siren: SIREN number
                - code_postal: Postal code
                - departement: Department code
                - naf: NAF/APE code (e.g., "62.01Z")
                - activite_principale: NAF code - full (62.01Z) or partial (62)
                - section_activite_principale: NAF section letter (J, M, F, G, C...)
                - date_creation_min: Minimum creation date (YYYY-MM-DD)
                - limit / per_page: Max results (default 25, max 25)

        Returns:
            Dict with 'results' list and 'total_results' count
        """
        # API limit is 25 per page max
        per_page = query.get("per_page", query.get("limit", 25))
        params = {"per_page": min(per_page, 25)}

        # Build query string
        q_parts = []
        if nom := query.get("nom"):
            q_parts.append(nom)
        if code_postal := query.get("code_postal"):
            params["code_postal"] = code_postal
        if departement := query.get("departement"):
            params["departement"] = departement
        if naf := query.get("naf"):
            # NAF code needs dot format: 6201Z -> 62.01Z
            if len(naf) == 5 and "." not in naf:
                naf = f"{naf[:2]}.{naf[2:]}"
            params["activite_principale"] = naf
        # Handle activite_principale - can be full code or partial
        if activite := query.get("activite_principale"):
            # If it's a 2-digit division code, map to section
            if len(activite) == 2 and activite.isdigit():
                section = self.NAF_DIVISION_TO_SECTION.get(activite)
                if section:
                    params["section_activite_principale"] = section
                else:
                    # Fallback: use text search instead
                    q_parts.append(f"NAF {activite}")
            else:
                # Full NAF code (with or without dot)
                if len(activite) == 5 and "." not in activite:
                    activite = f"{activite[:2]}.{activite[2:]}"
                params["activite_principale"] = activite
        # Direct section parameter
        if section := query.get("section_activite_principale"):
            params["section_activite_principale"] = section
        # Date filter for recent creations
        if date_min := query.get("date_creation_min"):
            params["date_creation_min"] = date_min

        if q_parts:
            params["q"] = " ".join(q_parts)

        try:
            response = await self._client.get(
                f"{self.config.base_url}/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "results": [
                    self._transform_result(r)
                    for r in data.get("results", [])
                ],
                "total_results": data.get("total_results", 0),
                "page": data.get("page", 1),
                "per_page": data.get("per_page", per_page),
            }

        except httpx.HTTPError as e:
            logger.error(f"Sirene search failed: {e}")
            return {"results": [], "total_results": 0}

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get enterprise by SIRET.

        Args:
            id: SIRET (14 digits) or SIREN (9 digits)

        Returns:
            Enterprise data or None
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/search",
                params={"q": id, "per_page": 1},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if results:
                return self._transform_result(results[0])
            return None

        except httpx.HTTPError as e:
            logger.error(f"Sirene get_by_id failed: {e}")
            return None

    async def health_check(self) -> bool:
        """Check if Sirene API is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/search",
                params={"q": "test", "per_page": 1},
                timeout=30.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sirene doesn't support incremental sync."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="Sirene API doesn't support incremental sync",
        )

    def _transform_result(self, result: dict) -> dict[str, Any]:
        """Transform API result to standard format."""
        siege = result.get("siege", {})

        return {
            "source": "sirene",
            "siret": siege.get("siret"),
            "siren": result.get("siren"),
            "nom": result.get("nom_complet"),
            "nom_commercial": result.get("nom_raison_sociale"),
            "nature_juridique": result.get("nature_juridique"),
            "date_creation": result.get("date_creation"),
            "effectif": result.get("tranche_effectif_salarie"),
            "naf_code": result.get("activite_principale"),
            "naf_label": result.get("libelle_activite_principale"),
            "adresse": {
                "rue": siege.get("adresse"),
                "code_postal": siege.get("code_postal"),
                "commune": siege.get("libelle_commune"),
                "departement": siege.get("departement"),
                "region": siege.get("region"),
            },
            "geo": {
                "lat": siege.get("latitude"),
                "lon": siege.get("longitude"),
            },
            "dirigeants": result.get("dirigeants", []),
            "raw": result,
        }
