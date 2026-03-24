"""
Sitadel collector  -  permis de construire (logements + locaux).

Source: SDES DiDo API (data.statistiques.developpement-durable.gouv.fr)
Data: Monthly departmental series, housing permits + non-residential permits.
Free, no auth required, updated monthly.

Signals generated:
- logements_autorises: number of housing permits authorized
- logements_commences: number of housing starts (DOC)
- locaux_autorises_m2: surface of non-residential permits (m²)
- locaux_commences_m2: surface of non-residential starts (m²)
"""

import csv
import io
from datetime import date
from typing import Any

import httpx
from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

DIDO_BASE = "https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1"

# Datafile RIDs from DiDo API
LOGEMENTS_DEPT_RID = "d264957b-c6d2-4efa-bf5e-6a8da836550a"
LOCAUX_DEPT_RID = "a301bf87-730c-400a-87e0-ce71b7b1d1af"


class SitadelCollector(BaseCollector):
    """Collect building permit data from Sitadel (SDES DiDo API)."""

    source_name = "sitadel"

    def __init__(
        self,
        departments: list[str] | None = None,
        recent_months: int = 12,
    ) -> None:
        """
        Args:
            departments: Filter to these department codes. None = all.
            recent_months: Only keep last N months of data.
        """
        super().__init__(CollectorConfig(name="sitadel", source_type="api"))
        self._departments = departments
        self._recent_months = recent_months

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect housing and non-residential permit signals."""
        if code_dept:
            self._departments = [code_dept]

        signals: list[dict[str, Any]] = []

        # 1. Housing permits (logements)
        housing = await self._fetch_csv(LOGEMENTS_DEPT_RID)
        signals.extend(self._parse_housing(housing))

        # 2. Non-residential permits (locaux)
        locaux = await self._fetch_csv(LOCAUX_DEPT_RID)
        signals.extend(self._parse_locaux(locaux))

        logger.info(f"[sitadel] Collected {len(signals)} signals")

        # Convert dicts to CollectedSignal objects
        return [
            CollectedSignal(
                source=s.get("source", self.source_name),
                source_url=s.get("source_url"),
                event_date=s.get("event_date"),
                code_dept=s.get("code_dept"),
                metric_name=s.get("metric_name", ""),
                metric_value=float(s["metric_value"])
                if s.get("metric_value") is not None
                else None,
                signal_type="neutre",
                confidence=0.8,
                raw_data=s.get("raw_data"),
            )
            for s in signals
        ]

    async def _fetch_csv(self, rid: str) -> list[dict[str, str]]:
        """Fetch CSV from DiDo API."""
        url = (
            f"{DIDO_BASE}/datafiles/{rid}/csv"
            f"?millesime=2026-02&withColumnName=true"
            f"&withColumnDescription=false&withColumnUnit=false"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text), delimiter=";")
        return list(reader)

    def _parse_housing(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Parse housing CSV into signals."""
        signals = []
        cutoff = self._cutoff_date()

        for row in rows:
            try:
                year = int(row.get("ANNEE", "").strip('"'))
                month = int(row.get("MOIS", "").strip('"'))
                dept = row.get("DEPARTEMENT_CODE", "").strip('"')
                type_lgt = row.get("TYPE_LGT", "").strip('"')

                ev_date = date(year, month, 1)
                if ev_date < cutoff:
                    continue

                if self._departments and dept not in self._departments:
                    continue

                # Logements autorisés
                log_aut = self._parse_int(row.get("LOG_AUT", ""))
                if log_aut is not None and log_aut > 0:
                    signals.append(
                        {
                            "source": self.source_name,
                            "source_url": f"https://data.statistiques.developpement-durable.gouv.fr/sitadel/logements/{dept}/{year}-{month:02d}",
                            "metric_name": f"logements_autorises_{type_lgt.lower().replace(' ', '_')}",
                            "metric_value": log_aut,
                            "code_dept": dept,
                            "event_date": ev_date,
                            "raw_data": {
                                "type_logement": type_lgt,
                                "dept_libelle": row.get("DEPARTEMENT_LIBELLE", "").strip('"'),
                                "log_commences": self._parse_int(row.get("LOG_COM", "")),
                                "sdp_autorisee": self._parse_int(row.get("SDP_AUT", "")),
                                "sdp_commencee": self._parse_int(row.get("SDP_COM", "")),
                            },
                        }
                    )

                # Logements commencés
                log_com = self._parse_int(row.get("LOG_COM", ""))
                if log_com is not None and log_com > 0:
                    signals.append(
                        {
                            "source": self.source_name,
                            "source_url": f"https://data.statistiques.developpement-durable.gouv.fr/sitadel/chantiers/{dept}/{year}-{month:02d}",
                            "metric_name": f"logements_commences_{type_lgt.lower().replace(' ', '_')}",
                            "metric_value": log_com,
                            "code_dept": dept,
                            "event_date": ev_date,
                            "raw_data": {
                                "type_logement": type_lgt,
                                "dept_libelle": row.get("DEPARTEMENT_LIBELLE", "").strip('"'),
                            },
                        }
                    )

            except (ValueError, KeyError):
                continue

        return signals

    def _parse_locaux(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Parse non-residential CSV into signals."""
        signals = []
        cutoff = self._cutoff_date()

        for row in rows:
            try:
                year = int(row.get("ANNEE", "").strip('"'))
                month = int(row.get("MOIS", "").strip('"'))
                dept = row.get("DEPARTEMENT_CODE", "").strip('"')

                ev_date = date(year, month, 1)
                if ev_date < cutoff:
                    continue

                if self._departments and dept not in self._departments:
                    continue

                # Find destination column  -  varies by CSV structure
                dest = row.get("DESTINATION_LIBELLE", row.get("DEST_LIBELLE", "")).strip('"')

                # Surfaces autorisées
                surf_aut = self._parse_int(row.get("SDP_AUT", row.get("SURFACE_AUT", "")))
                if surf_aut is not None and surf_aut > 0:
                    metric_suffix = (
                        dest.lower().replace(" ", "_").replace("'", "") if dest else "total"
                    )
                    signals.append(
                        {
                            "source": self.source_name,
                            "source_url": f"https://data.statistiques.developpement-durable.gouv.fr/sitadel/locaux/{dept}/{year}-{month:02d}/{metric_suffix}",
                            "metric_name": f"locaux_autorises_m2_{metric_suffix}",
                            "metric_value": surf_aut,
                            "code_dept": dept,
                            "event_date": ev_date,
                            "raw_data": {
                                "destination": dest,
                                "dept_libelle": row.get("DEPARTEMENT_LIBELLE", "").strip('"'),
                            },
                        }
                    )

            except (ValueError, KeyError):
                continue

        return signals

    def _cutoff_date(self) -> date:
        """Calculate cutoff date based on recent_months."""
        today = date.today()
        year = today.year
        month = today.month - self._recent_months
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    @staticmethod
    def _parse_int(val: str | None) -> int | None:
        """Parse integer from possibly quoted CSV value."""
        if not val:
            return None
        val = val.strip().strip('"')
        if not val or val in ("", "s", "nd", "n.d."):
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None
