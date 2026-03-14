"""France Travail collector - Employment signals from offres d'emploi API."""

import os
from datetime import date, timedelta
from typing import Any

import httpx
from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig


class FranceTravailCollector(BaseCollector):
    """Collect employment signals from France Travail API.

    Detects:
    - Job offer volume changes by department
    - Sector-specific hiring trends
    - Contract type distribution shifts
    """

    TOKEN_URL = (
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
    )
    BASE_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        super().__init__(
            CollectorConfig(
                name="france_travail",
                source_type="api",
                rate_limit=10,
                timeout=30,
            )
        )
        self._client_id = client_id or os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")
        self._access_token: str | None = None

    async def _authenticate(self) -> bool:
        """Get OAuth2 access token."""
        if not self._client_id or not self._client_secret:
            logger.error("[france_travail] Missing credentials")
            return False

        client = await self._get_client()
        try:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "api_offresdemploiv2 o2dsoffre",
                },
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            return True
        except Exception as e:
            logger.error(f"[france_travail] Auth failed: {e}")
            return False

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect job offer signals by department."""
        if not await self._authenticate():
            return []

        if since is None:
            since = date.today() - timedelta(days=7)

        signals = []

        # Collect offers for department
        # Note: minCreationDate and maxCreationDate are co-dependent
        params: dict[str, Any] = {
            "minCreationDate": f"{since.isoformat()}T00:00:00Z",
            "maxCreationDate": f"{date.today().isoformat()}T23:59:59Z",
            "range": "0-149",
        }
        if code_dept:
            params["departement"] = code_dept

        client = await self._get_client()
        client.headers["Authorization"] = f"Bearer {self._access_token}"

        response = await self._request_with_retry(
            "GET", f"{self.BASE_URL}/offres/search", params=params
        )
        if not response:
            return []

        data = response.json()
        offres = data.get("resultats", [])
        total = data.get("filtresPossibles", [{}])

        logger.info(f"[france_travail] Found {len(offres)} offers (dept={code_dept})")

        # Aggregate by commune
        commune_counts: dict[str, dict[str, Any]] = {}
        for offre in offres:
            lieu = offre.get("lieuTravail", {})
            commune = lieu.get("commune", "")
            if not commune:
                continue

            if commune not in commune_counts:
                commune_counts[commune] = {
                    "count": 0,
                    "cdi": 0,
                    "cdd": 0,
                    "sectors": {},
                }

            commune_counts[commune]["count"] += 1
            type_contrat = offre.get("typeContrat", "")
            if type_contrat == "CDI":
                commune_counts[commune]["cdi"] += 1
            elif type_contrat == "CDD":
                commune_counts[commune]["cdd"] += 1

            sector = offre.get("romeCode", "unknown")
            commune_counts[commune]["sectors"][sector] = (
                commune_counts[commune]["sectors"].get(sector, 0) + 1
            )

        # Convert to signals
        for commune, stats in commune_counts.items():
            signals.append(
                CollectedSignal(
                    source="france_travail",
                    source_url=f"ft:offres:{commune}:{since.isoformat()}",
                    event_date=date.today(),
                    code_commune=commune,
                    code_dept=commune[:2] if len(commune) >= 2 else code_dept,
                    metric_name="offres_emploi",
                    metric_value=float(stats["count"]),
                    signal_type="positif" if stats["count"] > 5 else "neutre",
                    confidence=0.8,
                    raw_data={
                        "total": stats["count"],
                        "cdi": stats["cdi"],
                        "cdd": stats["cdd"],
                        "top_sectors": dict(
                            sorted(stats["sectors"].items(), key=lambda x: -x[1])[:5]
                        ),
                    },
                )
            )

        return signals
