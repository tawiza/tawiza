"""BOAMP adapter - French public procurement announcements."""

from datetime import date, datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class BoampAdapter(BaseAdapter):
    """Adapter for BOAMP (Bulletin Officiel des Annonces de Marchés Publics).

    API Documentation: https://boamp-datadila.opendatasoft.com/api/v2/console

    Data includes:
    - Appels d'offres (calls for tenders)
    - Avis d'attribution (award notices)
    - Avis de marché (contract notices)
    - Rectificatifs (corrections)
    """

    # Type mapping for market notices (API v2.1 field values)
    TYPE_MAPPING = {
        "appel_offre": "APPEL_OFFRE",
        "attribution": "ATTRIBUTION",
        "marche": "MAPA",
        "rectificatif": "RECTIFICATIF",
        # Legacy codes (kept for backward compatibility)
        "aocm": "APPEL_OFFRE",
        "attr": "ATTRIBUTION",
    }

    TYPE_LABELS = {
        "APPEL_OFFRE": "appel_offre",
        "ATTRIBUTION": "attribution",
        "MAPA": "marche",
        "RECTIFICATIF": "rectificatif",
        "AAPC": "avis_appel",
        "JOUE": "journal_ue",
        # Legacy codes
        "AOCM": "appel_offre",
        "ATTR": "attribution",
        "RECT": "rectificatif",
    }

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                name="boamp",
                base_url="https://boamp-datadila.opendatasoft.com/api/explore/v2.1",
                rate_limit=30,
                cache_ttl=43200,  # 12h - updated twice daily
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search BOAMP announcements.

        Args:
            query: Search parameters
                - keywords: Search in title/description
                - siret: Buyer SIRET
                - type: Notice type (appel_offre, attribution, marche)
                - date_from: Start date (YYYY-MM-DD)
                - date_to: End date (YYYY-MM-DD)
                - departement: Department code (e.g., "59")
                - cpv: CPV code (product/service classification)
                - limit: Max results (default 100)

        Returns:
            List of BOAMP announcements
        """
        filters = []

        if keywords := query.get("keywords"):
            # Search in object (title) and description
            filters.append(
                f'(objet like "%{keywords}%" OR descripteur_libelle like "%{keywords}%")'
            )

        if acheteur := query.get("acheteur"):
            filters.append(f'nomacheteur like "%{acheteur}%"')

        if notice_type := query.get("type"):
            if mapped := self.TYPE_MAPPING.get(notice_type):
                filters.append(f'nature="{mapped}"')

        if date_from := query.get("date_from"):
            filters.append(f'dateparution>="{date_from}"')

        if date_to := query.get("date_to"):
            filters.append(f'dateparution<="{date_to}"')

        if dept := query.get("departement"):
            # code_departement is an array field, use 'like' for matching
            filters.append(f'code_departement like "{dept}"')

        if cpv := query.get("cpv"):
            filters.append(f'descripteur_code like "{cpv}%"')

        params = {
            "limit": query.get("limit", 100),
            "order_by": "dateparution desc",
        }

        if filters:
            params["where"] = " AND ".join(filters)

        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/boamp/records",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [self._transform_record(r) for r in data.get("results", [])]

        except httpx.HTTPError as e:
            logger.error(f"BOAMP search failed: {e}")
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get a specific announcement by idweb.

        Args:
            id: BOAMP announcement ID (idweb)

        Returns:
            Announcement details or None
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/boamp/records",
                params={"where": f'idweb="{id}"', "limit": 1},
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            return self._transform_record(results[0]) if results else None
        except httpx.HTTPError as e:
            logger.error(f"BOAMP get_by_id failed: {e}")
            return None

    async def health_check(self) -> bool:
        """Check if BOAMP API is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/boamp",
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync recent BOAMP announcements.

        Args:
            since: Sync announcements published after this date

        Returns:
            Sync status with count of new records
        """
        date_from = (
            since.strftime("%Y-%m-%d")
            if since
            else (date.today().replace(day=1).strftime("%Y-%m-%d"))
        )

        try:
            results = await self.search(
                {
                    "date_from": date_from,
                    "limit": 1000,
                }
            )

            return SyncStatus(
                adapter_name=self.name,
                last_sync=datetime.utcnow(),
                records_synced=len(results),
                status="success",
            )
        except Exception as e:
            return SyncStatus(
                adapter_name=self.name,
                last_sync=None,
                records_synced=0,
                status="failed",
                error=str(e),
            )

    def _transform_record(self, record: dict) -> dict[str, Any]:
        """Transform BOAMP record to standard format."""
        # code_departement is an array, extract first value
        depts = record.get("code_departement", [])
        dept_code = depts[0] if depts else None

        return {
            "source": "boamp",
            "id": record.get("idweb"),
            "reference": record.get("id"),
            "nom_acheteur": record.get("nomacheteur"),
            "titulaire": record.get("titulaire"),
            "objet": record.get("objet"),
            "type": self.TYPE_LABELS.get(record.get("nature"), "other"),
            "type_label": record.get("nature_libelle"),
            "nature_categorise": record.get("nature_categorise_libelle"),
            "date_publication": record.get("dateparution"),
            "date_fin_diffusion": record.get("datefindiffusion"),
            "date_limite_reponse": record.get("datelimitereponse"),
            "departement": dept_code,
            "departements": depts,
            "famille": record.get("famille_libelle"),
            "procedure": record.get("procedure_libelle"),
            "type_marche": record.get("type_marche"),
            "cpv_code": record.get("descripteur_code"),
            "cpv_label": record.get("descripteur_libelle"),
            "perimetre": record.get("perimetre"),
            "url": record.get("url_avis"),
            "raw": record,
        }

    async def search_opportunities(
        self,
        keywords: str | None = None,
        departements: list[str] | None = None,
        cpv_codes: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for business opportunities (convenience method).

        Args:
            keywords: Keywords to search
            departements: List of department codes
            cpv_codes: List of CPV codes (product/service types)
            limit: Max results

        Returns:
            List of open opportunities
        """
        results = []

        # Search by department if specified
        if departements:
            for dept in departements:
                query = {
                    "type": "appel_offre",
                    "departement": dept,
                    "limit": limit // len(departements),
                }
                if keywords:
                    query["keywords"] = keywords
                results.extend(await self.search(query))
        else:
            query = {"type": "appel_offre", "limit": limit}
            if keywords:
                query["keywords"] = keywords
            results = await self.search(query)

        # Filter by CPV if specified
        if cpv_codes:
            results = [
                r
                for r in results
                if any(r.get("cpv_code", "").startswith(cpv) for cpv in cpv_codes)
            ]

        return results[:limit]
