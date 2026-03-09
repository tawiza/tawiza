"""RNA adapter -- French associations (Repertoire National des Associations).

Uses the recherche-entreprises.api.gouv.fr API with nature_juridique filters
to retrieve associations loi 1901 and related types for a given department.

NJ codes for associations:
  - 9210: Association syndicale autorisee
  - 9220: Association declaree (loi 1901) -- largest set
  - 9221: Association declaree d'insertion
  - 9222: Association intermediaire
  - 9230: Association declaree reconnue d'utilite publique
  - 9240: Congregation
  - 9260: Association de droit local
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from loguru import logger

# Nature juridique codes that designate associations
_ASSOCIATION_NJ_CODES: list[str] = [
    "9220",  # Association declaree (loi 1901) -- bulk
    "9221",  # Association declaree d'insertion
    "9222",  # Association intermediaire
    "9230",  # Association declaree reconnue d'utilite publique
    "9210",  # Association syndicale autorisee
    "9240",  # Congregation
    "9260",  # Association de droit local
]

_NJ_LABELS: dict[str, str] = {
    "9210": "Association syndicale autorisee",
    "9220": "Association declaree (loi 1901)",
    "9221": "Association declaree d'insertion",
    "9222": "Association intermediaire",
    "9230": "Association declaree, reconnue d'utilite publique",
    "9240": "Congregation",
    "9260": "Association de droit local",
}

_BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"
_MAX_PER_PAGE = 25  # API hard limit


class RnaAdapter:
    """Async adapter for RNA data via recherche-entreprises API.

    Queries associations by department using nature_juridique filters.
    Returns normalised dicts ready for the RnaExtractor.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def search_by_department(
        self,
        department_code: str,
        limit: int = 100,
        nj_codes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch associations for *department_code*.

        Queries multiple NJ codes and merges results, deduplicating by SIREN.
        The API returns at most 25 results per page, so we paginate.

        Args:
            department_code: French department code (e.g. "13", "75", "2A").
            limit: Maximum total associations to return (across all NJ codes).
            nj_codes: Override which NJ codes to query (default: all association codes).

        Returns:
            List of normalised association dicts with keys:
            siren, titre, objet, date_creation, commune, code_postal,
            activite_principale, nature_juridique, nature_juridique_label,
            tranche_effectif, categorie_entreprise.
        """
        codes = nj_codes or _ASSOCIATION_NJ_CODES
        seen_sirens: set[str] = set()
        results: list[dict[str, Any]] = []

        # Budget allocation: spread the limit across NJ codes, but give the
        # bulk code (9220) a bigger share since it has the most results.
        remaining = limit

        for nj_code in codes:
            if remaining <= 0:
                break

            # Fetch up to `remaining` for this NJ code (paginated)
            page_limit = min(remaining, _MAX_PER_PAGE)
            page = 1

            while remaining > 0:
                try:
                    records = await self._fetch_page(
                        department_code, nj_code, page=page, per_page=page_limit
                    )
                except Exception:
                    logger.exception(
                        "RnaAdapter: API error for dept={} nj={} page={}",
                        department_code,
                        nj_code,
                        page,
                    )
                    break

                if not records:
                    break

                for rec in records:
                    siren = rec.get("siren", "")
                    if not siren or siren in seen_sirens:
                        continue
                    seen_sirens.add(siren)
                    results.append(self._normalise(rec, nj_code))
                    remaining -= 1
                    if remaining <= 0:
                        break

                # If we got fewer than requested, no more pages
                if len(records) < page_limit:
                    break

                page += 1
                # Small delay to be polite to the API
                await asyncio.sleep(0.15)

        logger.info(
            "RnaAdapter dept={}: fetched {} associations (codes: {})",
            department_code,
            len(results),
            ", ".join(codes[:3]) + ("..." if len(codes) > 3 else ""),
        )
        return results

    async def _fetch_page(
        self,
        department_code: str,
        nj_code: str,
        page: int = 1,
        per_page: int = 25,
    ) -> list[dict[str, Any]]:
        """Fetch a single page from the API."""
        params: dict[str, Any] = {
            "departement": department_code,
            "nature_juridique": nj_code,
            "per_page": min(per_page, _MAX_PER_PAGE),
            "page": page,
            "etat_administratif": "A",  # Only active associations
        }

        response = await self._client.get(_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    @staticmethod
    def _normalise(record: dict[str, Any], nj_code: str) -> dict[str, Any]:
        """Normalise an API record to our standard format."""
        siege = record.get("siege") or {}

        # Extract creation date (enterprise-level, then siege-level)
        date_creation = record.get("date_creation") or siege.get("date_creation")

        return {
            "siren": record.get("siren", ""),
            "titre": record.get("nom_complet", ""),
            "nom_raison_sociale": record.get("nom_raison_sociale", ""),
            "objet": "",  # recherche-entreprises does not expose RNA objet
            "date_creation": date_creation,
            "commune": siege.get("libelle_commune", ""),
            "code_postal": siege.get("code_postal", ""),
            "activite_principale": siege.get("activite_principale", ""),
            "nature_juridique": nj_code,
            "nature_juridique_label": _NJ_LABELS.get(nj_code, nj_code),
            "tranche_effectif": record.get("tranche_effectif_salarie", ""),
            "categorie_entreprise": record.get("categorie_entreprise", ""),
            "section_activite_principale": record.get("section_activite_principale", ""),
        }
