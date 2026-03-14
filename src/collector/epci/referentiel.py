"""
EPCI Reference Data — commune→EPCI mapping from geo.api.gouv.fr

Downloads and caches the full mapping of 34,871 French communes to their
1,255 EPCIs (Établissements Publics de Coopération Intercommunale).
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
COMMUNE_CACHE = CACHE_DIR / "commune_to_epci.json"
EPCI_CACHE = CACHE_DIR / "epcis.json"
CACHE_MAX_AGE = timedelta(days=30)

GEO_API = "https://geo.api.gouv.fr"


class EPCIReferentiel:
    """Reference data for EPCI ↔ commune mappings."""

    def __init__(self):
        self._commune_to_epci: dict[str, str] = {}
        self._epci_info: dict[str, dict] = {}
        self._commune_info: dict[str, dict] = {}
        self._loaded = False

    async def load(self, force_refresh: bool = False) -> None:
        """Load reference data from cache or API."""
        if self._loaded and not force_refresh:
            return

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if not force_refresh and self._cache_valid():
            self._load_from_cache()
        else:
            await self._fetch_from_api()
            self._save_to_cache()

        self._loaded = True
        logger.info(
            f"EPCI referentiel loaded: {len(self._commune_to_epci)} communes, "
            f"{len(self._epci_info)} EPCIs"
        )

    def _cache_valid(self) -> bool:
        if not COMMUNE_CACHE.exists() or not EPCI_CACHE.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(COMMUNE_CACHE.stat().st_mtime)
        return age < CACHE_MAX_AGE

    def _load_from_cache(self) -> None:
        with open(COMMUNE_CACHE) as f:
            self._commune_to_epci = json.load(f)
        with open(EPCI_CACHE) as f:
            data = json.load(f)
            self._epci_info = data.get("epcis", {})
            self._commune_info = data.get("communes", {})

    def _save_to_cache(self) -> None:
        with open(COMMUNE_CACHE, "w") as f:
            json.dump(self._commune_to_epci, f)
        with open(EPCI_CACHE, "w") as f:
            json.dump(
                {
                    "epcis": self._epci_info,
                    "communes": self._commune_info,
                    "updated": datetime.now().isoformat(),
                },
                f,
            )

    async def _fetch_from_api(self) -> None:
        """Fetch full commune and EPCI data from geo.api.gouv.fr."""
        async with httpx.AsyncClient(timeout=60) as client:
            # 1. All communes with EPCI codes
            logger.info("Fetching communes from geo.api.gouv.fr...")
            r = await client.get(
                f"{GEO_API}/communes",
                params={
                    "fields": "nom,code,codeDepartement,codeEpci,population,codesPostaux",
                    "limit": "50000",
                },
            )
            r.raise_for_status()
            communes = r.json()

            for c in communes:
                code = c["code"]
                epci = c.get("codeEpci")
                if epci:
                    self._commune_to_epci[code] = epci
                self._commune_info[code] = {
                    "nom": c.get("nom", ""),
                    "dept": c.get("codeDepartement", ""),
                    "pop": c.get("population", 0),
                    "epci": epci or "",
                }

            # 2. All EPCIs
            logger.info("Fetching EPCIs from geo.api.gouv.fr...")
            r = await client.get(
                f"{GEO_API}/epcis",
                params={
                    "fields": "nom,codesDepartements,population",
                    "limit": "2000",
                },
            )
            r.raise_for_status()
            epcis = r.json()

            for e in epcis:
                self._epci_info[e["code"]] = {
                    "nom": e.get("nom", ""),
                    "depts": e.get("codesDepartements", []),
                    "pop": e.get("population", 0),
                }

    # --- Public API ---

    def commune_to_epci(self, code_commune: str) -> str | None:
        """Get EPCI code for a commune."""
        return self._commune_to_epci.get(code_commune)

    def dept_to_epci(self, code_commune: str) -> str | None:
        """Get department code from commune code."""
        info = self._commune_info.get(code_commune)
        return info["dept"] if info else None

    def epci_name(self, code_epci: str) -> str:
        """Get EPCI name."""
        info = self._epci_info.get(code_epci)
        return info["nom"] if info else code_epci

    def epci_population(self, code_epci: str) -> int:
        """Get EPCI population."""
        info = self._epci_info.get(code_epci)
        return info.get("pop", 0) if info else 0

    def epci_departments(self, code_epci: str) -> list[str]:
        """Get department codes for an EPCI."""
        info = self._epci_info.get(code_epci)
        return info.get("depts", []) if info else []

    def communes_in_epci(self, code_epci: str) -> list[str]:
        """Get all commune codes in an EPCI."""
        return [c for c, e in self._commune_to_epci.items() if e == code_epci]

    def epcis_in_department(self, code_dept: str) -> list[str]:
        """Get all EPCI codes that cover a department."""
        return [
            code for code, info in self._epci_info.items() if code_dept in info.get("depts", [])
        ]

    def all_epcis(self) -> dict[str, dict]:
        """Get all EPCI info."""
        return self._epci_info

    def enrich_signal(self, code_commune: str | None, code_dept: str | None = None) -> str | None:
        """
        Resolve EPCI code from commune or department.
        Returns EPCI code or None.
        """
        if code_commune:
            epci = self._commune_to_epci.get(code_commune)
            if epci:
                return epci
        return None


# Singleton
_referentiel: EPCIReferentiel | None = None


async def get_referentiel() -> EPCIReferentiel:
    """Get or create the EPCI referentiel singleton."""
    global _referentiel
    if _referentiel is None:
        _referentiel = EPCIReferentiel()
        await _referentiel.load()
    return _referentiel
