"""INSEE Données Locales adapter - French local statistics (demographics, income, housing)."""

import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class INSEELocalAdapter(BaseAdapter):
    """Adapter for INSEE local data APIs with OAuth2 authentication.

    API Documentation: https://portail-api.insee.fr/

    Provides access to French local statistics:
    - Demographics (population, age, households)
    - Income and living standards
    - Housing (types, ownership, vacancies)
    - Employment (local job market)

    Uses OAuth2 client credentials flow for authentication.
    """

    # OAuth2 token endpoint
    TOKEN_URL = "https://auth.insee.net/auth/realms/apim-gravitee/protocol/openid-connect/token"

    # API base URLs
    DONNEES_LOCALES_URL = "https://api.insee.fr/donnees-locales/V0.1"

    # Available geographic levels
    GEO_LEVELS = {
        "COM": "Commune",
        "DEP": "Département",
        "REG": "Région",
        "ARR": "Arrondissement",
        "EPCI": "EPCI",
        "FE": "France entière",
    }

    def __init__(
        self,
        config: AdapterConfig | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Initialize the INSEE Local adapter with OAuth2 credentials.

        Args:
            config: Adapter configuration. If None, uses defaults.
            client_id: INSEE API client ID (from env if not provided)
            client_secret: INSEE API client secret (from env if not provided)
        """
        if config is None:
            config = AdapterConfig(
                name="insee_local",
                base_url=self.DONNEES_LOCALES_URL,
                rate_limit=30,  # 30 req/min limit
                cache_ttl=86400 * 7,  # 7 days - census data is annual
            )
        super().__init__(config)

        # OAuth2 credentials
        self._client_id = client_id or os.getenv("INSEE_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("INSEE_CLIENT_SECRET")

        # Token cache
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_access_token(self) -> str | None:
        """Get OAuth2 access token using client credentials flow."""
        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=1):
                return self._access_token

        if not self._client_id or not self._client_secret:
            logger.warning("INSEE API credentials not configured")
            return None

        try:
            response = await self._client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"INSEE OAuth2 token obtained, expires in {expires_in}s")
            return self._access_token

        except httpx.HTTPError as e:
            logger.error(f"Failed to get INSEE OAuth2 token: {e}")
            return None

    async def _api_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make authenticated request to INSEE API."""
        token = await self._get_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        try:
            url = f"{self.DONNEES_LOCALES_URL}{endpoint}"
            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self._log_error(f"api_request:{endpoint}", e)
            return None

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search local statistics.

        Args:
            query: Search parameters
                - type: 'population', 'logement', 'revenus', 'emploi', 'indicateur'
                - code_insee: Commune INSEE code
                - code_departement: Department code
                - code_region: Region code
                - indicateur: Specific indicator code (e.g., 'SEXE', 'P21_POP')
                - annee: Year (e.g., '2021')
                - niveau_geo: Geographic level ('COM', 'DEP', 'REG')

        Returns:
            List of statistical data
        """
        data_type = query.get("type", "population")

        if data_type == "population":
            return await self._get_population(query)
        elif data_type == "logement":
            return await self._get_logement(query)
        elif data_type == "revenus":
            return await self._get_revenus(query)
        elif data_type == "emploi":
            return await self._get_emploi(query)
        elif data_type == "indicateur":
            return await self._get_indicateur(query)
        else:
            return await self._get_dossier_complet(query)

    async def _get_indicateur(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get specific indicator data from INSEE API.

        INSEE Données Locales API format:
        /donnees/geo-{CODE_GEO}@{NIVEAU_GEO}/jeuDeDonnees/{INDICATEUR}
        """
        niveau_geo = query.get("niveau_geo", "DEP")
        code_geo = query.get("code_departement") or query.get("code_insee") or query.get("code_region")
        indicateur = query.get("indicateur", "GEO2024POP_G")  # Default: population data

        if not code_geo:
            return []

        endpoint = f"/donnees/geo-{code_geo}@{niveau_geo}/jeuDeDonnees/{indicateur}"
        data = await self._api_request(endpoint)

        if not data:
            # Fallback to geo API for basic population
            return await self._get_population_fallback(query)

        return [{
            "source": "insee_local",
            "type": "indicateur",
            "indicateur": indicateur,
            "niveau_geo": niveau_geo,
            "code_geo": code_geo,
            "data": data,
        }]

    async def _get_population(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get population data for a territory using real INSEE API."""
        code_dept = query.get("code_departement")
        query.get("code_insee")

        # Try authenticated API first for detailed data
        if code_dept:
            # Population par sexe et âge
            endpoint = f"/donnees/geo-{code_dept}@DEP/jeuDeDonnees/GEO2024POP_G"
            data = await self._api_request(endpoint)

            if data:
                return [{
                    "source": "insee_local",
                    "type": "population",
                    "niveau_geo": "DEP",
                    "code_geo": code_dept,
                    "authenticated": True,
                    "data": data,
                    "indicateurs": self._extract_population_indicators(data),
                }]

        # Fallback to geo API (always available)
        return await self._get_population_fallback(query)

    async def _get_population_fallback(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fallback population data from geo.api.gouv.fr."""
        code_insee = query.get("code_insee")
        code_dept = query.get("code_departement")

        if code_dept:
            # Get department population from geo API
            try:
                response = await self._client.get(
                    f"https://geo.api.gouv.fr/departements/{code_dept}/communes",
                    params={"fields": "population"},
                )
                response.raise_for_status()
                communes = response.json()
                total_pop = sum(c.get("population", 0) for c in communes)

                return [{
                    "source": "insee_local",
                    "type": "population",
                    "niveau_geo": "DEP",
                    "code_geo": code_dept,
                    "authenticated": False,
                    "population_totale": total_pop,
                    "nombre_communes": len(communes),
                }]
            except httpx.HTTPError as e:
                self._log_error("get_population_fallback", e)

        if code_insee:
            try:
                response = await self._client.get(
                    f"https://geo.api.gouv.fr/communes/{code_insee}",
                    params={"fields": "nom,code,population,densité"},
                )
                response.raise_for_status()
                data = response.json()

                return [{
                    "source": "insee_local",
                    "type": "population",
                    "code_insee": data.get("code"),
                    "nom": data.get("nom"),
                    "population": data.get("population"),
                    "densite": data.get("densité"),
                    "authenticated": False,
                }]
            except httpx.HTTPError as e:
                self._log_error("get_population_fallback", e)

        return []

    def _extract_population_indicators(self, data: dict) -> dict[str, Any]:
        """Extract key population indicators from INSEE response."""
        indicators = {}

        # Parse INSEE response structure
        if "Cellule" in data:
            for cell in data.get("Cellule", []):
                mesure = cell.get("Mesure")
                valeur = cell.get("Valeur")
                if mesure and valeur:
                    indicators[mesure] = float(valeur) if valeur else 0

        return indicators

    async def _get_logement(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get housing data for a territory."""
        code_dept = query.get("code_departement")
        code_insee = query.get("code_insee")
        code_geo = code_dept or code_insee
        niveau_geo = "DEP" if code_dept else "COM"

        if not code_geo:
            return []

        # Try INSEE API for housing data (indicateur: LOG_G - Logements)
        endpoint = f"/donnees/geo-{code_geo}@{niveau_geo}/jeuDeDonnees/GEO2024LOG_G"
        data = await self._api_request(endpoint)

        if data:
            return [{
                "source": "insee_local",
                "type": "logement",
                "niveau_geo": niveau_geo,
                "code_geo": code_geo,
                "authenticated": True,
                "data": data,
                "indicateurs": self._extract_housing_indicators(data),
            }]

        # Fallback with available indicators
        return [{
            "source": "insee_local",
            "type": "logement",
            "code_geo": code_geo,
            "authenticated": False,
            "message": "Données logement disponibles sur statistiques-locales.insee.fr",
            "url": "https://statistiques-locales.insee.fr/#bbox=-578921,6022566,1693773,982604&c=indicator&i=desl.log_vac&s=2020&view=map2",
            "indicators_available": [
                "residences_principales",
                "residences_secondaires",
                "logements_vacants",
                "proprietaires",
                "locataires",
            ],
        }]

    def _extract_housing_indicators(self, data: dict) -> dict[str, Any]:
        """Extract key housing indicators from INSEE response."""
        indicators = {}
        if "Cellule" in data:
            for cell in data.get("Cellule", []):
                mesure = cell.get("Mesure")
                valeur = cell.get("Valeur")
                modalite = cell.get("Modalite")
                if mesure and valeur:
                    key = f"{mesure}_{modalite}" if modalite else mesure
                    indicators[key] = float(valeur) if valeur else 0
        return indicators

    async def _get_revenus(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get income data for a territory."""
        code_dept = query.get("code_departement")
        code_insee = query.get("code_insee")
        code_geo = code_dept or code_insee
        niveau_geo = "DEP" if code_dept else "COM"

        if not code_geo:
            return []

        # Try INSEE API for income data (indicateur: REV_G - Revenus)
        endpoint = f"/donnees/geo-{code_geo}@{niveau_geo}/jeuDeDonnees/GEO2024REV_G"
        data = await self._api_request(endpoint)

        if data:
            return [{
                "source": "insee_local",
                "type": "revenus",
                "niveau_geo": niveau_geo,
                "code_geo": code_geo,
                "authenticated": True,
                "data": data,
            }]

        return [{
            "source": "insee_local",
            "type": "revenus",
            "code_geo": code_geo,
            "authenticated": False,
            "message": "Données revenus sur statistiques-locales.insee.fr",
            "url": "https://statistiques-locales.insee.fr",
        }]

    async def _get_emploi(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get employment data for a territory."""
        code_dept = query.get("code_departement")
        code_insee = query.get("code_insee")
        code_geo = code_dept or code_insee
        niveau_geo = "DEP" if code_dept else "COM"

        if not code_geo:
            return []

        # Try INSEE API for employment data (indicateur: EMP_G - Emploi)
        endpoint = f"/donnees/geo-{code_geo}@{niveau_geo}/jeuDeDonnees/GEO2024EMP_G"
        data = await self._api_request(endpoint)

        if data:
            return [{
                "source": "insee_local",
                "type": "emploi",
                "niveau_geo": niveau_geo,
                "code_geo": code_geo,
                "authenticated": True,
                "data": data,
            }]

        return [{
            "source": "insee_local",
            "type": "emploi",
            "code_geo": code_geo,
            "authenticated": False,
            "message": "Données emploi via statistiques-locales.insee.fr",
            "url": "https://statistiques-locales.insee.fr",
        }]

    async def _get_dossier_complet(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Get complete statistical file for a commune."""
        code_insee = query.get("code_insee")

        return [{
            "source": "insee_local",
            "type": "dossier_complet",
            "code_insee": code_insee,
            "url": f"https://www.insee.fr/fr/statistiques/2011101?geo=COM-{code_insee}",
            "sections": ["population", "logement", "revenus", "emploi", "entreprises"],
        }]

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get all available data for a commune."""
        results = await self._get_population({"code_insee": id})
        return results[0] if results else None

    async def get_population(self, territory_code: str) -> dict[str, Any] | None:
        """Get population data for a territory (department or commune).

        Args:
            territory_code: 2-digit department code or 5-digit commune code

        Returns:
            Dict with population, densite, and other demographic data
        """
        try:
            # Determine if department or commune
            if len(territory_code) == 2:
                # Department - use geo API for basic data
                response = await self._client.get(
                    f"https://geo.api.gouv.fr/departements/{territory_code}",
                    params={"fields": "nom,code,codeRegion"},
                )
                response.raise_for_status()
                dept_data = response.json()

                # Get communes to calculate population
                communes_response = await self._client.get(
                    f"https://geo.api.gouv.fr/departements/{territory_code}/communes",
                    params={"fields": "nom,population,surface"},
                )
                communes_response.raise_for_status()
                communes = communes_response.json()

                total_pop = sum(c.get("population", 0) for c in communes)
                total_surface = sum(c.get("surface", 0) for c in communes) / 100  # ha to km2

                return {
                    "code": territory_code,
                    "nom": dept_data.get("nom"),
                    "population": total_pop,
                    "densite": total_pop / max(1, total_surface),
                    "surface_km2": total_surface,
                    "nb_communes": len(communes),
                }
            else:
                # Commune
                response = await self._client.get(
                    f"https://geo.api.gouv.fr/communes/{territory_code}",
                    params={"fields": "nom,population,surface,departement"},
                )
                response.raise_for_status()
                commune_data = response.json()

                pop = commune_data.get("population", 0)
                surface = commune_data.get("surface", 1) / 100  # ha to km2

                return {
                    "code": territory_code,
                    "nom": commune_data.get("nom"),
                    "population": pop,
                    "densite": pop / max(1, surface),
                    "surface_km2": surface,
                    "departement": commune_data.get("departement"),
                }

        except httpx.HTTPError as e:
            self._log_error("get_population", e)
            return None

    async def get_commune_profile(self, code_insee: str) -> dict[str, Any]:
        """Get complete profile for a commune combining multiple data sources."""
        try:
            response = await self._client.get(
                f"https://geo.api.gouv.fr/communes/{code_insee}",
                params={"fields": "nom,code,population,departement,region,codesPostaux,centre"},
            )
            response.raise_for_status()
            geo_data = response.json()

            return {
                "source": "insee_local",
                "code_insee": code_insee,
                "nom": geo_data.get("nom"),
                "population": geo_data.get("population"),
                "departement": geo_data.get("departement"),
                "region": geo_data.get("region"),
                "codes_postaux": geo_data.get("codesPostaux", []),
                "geo": {
                    "lat": geo_data.get("centre", {}).get("coordinates", [0, 0])[1],
                    "lon": geo_data.get("centre", {}).get("coordinates", [0, 0])[0],
                },
            }

        except httpx.HTTPError as e:
            self._log_error("get_commune_profile", e)
            return {"code_insee": code_insee, "error": str(e)}

    async def get_department_stats(self, code_dept: str) -> dict[str, Any]:
        """Get aggregated stats for a department with real INSEE data."""
        result = {
            "source": "insee_local",
            "type": "departement",
            "code": code_dept,
        }

        # Get basic info from geo API
        try:
            response = await self._client.get(
                f"https://geo.api.gouv.fr/departements/{code_dept}",
                params={"fields": "nom,code,codeRegion"},
            )
            response.raise_for_status()
            dept_data = response.json()
            result["nom"] = dept_data.get("nom")
            result["code_region"] = dept_data.get("codeRegion")
        except httpx.HTTPError as e:
            self._log_error("get_department_stats:geo", e)

        # Get population data from INSEE API
        pop_data = await self._get_population({"code_departement": code_dept})
        if pop_data and pop_data[0].get("authenticated"):
            result["population_data"] = pop_data[0].get("indicateurs", {})
            result["authenticated"] = True
        elif pop_data:
            result["population_totale"] = pop_data[0].get("population_totale")
            result["authenticated"] = False

        # Get employment data
        emp_data = await self._get_emploi({"code_departement": code_dept})
        if emp_data and emp_data[0].get("authenticated"):
            result["emploi_data"] = emp_data[0].get("data", {})

        return result

    async def get_unemployment_rate(self, code_dept: str) -> float | None:
        """Get unemployment rate for a department from INSEE data.

        Returns:
            Unemployment rate as percentage, or None if unavailable
        """
        # Try to get from bulk cache first
        all_rates = await self.get_all_unemployment_rates()
        if all_rates and code_dept in all_rates:
            return all_rates[code_dept]

        return None  # Not available without authenticated data

    async def get_all_unemployment_rates(self) -> dict[str, float]:
        """Get unemployment rates for ALL French departments from INSEE BDM API.

        Uses the TAUX-CHOMAGE dataflow from INSEE's BDM (Base de Données Macroéconomiques).
        Data is updated quarterly with a ~3 month delay.

        Returns:
            Dict mapping department codes (e.g., "75", "2A") to unemployment rates (%)
        """
        cache_key = "unemployment_rates_all"
        if cached := self._get_cache(cache_key):
            return cached

        token = await self._get_access_token()
        if not token:
            logger.warning("Cannot fetch unemployment rates: no INSEE OAuth2 token")
            return {}

        try:
            # Query BDM API for localized unemployment rates
            # TAUX-CHOMAGE dataflow with lastNObservations=1 gets the latest quarter
            url = "https://api.insee.fr/series/BDM/V1/data/TAUX-CHOMAGE"
            params = {"lastNObservations": "1"}
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/xml",  # SDMX format
            }

            response = await self._client.get(url, headers=headers, params=params)
            response.raise_for_status()

            # Parse SDMX XML response
            rates = self._parse_unemployment_sdmx(response.text)

            if rates:
                logger.info(f"Fetched real unemployment rates for {len(rates)} departments")
                self._set_cache(cache_key, rates)
                return rates

        except httpx.HTTPError as e:
            self._log_error("get_all_unemployment_rates", e)

        return {}

    def _parse_unemployment_sdmx(self, xml_text: str) -> dict[str, float]:
        """Parse SDMX XML from INSEE BDM to extract unemployment rates by department.

        The TAUX-CHOMAGE dataflow returns series with REF_AREA like "D75" for Paris.
        Each series has observations with TIME_PERIOD and OBS_VALUE.

        Args:
            xml_text: Raw SDMX XML response

        Returns:
            Dict mapping department codes to unemployment rates
        """
        import re

        rates: dict[str, float] = {}

        # Find all Series elements with REF_AREA starting with 'D' (departement)
        # Pattern: <Series ...REF_AREA="D75"...>...<Obs ...OBS_VALUE="6.1".../>...</Series>
        series_pattern = re.compile(
            r'<Series[^>]*REF_AREA="(D[0-9A-B]+)"[^>]*>.*?<Obs[^>]*OBS_VALUE="([0-9.]+)"',
            re.DOTALL
        )

        for match in series_pattern.finditer(xml_text):
            ref_area = match.group(1)  # e.g., "D75"
            obs_value = match.group(2)  # e.g., "6.1"

            # Convert D75 -> "75", D2A -> "2A", D971 -> "971"
            dept_code = ref_area[1:]  # Remove 'D' prefix

            try:
                rates[dept_code] = float(obs_value)
            except ValueError:
                logger.debug(f"Invalid unemployment value for {dept_code}: {obs_value}")

        return rates

    def _set_cache(self, key: str, value: Any) -> None:
        """Set a value in the adapter cache."""
        # Use module-level cache for simplicity (could use Redis in production)
        if not hasattr(self, "_local_cache"):
            self._local_cache = {}
            self._local_cache_timestamps = {}

        self._local_cache[key] = value
        self._local_cache_timestamps[key] = datetime.now()

    def _get_cache(self, key: str) -> Any | None:
        """Get a value from the adapter cache if still valid."""
        if not hasattr(self, "_local_cache"):
            return None

        if key not in self._local_cache:
            return None

        # Check TTL (unemployment data is quarterly, cache for 6 hours)
        timestamp = self._local_cache_timestamps.get(key)
        if timestamp:
            age_seconds = (datetime.now() - timestamp).total_seconds()
            if age_seconds < 21600:  # 6 hours
                return self._local_cache[key]

        return None

    async def health_check(self) -> bool:
        """Check if INSEE API is available and authenticated."""
        # Check OAuth2 authentication
        token = await self._get_access_token()
        if token:
            logger.info("INSEE API: OAuth2 authentication successful")
            return True

        # Fallback: check geo API
        try:
            response = await self._client.get(
                "https://geo.api.gouv.fr/communes",
                params={"nom": "Paris", "limit": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """INSEE data is updated annually (census)."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="INSEE data is updated annually with census",
        )
