"""DGFiP collector - Fiscal data via data.economie.gouv.fr.

Source: data.economie.gouv.fr (OpenDataSoft platform)
Data: Tax declarations, fiscal statistics by department.
Free, no auth required, updated yearly.

Note: DGFiP datasets on data.economie.gouv.fr are mainly national budget data.
For departmental fiscal data, we use the IR (impot sur le revenu) declarations dataset.
"""

from datetime import date
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

DGFIP_BASE = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"

DATASETS = {
    "ir_declarations": "declarations-nationales-de-resultats-des-impots-professionnels-bicis-bnc-et-ba",
}


class DGFiPCollector(BaseCollector):
    """Collect fiscal data from DGFiP open data."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="dgfip",
                source_type="api",
                rate_limit=1,
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect DGFiP fiscal signals."""
        signals: list[CollectedSignal] = []

        for metric_key, dataset_id in DATASETS.items():
            try:
                new_signals = await self._fetch_dataset(dataset_id, metric_key, code_dept)
                signals.extend(new_signals)
            except Exception as e:
                logger.warning(f"[dgfip] Failed to fetch {metric_key}: {e}")

        logger.info(f"[dgfip] Collected {len(signals)} signals")
        return signals

    async def _fetch_dataset(
        self, dataset_id: str, metric_key: str, code_dept: str | None
    ) -> list[CollectedSignal]:
        """Fetch a single dataset from DGFiP open data."""
        params: dict[str, Any] = {
            "limit": 100,
        }
        if code_dept:
            params["where"] = f"code_departement='{code_dept}' OR dep='{code_dept}'"

        url = f"{DGFIP_BASE}/{dataset_id}/records"
        response = await self._request_with_retry("GET", url, params=params)
        if not response:
            return []

        data = response.json()
        records = data.get("results", [])
        signals: list[CollectedSignal] = []

        for record in records:
            dept = record.get("code_departement") or record.get("dep") or record.get("departement")
            if not dept:
                continue
            dept = str(dept).zfill(2) if len(str(dept)) < 2 else str(dept)

            year = record.get("annee") or record.get("millesime") or record.get("year")
            ev_date = date(int(year), 1, 1) if year else date.today()

            # Extract main fiscal value
            value = (
                record.get("nombre_de_declarations")
                or record.get("montant")
                or record.get("nombre_de_foyers_fiscaux")
                or record.get("total_net")
                or 0
            )

            if value and float(value) > 0:
                signals.append(
                    CollectedSignal(
                        source="dgfip",
                        source_url=f"https://data.economie.gouv.fr/explore/dataset/{dataset_id}",
                        event_date=ev_date,
                        code_dept=dept,
                        metric_name=f"dgfip_{metric_key}",
                        metric_value=float(value),
                        signal_type="neutre",
                        confidence=0.9,
                        raw_data=record,
                    )
                )

        return signals
