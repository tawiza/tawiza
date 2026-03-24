"""Education Nationale collector - School and education data.

Source: data.education.gouv.fr (OpenDataSoft platform)
Data: School directory, exam results by department.
Free, no auth required, updated yearly.

Note: code_departement uses 3-digit format on this API (e.g. "075" for Paris).
"""

from datetime import date
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

EDUC_BASE = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets"

DATASETS = {
    "etablissements": "fr-en-annuaire-education",
    "evaluations": "fr-en-evaluations_nationales_2de_pro_departement",
}


class EducationNationaleCollector(BaseCollector):
    """Collect education data from Education Nationale open data."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="education_nationale",
                source_type="api",
                rate_limit=1,
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect education signals by department."""
        signals: list[CollectedSignal] = []

        for metric_key, dataset_id in DATASETS.items():
            try:
                new_signals = await self._fetch_dataset(dataset_id, metric_key, code_dept)
                signals.extend(new_signals)
            except Exception as e:
                logger.warning(f"[education_nationale] Failed to fetch {metric_key}: {e}")

        logger.info(f"[education_nationale] Collected {len(signals)} signals")
        return signals

    async def _fetch_dataset(
        self, dataset_id: str, metric_key: str, code_dept: str | None
    ) -> list[CollectedSignal]:
        """Fetch a single dataset from Education Nationale open data."""
        params: dict[str, Any] = {
            "limit": 100,
        }

        if code_dept:
            # Education nationale uses 3-digit dept codes (e.g. "075")
            dept_3d = code_dept.zfill(3)
            params["where"] = f"code_departement='{dept_3d}'"

        url = f"{EDUC_BASE}/{dataset_id}/records"
        response = await self._request_with_retry("GET", url, params=params)
        if not response:
            return []

        data = response.json()
        records = data.get("results", [])
        total_count = data.get("total_count", len(records))

        if not records:
            return []

        signals: list[CollectedSignal] = []

        if metric_key == "etablissements":
            # Count establishments by type
            type_counts: dict[str, int] = {}
            dept_code = code_dept or "unknown"

            for record in records:
                etype = record.get("type_etablissement", "Autre")
                type_counts[etype] = type_counts.get(etype, 0) + 1
                if dept_code == "unknown":
                    raw_dept = record.get("code_departement", "")
                    if raw_dept:
                        dept_code = str(raw_dept).lstrip("0") or raw_dept

            # Use total_count for the aggregate signal
            signals.append(
                CollectedSignal(
                    source="education_nationale",
                    source_url=f"https://data.education.gouv.fr/explore/dataset/{dataset_id}",
                    event_date=date.today(),
                    code_dept=code_dept or dept_code,
                    metric_name="education_etablissements_count",
                    metric_value=float(total_count),
                    signal_type="neutre",
                    confidence=0.9,
                    raw_data={"types": type_counts, "total": total_count},
                )
            )
        else:
            # Generic record processing for evaluation datasets
            for record in records:
                dept = record.get("code_departement", "")
                if dept:
                    dept = str(dept).lstrip("0") or dept

                signals.append(
                    CollectedSignal(
                        source="education_nationale",
                        source_url=f"https://data.education.gouv.fr/explore/dataset/{dataset_id}",
                        event_date=date.today(),
                        code_dept=code_dept or dept,
                        metric_name=f"education_{metric_key}",
                        metric_value=1.0,
                        signal_type="neutre",
                        confidence=0.7,
                        raw_data=record,
                    )
                )

        return signals
