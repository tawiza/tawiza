"""INSEE Melodi adapter - Open statistical data from INSEE catalog.

API Documentation: https://portail-api.insee.fr/catalog/api/a890b735-159c-4c91-90b7-35159c7c9126

Provides FREE access (no authentication) to 95+ INSEE statistical datasets:
- Population (DS_POPULATIONS_REFERENCE, DS_ESTIMATION_POPULATION)
- Local equipment (DS_BPE - commerce, santé, services)
- Regional accounts (DS_COMPTES_REGIONAUX - PIB)
- Employment and wages (DS_BTS_SAL_EQTP_SEX_AGE)
- Demographics (DS_ETAT_CIVIL_DECES_COMMUNES, DS_ETAT_CIVIL_NAIS_COMMUNES)
- Electoral data (DS_ELECTORAL)

Rate limit: 30 requests/minute (anonymous access)
"""

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class MelodiAdapter(BaseAdapter):
    """Adapter for INSEE Melodi open data API.

    The Melodi API provides free access to all INSEE statistical datasets
    without authentication. Perfect for territorial analysis.
    """

    # API base URL
    BASE_URL = "https://api.insee.fr/melodi"

    # Key datasets for territorial analysis
    TERRITORIAL_DATASETS = {
        # Population
        "DS_POPULATIONS_REFERENCE": "Populations de référence",
        "DS_ESTIMATION_POPULATION": "Estimations de population",
        # Demographics
        "DS_ETAT_CIVIL_DECES_COMMUNES": "Décès annuels par commune",
        "DS_ETAT_CIVIL_NAIS_COMMUNES": "Naissances annuelles par commune",
        "DS_EC_DECES": "Décès quotidiens/mensuels",
        "DS_EC_NAIS": "Naissances mensuelles",
        # Local equipment
        "DS_BPE": "Équipements (commerce, santé, services)",
        "DS_BPE_EDUCATION": "Équipements éducation",
        "DS_BPE_SPORT_CULTURE": "Équipements sport/culture",
        "DS_BPE_EVOLUTION": "Évolution des équipements",
        # Economy
        "DS_COMPTES_REGIONAUX": "Comptes régionaux (PIB)",
        "DS_BTS_SAL_EQTP_SEX_AGE": "Salaires par sexe/âge (communal)",
        "DS_BTS_SAL_EQTP_SEX_PCS": "Salaires par CSP (communal)",
        # Electoral
        "DS_ELECTORAL": "Corps électoral",
    }

    # Geographic level mappings
    GEO_LEVELS = {
        "commune": "COM",
        "departement": "DEP",
        "region": "REG",
        "epci": "EPCI",
        "arrondissement": "ARR",
        "france": "FRANCE",
    }

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialize the Melodi adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
        """
        if config is None:
            config = AdapterConfig(
                name="melodi",
                base_url=self.BASE_URL,
                rate_limit=30,  # 30 req/min anonymous limit
                cache_ttl=86400,  # 24h cache - statistical data
            )
        super().__init__(config)
        self._catalog_cache: list[dict] | None = None

    async def get_catalog(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get the complete catalog of available datasets.

        Args:
            force_refresh: Bypass cache and fetch fresh catalog

        Returns:
            List of dataset metadata
        """
        if self._catalog_cache and not force_refresh:
            return self._catalog_cache

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/catalog/all",
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            self._catalog_cache = response.json()
            logger.info(f"Melodi catalog loaded: {len(self._catalog_cache)} datasets")
            return self._catalog_cache

        except httpx.HTTPError as e:
            self._log_error("get_catalog", e)
            return []

    async def get_territorial_datasets(self) -> list[dict[str, Any]]:
        """Get datasets with territorial resolution (COM, DEP, REG, EPCI).

        Returns:
            List of datasets that can be queried at sub-national level
        """
        catalog = await self.get_catalog()

        territorial = []
        for ds in catalog:
            resolutions = ds.get("spatialResolution", [])
            resolution_ids = [r.get("id", "") for r in resolutions]

            if any(level in resolution_ids for level in ["COM", "DEP", "REG", "EPCI", "ARR"]):
                territorial.append(
                    {
                        "identifier": ds.get("identifier"),
                        "title": ds.get("title", [{}])[0].get("content", ""),
                        "resolutions": resolution_ids,
                        "observations": ds.get("numObservations", 0),
                    }
                )

        return territorial

    async def get_data(
        self,
        dataset_id: str,
        geo: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get data from a specific dataset.

        Args:
            dataset_id: Dataset identifier (e.g., 'DS_POPULATIONS_REFERENCE')
            geo: Geographic filter (e.g., 'DEP-75', 'COM-75056', 'REG-11')
            filters: Additional dimension filters

        Returns:
            Dataset observations with metadata
        """
        params = {}
        if geo:
            params["GEO"] = geo
        if filters:
            params.update(filters)

        try:
            url = f"{self.BASE_URL}/data/{dataset_id}"
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "source": "melodi",
                "dataset": dataset_id,
                "geo": geo,
                "filters": filters,
                "title": data.get("title", {}),
                "observations": data.get("observations", []),
                "paging": data.get("paging"),
            }

        except httpx.HTTPError as e:
            error_text = ""
            if hasattr(e, "response") and e.response is not None:
                error_text = e.response.text
            self._log_error(f"get_data:{dataset_id}", e)
            return {
                "source": "melodi",
                "dataset": dataset_id,
                "error": str(e),
                "detail": error_text,
            }

    async def get_population(
        self,
        code_dept: str | None = None,
        code_region: str | None = None,
        code_commune: str | None = None,
    ) -> dict[str, Any]:
        """Get population data from DS_POPULATIONS_REFERENCE.

        Args:
            code_dept: Department code (e.g., '75')
            code_region: Region code (e.g., '11')
            code_commune: Commune code (e.g., '75056')

        Returns:
            Population data with observations
        """
        if code_commune:
            geo = f"COM-{code_commune}"
        elif code_dept:
            geo = f"DEP-{code_dept}"
        elif code_region:
            geo = f"REG-{code_region}"
        else:
            geo = "FRANCE-F"

        data = await self.get_data("DS_POPULATIONS_REFERENCE", geo=geo)

        # Extract population value from observations
        if "observations" in data and data["observations"]:
            obs = data["observations"][0]
            measures = obs.get("measures", {})
            pop_value = measures.get("OBS_VALUE_NIVEAU", {}).get("value")
            data["population"] = pop_value

        return data

    async def get_regional_accounts(
        self,
        code_region: str | None = None,
        code_dept: str | None = None,
    ) -> dict[str, Any]:
        """Get regional accounts (PIB, emploi) from DS_COMPTES_REGIONAUX.

        Args:
            code_region: Region code (e.g., '11' for IDF)
            code_dept: Department code

        Returns:
            Regional economic data
        """
        if code_region:
            geo = f"REG-{code_region}"
        elif code_dept:
            geo = f"DEP-{code_dept}"
        else:
            geo = "FRANCE-F"

        return await self.get_data("DS_COMPTES_REGIONAUX", geo=geo)

    async def get_equipment_count(
        self,
        code_dept: str | None = None,
        code_commune: str | None = None,
        equipment_type: str | None = None,
    ) -> dict[str, Any]:
        """Get local equipment counts from DS_BPE.

        Args:
            code_dept: Department code
            code_commune: Commune code
            equipment_type: Equipment type filter (e.g., 'A203' for police)

        Returns:
            Equipment count data
        """
        if code_commune:
            geo = f"COM-{code_commune}"
        elif code_dept:
            geo = f"DEP-{code_dept}"
        else:
            geo = "FRANCE-F"

        filters = {}
        if equipment_type:
            filters["TYPEQU"] = equipment_type

        return await self.get_data("DS_BPE", geo=geo, filters=filters)

    async def get_demographics(
        self,
        code_dept: str | None = None,
        code_commune: str | None = None,
        data_type: str = "births",
    ) -> dict[str, Any]:
        """Get demographic data (births/deaths).

        Args:
            code_dept: Department code
            code_commune: Commune code
            data_type: 'births' or 'deaths'

        Returns:
            Demographic data
        """
        if code_commune:
            geo = f"COM-{code_commune}"
            dataset = (
                "DS_ETAT_CIVIL_NAIS_COMMUNES"
                if data_type == "births"
                else "DS_ETAT_CIVIL_DECES_COMMUNES"
            )
        elif code_dept:
            geo = f"DEP-{code_dept}"
            dataset = "DS_EC_NAIS" if data_type == "births" else "DS_EC_DECES"
        else:
            geo = "FRANCE-F"
            dataset = "DS_EC_NAIS" if data_type == "births" else "DS_EC_DECES"

        return await self.get_data(dataset, geo=geo)

    async def get_salaries(
        self,
        code_dept: str | None = None,
        code_commune: str | None = None,
    ) -> dict[str, Any]:
        """Get salary data from DS_BTS_SAL_EQTP_SEX_AGE.

        Args:
            code_dept: Department code
            code_commune: Commune code

        Returns:
            Salary data by sex and age
        """
        if code_commune:
            geo = f"COM-{code_commune}"
        elif code_dept:
            geo = f"DEP-{code_dept}"
        else:
            geo = "FRANCE-F"

        return await self.get_data("DS_BTS_SAL_EQTP_SEX_AGE", geo=geo)

    async def get_electoral_data(
        self,
        code_dept: str | None = None,
        code_commune: str | None = None,
    ) -> dict[str, Any]:
        """Get electoral body characteristics from DS_ELECTORAL.

        Args:
            code_dept: Department code
            code_commune: Commune code

        Returns:
            Electoral data
        """
        if code_commune:
            geo = f"COM-{code_commune}"
        elif code_dept:
            geo = f"DEP-{code_dept}"
        else:
            geo = "FRANCE-F"

        return await self.get_data("DS_ELECTORAL", geo=geo)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search Melodi datasets.

        Args:
            query: Search parameters
                - type: 'population', 'equipment', 'economy', 'demographics', 'salaries'
                - code_dept: Department code
                - code_commune: Commune code
                - code_region: Region code

        Returns:
            List of data results
        """
        data_type = query.get("type", "population")
        code_dept = query.get("code_dept") or query.get("code_departement")
        code_commune = query.get("code_commune") or query.get("code_insee")
        code_region = query.get("code_region")

        if data_type == "population":
            result = await self.get_population(code_dept, code_region, code_commune)
        elif data_type == "equipment":
            result = await self.get_equipment_count(code_dept, code_commune)
        elif data_type == "economy":
            result = await self.get_regional_accounts(code_region, code_dept)
        elif data_type == "demographics":
            result = await self.get_demographics(code_dept, code_commune)
        elif data_type == "salaries":
            result = await self.get_salaries(code_dept, code_commune)
        elif data_type == "electoral":
            result = await self.get_electoral_data(code_dept, code_commune)
        elif data_type == "catalog":
            return await self.get_territorial_datasets()
        else:
            result = await self.get_data(data_type, geo=query.get("geo"))

        return [result]

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get dataset metadata by identifier."""
        catalog = await self.get_catalog()
        for ds in catalog:
            if ds.get("identifier") == id:
                return {
                    "source": "melodi",
                    "identifier": ds.get("identifier"),
                    "title": ds.get("title"),
                    "description": ds.get("description"),
                    "temporal": ds.get("temporal"),
                    "spatial": ds.get("spatial"),
                    "spatialResolution": ds.get("spatialResolution"),
                    "numObservations": ds.get("numObservations"),
                }
        return None

    async def health_check(self) -> bool:
        """Check if Melodi API is available."""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/data/DS_POPULATIONS_REFERENCE",
                params={"GEO": "DEP-75"},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Melodi provides static statistical data."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="Melodi provides static statistical datasets",
        )
