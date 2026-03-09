"""France Travail adapter - French employment data (ex-Pôle Emploi).

OAuth2 Authentication:
    1. Register at https://francetravail.io/inscription
    2. Create an application to get client_id and client_secret
    3. Set environment variables:
       - FRANCE_TRAVAIL_CLIENT_ID
       - FRANCE_TRAVAIL_CLIENT_SECRET

Supported APIs (17 total):
    - Offres d'emploi v2 (10/s) - Job offers
    - ROME 4.0 Fiches métiers v1 (1/s) - Job descriptions
    - ROME 4.0 Métiers v1 (1/s) - Job codes
    - ROME 4.0 Compétences v1 (1/s) - Skills
    - ROME 4.0 Contextes de travail v1 (1/s) - Work contexts
    - Marché du travail v1 (10/s) - Job market stats
    - La Bonne Boite v2 (2/s) - Hidden job market
    - Cadre de vie des communes v1 (2/s) - Quality of life
    - Informations sur un territoire v1 (10/s) - Territory info
    - ROMEO v2 (3/s) - AI job matching
    - Anotéa v1 (8/s) - Training reviews
    - Open Formation v1 (10/s) - Training offers
    - Sortants de formation v1 (10/s) - Training outcomes
    - Accès à l'emploi v1 (10/s) - Employment access
    - Référentiel des agences v1 (1/s) - Agency locations
    - Synthèse Pages employeurs v1 (50/s) - Employer pages
    - Mes évènements emploi v1 (10/s) - Employment events
"""

import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class FranceTravailAdapter(BaseAdapter):
    """Adapter for France Travail API (francetravail.io).

    API Documentation: https://francetravail.io/data/api

    Provides comprehensive French employment data:
    - Job offers and market statistics
    - ROME 4.0 taxonomy (métiers, compétences, contextes)
    - Territory analysis (quality of life, employment access)
    - AI matching (ROMEO, La Bonne Boite)
    - Training (formations, sortants, Anotéa reviews)
    - Agency locations and employer pages

    Authentication: OAuth2 Client Credentials flow
    Token endpoint: https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire
    """

    # OAuth2 configuration
    TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"

    # API scopes mapping (API name -> required scopes)
    # Use FRANCE_TRAVAIL_SCOPES env var to override
    API_SCOPES = {
        "offres": "api_offresdemploiv2 o2dsoffre",
        "rome_fiches": "api_rome-fiches-metiersv1 nomenclatureRome",
        "rome_metiers": "api_rome-metiersv1 nomenclatureRome",
        "rome_competences": "api_rome-competencesv1 nomenclatureRome",
        "rome_contextes": "api_rome-contextes-travailv1 nomenclatureRome",
        "marche_travail": "api_marche-travailv1",
        "la_bonne_boite": "api_labonneboitev2 labonneboite",
        "cadre_vie": "api_cadrevi-communesv1",
        "territoire": "api_infotravail-territoirev1",
        "romeo": "api_romeov2",
        "anotea": "api_anoteav1",
        "formation": "api_openformationv1",
        "sortants": "api_sortformav1",
        "acces_emploi": "api_accesemploiv1",
        "agences": "api_referenagencesv1",
        "employeurs": "api_synthpageemployeursv1",
        "evenements": "api_mesevtemploi",
    }

    # Working scopes (validated through OAuth2 token tests)
    # Note: New APIs (marche-travail, labonneboite, etc.) require subscription on francetravail.io
    DEFAULT_SCOPES = " ".join([
        # Offres d'emploi v2 ✅
        "api_offresdemploiv2", "o2dsoffre",
        # ROME 4.0 (all 4 APIs) ✅
        "api_rome-fiches-metiersv1", "nomenclatureRome",
        "api_rome-metiersv1",
        "api_rome-competencesv1",
        "api_rome-contextes-travailv1",
        # ROMEO AI matching ✅
        "api_romeov2",
        # Open Formation ✅
        "api_openformationv1",
        # Anotéa reviews ✅
        "api_anoteav1",
        # La Bonne Boîte v2 ✅ (validated 2026-02-06)
        "api_labonneboitev2",
        # Référentiel agences ✅ (validated 2026-02-06)
        "api_referentielagencesv1",
        # Synthèse pages employeurs ✅ (validated 2026-02-06)
        "api_synthese-pages-employeursv1",
        # TODO: Find correct scope names for these (subscribed but scope unknown):
        # - Marché du travail v1
        # - Informations territoire v1
        # - Cadre de vie communes v1
        # - Sortants formation v1
        # - Accès emploi v1
        # - Mes évènements emploi v1
    ])

    def __init__(
        self,
        config: AdapterConfig | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Initialize the France Travail adapter.

        Args:
            config: Adapter configuration. If None, uses defaults.
            client_id: OAuth2 client ID. Falls back to FRANCE_TRAVAIL_CLIENT_ID env var.
            client_secret: OAuth2 client secret. Falls back to FRANCE_TRAVAIL_CLIENT_SECRET env var.
        """
        if config is None:
            config = AdapterConfig(
                name="france_travail",
                base_url="https://api.francetravail.io/partenaire",
                rate_limit=30,
                cache_ttl=3600,  # 1h - employment data updates frequently
                timeout=30,
            )
        super().__init__(config)

        # OAuth2 credentials
        self._client_id = client_id or os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

        # Load scopes from env or use defaults
        self._scopes = os.getenv("FRANCE_TRAVAIL_SCOPES", self.DEFAULT_SCOPES)

        # Open data endpoints (no auth required)
        self._open_data_url = "https://www.data.gouv.fr/api/1/datasets"
        self._dares_url = "https://dares.travail-emploi.gouv.fr"

    @property
    def has_credentials(self) -> bool:
        """Check if OAuth2 credentials are configured."""
        return bool(self._client_id and self._client_secret)

    async def _get_access_token(self) -> str | None:
        """Get OAuth2 access token using client credentials flow.

        Returns:
            Access token string or None if authentication fails.
        """
        if not self.has_credentials:
            logger.warning("France Travail: No OAuth2 credentials configured")
            return None

        # Check if token is still valid (with 60s buffer)
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token

        try:
            response = await self._client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": self._scopes,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 1500)  # Default 25 minutes
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            logger.info(f"France Travail: OAuth2 token obtained, expires in {expires_in}s")
            return self._access_token

        except httpx.HTTPError as e:
            logger.error(f"France Travail: OAuth2 token error: {e}")
            return None

    async def _authenticated_request(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response | None:
        """Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional httpx request arguments

        Returns:
            Response object or None if authentication failed.
        """
        token = await self._get_access_token()
        if not token:
            return None

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as e:
            self._log_error(f"authenticated_request {method} {url}", e)
            return None

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search employment data.

        Args:
            query: Search parameters
                - type: 'marche_travail', 'tensions', 'agences', 'rome'
                - code_insee: Commune INSEE code
                - code_departement: Department code
                - code_region: Region code
                - rome: ROME code (métier)
                - limit: Max results (default 50)

        Returns:
            List of employment data records
        """
        data_type = query.get("type", "marche_travail")

        if data_type == "marche_travail":
            return await self._search_marche_travail(query)
        elif data_type == "tensions":
            return await self._search_tensions(query)
        elif data_type == "agences":
            return await self._search_agences(query)
        elif data_type == "rome":
            return await self._search_rome(query)
        else:
            self._log_error("search", ValueError(f"Unknown type: {data_type}"))
            return []

    async def _search_marche_travail(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search job offers by territory (authenticated endpoint).

        Uses the Offres d'emploi API v2.
        """
        if not self.has_credentials:
            return [{
                "source": "france_travail",
                "type": "marche_travail",
                "error": "OAuth2 credentials required",
                "setup": "Set FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET",
                "registration": "https://francetravail.io/inscription",
            }]

        params = {"range": f"0-{query.get('limit', 50) - 1}"}

        # Location filters
        if code_dept := query.get("code_departement"):
            params["departement"] = code_dept
        if code_commune := query.get("code_insee"):
            params["commune"] = code_commune

        # Job filters
        if rome := query.get("rome"):
            params["codeROME"] = rome
        if motscles := query.get("motscles"):
            params["motsCles"] = motscles

        # Contract type
        if type_contrat := query.get("type_contrat"):
            params["typeContrat"] = type_contrat

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/offresdemploi/v2/offres/search",
            params=params,
        )

        if not response:
            return []

        data = response.json()
        resultats = data.get("resultats", [])
        return [self._transform_offre(o) for o in resultats]

    async def _search_tensions(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search job tensions (métiers en tension) by territory."""
        # Métiers en tension data from BMO (Besoins en Main d'Oeuvre)
        params = {}
        if code_dept := query.get("code_departement"):
            params["codeDepartement"] = code_dept
        if rome := query.get("rome"):
            params["codeRome"] = rome

        return [{
            "source": "france_travail",
            "type": "tensions",
            "message": "Use BMO survey data for job tensions",
            "url": "https://statistiques.pole-emploi.org/bmo",
        }]

    async def _search_agences(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search France Travail agencies."""
        params = {"range": f"0-{query.get('limit', 50)}"}
        if code_dept := query.get("code_departement"):
            params["codeDepartement"] = code_dept
        if code_commune := query.get("code_insee"):
            params["codeCommune"] = code_commune

        data = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/referentiel-agences/v1/agences",
            params=params,
        )

        if data:
            return [self._transform_agence(a) for a in data]
        return []

    async def _search_rome(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search ROME codes (métiers)."""
        params = {}
        if libelle := query.get("libelle"):
            params["champ"] = "libelle"
            params["q"] = libelle

        try:
            response = await self._client.get(
                f"{self.config.base_url}/offresdemploi/v2/referentiel/metiers",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [self._transform_rome(r) for r in data]

        except httpx.HTTPError as e:
            self._log_error("search_rome", e)
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get ROME métier by code.

        Args:
            id: ROME code (e.g., 'M1805')

        Returns:
            Métier data or None
        """
        try:
            response = await self._client.get(
                f"{self.config.base_url}/offresdemploi/v2/referentiel/metiers",
                params={"champ": "code", "q": id},
            )
            response.raise_for_status()
            data = response.json()

            if data:
                return self._transform_rome(data[0])
            return None

        except httpx.HTTPError as e:
            self._log_error("get_by_id", e)
            return None

    async def get_stats_departement(self, code_dept: str) -> dict[str, Any]:
        """Get employment statistics for a department.

        Args:
            code_dept: Department code

        Returns:
            Employment statistics
        """
        # Get agencies count as proxy for employment activity
        agences = await self._search_agences({"code_departement": code_dept, "limit": 100})

        return {
            "source": "france_travail",
            "code_departement": code_dept,
            "nombre_agences": len(agences),
            "agences": agences[:5],  # Top 5 agencies
            "data_source": "Pour les statistiques détaillées, consultez DARES",
            "url_dares": "https://dares.travail-emploi.gouv.fr/dossier/open-data",
        }

    async def get_metiers_tension(self, code_dept: str | None = None) -> list[dict[str, Any]]:
        """Get métiers en tension (high-demand jobs).

        Args:
            code_dept: Optional department filter

        Returns:
            List of high-demand jobs
        """
        # This would require BMO data access
        return [{
            "source": "france_travail",
            "type": "metiers_tension",
            "message": "Consultez l'enquête BMO pour les métiers en tension",
            "url": "https://statistiques.pole-emploi.org/bmo",
        }]

    async def search_offres(
        self,
        departement: str | None = None,
        commune: str | None = None,
        rome: str | None = None,
        motscles: str | None = None,
        type_contrat: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search job offers (convenience method).

        Args:
            departement: Department code (e.g., '75')
            commune: Commune INSEE code
            rome: ROME code (e.g., 'M1805' for data analyst)
            motscles: Keywords to search
            type_contrat: Contract type (CDI, CDD, etc.)
            limit: Max results (default 50)

        Returns:
            List of job offers
        """
        return await self.search({
            "type": "marche_travail",
            "code_departement": departement,
            "code_insee": commune,
            "rome": rome,
            "motscles": motscles,
            "type_contrat": type_contrat,
            "limit": limit,
        })

    async def health_check(self) -> bool:
        """Check if France Travail API is available.

        Returns True if:
        - Credentials configured AND OAuth2 token can be obtained, OR
        - Open referentiel endpoint responds (fallback)
        """
        # Try OAuth2 first if credentials available
        if self.has_credentials:
            token = await self._get_access_token()
            if token:
                return True

        # Fallback: check open referentiel endpoint
        try:
            response = await self._client.get(
                f"{self.config.base_url}/offresdemploi/v2/referentiel/metiers",
                params={"champ": "libelle", "q": "test"},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """France Travail data updates daily."""
        return SyncStatus(
            adapter_name=self.name,
            last_sync=None,
            records_synced=0,
            status="not_supported",
            error="France Travail real-time data requires API key",
        )

    def _transform_agence(self, agence: dict) -> dict[str, Any]:
        """Transform agency data to standard format."""
        adresse = agence.get("adresse", {})
        contact = agence.get("contact", {})

        return {
            "source": "france_travail",
            "type": "agence",
            "code": agence.get("code"),
            "nom": agence.get("libelle"),
            "type_agence": agence.get("typeAgence"),
            "adresse": {
                "ligne1": adresse.get("ligne1"),
                "ligne2": adresse.get("ligne2"),
                "code_postal": adresse.get("codePostal"),
                "commune": adresse.get("commune"),
            },
            "contact": {
                "telephone": contact.get("telephonePublic"),
                "email": contact.get("email"),
            },
            "geo": {
                "lat": agence.get("latitude"),
                "lon": agence.get("longitude"),
            },
            "raw": agence,
        }

    def _transform_rome(self, rome: dict) -> dict[str, Any]:
        """Transform ROME métier data to standard format."""
        return {
            "source": "france_travail",
            "type": "rome",
            "code": rome.get("code"),
            "libelle": rome.get("libelle"),
            "raw": rome,
        }

    def _transform_offre(self, offre: dict) -> dict[str, Any]:
        """Transform job offer data to standard format."""
        lieu = offre.get("lieuTravail", {})
        entreprise = offre.get("entreprise", {})
        salaire = offre.get("salaire", {})
        contrat = offre.get("typeContrat")

        return {
            "source": "france_travail",
            "type": "offre",
            "id": offre.get("id"),
            "intitule": offre.get("intitule"),
            "description": offre.get("description"),
            "date_creation": offre.get("dateCreation"),
            "date_actualisation": offre.get("dateActualisation"),
            "lieu": {
                "libelle": lieu.get("libelle"),
                "code_postal": lieu.get("codePostal"),
                "commune": lieu.get("commune"),
                "code_insee": lieu.get("codeInsee"),
                "departement": lieu.get("departement"),
                "region": lieu.get("region"),
                "lat": lieu.get("latitude"),
                "lon": lieu.get("longitude"),
            },
            "entreprise": {
                "nom": entreprise.get("nom"),
                "description": entreprise.get("description"),
                "logo": entreprise.get("logo"),
                "url": entreprise.get("url"),
            },
            "contrat": {
                "type": contrat,
                "libelle": offre.get("typeContratLibelle"),
                "nature": offre.get("natureContrat"),
                "duree": offre.get("dureeTravailLibelle"),
            },
            "salaire": {
                "libelle": salaire.get("libelle"),
                "commentaire": salaire.get("commentaire"),
            },
            "experience": {
                "libelle": offre.get("experienceLibelle"),
                "exigence": offre.get("experienceExigence"),
            },
            "competences": [
                {"libelle": c.get("libelle"), "exigence": c.get("exigence")}
                for c in offre.get("competences", [])
            ],
            "rome": {
                "code": offre.get("romeCode"),
                "libelle": offre.get("romeLibelle"),
            },
            "url": offre.get("origineOffre", {}).get("urlOrigine"),
            "raw": offre,
        }

    # =========================================================================
    # ROME 4.0 APIs
    # =========================================================================

    async def get_rome_fiche(self, code_rome: str) -> dict[str, Any] | None:
        """Get detailed ROME 4.0 job description (fiche métier).

        Args:
            code_rome: ROME code (e.g., 'M1805')

        Returns:
            Detailed job description with tasks, skills, conditions

        Note:
            Rate limit: 1 call/second for ROME 4.0 APIs
        """
        # Correct endpoint: /rome-fiches-metiers/v1/fichesMetiers/{code}
        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/rome-fiches-metiers/v1/fichesMetiers/{code_rome}",
        )
        if not response:
            return None

        data = response.json()
        return {
            "source": "france_travail",
            "type": "rome_fiche",
            "code": code_rome,
            "data": data,
        }

    async def get_rome_competences(
        self, code_rome: str | None = None, libelle: str | None = None
    ) -> list[dict[str, Any]]:
        """Search ROME 4.0 competences (skills).

        Args:
            code_rome: Filter by ROME code
            libelle: Search by skill name

        Returns:
            List of competences with codes and descriptions
        """
        params = {}
        if code_rome:
            params["codeRome"] = code_rome
        if libelle:
            params["libelle"] = libelle

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/rome-competences/v1/competences",
            params=params,
        )
        if not response:
            return []

        data = response.json()
        return [
            {
                "source": "france_travail",
                "type": "competence",
                "code": c.get("code"),
                "libelle": c.get("libelle"),
                "type_competence": c.get("typeCompetence"),
                "raw": c,
            }
            for c in data
        ]

    async def get_rome_contextes(self, code_rome: str) -> list[dict[str, Any]]:
        """Get ROME 4.0 work contexts for a job.

        Args:
            code_rome: ROME code

        Returns:
            List of work contexts (conditions, environments)
        """
        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/rome-contextes-travail/v1/contextes/{code_rome}",
        )
        if not response:
            return []

        data = response.json()
        return [
            {
                "source": "france_travail",
                "type": "contexte_travail",
                "code": c.get("code"),
                "libelle": c.get("libelle"),
                "raw": c,
            }
            for c in (data if isinstance(data, list) else [data])
        ]

    # =========================================================================
    # Marché du Travail API
    # =========================================================================

    async def get_marche_travail_stats(
        self,
        code_departement: str | None = None,
        code_region: str | None = None,
        code_rome: str | None = None,
    ) -> dict[str, Any]:
        """Get job market statistics for a territory.

        Args:
            code_departement: Department code
            code_region: Region code
            code_rome: ROME code for specific job

        Returns:
            Employment statistics: offers, demands, tensions
        """
        params = {}
        if code_departement:
            params["codeDepartement"] = code_departement
        if code_region:
            params["codeRegion"] = code_region
        if code_rome:
            params["codeRome"] = code_rome

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/marche-travail/v1/statistiques",
            params=params,
        )
        if not response:
            return {"source": "france_travail", "type": "marche_travail", "error": "API unavailable"}

        data = response.json()
        return {
            "source": "france_travail",
            "type": "marche_travail_stats",
            "territoire": code_departement or code_region or "France",
            "data": data,
        }

    # =========================================================================
    # La Bonne Boite API - Hidden Job Market
    # =========================================================================

    async def search_la_bonne_boite(
        self,
        latitude: float,
        longitude: float,
        rome: str,
        distance: int = 30,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search companies likely to hire (hidden job market).

        Args:
            latitude: Location latitude
            longitude: Location longitude
            rome: ROME code for job type
            distance: Search radius in km (default 30)
            limit: Max results (default 20)

        Returns:
            List of companies with hiring probability
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "rome": rome,
            "distance": distance,
            "limit": limit,
        }

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/labonneboite/v2/companies",
            params=params,
        )
        if not response:
            return []

        data = response.json()
        companies = data.get("companies", [])
        return [
            {
                "source": "france_travail",
                "type": "la_bonne_boite",
                "siret": c.get("siret"),
                "nom": c.get("name"),
                "naf": c.get("naf"),
                "effectif": c.get("headcount"),
                "score_embauche": c.get("score"),
                "distance_km": c.get("distance"),
                "adresse": {
                    "rue": c.get("address"),
                    "ville": c.get("city"),
                    "code_postal": c.get("zipcode"),
                },
                "geo": {
                    "lat": c.get("latitude"),
                    "lon": c.get("longitude"),
                },
                "contact": {
                    "email": c.get("email"),
                    "telephone": c.get("phone"),
                    "url": c.get("website"),
                },
                "raw": c,
            }
            for c in companies
        ]

    # =========================================================================
    # Cadre de Vie API - Quality of Life
    # =========================================================================

    async def get_cadre_vie(self, code_commune: str) -> dict[str, Any] | None:
        """Get quality of life indicators for a commune.

        Args:
            code_commune: INSEE commune code

        Returns:
            Quality of life data: services, transport, environment
        """
        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/cadre-vie-communes/v1/communes/{code_commune}",
        )
        if not response:
            return None

        data = response.json()
        return {
            "source": "france_travail",
            "type": "cadre_vie",
            "code_commune": code_commune,
            "indicateurs": data,
        }

    # =========================================================================
    # Informations Territoire API
    # =========================================================================

    async def get_infos_territoire(
        self,
        code_departement: str | None = None,
        code_region: str | None = None,
    ) -> dict[str, Any]:
        """Get territory employment information.

        Args:
            code_departement: Department code
            code_region: Region code

        Returns:
            Territory info: employment, demographics, economy
        """
        params = {}
        if code_departement:
            params["codeDepartement"] = code_departement
        if code_region:
            params["codeRegion"] = code_region

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/infotravail-territoire/v1/territoires",
            params=params,
        )
        if not response:
            return {"source": "france_travail", "type": "territoire", "error": "API unavailable"}

        data = response.json()
        return {
            "source": "france_travail",
            "type": "infos_territoire",
            "territoire": code_departement or code_region or "France",
            "data": data,
        }

    # =========================================================================
    # ROMEO API - AI Job Matching
    # =========================================================================

    async def get_romeo_matching(
        self, texte: str, nb_resultats: int = 10
    ) -> list[dict[str, Any]]:
        """AI-powered job matching from free text (CV, description).

        Args:
            texte: Free text to analyze (CV, job description)
            nb_resultats: Number of matches to return

        Returns:
            List of matching ROME codes with confidence scores
        """
        response = await self._authenticated_request(
            "POST",
            f"{self.config.base_url}/romeo/v2/predict",
            json={"texte": texte, "nbResultats": nb_resultats},
        )
        if not response:
            return []

        data = response.json()
        predictions = data.get("predictions", [])
        return [
            {
                "source": "france_travail",
                "type": "romeo_matching",
                "code_rome": p.get("codeRome"),
                "libelle_rome": p.get("libelleRome"),
                "score": p.get("score"),
                "raw": p,
            }
            for p in predictions
        ]

    # =========================================================================
    # Formation APIs
    # =========================================================================

    async def search_formations(
        self,
        code_departement: str | None = None,
        code_rome: str | None = None,
        motscles: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search training offers (Open Formation API).

        Args:
            code_departement: Department code
            code_rome: Target ROME code
            motscles: Keywords
            limit: Max results

        Returns:
            List of training offers
        """
        params = {"range": f"0-{limit - 1}"}
        if code_departement:
            params["codeDepartement"] = code_departement
        if code_rome:
            params["codeRome"] = code_rome
        if motscles:
            params["motsCles"] = motscles

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/open-formation/v1/formations",
            params=params,
        )
        if not response:
            return []

        data = response.json()
        formations = data.get("resultats", []) if isinstance(data, dict) else data
        return [
            {
                "source": "france_travail",
                "type": "formation",
                "id": f.get("id"),
                "intitule": f.get("intitule"),
                "organisme": f.get("organisme"),
                "lieu": f.get("lieuFormation"),
                "date_debut": f.get("dateDebut"),
                "duree": f.get("duree"),
                "objectif": f.get("objectif"),
                "raw": f,
            }
            for f in formations
        ]

    async def get_anotea_formations(
        self, items_per_page: int = 20, page: int = 0
    ) -> list[dict[str, Any]]:
        """Get training formations with Anotéa reviews.

        Args:
            items_per_page: Number of results per page
            page: Page number (0-indexed)

        Returns:
            List of formations with review scores
        """
        params = {
            "items_par_page": items_per_page,
            "page": page,
        }

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/anotea/v1/formations",
            params=params,
        )
        if not response:
            return []

        data = response.json()
        formations = data.get("formations", []) if isinstance(data, dict) else data
        return [
            {
                "source": "france_travail",
                "type": "anotea_formation",
                "intitule": f.get("intitule"),
                "organisme": f.get("organisme"),
                "lieu": f.get("lieu"),
                "score": f.get("score", {}),
                "nb_avis": f.get("score", {}).get("nb_avis", 0),
                "raw": f,
            }
            for f in formations
        ]

    # =========================================================================
    # Accès Emploi API
    # =========================================================================

    async def get_acces_emploi(
        self, code_departement: str | None = None, code_rome: str | None = None
    ) -> dict[str, Any]:
        """Get employment access statistics.

        Args:
            code_departement: Department code
            code_rome: ROME code

        Returns:
            Employment access data: insertion rates, durations
        """
        params = {}
        if code_departement:
            params["codeDepartement"] = code_departement
        if code_rome:
            params["codeRome"] = code_rome

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/acces-emploi/v1/statistiques",
            params=params,
        )
        if not response:
            return {"source": "france_travail", "type": "acces_emploi", "error": "API unavailable"}

        data = response.json()
        return {
            "source": "france_travail",
            "type": "acces_emploi",
            "territoire": code_departement or "France",
            "data": data,
        }

    # =========================================================================
    # Événements Emploi API
    # =========================================================================

    async def search_evenements(
        self,
        code_departement: str | None = None,
        date_debut: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search employment events (job fairs, workshops).

        Args:
            code_departement: Department code
            date_debut: Start date (YYYY-MM-DD)
            limit: Max results

        Returns:
            List of employment events
        """
        params = {"range": f"0-{limit - 1}"}
        if code_departement:
            params["codeDepartement"] = code_departement
        if date_debut:
            params["dateDebut"] = date_debut

        response = await self._authenticated_request(
            "GET",
            f"{self.config.base_url}/evenements-emploi/v1/evenements",
            params=params,
        )
        if not response:
            return []

        data = response.json()
        evenements = data.get("evenements", []) if isinstance(data, dict) else data
        return [
            {
                "source": "france_travail",
                "type": "evenement_emploi",
                "id": e.get("id"),
                "titre": e.get("titre"),
                "description": e.get("description"),
                "date": e.get("dateEvenement"),
                "lieu": e.get("lieu"),
                "organisateur": e.get("organisateur"),
                "url": e.get("url"),
                "raw": e,
            }
            for e in evenements
        ]
