"""CAF (Caisse d'Allocations Familiales) collector - Social benefits data.

Source: data.caf.fr open data API (OpenDataSoft platform)
Data: Departmental statistics on RSA, ASF, AAH beneficiaries.
Free, no auth required, updated monthly/quarterly.
"""

from datetime import date
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

CAF_BASE = "https://data.caf.fr/api/explore/v2.1/catalog/datasets"

# Real dataset IDs from data.caf.fr
DATASETS = {
    "rsa": "rsa_s_type_age_5_dep",          # RSA beneficiaries by dept
    "asf": "asf_s_ben_dep",                  # ASF beneficiaries by dept
    "aah": "aah_s_tx_inca_age_5_dep",        # AAH beneficiaries by dept
    "allocations_familiales": "af_s_tx_dep",  # Family allowances by dept
}

# Field mapping for each dataset
DATASET_FIELDS = {
    "rsa": {"count": "indfoy_rsa", "amount": "indmtt_rsa"},
    "asf": {"count": "indfoy_asf", "amount": None},
    "aah": {"count": "indfoy_aah", "amount": "indmtt_aah"},
    "allocations_familiales": {"count": "indfoy_af", "amount": "indmtt_af"},
}


class CAFCollector(BaseCollector):
    """Collect social benefits data from CAF open data."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="caf",
                source_type="api",
                rate_limit=1,
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect CAF beneficiary statistics by department."""
        signals: list[CollectedSignal] = []

        for metric_key, dataset_id in DATASETS.items():
            try:
                new_signals = await self._fetch_dataset(
                    dataset_id, metric_key, code_dept
                )
                signals.extend(new_signals)
            except Exception as e:
                logger.warning(f"[caf] Failed to fetch {metric_key}: {e}")

        logger.info(f"[caf] Collected {len(signals)} signals")
        return signals

    async def _fetch_dataset(
        self, dataset_id: str, metric_key: str, code_dept: str | None
    ) -> list[CollectedSignal]:
        """Fetch a single dataset from CAF open data."""
        params: dict[str, Any] = {
            "limit": 100,
            "order_by": "dtreffre DESC",
        }
        if code_dept:
            params["where"] = f"numdep='{code_dept}'"

        url = f"{CAF_BASE}/{dataset_id}/records"
        response = await self._request_with_retry("GET", url, params=params)
        if not response:
            return []

        data = response.json()
        records = data.get("results", [])
        signals: list[CollectedSignal] = []
        fields = DATASET_FIELDS.get(metric_key, {})

        for record in records:
            dept = record.get("numdep")
            if not dept:
                continue
            dept = str(dept).zfill(2)

            # Parse date
            date_str = record.get("dtreffre", "")
            ev_date = self._parse_date(str(date_str))

            # Extract count
            count_field = fields.get("count", "")
            count = record.get(count_field, 0)
            if not count or int(count) <= 0:
                continue

            signals.append(
                CollectedSignal(
                    source="caf",
                    source_url=f"https://data.caf.fr/explore/dataset/{dataset_id}",
                    event_date=ev_date or date.today(),
                    code_dept=dept,
                    metric_name=f"caf_{metric_key}_beneficiaires",
                    metric_value=float(int(count)),
                    signal_type="neutre",
                    confidence=0.85,
                    raw_data={
                        k: v for k, v in record.items()
                        if k in ("nomdep", "nomregi", count_field,
                                 fields.get("amount", ""), "dtreffre")
                    },
                )
            )

        return signals

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse various date formats from CAF data."""
        if not date_str:
            return None
        date_str = str(date_str).strip()
        # ISO format (2025-05-01)
        if len(date_str) >= 10 and "-" in date_str:
            try:
                return date.fromisoformat(date_str[:10])
            except ValueError:
                pass
        # YYYY-MM format
        if len(date_str) == 7 and "-" in date_str:
            try:
                parts = date_str.split("-")
                return date(int(parts[0]), int(parts[1]), 1)
            except (ValueError, IndexError):
                pass
        return None
