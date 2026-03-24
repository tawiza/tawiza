"""DVF (Demandes de Valeurs Foncières) collector - Real estate transactions.

Source: https://files.data.gouv.fr/geo-dvf/latest/csv/
Official open data from DGFiP, updated yearly. CSV per department, gzipped.
"""

import csv
import gzip
import io
from datetime import date, timedelta
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

# geo-dvf provides CSVs by year and department
DVF_BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"


class DVFCollector(BaseCollector):
    """Collect real estate transaction signals from DVF open data (CSV)."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="dvf",
                source_type="api",
                rate_limit=2,
                timeout=60,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect DVF transaction signals from CSV files."""
        if since is None:
            since = date.today() - timedelta(days=365)

        depts = [code_dept] if code_dept else ["75"]
        all_signals: list[CollectedSignal] = []

        # Determine which years to fetch (DVF published with delay)
        years = set()
        current_year = date.today().year
        years.add(current_year)
        years.add(current_year - 1)  # DVF data often not available for current year
        if since.year < current_year:
            years.add(since.year)

        for dept in depts:
            for year in sorted(years, reverse=True):
                try:
                    signals = await self._fetch_department_year(dept, year, since)
                    all_signals.extend(signals)
                    logger.info(f"[dvf] {dept}/{year}: {len(signals)} signals")
                except Exception as e:
                    logger.warning(f"[dvf] Failed {dept}/{year}: {e}")

        logger.info(f"[dvf] Total: {len(all_signals)} signals collected")
        return all_signals

    async def _fetch_department_year(
        self, code_dept: str, year: int, since: date
    ) -> list[CollectedSignal]:
        """Fetch and parse a department CSV for a given year."""
        url = f"{DVF_BASE_URL}/{year}/departements/{code_dept}.csv.gz"

        response = await self._request_with_retry("GET", url)
        if not response:
            return []

        # Decompress and parse CSV
        try:
            raw = gzip.decompress(response.content)
            text = raw.decode("utf-8")
        except Exception as e:
            logger.error(f"[dvf] Decompress failed for {code_dept}/{year}: {e}")
            return []

        reader = csv.DictReader(io.StringIO(text))
        return self._process_csv(reader, code_dept, since)

    def _process_csv(
        self, reader: csv.DictReader, code_dept: str, since: date
    ) -> list[CollectedSignal]:
        """Process CSV rows into aggregated signals per commune."""
        commune_stats: dict[str, dict[str, Any]] = {}

        for row in reader:
            # Filter by date
            date_str = row.get("date_mutation", "")
            if not date_str:
                continue
            try:
                mutation_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            if mutation_date < since:
                continue

            commune = row.get("code_commune", "")
            if not commune or len(commune) < 5:
                continue

            if commune not in commune_stats:
                commune_stats[commune] = {
                    "nom": row.get("nom_commune", ""),
                    "prices_m2": [],
                    "count": 0,
                    "total_value": 0.0,
                    "types": {},
                    "last_date": mutation_date,
                }

            stats = commune_stats[commune]
            stats["count"] += 1
            if mutation_date > stats["last_date"]:
                stats["last_date"] = mutation_date

            try:
                valeur = float(row.get("valeur_fonciere", 0) or 0)
            except (ValueError, TypeError):
                valeur = 0.0
            stats["total_value"] += valeur

            try:
                surface = float(row.get("surface_reelle_bati", 0) or 0)
            except (ValueError, TypeError):
                surface = 0.0

            if surface > 0 and valeur > 0:
                prix_m2 = valeur / surface
                if 500 < prix_m2 < 50000:
                    stats["prices_m2"].append(prix_m2)

            type_bien = row.get("type_local", "Autre") or "Autre"
            stats["types"][type_bien] = stats["types"].get(type_bien, 0) + 1

        # Convert to signals
        signals: list[CollectedSignal] = []
        for commune, stats in commune_stats.items():
            dept = commune[:3] if commune.startswith("97") else commune[:2]

            # Transaction volume signal
            signals.append(
                CollectedSignal(
                    source="dvf",
                    source_url=f"https://files.data.gouv.fr/geo-dvf/latest/csv/{commune}/transactions",
                    event_date=stats["last_date"],
                    code_commune=commune,
                    code_dept=dept,
                    metric_name="transactions_immobilieres",
                    metric_value=float(stats["count"]),
                    signal_type="neutre",
                    confidence=0.9,
                    raw_data={
                        "nom_commune": stats["nom"],
                        "total_value": stats["total_value"],
                        "types": stats["types"],
                    },
                )
            )

            # Price per m² signal
            if stats["prices_m2"]:
                avg_price = sum(stats["prices_m2"]) / len(stats["prices_m2"])
                signals.append(
                    CollectedSignal(
                        source="dvf",
                        source_url=f"https://files.data.gouv.fr/geo-dvf/latest/csv/{commune}/prix_m2",
                        event_date=stats["last_date"],
                        code_dept=dept,
                        code_commune=commune,
                        metric_name="prix_m2_moyen",
                        metric_value=round(avg_price, 2),
                        signal_type="neutre",
                        confidence=min(0.5 + len(stats["prices_m2"]) * 0.05, 0.95),
                        raw_data={
                            "nom_commune": stats["nom"],
                            "nb_transactions": len(stats["prices_m2"]),
                            "min": round(min(stats["prices_m2"]), 2),
                            "max": round(max(stats["prices_m2"]), 2),
                        },
                    )
                )

        return signals
