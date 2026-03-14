"""BODACC Ingester - Ingère les annonces légales historiques.

Source: API OpenDataSoft BODACC
Données: Procédures collectives, privilèges, radiations
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger


@dataclass
class BODACCAnnouncement:
    """Une annonce BODACC."""

    id: str
    date_parution: datetime
    type_annonce: str  # Procédure collective, Modification, etc.
    famille: str  # RJ, LJ, Privilège, etc.
    departement: str
    siren: str | None
    nom_entreprise: str
    ville: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date_parution": self.date_parution.isoformat(),
            "type_annonce": self.type_annonce,
            "famille": self.famille,
            "departement": self.departement,
            "siren": self.siren,
            "nom_entreprise": self.nom_entreprise,
            "ville": self.ville,
        }


class BODACCIngester:
    """Ingère les données BODACC depuis l'API OpenDataSoft."""

    BASE_URL = "https://bodacc-datadila.opendatasoft.com/api/records/1.0/search"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=60)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def fetch_by_department(
        self,
        department: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10000,
    ) -> list[BODACCAnnouncement]:
        """Récupère les annonces pour un département.

        Args:
            department: Code département (01, 2A, 75, etc.)
            start_date: Date de début
            end_date: Date de fin
            limit: Nombre max de résultats

        Returns:
            Liste des annonces
        """
        # Build date range filter
        date_filter = ""
        if start_date and end_date:
            date_filter = f"dateparution:[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
        elif start_date:
            date_filter = f"dateparution>={start_date.strftime('%Y-%m-%d')}"
        elif end_date:
            date_filter = f"dateparution<={end_date.strftime('%Y-%m-%d')}"

        query = date_filter

        announcements = []
        offset = 0
        batch_size = 100

        # Build CP range for department filtering
        # Department 69 -> CP 69000-69999
        dept_num = department.zfill(2)
        cp_min = int(dept_num) * 1000
        cp_max = cp_min + 999

        # Build full query with CP range
        cp_filter = f"cp>={cp_min} AND cp<={cp_max}"
        full_query = f"({cp_filter})"
        if query:
            full_query = f"({cp_filter}) AND ({query})"

        while len(announcements) < limit:
            params = {
                "dataset": "annonces-commerciales",
                "q": full_query,
                "rows": min(batch_size, limit - len(announcements)),
                "start": offset,
                "sort": "-dateparution",
                "refine.publicationavis": "B",  # BODACC B = procédures collectives
            }

            try:
                response = await self._client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                records = data.get("records", [])
                if not records:
                    break

                for record in records:
                    fields = record.get("fields", {})

                    try:
                        date_str = fields.get("dateparution", "")
                        date_parution = (
                            datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
                        )

                        ann = BODACCAnnouncement(
                            id=record.get("recordid", ""),
                            date_parution=date_parution,
                            type_annonce=fields.get("publicationavis", ""),
                            famille=fields.get("familleavis", ""),
                            departement=fields.get("departement_nom_officiel", department),
                            siren=fields.get("numeroidentification", ""),
                            nom_entreprise=fields.get(
                                "nomcommercial", fields.get("raisonsociale", "")
                            ),
                            ville=fields.get("ville", ""),
                        )
                        announcements.append(ann)
                    except Exception as e:
                        logger.debug(f"Parse error: {e}")
                        continue

                offset += len(records)

                if len(records) < batch_size:
                    break

            except Exception as e:
                logger.error(f"BODACC fetch error: {e}")
                break

        logger.info(f"Fetched {len(announcements)} BODACC announcements for dept {department}")
        return announcements

    async def aggregate_monthly(
        self,
        department: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, dict[str, int]]:
        """Agrège les annonces par mois et type.

        Returns:
            Dict {YYYY-MM: {type: count}}
        """
        announcements = await self.fetch_by_department(department, start_date, end_date)

        monthly: dict[str, dict[str, int]] = {}

        for ann in announcements:
            period = ann.date_parution.strftime("%Y-%m")

            if period not in monthly:
                monthly[period] = {
                    "total": 0,
                    "procedures": 0,
                    "liquidations": 0,
                    "redressements": 0,
                    "privileges": 0,
                }

            monthly[period]["total"] += 1

            famille = ann.famille.lower()
            if "liquidation" in famille:
                monthly[period]["liquidations"] += 1
            elif "redressement" in famille:
                monthly[period]["redressements"] += 1
            elif "privilège" in famille or "privilege" in famille:
                monthly[period]["privileges"] += 1

            if any(x in famille for x in ["liquidation", "redressement", "sauvegarde"]):
                monthly[period]["procedures"] += 1

        return monthly


async def test_bodacc():
    """Test BODACC ingestion."""
    async with BODACCIngester() as ingester:
        start = datetime(2023, 1, 1)
        end = datetime(2024, 12, 31)

        monthly = await ingester.aggregate_monthly("69", start, end)

        print("\nBODACC Rhône (69) 2023-2024:")
        for period, counts in sorted(monthly.items()):
            print(
                f"  {period}: {counts['total']} total, {counts['procedures']} proc, {counts['liquidations']} LJ"
            )


if __name__ == "__main__":
    asyncio.run(test_bodacc())
