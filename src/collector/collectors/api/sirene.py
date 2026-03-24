"""SIRENE collector - Enterprise creation/closure signals via INSEE API.

Uses two sources:
1. recherche-entreprises.api.gouv.fr (FREE, no auth, limited filtering)
2. api.insee.fr SIRENE 3.11 (OAuth2, full filtering)  -  needs active subscription

Token endpoint migrated (2024):
  OLD: https://api.insee.fr/token
  NEW: https://auth.insee.net/auth/realms/apim-gravitee/protocol/openid-connect/token
"""

import os
from datetime import date, timedelta

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

# Free API (no auth needed)
FREE_API = "https://recherche-entreprises.api.gouv.fr"

# Full SIRENE API (OAuth2)
SIRENE_API = "https://api.insee.fr/api-sirene/3.11"
TOKEN_ENDPOINT = "https://auth.insee.net/auth/realms/apim-gravitee/protocol/openid-connect/token"


class SireneCollector(BaseCollector):
    """Collect enterprise creation and closure signals from SIRENE/INSEE.

    Detects:
    - New enterprise creations by commune/department
    - Enterprise closures (radiations)
    - Sector-specific movements (NAF codes)

    Falls back to free API if OAuth2 credentials unavailable or subscription expired.
    """

    def __init__(self, bearer_token: str | None = None) -> None:
        super().__init__(
            CollectorConfig(
                name="sirene",
                source_type="api",
                rate_limit=7,  # INSEE allows ~7 req/s
                timeout=30,
            )
        )
        self._bearer_token = bearer_token
        self._use_free_api = bearer_token is None

    async def _get_oauth_token(self) -> str | None:
        """Get OAuth2 token from new INSEE endpoint."""
        client_id = os.getenv("INSEE_CLIENT_ID")
        client_secret = os.getenv("INSEE_CLIENT_SECRET")
        if not client_id or not client_secret:
            logger.debug("[sirene] No INSEE credentials, using free API")
            return None

        try:
            response = await self._request_with_retry(
                "POST",
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response and response.status_code == 200:
                token = response.json().get("access_token")
                logger.info("[sirene] OAuth2 token obtained from auth.insee.net")
                return token
            else:
                logger.warning(
                    f"[sirene] OAuth2 failed ({response.status_code if response else 'no response'}), falling back to free API"
                )
                return None
        except Exception as e:
            logger.warning(f"[sirene] OAuth2 error: {e}, falling back to free API")
            return None

    async def _get_client(self):
        client = await super()._get_client()
        if self._bearer_token:
            client.headers["Authorization"] = f"Bearer {self._bearer_token}"
        return client

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect SIRENE signals (creations + closures)."""
        if since is None:
            since = date.today() - timedelta(days=7)

        # Try OAuth2 if no token yet
        if not self._bearer_token and not self._use_free_api:
            self._bearer_token = await self._get_oauth_token()
            if not self._bearer_token:
                self._use_free_api = True

        # Use free API if no valid token
        if self._use_free_api:
            return await self._collect_free_api(code_dept, since)

        signals = []
        signals.extend(await self._collect_creations(code_dept, since))
        signals.extend(await self._collect_closures(code_dept, since))
        return signals

    async def _collect_free_api(self, code_dept: str | None, since: date) -> list[CollectedSignal]:
        """Collect from free recherche-entreprises API (no auth needed).

        Limited: can search by NAF code + department but no date filtering.
        Strategy: query active enterprises by key NAF codes per department.
        """
        signals: list[CollectedSignal] = []

        # Key NAF codes for territorial intelligence
        naf_queries = [
            ("56.10A", "Restauration traditionnelle"),
            ("47.11D", "Supérettes"),
            ("86.21Z", "Médecins généralistes"),
            ("85.20Z", "Enseignement primaire"),
        ]

        for naf, label in naf_queries:
            try:
                params = {"activite_principale": naf, "per_page": 25, "page": 1}
                if code_dept:
                    params["departement"] = code_dept

                response = await self._request_with_retry(
                    "GET", f"{FREE_API}/search", params=params
                )
                if not response or response.status_code != 200:
                    continue

                data = response.json()
                results = data.get("results", [])
                total = data.get("total_results", 0)

                signals.append(
                    CollectedSignal(
                        source="sirene",
                        source_url=f"{FREE_API}/search?activite_principale={naf}&departement={code_dept}",
                        event_date=date.today(),
                        code_dept=code_dept,
                        code_commune=None,
                        metric_name=f"entreprises_actives_{naf}",
                        metric_value=float(total),
                        signal_type="neutre",
                        confidence=0.85,
                        raw_data={
                            "naf": naf,
                            "label": label,
                            "total": total,
                            "sample_size": len(results),
                        },
                    )
                )
                logger.debug(f"[sirene-free] {code_dept} NAF {naf}: {total} entreprises")

            except Exception as e:
                logger.warning(f"[sirene-free] Error on NAF {naf}: {e}")

        logger.info(f"[sirene-free] {code_dept}: {len(signals)} signals collected")
        return signals

    async def _collect_creations(self, code_dept: str | None, since: date) -> list[CollectedSignal]:
        """Collect new enterprise creations."""
        # Build SIRENE query filter
        q_parts = [f"dateCreationEtablissement:[{since.isoformat()} TO *]"]
        if code_dept:
            q_parts.append(f"codeCommuneEtablissement:{code_dept}*")

        params = {
            "q": " AND ".join(q_parts),
            "nombre": 1000,
            "champs": "siren,siret,dateCreationEtablissement,activitePrincipaleEtablissement,"
            "codeCommuneEtablissement,denominationUniteLegale,trancheEffectifsEtablissement",
        }

        response = await self._request_with_retry("GET", f"{self.BASE_URL}/siret", params=params)
        if not response:
            return []

        data = response.json()
        etablissements = data.get("etablissements", [])
        logger.info(f"[sirene] Found {len(etablissements)} new creations since {since}")

        signals = []
        for etab in etablissements:
            commune = etab.get("adresseEtablissement", {}).get("codeCommuneEtablissement", "")
            signals.append(
                CollectedSignal(
                    source="sirene",
                    source_url=f"sirene:{etab.get('siret', '')}",
                    event_date=_parse_date(etab.get("dateCreationEtablissement")),
                    code_commune=commune,
                    code_dept=commune[:2] if len(commune) >= 2 else code_dept,
                    metric_name="creation_entreprise",
                    metric_value=1.0,
                    signal_type="positif",
                    confidence=0.9,
                    raw_data={
                        "siren": etab.get("siren"),
                        "siret": etab.get("siret"),
                        "naf": etab.get("activitePrincipaleEtablissement"),
                        "denomination": etab.get("uniteLegale", {}).get("denominationUniteLegale"),
                        "effectif": etab.get("trancheEffectifsEtablissement"),
                    },
                )
            )
        return signals

    async def _collect_closures(self, code_dept: str | None, since: date) -> list[CollectedSignal]:
        """Collect enterprise closures (radiations)."""
        q_parts = [
            f"dateFin:[{since.isoformat()} TO *]",
            "etatAdministratifEtablissement:F",  # Fermé
        ]
        if code_dept:
            q_parts.append(f"codeCommuneEtablissement:{code_dept}*")

        params = {
            "q": " AND ".join(q_parts),
            "nombre": 1000,
            "champs": "siren,siret,dateFin,activitePrincipaleEtablissement,"
            "codeCommuneEtablissement,denominationUniteLegale",
        }

        response = await self._request_with_retry("GET", f"{self.BASE_URL}/siret", params=params)
        if not response:
            return []

        data = response.json()
        etablissements = data.get("etablissements", [])
        logger.info(f"[sirene] Found {len(etablissements)} closures since {since}")

        signals = []
        for etab in etablissements:
            commune = etab.get("adresseEtablissement", {}).get("codeCommuneEtablissement", "")
            signals.append(
                CollectedSignal(
                    source="sirene",
                    source_url=f"sirene:{etab.get('siret', '')}",
                    event_date=_parse_date(etab.get("dateFin")),
                    code_commune=commune,
                    code_dept=commune[:2] if len(commune) >= 2 else code_dept,
                    metric_name="fermeture_entreprise",
                    metric_value=1.0,
                    signal_type="negatif",
                    confidence=0.9,
                    raw_data={
                        "siren": etab.get("siren"),
                        "siret": etab.get("siret"),
                        "naf": etab.get("activitePrincipaleEtablissement"),
                        "denomination": etab.get("uniteLegale", {}).get("denominationUniteLegale"),
                    },
                )
            )
        return signals


def _parse_date(date_str: str | None) -> date | None:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except (ValueError, TypeError):
        return None
