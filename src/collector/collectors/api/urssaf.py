"""URSSAF collector - Employment and social contributions data.

Source: open.urssaf.fr API (OpenDataSoft platform)
Data: Independent workers revenue, ESS employment, by department.
Free, no auth required, updated yearly.
"""

from datetime import date
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

URSSAF_BASE = "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets"

# Real dataset IDs from open.urssaf.fr
DATASETS = {
    "revenus_ti": "les-revenus-des-travailleurs-independants-par-departement",
    "effectifs_ess": "nombre-etab-effectifs-salaries-et-masse-salariale-ess-departements",
}


class URSSAFCollector(BaseCollector):
    """Collect employment data from URSSAF open data."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="urssaf",
                source_type="api",
                rate_limit=1,
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect URSSAF employment signals by department."""
        signals: list[CollectedSignal] = []

        for metric_key, dataset_id in DATASETS.items():
            try:
                new_signals = await self._fetch_dataset(
                    dataset_id, metric_key, code_dept
                )
                signals.extend(new_signals)
            except Exception as e:
                logger.warning(f"[urssaf] Failed to fetch {metric_key}: {e}")

        logger.info(f"[urssaf] Collected {len(signals)} signals")
        return signals

    async def _fetch_dataset(
        self, dataset_id: str, metric_key: str, code_dept: str | None
    ) -> list[CollectedSignal]:
        """Fetch a single dataset from URSSAF open data."""
        params: dict[str, Any] = {
            "limit": 100,
            "order_by": "annee DESC",
        }
        if code_dept:
            params["where"] = f"code_departement='{code_dept}'"

        url = f"{URSSAF_BASE}/{dataset_id}/records"
        response = await self._request_with_retry("GET", url, params=params)
        if not response:
            return []

        data = response.json()
        records = data.get("results", [])
        signals: list[CollectedSignal] = []

        for record in records:
            dept = record.get("code_departement")
            if not dept:
                continue
            dept = str(dept).zfill(2)

            year = record.get("annee")
            ev_date = date(int(year), 1, 1) if year else date.today()

            if metric_key == "revenus_ti":
                value = record.get("nombre_de_ti") or record.get("revenu") or 0
                metric_name = "urssaf_travailleurs_independants"
            else:
                value = record.get("effectifs_salaries_moyens") or record.get("nombre_d_etablissements") or 0
                metric_name = "urssaf_effectifs_ess"

            if value and float(value) > 0:
                signals.append(
                    CollectedSignal(
                        source="urssaf",
                        source_url=f"https://open.urssaf.fr/explore/dataset/{dataset_id}",
                        event_date=ev_date,
                        code_dept=dept,
                        metric_name=metric_name,
                        metric_value=float(value),
                        signal_type="neutre",
                        confidence=0.85,
                        raw_data={
                            k: v for k, v in record.items()
                            if k in ("departement", "annee", "nombre_de_ti",
                                     "revenu", "effectifs_salaries_moyens",
                                     "nombre_d_etablissements", "masse_salariale",
                                     "type_de_travailleur_independant", "famille_ess")
                        },
                    )
                )

        return signals
