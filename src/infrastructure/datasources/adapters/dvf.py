"""DVF adapter - French real estate transactions (Demandes de Valeurs Foncières)."""

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class DVFAdapter(BaseAdapter):
    """Adapter for DVF API (Demandes de Valeurs Foncières).

    API Documentation: https://api.gouv.fr/les-api/api-donnees-foncieres

    Provides FREE access to real estate transactions in France:
    - Sales prices
    - Property details (type, surface, rooms)
    - Location (commune, address)
    - Transaction dates

    Data available from 2014 onwards.
    No authentication required for open data endpoints.

    Uses Cerema DVF OpenData API (preprod).
    """

    # Arrondissements codes for Paris, Lyon, Marseille
    # These cities use arrondissement codes, not commune code
    _ARRONDISSEMENTS = {
        # Paris: 75056 -> 75101-75120
        "75056": [f"751{i:02d}" for i in range(1, 21)],
        "75": [f"751{i:02d}" for i in range(1, 21)],
        # Lyon: 69123 -> 69381-69389
        "69123": [f"6938{i}" for i in range(1, 10)],
        # Marseille: 13055 -> 13201-13216
        "13055": [f"132{i:02d}" for i in range(1, 17)],
    }

    def __init__(
        self,
        config: AdapterConfig | None = None,
        use_local_cache: bool = True,
        cache_path: str | None = None,
    ) -> None:
        """Initialize the DVF adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
            use_local_cache: Use local SQLite cache when available (faster for big communes)
            cache_path: Path to cache database (default: /data/dvf_cache.db)
        """
        if config is None:
            config = AdapterConfig(
                name="dvf",
                base_url="https://apidf-preprod.cerema.fr",  # Cerema DVF OpenData API
                rate_limit=30,
                cache_ttl=86400,  # 24h - transaction data is historical
                timeout=30,  # DVF API can be slow
            )
        super().__init__(config)
        # Geo API for commune lookup (to convert dept to INSEE codes)
        self._geo_url = "https://geo.api.gouv.fr"
        
        # Local cache for fast queries on big departments
        self._use_local_cache = use_local_cache
        self._local_cache = None
        if use_local_cache:
            try:
                from src.infrastructure.datasources.adapters.dvf_cache import DVFLocalCache
                self._local_cache = DVFLocalCache(cache_path)
            except Exception as e:
                logger.warning(f"Could not initialize DVF local cache: {e}")

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search real estate transactions.

        Args:
            query: Search parameters
                - code_insee: Commune INSEE code
                - code_postal: Postal code
                - code_departement: Department code
                - annee_min: Start year (e.g., 2020)
                - annee_max: End year (e.g., 2024)
                - type_local: Property type (mapped to codtypbien)
                - valeur_min: Min price
                - valeur_max: Max price
                - limit: Max results (default 50)

        Returns:
            List of transactions
        """
        # Try local cache first (much faster for big communes)
        if self._local_cache:
            dept = self._get_department_from_query(query)
            if dept and self._local_cache.is_cached(dept):
                logger.debug(f"Using local cache for department {dept}")
                return self._local_cache.search(
                    code_insee=query.get("code_insee"),
                    code_departement=query.get("code_departement"),
                    annee_min=query.get("annee_min"),
                    annee_max=query.get("annee_max"),
                    type_local=query.get("type_local"),
                    limit=query.get("limit", 50),
                )
        
        # Fallback to Cerema API
        return await self._search_cerema(query)
    
    def _get_department_from_query(self, query: dict[str, Any]) -> str | None:
        """Extract department code from query."""
        if dept := query.get("code_departement"):
            return dept
        if code_insee := query.get("code_insee"):
            # INSEE code starts with department (except Corsica: 2A, 2B)
            if code_insee.startswith("97"):
                return code_insee[:3]  # DOM-TOM
            return code_insee[:2]
        return None

    async def _search_cerema(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search via Cerema DVF OpenData API.

        Note: Cerema API requires code_insee. If only department is provided,
        we fetch the prefecture commune code for that department.
        For Paris/Lyon/Marseille, we expand to arrondissement codes.
        """
        limit = query.get("limit", 50)
        code_insee = query.get("code_insee")
        code_dept = query.get("code_departement")

        # Determine which INSEE codes to query
        codes_to_query: list[str] = []

        if code_insee:
            # Check if this is a commune with arrondissements
            if code_insee in self._ARRONDISSEMENTS:
                codes_to_query = self._ARRONDISSEMENTS[code_insee]
            else:
                codes_to_query = [code_insee]
        elif code_dept:
            # Check if department is Paris (special case)
            if code_dept in self._ARRONDISSEMENTS:
                codes_to_query = self._ARRONDISSEMENTS[code_dept]
            else:
                # Get prefecture code for department
                prefecture = await self._get_prefecture_code(code_dept)
                if prefecture:
                    codes_to_query = [prefecture]

        if not codes_to_query:
            logger.warning("DVF search requires code_insee or code_departement")
            return []

        # Build base params
        base_params: dict[str, Any] = {}
        if annee_min := query.get("annee_min"):
            base_params["anneemut_min"] = annee_min
        if annee_max := query.get("annee_max"):
            base_params["anneemut_max"] = annee_max
        if codtypbien := query.get("codtypbien"):
            base_params["codtypbien"] = codtypbien

        # Query each code (for arrondissements) and aggregate
        all_results: list[dict[str, Any]] = []
        per_code_limit = max(10, limit // len(codes_to_query)) if len(codes_to_query) > 1 else limit

        for code in codes_to_query:
            if len(all_results) >= limit:
                break

            params = {**base_params, "code_insee": code, "page_size": per_code_limit}

            try:
                response = await self._client.get(
                    f"{self.config.base_url}/dvf_opendata/mutations/",
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                for r in data.get("results", []):
                    if len(all_results) >= limit:
                        break
                    all_results.append(self._transform_cerema_result(r))

            except httpx.HTTPError as e:
                self._log_error(f"search_cerema({code})", e)
                continue

        return all_results

    async def _get_prefecture_code(self, code_dept: str) -> str | None:
        """Get prefecture commune INSEE code for a department.

        Uses geo.api.gouv.fr to find the main commune of a department.
        """
        try:
            response = await self._client.get(
                f"{self._geo_url}/departements/{code_dept}/communes",
                params={"fields": "code,nom,population", "limit": 1, "boost": "population"},
            )
            response.raise_for_status()
            communes = response.json()

            if communes:
                # Return the most populous commune (usually prefecture)
                return communes[0].get("code")
            return None

        except httpx.HTTPError as e:
            logger.warning(f"Failed to get prefecture for {code_dept}: {e}")
            return None

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get transaction by ID.

        Args:
            id: Transaction ID (mutation ID)

        Returns:
            Transaction data or None
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/dvf_opendata/mutations/{id}/",
            )
            response.raise_for_status()
            data = response.json()
            return self._transform_cerema_result(data)

        except httpx.HTTPError as e:
            self._log_error("get_by_id", e)
            return None

    async def get_stats_commune(self, code_insee: str, annee: int | None = None) -> dict[str, Any]:
        """Get transaction statistics for a commune.

        Args:
            code_insee: Commune INSEE code (handles Paris/Lyon/Marseille arrondissements)
            annee: Year to analyze (default: last available)

        Returns:
            Statistics dict with median prices, volumes, etc.
        """
        # Try local cache first
        if self._local_cache:
            dept = code_insee[:3] if code_insee.startswith("97") else code_insee[:2]
            if self._local_cache.is_cached(dept):
                logger.debug(f"Using local cache for stats {code_insee}")
                return self._local_cache.get_stats(code_insee, annee)
        
        query: dict[str, Any] = {"code_insee": code_insee, "limit": 1000}
        if annee:
            query["annee_min"] = annee
            query["annee_max"] = annee

        transactions = await self.search(query)

        if not transactions:
            return {
                "source": "dvf",
                "code_insee": code_insee,
                "count": 0,
                "error": "No data available",
            }

        # Filter by type_bien (DVF OpenData uses libtypbien)
        # Types: APPARTEMENT, MAISON, LOCAL INDUSTRIEL, DEPENDANCE, etc.
        appartements = [t for t in transactions if "APPARTEMENT" in (t.get("type_bien") or "").upper()]
        maisons = [t for t in transactions if "MAISON" in (t.get("type_bien") or "").upper()]
        # Include mixed residential
        logements = [t for t in transactions if "LOGEMENT" in (t.get("type_bien") or "").upper()]

        def calc_median(items: list, key: str) -> float | None:
            values = [i.get(key) for i in items if i.get(key) and i.get(key) > 0]
            if not values:
                return None
            values.sort()
            n = len(values)
            if n % 2 == 0:
                return (values[n // 2 - 1] + values[n // 2]) / 2
            return values[n // 2]

        def calc_prix_m2_median(items: list) -> float | None:
            prix_m2 = []
            for item in items:
                if item.get("valeur") and item.get("surface_reelle") and item["surface_reelle"] > 0:
                    prix_m2.append(item["valeur"] / item["surface_reelle"])
            if not prix_m2:
                return None
            prix_m2.sort()
            n = len(prix_m2)
            if n % 2 == 0:
                return (prix_m2[n // 2 - 1] + prix_m2[n // 2]) / 2
            return prix_m2[n // 2]

        return {
            "source": "dvf",
            "code_insee": code_insee,
            "annee": annee,
            "total_transactions": len(transactions),
            "appartements": {
                "count": len(appartements),
                "prix_median": calc_median(appartements, "valeur"),
                "prix_m2_median": calc_prix_m2_median(appartements),
                "surface_mediane": calc_median(appartements, "surface_reelle"),
            },
            "maisons": {
                "count": len(maisons),
                "prix_median": calc_median(maisons, "valeur"),
                "prix_m2_median": calc_prix_m2_median(maisons),
                "surface_mediane": calc_median(maisons, "surface_reelle"),
            },
            "logements_mixtes": {
                "count": len(logements),
                "prix_median": calc_median(logements, "valeur"),
            },
        }

    async def get_evolution_prix(
        self, code_insee: str, annee_debut: int = 2019, annee_fin: int = 2024
    ) -> list[dict[str, Any]]:
        """Get price evolution over years for a commune.

        Args:
            code_insee: Commune INSEE code
            annee_debut: Start year
            annee_fin: End year

        Returns:
            List of yearly statistics
        """
        evolution = []
        for annee in range(annee_debut, annee_fin + 1):
            stats = await self.get_stats_commune(code_insee, annee)
            if stats.get("total_transactions", 0) > 0:
                evolution.append(stats)
        return evolution

    async def health_check(self) -> bool:
        """Check if DVF API is available."""
        try:
            # API requires code_insee, use Paris 1er as test
            response = await self._client.get(
                f"{self.config.base_url}/dvf_opendata/mutations/",
                params={"code_insee": "75101", "page_size": 1},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """DVF is updated semi-annually."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="DVF data is updated semi-annually by DGFiP",
        )

    def _transform_cerema_result(self, result: dict) -> dict[str, Any]:
        """Transform Cerema DVF OpenData API result to standard format.

        API field mapping (2024 schema):
        - idmutation -> id
        - datemut -> date_mutation
        - libnatmut -> nature_mutation
        - valeurfonc -> valeur
        - libtypbien -> type_local
        - sbati -> surface_reelle
        - sterr -> surface_terrain
        - coddep -> code_departement
        - l_codinsee -> code_insee (list, take first)
        """
        # Parse valeur (string with decimals)
        valeur_str = result.get("valeurfonc")
        valeur = float(valeur_str) if valeur_str else None

        # Parse surfaces (strings with decimals)
        sbati_str = result.get("sbati")
        sterr_str = result.get("sterr")
        surface_reelle = float(sbati_str) if sbati_str and sbati_str != "0.00" else None
        surface_terrain = float(sterr_str) if sterr_str and sterr_str != "0.00" else None

        # Get first INSEE code from list
        l_codinsee = result.get("l_codinsee", [])
        code_insee = l_codinsee[0] if l_codinsee else None

        return {
            "source": "dvf",
            "id": result.get("idmutation"),
            "id_opendata": result.get("idopendata"),
            "date_mutation": result.get("datemut"),
            "annee": result.get("anneemut"),
            "nature_mutation": result.get("libnatmut"),
            "valeur": valeur,
            "type_bien": result.get("libtypbien"),
            "code_type_bien": result.get("codtypbien"),
            "surface_reelle": surface_reelle,
            "surface_terrain": surface_terrain,
            "nb_locaux": result.get("nblocmut"),
            "nb_parcelles": result.get("nbpar"),
            "vefa": result.get("vefa", False),
            "code_insee": code_insee,
            "code_departement": result.get("coddep"),
            "raw": result,
        }
