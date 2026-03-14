"""
EPCI-level scoring — aggregate signals at intercommunality level.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from .referentiel import get_referentiel

logger = logging.getLogger(__name__)


async def get_epci_scores(
    engine: AsyncEngine,
    code_dept: str | None = None,
    days: int = 180,
) -> list[dict[str, Any]]:
    """
    Calculate composite scores for EPCIs, similar to department scoring.

    Args:
        engine: Async SQLAlchemy engine
        code_dept: Optional department filter
        days: Lookback period

    Returns:
        List of EPCI scores with details
    """
    ref = await get_referentiel()
    since = date.today() - timedelta(days=days)

    # Get signals aggregated by EPCI
    query = """
    SELECT
        code_epci,
        metric_name,
        AVG(metric_value) as avg_value,
        COUNT(*) as signal_count,
        COUNT(DISTINCT source) as source_count
    FROM signals
    WHERE code_epci IS NOT NULL
        AND code_epci != ''
        AND event_date >= :since
        AND metric_value IS NOT NULL
    """
    params: dict = {"since": since}

    if code_dept:
        query += " AND code_dept = :dept"
        params["dept"] = code_dept

    query += """
    GROUP BY code_epci, metric_name
    HAVING COUNT(*) >= 2
    ORDER BY code_epci
    """

    async with engine.connect() as conn:
        result = await conn.execute(text(query), params)
        rows = result.fetchall()

    if not rows:
        return []

    # Build per-EPCI metric profiles
    epci_metrics: dict[str, dict[str, float]] = {}
    epci_signal_counts: dict[str, int] = {}
    epci_source_counts: dict[str, int] = {}

    for row in rows:
        code_epci = row[0]
        metric = row[1]
        avg_val = float(row[2])
        sig_count = int(row[3])
        src_count = int(row[4])

        if code_epci not in epci_metrics:
            epci_metrics[code_epci] = {}
            epci_signal_counts[code_epci] = 0
            epci_source_counts[code_epci] = 0

        epci_metrics[code_epci][metric] = avg_val
        epci_signal_counts[code_epci] += sig_count
        epci_source_counts[code_epci] = max(epci_source_counts[code_epci], src_count)

    # Score factors (same logic as department scoring)
    factors = {
        "emploi": ["offres_emploi", "demandeurs_emploi_abc", "tension_emploi"],
        "entreprises": [
            "creation_entreprise",
            "immatriculation_entreprise",
            "liquidation_judiciaire",
            "redressement_judiciaire",
        ],
        "immobilier": ["transactions_immobilieres", "prix_m2_median", "prix_m2_moyen"],
        "construction": ["logements_autorises", "logements_commences"],
        "presse": ["presse_fermeture", "presse_licenciement", "presse_ouverture"],
    }

    scored_epcis = []

    for code_epci, metrics in epci_metrics.items():
        pop = ref.epci_population(code_epci)
        name = ref.epci_name(code_epci)
        depts = ref.epci_departments(code_epci)

        factor_scores = {}
        for factor_name, metric_keys in factors.items():
            values = [metrics.get(k, 0) for k in metric_keys if k in metrics]
            if values:
                # Normalize by population if available
                raw = np.mean(values)
                if pop > 0 and factor_name in ("emploi", "entreprises", "immobilier"):
                    raw = raw / (pop / 10000)  # per 10k inhabitants
                factor_scores[factor_name] = float(raw)

        # Composite score (0-100 scale)
        if factor_scores:
            # Simple average of z-scored factors
            vals = list(factor_scores.values())
            composite = 50 + 10 * np.mean(vals) if vals else 50
            composite = max(0, min(100, composite))
        else:
            composite = 50

        scored_epcis.append(
            {
                "code_epci": code_epci,
                "nom": name,
                "population": pop,
                "departments": depts,
                "composite_score": round(float(composite), 2),
                "factor_scores": factor_scores,
                "signal_count": epci_signal_counts.get(code_epci, 0),
                "source_count": epci_source_counts.get(code_epci, 0),
            }
        )

    # Sort by composite score descending
    scored_epcis.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored_epcis


async def get_epci_signals(
    engine: AsyncEngine,
    code_epci: str,
    days: int = 90,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get signals for a specific EPCI."""
    since = date.today() - timedelta(days=days)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, source, event_date, code_commune, code_dept,
                       metric_name, metric_value, signal_type, confidence
                FROM signals
                WHERE code_epci = :epci
                  AND event_date >= :since
                ORDER BY event_date DESC
                LIMIT :limit
            """),
            {"epci": code_epci, "since": since.isoformat(), "limit": limit},
        )
        rows = result.fetchall()

    return [
        {
            "id": r[0],
            "source": r[1],
            "date": r[2].isoformat() if r[2] else None,
            "commune": r[3],
            "dept": r[4],
            "metric": r[5],
            "value": float(r[6]) if r[6] else None,
            "type": r[7],
            "confidence": float(r[8]) if r[8] else None,
        }
        for r in rows
    ]
