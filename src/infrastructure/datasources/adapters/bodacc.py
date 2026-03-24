"""BODACC adapter - French legal announcements (creations, modifications, procedures)."""

from datetime import date, datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class BodaccAdapter(BaseAdapter):
    """Adapter for BODACC (Bulletin Officiel des Annonces Civiles et Commerciales).

    API Documentation: https://bodacc-datadila.opendatasoft.com/api/v2/console

    Data includes:
    - Company creations (immatriculations)
    - Modifications (changes to company info)
    - Radiations (company closures)
    - Collective procedures (bankruptcy, liquidation)
    """

    # Event type mapping - BODACC familleavis field contains these values directly
    # Note: The API returns human-readable French values, not codes
    TYPE_MAPPING = {
        "creation": "creation",  # Immatriculation / création d'entreprise
        "modification": "modification",  # Modifications diverses
        "radiation": "radiation",  # Radiation / fermeture
        "procedure": "rectificatif_collectif",  # Procédures collectives
        "vente": "vente",  # Ventes et cessions
    }

    # Reverse mapping for display (full names + API short codes)
    TYPE_LABELS = {
        "creation": "creation",
        "modification": "modification",
        "radiation": "radiation",
        "rectificatif_collectif": "procedure",
        "vente": "vente",
        # Short codes returned by BODACC API in familleavis field
        "imm": "creation",
        "mod": "modification",
        "rad": "radiation",
        "pcl": "procedure",
        "dpc": "depot_comptes",
    }

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialise l'adapter BODACC.

        Args:
            config: Configuration de l'adapter. Si None, utilise les
                valeurs par défaut pour l'API OpenDataSoft de BODACC.
        """
        if config is None:
            config = AdapterConfig(
                name="bodacc",
                base_url="https://bodacc-datadila.opendatasoft.com/api/explore/v2.1",
                rate_limit=30,
                cache_ttl=86400,
            )
        super().__init__(config)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search BODACC announcements.

        Args:
            query: Search parameters
                - siren: Company SIREN (9 digits)
                - siret: Company SIRET (14 digits)
                - nom: Company name (partial match)
                - type: Event type (creation, modification, radiation, procedure)
                - date_from: Start date (YYYY-MM-DD)
                - date_to: End date (YYYY-MM-DD)
                - departement: Department code (e.g., "59")
                - limit: Max results (default 100)

        Returns:
            List of BODACC announcements
        """
        # Build API filter
        filters = []

        if siren := query.get("siren"):
            # registre field contains SIREN in array format
            filters.append(f'registre="{siren}"')

        if siret := query.get("siret"):
            # SIRET = SIREN + NIC, extract SIREN
            siren = siret[:9]
            filters.append(f'registre="{siren}"')

        if nom := query.get("nom"):
            filters.append(f'commercant like "%{nom}%"')

        if event_type := query.get("type"):
            if mapped := self.TYPE_MAPPING.get(event_type):
                filters.append(f'familleavis="{mapped}"')

        if date_from := query.get("date_from"):
            filters.append(f'dateparution>="{date_from}"')

        if date_to := query.get("date_to"):
            filters.append(f'dateparution<="{date_to}"')

        if dept := query.get("departement"):
            filters.append(f'numerodepartement="{dept}"')

        # Build request
        params = {
            "limit": query.get("limit", 100),
            "order_by": "dateparution desc",
        }

        if filters:
            params["where"] = " AND ".join(filters)

        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/annonces-commerciales/records",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return [self._transform_record(r) for r in data.get("results", [])]

        except httpx.HTTPError as e:
            logger.error(f"BODACC search failed: {e}")
            return []

    async def count_events(
        self,
        dept: str,
        event_type: str,
        date_from: str,
        date_to: str,
    ) -> int:
        """Count BODACC events using total_count (no result download).

        Args:
            dept: Department code
            event_type: Event type (creation, modification, radiation)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Total count of matching events
        """
        filters = [f'numerodepartement="{dept}"']
        if mapped := self.TYPE_MAPPING.get(event_type):
            filters.append(f'familleavis="{mapped}"')
        filters.append(f'dateparution>="{date_from}"')
        filters.append(f'dateparution<="{date_to}"')

        params = {
            "where": " AND ".join(filters),
            "limit": 0,
        }

        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/annonces-commerciales/records",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("total_count", 0)
        except httpx.HTTPError as e:
            logger.warning(f"BODACC count failed for {dept}/{event_type}: {e}")
            return 0

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get announcements for a specific SIREN/SIRET.

        Args:
            id: SIREN (9 digits) or SIRET (14 digits)

        Returns:
            Most recent announcement for the company
        """
        siren = id[:9] if len(id) >= 9 else id
        results = await self.search({"siren": siren, "limit": 1})
        return results[0] if results else None

    async def health_check(self) -> bool:
        """Check if BODACC API is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/annonces-commerciales",
                timeout=30.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync recent BODACC announcements.

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
        """Transform BODACC record to standard format."""
        # Extract SIREN from registre array
        registre = record.get("registre", [])
        siren = registre[0].replace(" ", "") if registre else None

        return {
            "source": "bodacc",
            "id": record.get("id"),
            "siren": siren,
            "nom": record.get("commercant"),
            "type": self.TYPE_LABELS.get(record.get("familleavis"), "other"),
            "type_label": record.get("familleavis_lib"),
            "date_publication": record.get("dateparution"),
            "numero_annonce": record.get("numeroannonce"),
            "departement": record.get("departement_nom_officiel"),
            "numero_departement": record.get("numerodepartement"),
            "region": record.get("region_nom_officiel"),
            "ville": record.get("ville"),
            "code_postal": record.get("cp"),
            "tribunal": record.get("tribunal"),
            "contenu": (
                record.get("acte")
                or record.get("jugement")
                or record.get("depot")
                or record.get("modificationsgenerales")
            ),
            "url": record.get("url_complete"),
            "raw": record,
        }

    def _reverse_type(self, bodacc_type: str | None) -> str:
        """Convert BODACC type to our standard type."""
        if not bodacc_type:
            return "unknown"
        return self.TYPE_LABELS.get(bodacc_type, "other")
