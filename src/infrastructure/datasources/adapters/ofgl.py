"""OFGL adapter - French local government finances (Observatoire des Finances Locales)."""

from datetime import datetime
from typing import Any

import httpx

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class OFGLAdapter(BaseAdapter):
    """Adapter for OFGL API (data.ofgl.fr).

    API Documentation: https://data.ofgl.fr/

    Provides FREE access to French local government financial data:
    - Commune budgets
    - Department budgets
    - Region budgets
    - EPCI (intercommunalité) budgets
    - Financial indicators
    - Tax rates

    No authentication required.
    """

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialize the OFGL adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
        """
        if config is None:
            config = AdapterConfig(
                name="ofgl",
                base_url="https://data.ofgl.fr/api/explore/v2.1",
                rate_limit=30,
                cache_ttl=86400,  # 24h - budget data is annual
                timeout=30,  # OFGL can be slow
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=30)  # Override with longer timeout

        # Available datasets
        self._datasets = {
            "communes": "ofgl-base-communes-consolidee",
            "departements": "ofgl-base-departements-consolidee",
            "regions": "ofgl-base-regions-consolidee",
            "epci": "ofgl-base-gfp-consolidee",
            "populations": "populations-ofgl-ei",
            "compositions_epci": "detail_compositions_intercommunales_2012_2023",
        }

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search local government financial data.

        Args:
            query: Search parameters
                - type: 'communes', 'departements', 'regions', 'epci'
                - code_insee: Commune INSEE code
                - code_siren: SIREN code
                - nom: Name to search
                - annee: Year
                - limit: Max results (default 50)

        Returns:
            List of financial records
        """
        entity_type = query.get("type", "communes")
        dataset = self._datasets.get(entity_type, self._datasets["communes"])

        # Build WHERE clause
        where_parts = []
        if code_insee := query.get("code_insee"):
            where_parts.append(f"insee = '{code_insee}'")
        if code_siren := query.get("code_siren"):
            where_parts.append(f"siren = '{code_siren}'")
        if annee := query.get("annee"):
            where_parts.append(f"exer = {annee}")
        if nom := query.get("nom"):
            where_parts.append(f"search(lbudg, '{nom}')")

        params = {
            "limit": query.get("limit", 50),
        }
        if where_parts:
            params["where"] = " AND ".join(where_parts)

        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/{dataset}/records",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [
                self._transform_result(r.get("record", {}).get("fields", {}), entity_type)
                for r in data.get("results", [])
            ]

        except httpx.HTTPError as e:
            self._log_error("search", e)
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get commune financial data by INSEE code.

        Args:
            id: INSEE code (5 digits)

        Returns:
            Financial data or None
        """
        results = await self.search({
            "type": "communes",
            "code_insee": id,
            "limit": 1,
        })
        return results[0] if results else None

    async def get_commune_finances(
        self, code_insee: str, annee: int | None = None
    ) -> dict[str, Any] | None:
        """Get detailed finances for a commune.

        Args:
            code_insee: Commune INSEE code
            annee: Year (default: latest available)

        Returns:
            Detailed financial data
        """
        query = {"type": "communes", "code_insee": code_insee, "limit": 1}
        if annee:
            query["annee"] = annee

        results = await self.search(query)
        return results[0] if results else None

    async def get_finances_evolution(
        self, code_insee: str, annee_debut: int = 2018, annee_fin: int = 2023
    ) -> list[dict[str, Any]]:
        """Get financial evolution over years.

        Args:
            code_insee: Commune/EPCI INSEE code
            annee_debut: Start year
            annee_fin: End year

        Returns:
            List of yearly financial data
        """
        evolution = []
        for annee in range(annee_debut, annee_fin + 1):
            data = await self.get_commune_finances(code_insee, annee)
            if data:
                evolution.append(data)
        return evolution

    async def get_department_communes(self, code_dept: str) -> list[dict[str, Any]]:
        """Get financial data for all communes in a department.

        Args:
            code_dept: Department code (e.g., '75')

        Returns:
            List of commune financial data
        """
        params = {
            "limit": 500,  # Most depts have < 500 communes
            "where": f"dep = '{code_dept}'",
        }

        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets/{self._datasets['communes']}/records",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [
                self._transform_result(r.get("record", {}).get("fields", {}), "communes")
                for r in data.get("results", [])
            ]

        except httpx.HTTPError as e:
            self._log_error("get_department_communes", e)
            return []

    async def get_available_datasets(self) -> list[dict[str, Any]]:
        """List available OFGL datasets.

        Returns:
            List of dataset info
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets",
                params={"limit": 50},
            )
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "id": r.get("dataset_id"),
                    "title": r.get("dataset", {}).get("metas", {}).get("default", {}).get("title"),
                }
                for r in data.get("results", [])
            ]

        except httpx.HTTPError as e:
            self._log_error("get_available_datasets", e)
            return []

    async def health_check(self) -> bool:
        """Check if OFGL API is available."""
        try:
            response = await self._client.get(
                f"{self.config.base_url}/catalog/datasets",
                params={"limit": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """OFGL is updated annually."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="OFGL data is updated annually",
        )

    def _transform_result(self, fields: dict, entity_type: str) -> dict[str, Any]:
        """Transform API result to standard format."""
        result = {
            "source": "ofgl",
            "type": entity_type,
            "code_insee": fields.get("insee"),
            "code_siren": fields.get("siren"),
            "nom": fields.get("lbudg"),
            "annee": fields.get("exer"),
            "departement": fields.get("dep"),
            "region": fields.get("reg"),
        }

        # Financial indicators (vary by entity type)
        financials = {}

        # Recettes
        if tot_rec := fields.get("produits_total"):
            financials["recettes_totales"] = tot_rec
        if rec_fonct := fields.get("produits_de_fonctionnement"):
            financials["recettes_fonctionnement"] = rec_fonct
        if rec_invest := fields.get("recettes_investissement"):
            financials["recettes_investissement"] = rec_invest

        # Dépenses
        if tot_dep := fields.get("charges_total"):
            financials["depenses_totales"] = tot_dep
        if dep_fonct := fields.get("charges_de_fonctionnement"):
            financials["depenses_fonctionnement"] = dep_fonct
        if dep_invest := fields.get("depenses_investissement"):
            financials["depenses_investissement"] = dep_invest

        # Fiscalité
        if taxe_hab := fields.get("produit_taxe_habitation"):
            financials["taxe_habitation"] = taxe_hab
        if taxe_fonc_bati := fields.get("produit_taxe_fonciere_bati"):
            financials["taxe_fonciere_bati"] = taxe_fonc_bati
        if taxe_fonc_non_bati := fields.get("produit_taxe_fonciere_non_bati"):
            financials["taxe_fonciere_non_bati"] = taxe_fonc_non_bati

        # Ratios
        if encours_dette := fields.get("encours_total_de_la_dette"):
            financials["encours_dette"] = encours_dette
        if epargne_brute := fields.get("epargne_brute"):
            financials["epargne_brute"] = epargne_brute
        if cap_autofinancement := fields.get("capacite_autofinancement"):
            financials["capacite_autofinancement"] = cap_autofinancement

        # Population
        if pop := fields.get("pop_tot"):
            result["population"] = pop

        result["finances"] = financials
        result["raw"] = fields
        return result
