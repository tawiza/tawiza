"""DBnomics adapter - Access to macroeconomic data from 80+ providers.

API Documentation: https://db.nomics.world/docs/api/
Free access, no authentication required.

Key providers for French territorial analysis:
- INSEE: French national statistics
- Eurostat: European statistics
- BDF: Banque de France
- ECB: European Central Bank
- OECD: Economic indicators
"""

from datetime import datetime
from typing import Any

import httpx

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class DBnomicsAdapter(BaseAdapter):
    """Adapter for DBnomics open macroeconomic data.

    DBnomics aggregates data from 80+ statistical offices and providers.
    Perfect for contextualizing territorial analysis with macro trends.
    """

    BASE_URL = "https://api.db.nomics.world/v22"

    # Key datasets for territorial analysis
    TERRITORIAL_DATASETS = {
        # INSEE France
        "INSEE/CHOMAGE-TRIM-REGION": "Chomage trimestriel par region",
        "INSEE/PIB-REGIONAL": "PIB regional",
        "INSEE/LOGEMENT-MENAGES": "Logements par menage",
        "INSEE/DEFM-ZONE-EMPLOI": "Demandeurs d'emploi par zone",
        # Eurostat
        "Eurostat/nama_10r_3gdp": "PIB regional (NUTS3)",
        "Eurostat/lfst_r_lfu3rt": "Taux de chomage regional",
        "Eurostat/demo_r_d2jan": "Population regionale",
        # Banque de France
        "BDF/WEBSTAT-CREDIT": "Credit aux entreprises",
        "BDF/WEBSTAT-EPARGNE": "Epargne des menages",
    }

    # French region codes for INSEE
    REGION_CODES = {
        "11": "Ile-de-France",
        "24": "Centre-Val de Loire",
        "27": "Bourgogne-Franche-Comte",
        "28": "Normandie",
        "32": "Hauts-de-France",
        "44": "Grand Est",
        "52": "Pays de la Loire",
        "53": "Bretagne",
        "75": "Nouvelle-Aquitaine",
        "76": "Occitanie",
        "84": "Auvergne-Rhone-Alpes",
        "93": "Provence-Alpes-Cote d'Azur",
        "94": "Corse",
    }

    def __init__(self, config: AdapterConfig | None = None) -> None:
        """Initialize DBnomics adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
        """
        if config is None:
            config = AdapterConfig(
                name="dbnomics",
                base_url=self.BASE_URL,
                rate_limit=60,  # 60 req/min
                cache_ttl=86400,  # 24h cache - macro data updates slowly
            )
        super().__init__(config)

    async def get_providers(self) -> list[dict[str, Any]]:
        """Get list of available data providers.

        Returns:
            List of provider metadata with codes and names.
        """
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/providers",
                params={"limit": 100},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("providers", {}).get("docs", [])

        except httpx.HTTPError as e:
            self._log_error("get_providers", e)
            return []

    async def get_datasets(
        self,
        provider: str,
        search: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get datasets from a specific provider.

        Args:
            provider: Provider code (e.g., 'INSEE', 'Eurostat')
            search: Optional search term
            limit: Maximum results

        Returns:
            List of dataset metadata
        """
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["q"] = search

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/providers/{provider}",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            datasets = data.get("provider", {}).get("datasets", {}).get("docs", [])
            return [
                {
                    "code": ds.get("code"),
                    "name": ds.get("name"),
                    "nb_series": ds.get("nb_series"),
                    "indexed_at": ds.get("indexed_at"),
                }
                for ds in datasets
            ]

        except httpx.HTTPError as e:
            self._log_error(f"get_datasets:{provider}", e)
            return []

    async def get_series(
        self,
        provider: str,
        dataset: str,
        series_id: str | None = None,
        dimensions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get time series data from a dataset.

        Args:
            provider: Provider code
            dataset: Dataset code
            series_id: Specific series ID (optional)
            dimensions: Dimension filters (optional)

        Returns:
            Series data with observations
        """
        try:
            if series_id:
                url = f"{self.BASE_URL}/series/{provider}/{dataset}/{series_id}"
                response = await self._client.get(url)
            else:
                url = f"{self.BASE_URL}/series/{provider}/{dataset}"
                params = {"limit": 50}
                if dimensions:
                    # Use q= for filtering - dimensions parameter is broken in v22
                    filter_parts = list(dimensions.values())
                    params["q"] = " ".join(filter_parts)
                response = await self._client.get(url, params=params)

            response.raise_for_status()
            data = response.json()

            series_list = data.get("series", {}).get("docs", [])

            return {
                "source": "dbnomics",
                "provider": provider,
                "dataset": dataset,
                "series_count": len(series_list),
                "series": [
                    {
                        "id": s.get("series_code"),
                        "name": s.get("series_name"),
                        "dimensions": s.get("dimensions", {}),
                        "observations": s.get("period", []),
                        "values": s.get("value", []),
                    }
                    for s in series_list[:10]  # Limit to first 10
                ],
            }

        except httpx.HTTPError as e:
            self._log_error(f"get_series:{provider}/{dataset}", e)
            return {"source": "dbnomics", "error": str(e)}

    async def search_series(
        self,
        query: str,
        providers: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for series across providers.

        Args:
            query: Search term
            providers: List of provider codes to search in
            limit: Maximum results

        Returns:
            List of matching series
        """
        if providers is None:
            providers = ["INSEE", "Eurostat", "BDF"]

        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
        }

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/series",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            series = data.get("series", {}).get("docs", [])

            # Filter by providers if specified
            if providers:
                series = [s for s in series if s.get("provider_code") in providers]

            return [
                {
                    "id": s.get("series_code"),
                    "provider": s.get("provider_code"),
                    "dataset": s.get("dataset_code"),
                    "name": s.get("series_name"),
                    "frequency": s.get("@frequency"),
                    "last_update": s.get("indexed_at"),
                }
                for s in series
            ]

        except httpx.HTTPError as e:
            self._log_error(f"search_series:{query}", e)
            return []

    async def get_regional_gdp(self, region_code: str) -> dict[str, Any]:
        """Get regional GDP data.

        Args:
            region_code: French region code (e.g., '11' for IDF)

        Returns:
            GDP time series for the region
        """
        # Try Eurostat NUTS2 first (more complete)
        nuts2_mapping = {
            "11": "FR10",  # Ile-de-France
            "84": "FRK2",  # Auvergne-Rhone-Alpes
            "93": "FRL0",  # PACA
            "75": "FRI1",  # Nouvelle-Aquitaine
            "76": "FRJ2",  # Occitanie
        }

        nuts_code = nuts2_mapping.get(region_code)
        if nuts_code:
            result = await self.get_series(
                provider="Eurostat",
                dataset="nama_10r_3gdp",
                dimensions={"geo": nuts_code},
            )
            if "error" not in result:
                result["region_name"] = self.REGION_CODES.get(region_code, region_code)
                return result

        # Fallback to INSEE
        return await self.get_series(
            provider="INSEE",
            dataset="PIB-REGIONAL",
            dimensions={"REG": region_code},
        )

    async def get_unemployment_rate(self, territory: str) -> dict[str, Any]:
        """Get unemployment rate for a territory.

        Args:
            territory: Region code or 'France'

        Returns:
            Unemployment rate time series
        """
        if territory.upper() == "FRANCE":
            return await self.get_series(
                provider="INSEE",
                dataset="CHOMAGE-TRIM",
            )

        return await self.get_series(
            provider="INSEE",
            dataset="CHOMAGE-TRIM-REGION",
            dimensions={"REG": territory},
        )

    async def get_inflation(self, country: str = "FR") -> dict[str, Any]:
        """Get inflation data.

        Args:
            country: ISO country code

        Returns:
            Inflation/CPI time series
        """
        return await self.get_series(
            provider="Eurostat",
            dataset="prc_hicp_manr",
            dimensions={"geo": country},
        )

    async def get_credit_data(self, region_code: str | None = None) -> dict[str, Any]:
        """Get credit to enterprises data from Banque de France.

        Args:
            region_code: Optional region filter

        Returns:
            Credit data time series
        """
        dimensions = {}
        if region_code:
            dimensions["REG"] = region_code

        return await self.get_series(
            provider="BDF",
            dataset="WEBSTAT-CREDIT",
            dimensions=dimensions if dimensions else None,
        )

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search DBnomics data.

        Args:
            query: Search parameters
                - type: 'gdp', 'unemployment', 'inflation', 'credit', 'search'
                - region: Region code
                - q: Search term (for type='search')
                - providers: Provider list

        Returns:
            List of results
        """
        data_type = query.get("type", "search")
        region = query.get("region") or query.get("code_region")

        if data_type == "gdp":
            if region:
                result = await self.get_regional_gdp(region)
            else:
                result = await self.get_series("INSEE", "PIB-REGIONAL")
            return [result]

        elif data_type == "unemployment":
            territory = region or "France"
            result = await self.get_unemployment_rate(territory)
            return [result]

        elif data_type == "inflation":
            country = query.get("country", "FR")
            result = await self.get_inflation(country)
            return [result]

        elif data_type == "credit":
            result = await self.get_credit_data(region)
            return [result]

        else:
            # Generic search
            search_term = query.get("q", query.get("query", ""))
            providers = query.get("providers", ["INSEE", "Eurostat"])
            return await self.search_series(search_term, providers)

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get series by full ID (provider/dataset/series).

        Args:
            id: Full series identifier

        Returns:
            Series data or None
        """
        parts = id.split("/")
        if len(parts) >= 3:
            provider, dataset, series_id = parts[0], parts[1], "/".join(parts[2:])
            result = await self.get_series(provider, dataset, series_id)
            if "error" not in result:
                return result
        return None

    async def health_check(self) -> bool:
        """Check if DBnomics API is available."""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/providers",
                params={"limit": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """DBnomics provides aggregated statistical data."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="DBnomics aggregates static statistical datasets",
        )
