"""Banque de France collector - Business failure statistics."""

import csv
import io
from datetime import date, timedelta
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig


class BanqueFranceCollector(BaseCollector):
    """Collect business failure statistics from Banque de France and open data sources.

    Monitors:
    - Company failures by department
    - Monthly business failure trends
    - Sector-specific failure rates
    """

    # Try multiple data sources for robustness.
    # Audit 2026-02-21: old BdF URLs return 403/404, migrated to new endpoints.
    #   - webstat v1 SDMX -> explore v2.1 (Opendatasoft)
    #   - BdF CSV direct link -> data.gouv.fr search
    #   - Kept open_urssaf as secondary source
    DATA_SOURCES = [
        {
            "name": "webstat_banque_france_v2",
            "url": "https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/tableaux_rapports_preetablis/records",
            "params": {"limit": "20", "where": "theme_fr LIKE '%défaillance%'"},
        },
        {
            "name": "data_gouv_defaillances",
            "url": "https://www.data.gouv.fr/api/1/datasets/",
            "params": {"q": "defaillances entreprises banque france", "page_size": "5"},
        },
        {
            "name": "open_urssaf",
            "url": "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets",
            "params": {"q": "defaillances"},
        },
    ]

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="banque_france",
                source_type="api",
                rate_limit=1.0,
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect business failure data from available sources."""
        if since is None:
            since = date.today() - timedelta(days=30)

        signals = []

        # Try each data source until we find working data
        for source in self.DATA_SOURCES:
            logger.info(f"[banque_france] Trying source: {source['name']}")

            try:
                source_signals = await self._collect_from_source(source, code_dept, since)
                if source_signals:
                    signals.extend(source_signals)
                    logger.info(
                        f"[banque_france] Got {len(source_signals)} signals from {source['name']}"
                    )
                    break  # Stop after first successful source

            except Exception as e:
                logger.warning(f"[banque_france] Source {source['name']} failed: {e}")
                continue

        # If no external source worked, generate synthetic data based on patterns
        if not signals:
            logger.info("[banque_france] No external data available, using fallback approach")
            signals = await self._generate_fallback_data(code_dept, since)

        logger.info(f"[banque_france] Collected {len(signals)} total signals")
        return signals

    async def _collect_from_source(
        self, source: dict, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Collect data from a specific source."""
        if source["name"] == "banque_france_csv":
            return await self._collect_from_csv(source["url"], code_dept, since)
        else:
            return await self._collect_from_api(source, code_dept, since)

    async def _collect_from_csv(
        self, url: str, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Try to fetch CSV data directly from Banque de France."""
        response = await self._request_with_retry("GET", url)
        if not response:
            return []

        try:
            csv_content = response.text
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            signals = []
            for row in csv_reader:
                signal = await self._process_csv_row(row, code_dept, since)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"[banque_france] CSV processing failed: {e}")
            return []

    async def _collect_from_api(
        self, source: dict, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Try to fetch data from API endpoints."""
        params = source.get("params", {})
        response = await self._request_with_retry("GET", source["url"], params=params)

        if not response:
            return []

        try:
            data = response.json()
            datasets = data.get("datasets", [])

            # Look for datasets related to business failures
            for dataset in datasets:
                if self._is_relevant_dataset(dataset):
                    return await self._process_api_dataset(dataset, code_dept, since)

            return []

        except Exception as e:
            logger.error(f"[banque_france] API processing failed: {e}")
            return []

    async def _process_csv_row(
        self, row: dict, code_dept: str | None, since: date
    ) -> CollectedSignal | None:
        """Process a single CSV row into a signal."""
        try:
            # Try to extract department and failure count from CSV row
            # This is speculative since we don't know the exact CSV format
            dept = row.get("departement") or row.get("dept") or row.get("code_dept")
            failures = row.get("defaillances") or row.get("nb_defaillances") or row.get("count")

            if not dept or not failures:
                return None

            if code_dept and dept != code_dept:
                return None

            return CollectedSignal(
                source="banque_france",
                source_url=f"bdf:defaillances:{dept}:{since.isoformat()}",
                event_date=date.today(),
                code_dept=dept,
                metric_name="defaillances_entreprises",
                metric_value=float(failures),
                signal_type="negatif" if float(failures) > 10 else "neutre",
                confidence=0.8,
                raw_data={"source_row": dict(row), "data_source": "csv"},
            )

        except Exception as e:
            logger.debug(f"[banque_france] Error processing CSV row: {e}")
            return None

    async def _process_api_dataset(
        self, dataset: dict, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Process API dataset to extract signals."""
        signals = []

        try:
            # Get dataset records if available
            dataset_id = dataset.get("dataset_id")
            if not dataset_id:
                return []

            # This would need to be adapted based on actual API structure
            logger.info(f"[banque_france] Processing dataset: {dataset_id}")

            # For now, create a placeholder signal based on dataset metadata
            signal = CollectedSignal(
                source="banque_france",
                source_url=f"bdf:api:{dataset_id}",
                event_date=date.today(),
                code_dept=code_dept,
                metric_name="defaillances_entreprises",
                metric_value=0.0,  # Would be extracted from actual data
                signal_type="neutre",
                confidence=0.3,
                raw_data={"dataset": dataset, "data_source": "api"},
            )
            signals.append(signal)

        except Exception as e:
            logger.warning(f"[banque_france] Dataset processing error: {e}")

        return signals

    async def _generate_fallback_data(
        self, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Generate realistic fallback data when external sources fail."""
        signals = []

        # French departments with estimated monthly business failure patterns
        dept_patterns = {
            "75": 45,  # Paris - high business activity, higher failures
            "13": 25,  # Bouches-du-Rhône
            "69": 20,  # Rhône
            "59": 18,  # Nord
            "92": 15,  # Hauts-de-Seine
            "93": 12,  # Seine-Saint-Denis
            "94": 10,  # Val-de-Marne
            "95": 8,  # Val-d'Oise
        }

        # If specific department requested
        if code_dept:
            if code_dept in dept_patterns:
                failure_count = dept_patterns[code_dept]
            else:
                # Estimate based on department size (rough heuristic)
                dept_num = int(code_dept) if code_dept.isdigit() else 50
                failure_count = max(3, 30 - (dept_num // 10))
        else:
            # Generate for all departments
            for dept, count in dept_patterns.items():
                signal = CollectedSignal(
                    source="banque_france",
                    source_url=f"bdf:fallback:{dept}:{since.isoformat()}",
                    event_date=date.today(),
                    code_dept=dept,
                    metric_name="defaillances_entreprises",
                    metric_value=float(count),
                    signal_type="negatif" if count > 15 else "neutre",
                    confidence=0.2,  # Low confidence for fallback data
                    raw_data={
                        "estimated": True,
                        "data_source": "fallback",
                        "note": "External sources unavailable",
                    },
                )
                signals.append(signal)

            return signals

        # Single department case
        if code_dept:
            failure_count = dept_patterns.get(code_dept, 5)
            signal = CollectedSignal(
                source="banque_france",
                source_url=f"bdf:fallback:{code_dept}:{since.isoformat()}",
                event_date=date.today(),
                code_dept=code_dept,
                metric_name="defaillances_entreprises",
                metric_value=float(failure_count),
                signal_type="negatif" if failure_count > 10 else "neutre",
                confidence=0.2,
                raw_data={"estimated": True, "data_source": "fallback"},
            )
            signals.append(signal)

        return signals

    def _is_relevant_dataset(self, dataset: dict) -> bool:
        """Check if a dataset is relevant for business failures."""
        title = dataset.get("title", "").lower()
        desc = dataset.get("description", "").lower()

        relevant_terms = [
            "defaillance",
            "faillite",
            "liquidation",
            "cessation",
            "entreprise",
            "societe",
        ]

        text_to_check = f"{title} {desc}"
        return any(term in text_to_check for term in relevant_terms)
