"""DVF Ingester - Télécharge et indexe les données DVF historiques.

Données Valeurs Foncières (DVF) depuis 2020.
Source: https://files.data.gouv.fr/geo-dvf/latest/csv/
"""

import asyncio
import csv
import gzip
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from loguru import logger


@dataclass
class DVFTransaction:
    """Une transaction immobilière DVF."""

    id_mutation: str
    date_mutation: datetime
    nature_mutation: str  # Vente, Expropriation, etc.
    valeur_fonciere: float
    code_postal: str
    code_commune: str
    nom_commune: str
    code_departement: str
    type_local: str  # Maison, Appartement, Local, etc.
    surface_reelle_bati: float | None
    nombre_pieces_principales: int | None
    surface_terrain: float | None
    longitude: float | None
    latitude: float | None

    def to_dict(self) -> dict:
        return {
            "id_mutation": self.id_mutation,
            "date_mutation": self.date_mutation.isoformat(),
            "nature_mutation": self.nature_mutation,
            "valeur_fonciere": self.valeur_fonciere,
            "code_postal": self.code_postal,
            "code_commune": self.code_commune,
            "nom_commune": self.nom_commune,
            "code_departement": self.code_departement,
            "type_local": self.type_local,
            "surface_reelle_bati": self.surface_reelle_bati,
            "nombre_pieces_principales": self.nombre_pieces_principales,
            "surface_terrain": self.surface_terrain,
            "longitude": self.longitude,
            "latitude": self.latitude,
        }


class DVFIngester:
    """Ingère les données DVF depuis data.gouv.fr.

    Télécharge les CSV par année/département et les indexe dans PostgreSQL.
    """

    BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
    YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

    # Colonnes du CSV DVF
    CSV_COLUMNS = {
        "id_mutation": "id_mutation",
        "date_mutation": "date_mutation",
        "nature_mutation": "nature_mutation",
        "valeur_fonciere": "valeur_fonciere",
        "code_postal": "code_postal",
        "code_commune": "code_commune",
        "nom_commune": "nom_commune",
        "code_departement": "code_departement",
        "type_local": "type_local",
        "surface_reelle_bati": "surface_reelle_bati",
        "nombre_pieces_principales": "nombre_pieces_principales",
        "surface_terrain": "surface_terrain",
        "longitude": "longitude",
        "latitude": "latitude",
    }

    def __init__(self, data_dir: Path | None = None):
        """Initialize ingester.

        Args:
            data_dir: Directory to cache downloaded files
        """
        self.data_dir = data_dir or Path("/tmp/dvf_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=120)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def get_available_departments(self, year: int) -> list[str]:
        """Liste les départements disponibles pour une année."""
        url = f"{self.BASE_URL}/{year}/"

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            # Parse HTML directory listing
            departments = []
            for line in response.text.split("\n"):
                if ".csv" in line.lower():
                    # Extract department code from filename
                    import re

                    match = re.search(r"(\d{2,3})\.csv", line, re.I)
                    if match:
                        departments.append(match.group(1))

            return sorted(set(departments))
        except Exception as e:
            logger.error(f"Failed to list departments for {year}: {e}")
            return []

    async def download_department(
        self, year: int, department: str, force: bool = False
    ) -> Path | None:
        """Télécharge le CSV d'un département.

        Args:
            year: Année (2020-2025)
            department: Code département (01, 75, 2A, etc.)
            force: Re-télécharger même si existe

        Returns:
            Path du fichier téléchargé
        """
        filename = f"dvf_{year}_{department}.csv"
        local_path = self.data_dir / filename

        if local_path.exists() and not force:
            logger.debug(f"Using cached {filename}")
            return local_path

        # Structure: /geo-dvf/latest/csv/{year}/departements/{dept}.csv.gz
        url = f"{self.BASE_URL}/{year}/departements/{department}.csv.gz"

        try:
            logger.info(f"Downloading DVF {year}/{department}...")
            response = await self._client.get(url)

            if response.status_code == 404:
                # Try communes folder
                url = f"{self.BASE_URL}/{year}/communes/{department}.csv.gz"
                response = await self._client.get(url)

            response.raise_for_status()

            # Decompress if gzipped
            content = response.content
            if url.endswith(".gz"):
                content = gzip.decompress(content)

            # Save to disk
            local_path.write_bytes(content)
            logger.info(f"Downloaded {filename} ({len(content) / 1024 / 1024:.1f} MB)")

            return local_path

        except Exception as e:
            logger.error(f"Failed to download DVF {year}/{department}: {e}")
            return None

    async def parse_csv(
        self, file_path: Path, batch_size: int = 1000
    ) -> AsyncIterator[list[DVFTransaction]]:
        """Parse un CSV DVF en batches.

        Yields:
            Batches de transactions
        """
        transactions = []

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    tx = self._parse_row(row)
                    if tx:
                        transactions.append(tx)

                        if len(transactions) >= batch_size:
                            yield transactions
                            transactions = []

                except Exception as e:
                    logger.debug(f"Parse error: {e}")
                    continue

        if transactions:
            yield transactions

    def _parse_row(self, row: dict) -> DVFTransaction | None:
        """Parse une ligne CSV en DVFTransaction."""
        try:
            # Skip if no price
            valeur = row.get("valeur_fonciere", "").replace(",", ".")
            if not valeur or valeur == "":
                return None

            valeur_fonciere = float(valeur)
            if valeur_fonciere <= 0:
                return None

            # Parse date
            date_str = row.get("date_mutation", "")
            if not date_str:
                return None
            date_mutation = datetime.strptime(date_str, "%Y-%m-%d")

            # Parse optional floats
            def parse_float(val: str) -> float | None:
                if not val or val == "":
                    return None
                try:
                    return float(val.replace(",", "."))
                except ValueError:
                    return None

            def parse_int(val: str) -> int | None:
                if not val or val == "":
                    return None
                try:
                    return int(float(val))
                except ValueError:
                    return None

            return DVFTransaction(
                id_mutation=row.get("id_mutation", ""),
                date_mutation=date_mutation,
                nature_mutation=row.get("nature_mutation", "Vente"),
                valeur_fonciere=valeur_fonciere,
                code_postal=row.get("code_postal", "")[:5],
                code_commune=row.get("code_commune", "")[:5],
                nom_commune=row.get("nom_commune", ""),
                code_departement=row.get("code_departement", "")[:3],
                type_local=row.get("type_local", ""),
                surface_reelle_bati=parse_float(row.get("surface_reelle_bati", "")),
                nombre_pieces_principales=parse_int(row.get("nombre_pieces_principales", "")),
                surface_terrain=parse_float(row.get("surface_terrain", "")),
                longitude=parse_float(row.get("longitude", "")),
                latitude=parse_float(row.get("latitude", "")),
            )

        except Exception:
            return None

    async def ingest_department(
        self,
        year: int,
        department: str,
        db_session=None,
    ) -> dict:
        """Ingère un département complet.

        Args:
            year: Année
            department: Code département
            db_session: Session SQLAlchemy async

        Returns:
            Stats d'ingestion
        """
        stats = {
            "year": year,
            "department": department,
            "transactions": 0,
            "total_value": 0,
            "by_type": {},
            "errors": 0,
        }

        # Download
        file_path = await self.download_department(year, department)
        if not file_path:
            stats["errors"] = 1
            return stats

        # Parse and aggregate
        async for batch in self.parse_csv(file_path):
            for tx in batch:
                stats["transactions"] += 1
                stats["total_value"] += tx.valeur_fonciere

                type_key = tx.type_local or "Autre"
                if type_key not in stats["by_type"]:
                    stats["by_type"][type_key] = {"count": 0, "value": 0}
                stats["by_type"][type_key]["count"] += 1
                stats["by_type"][type_key]["value"] += tx.valeur_fonciere

                # Aggregate for time series storage (transactions are too many to store individually)

        logger.info(
            f"Ingested DVF {year}/{department}: "
            f"{stats['transactions']:,} transactions, "
            f"{stats['total_value'] / 1e9:.2f}B€"
        )

        return stats

    async def ingest_all(
        self,
        years: list[int] | None = None,
        departments: list[str] | None = None,
    ) -> dict:
        """Ingère toutes les données DVF.

        Args:
            years: Années à ingérer (défaut: toutes)
            departments: Départements à ingérer (défaut: tous)

        Returns:
            Stats globales
        """
        years = years or self.YEARS

        global_stats = {
            "years": years,
            "departments_processed": 0,
            "total_transactions": 0,
            "total_value": 0,
            "by_year": {},
        }

        for year in years:
            year_stats = {"transactions": 0, "value": 0}

            # Get available departments
            available = departments or await self.get_available_departments(year)

            for dept in available:
                stats = await self.ingest_department(year, dept)

                year_stats["transactions"] += stats["transactions"]
                year_stats["value"] += stats["total_value"]
                global_stats["departments_processed"] += 1

            global_stats["by_year"][year] = year_stats
            global_stats["total_transactions"] += year_stats["transactions"]
            global_stats["total_value"] += year_stats["value"]

            logger.info(
                f"Year {year} complete: {year_stats['transactions']:,} tx, "
                f"{year_stats['value'] / 1e9:.2f}B€"
            )

        return global_stats

    async def store_aggregates_to_db(
        self,
        stats: dict,
        year: int,
        department: str,
        db_session,
    ) -> None:
        """Store DVF aggregates as time series in PostgreSQL.

        Stores aggregated indicators rather than individual transactions.

        Args:
            stats: Aggregation stats from ingest_department
            year: Year of data
            department: Department code
            db_session: SQLAlchemy async session
        """
        from datetime import datetime

        from src.infrastructure.persistence.models.territorial_timeseries import (
            GranularityType,
            IndicatorType,
            TerritorialTimeSeries,
        )

        period_start = datetime(year, 1, 1)
        period_end = datetime(year, 12, 31)

        # Transaction count
        ts_count = TerritorialTimeSeries(
            territory_type="departement",
            territory_code=department,
            indicator=IndicatorType.DVF_TRANSACTIONS,
            granularity=GranularityType.YEARLY,
            period_start=period_start,
            period_end=period_end,
            value=stats["transactions"],
            count=stats["transactions"],
            source="dvf",
            extra_data={"by_type": stats.get("by_type", {})},
        )
        db_session.add(ts_count)

        # Total volume
        ts_volume = TerritorialTimeSeries(
            territory_type="departement",
            territory_code=department,
            indicator=IndicatorType.DVF_VOLUME,
            granularity=GranularityType.YEARLY,
            period_start=period_start,
            period_end=period_end,
            value=stats["total_value"],
            count=stats["transactions"],
            source="dvf",
        )
        db_session.add(ts_volume)

        # Price per m² by type (if we have surface data)
        for type_key, type_stats in stats.get("by_type", {}).items():
            if type_stats["count"] > 0:
                avg_price = type_stats["value"] / type_stats["count"]
                indicator = (
                    IndicatorType.DVF_PRICE_M2_APT
                    if "Appartement" in type_key
                    else IndicatorType.DVF_PRICE_M2_HOUSE
                    if "Maison" in type_key
                    else None
                )
                if indicator:
                    ts_price = TerritorialTimeSeries(
                        territory_type="departement",
                        territory_code=department,
                        indicator=indicator,
                        granularity=GranularityType.YEARLY,
                        period_start=period_start,
                        period_end=period_end,
                        value=avg_price,
                        count=type_stats["count"],
                        source="dvf",
                        extra_data={"type": type_key},
                    )
                    db_session.add(ts_price)

        await db_session.flush()
        logger.info(f"Stored DVF aggregates for {department}/{year} in PostgreSQL")


async def test_dvf_ingestion():
    """Test DVF ingestion on one department."""
    async with DVFIngester() as ingester:
        # Test with Rhône (69) for 2024
        stats = await ingester.ingest_department(2024, "69")
        print("\nDVF 2024/69 Stats:")
        print(f"  Transactions: {stats['transactions']:,}")
        print(f"  Total value: {stats['total_value'] / 1e9:.2f}B€")
        print(f"  By type: {stats['by_type']}")


if __name__ == "__main__":
    asyncio.run(test_dvf_ingestion())
