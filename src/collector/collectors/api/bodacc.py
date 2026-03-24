"""BODACC collector - Procédures collectives (liquidations, redressements).

Source: https://bodacc-datadila.opendatasoft.com
Free API, no auth needed. 3.2M+ procédures collectives.

Key families:
- collective: procédures collectives (liquidation, redressement, sauvegarde)
- vente: ventes et cessions de fonds de commerce
- creation: immatriculations RCS
- radiation: radiations RCS

Jugement nature types for collective:
- "Jugement d'ouverture de Liquidation judiciaire"
- "Jugement d'ouverture de Redressement judiciaire"
- "Jugement d'ouverture de Sauvegarde"
- "Jugement de conversion en Liquidation judiciaire"
- "Jugement de clôture pour insuffisance d'actif"
"""

import json
from datetime import date, timedelta
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

BODACC_API = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"

# Signal classification by nature keywords
NATURE_SIGNALS = {
    "liquidation": ("liquidation_judiciaire", "negatif", 0.95),
    "redressement": ("redressement_judiciaire", "negatif", 0.85),
    "sauvegarde": ("sauvegarde", "negatif", 0.7),
    "clôture pour insuffisance": ("cloture_insuffisance_actif", "negatif", 0.9),
    "plan de cession": ("plan_cession", "negatif", 0.8),
    "plan de continuation": ("plan_continuation", "positif", 0.7),
    "plan de redressement": ("plan_redressement", "positif", 0.65),
}


class BodaccCollector(BaseCollector):
    """Collect business distress signals from BODACC procédures collectives."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="bodacc",
                source_type="api",
                rate_limit=5,
                timeout=30,
            )
        )

    async def collect(
        self,
        code_dept: str | None = None,
        since: date | None = None,
        families: list[str] | None = None,
    ) -> list[CollectedSignal]:
        """Collect BODACC signals.

        Args:
            code_dept: Department code filter
            since: Start date (default: 30 days ago)
            families: BODACC families to query (default: collective + vente)
        """
        if since is None:
            since = date.today() - timedelta(days=30)
        if families is None:
            families = ["collective", "vente"]

        all_signals: list[CollectedSignal] = []

        for family in families:
            try:
                signals = await self._collect_family(family, code_dept, since)
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"[bodacc] Error on family {family}: {e}")

        logger.info(f"[bodacc] {code_dept or 'all'}: {len(all_signals)} signals collected")
        return all_signals

    async def _collect_family(
        self, family: str, code_dept: str | None, since: date
    ) -> list[CollectedSignal]:
        """Collect one BODACC family."""
        signals: list[CollectedSignal] = []
        offset = 0
        limit = 100
        max_records = 5000  # Safety limit per family/dept

        while offset < max_records:
            where_parts = [
                f'familleavis="{family}"',
                f'dateparution>="{since.isoformat()}"',
            ]
            if code_dept:
                where_parts.append(f'numerodepartement="{code_dept}"')

            params = {
                "where": " AND ".join(where_parts),
                "order_by": "dateparution DESC",
                "limit": limit,
                "offset": offset,
            }

            response = await self._request_with_retry("GET", BODACC_API, params=params)
            if not response or response.status_code != 200:
                break

            data = response.json()
            results = data.get("results", [])
            if not results:
                break

            for record in results:
                signal = self._parse_record(record, family)
                if signal:
                    signals.append(signal)

            offset += limit
            if offset >= data.get("total_count", 0):
                break

        return signals

    def _parse_record(self, record: dict[str, Any], family: str) -> CollectedSignal | None:
        """Parse a BODACC record into a signal."""
        dept = record.get("numerodepartement", "")
        if not dept:
            return None

        date_str = record.get("dateparution", "")
        try:
            event_date = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            event_date = date.today()

        commercant = record.get("commercant", "") or ""
        ville = record.get("ville", "") or ""
        cp = record.get("cp", "") or ""
        url = (
            record.get("url_complete", "")
            or f"https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:{record.get('id', '')}"
        )

        # Parse jugement for collective procedures
        jugement_raw = record.get("jugement", "") or ""
        nature = ""
        jugement_detail = ""
        if jugement_raw:
            try:
                j = json.loads(jugement_raw)
                nature = j.get("nature", "") or ""
                jugement_detail = j.get("complementJugement", "") or ""
            except (json.JSONDecodeError, TypeError):
                nature = jugement_raw[:100] if isinstance(jugement_raw, str) else ""

        # Classify signal
        metric_name, signal_type, confidence = self._classify(family, nature, jugement_detail)

        # Extract commune code from CP
        code_commune = None
        if cp and len(cp) == 5:
            # Approximate: CP → commune (not always 1:1 but good enough)
            code_commune = cp

        # Extract SIREN from registre
        registre = record.get("registre", []) or []
        siren = registre[0] if registre else None

        return CollectedSignal(
            source="bodacc",
            source_url=url,
            event_date=event_date,
            code_dept=dept,
            code_commune=code_commune,
            metric_name=metric_name,
            metric_value=1.0,
            signal_type=signal_type,
            confidence=confidence,
            raw_data={
                "commercant": commercant[:100],
                "ville": ville,
                "cp": cp,
                "nature": nature[:100],
                "famille": family,
                "siren": siren,
                "tribunal": (record.get("tribunal", "") or "")[:80],
            },
        )

    def _classify(self, family: str, nature: str, detail: str) -> tuple[str, str, float]:
        """Classify a BODACC record into metric/signal type."""
        nature_lower = (nature + " " + detail).lower()

        # Check nature keywords for collective procedures
        for keyword, (metric, sig_type, conf) in NATURE_SIGNALS.items():
            if keyword in nature_lower:
                return metric, sig_type, conf

        # Family-based defaults
        family_defaults = {
            "collective": ("procedure_collective", "negatif", 0.8),
            "vente": ("vente_fonds_commerce", "neutre", 0.7),
            "creation": ("immatriculation_rcs", "positif", 0.8),
            "radiation": ("radiation_rcs", "negatif", 0.85),
        }
        return family_defaults.get(family, (f"bodacc_{family}", "neutre", 0.5))
