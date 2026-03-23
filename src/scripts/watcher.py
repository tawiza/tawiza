#!/usr/bin/env python3
"""Watcher Service  -  Surveillance continue des indicateurs territoriaux.

Toutes les N minutes, compare les dernières valeurs aux moyennes historiques
et détecte les changements significatifs (seuils configurables).

Alertes stockées dans la table `watcher_alerts` et exposées via API.
"""

import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import os

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5433/tawiza")

# ─── Configuration ────────────────────────────────────────────

WATCH_INTERVAL_MINUTES = 30  # Check every 30 min
LOOKBACK_DAYS = 90  # Historical baseline window
Z_THRESHOLD = 2.0  # Z-score threshold for alert
MIN_DATA_POINTS = 5  # Minimum points for baseline

# Metrics to watch, grouped by priority
WATCHED_METRICS = {
    "high": [
        "liquidation_judiciaire",
        "radiation",
        "offre_emploi_cdi",
        "offre_emploi_cdd",
        "transaction_immobiliere",
    ],
    "medium": [
        "creation_entreprise",
        "modification_entreprise",
        "permis_construire",
        "capacite_autofinancement",
        "dette_bancaire",
    ],
    "low": [
        "taux_moyen_tfb",
        "taux_moyen_cfe",
        "recettes_fonctionnement",
        "epargne_brute",
    ],
}

ALL_METRICS = []
for v in WATCHED_METRICS.values():
    ALL_METRICS.extend(v)


@dataclass
class Alert:
    department: str
    metric: str
    priority: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    direction: str  # "up" or "down"
    message: str
    detected_at: datetime


async def ensure_table(conn):
    """Create watcher_alerts table if needed."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS watcher_alerts (
            id SERIAL PRIMARY KEY,
            department TEXT NOT NULL,
            metric TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            current_value DOUBLE PRECISION,
            baseline_mean DOUBLE PRECISION,
            baseline_std DOUBLE PRECISION,
            z_score DOUBLE PRECISION,
            direction TEXT,
            message TEXT,
            detected_at TIMESTAMPTZ DEFAULT NOW(),
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_watcher_alerts_dept ON watcher_alerts(department);
        CREATE INDEX IF NOT EXISTS idx_watcher_alerts_date ON watcher_alerts(detected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_watcher_alerts_ack ON watcher_alerts(acknowledged);
    """)


def get_priority(metric: str) -> str:
    for prio, metrics in WATCHED_METRICS.items():
        if metric in metrics:
            return prio
    return "low"


async def compute_baselines(conn, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """Compute mean + stddev per (dept, metric) over the lookback window."""
    cutoff = date.today() - timedelta(days=lookback_days)

    rows = await conn.fetch(
        """
        SELECT code_dept, metric_name,
               AVG(metric_value) as mean_val,
               STDDEV(metric_value) as std_val,
               COUNT(*) as cnt
        FROM signals
        WHERE metric_value IS NOT NULL
          AND event_date >= $1
          AND metric_name = ANY($2)
        GROUP BY code_dept, metric_name
        HAVING COUNT(*) >= $3
    """,
        cutoff,
        ALL_METRICS,
        MIN_DATA_POINTS,
    )

    baselines = {}
    for r in rows:
        key = (r["code_dept"], r["metric_name"])
        baselines[key] = {
            "mean": float(r["mean_val"]),
            "std": float(r["std_val"]) if r["std_val"] else 0.0,
            "count": r["cnt"],
        }

    return baselines


async def get_latest_values(conn, days: int = 7) -> list:
    """Get latest signal values per (dept, metric) from last N days."""
    cutoff = date.today() - timedelta(days=days)

    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (code_dept, metric_name)
               code_dept, metric_name, metric_value, event_date, collected_at
        FROM signals
        WHERE metric_value IS NOT NULL
          AND event_date >= $1
          AND metric_name = ANY($2)
        ORDER BY code_dept, metric_name, collected_at DESC
    """,
        cutoff,
        ALL_METRICS,
    )

    return rows


async def detect_alerts(conn) -> list[Alert]:
    """Compare latest values to baselines and generate alerts."""
    logger.info("Computing baselines...")
    baselines = await compute_baselines(conn)
    logger.info(f"  {len(baselines)} baselines computed")

    logger.info("Fetching latest values...")
    latest = await get_latest_values(conn)
    logger.info(f"  {len(latest)} recent values found")

    alerts = []
    now = datetime.now()

    for row in latest:
        dept = row["code_dept"]
        metric = row["metric_name"]
        value = float(row["metric_value"])
        key = (dept, metric)

        if key not in baselines:
            continue

        bl = baselines[key]
        if bl["std"] < 0.001:  # No variance = no anomaly possible
            continue

        z = (value - bl["mean"]) / bl["std"]

        if abs(z) >= Z_THRESHOLD:
            direction = "up" if z > 0 else "down"
            priority = get_priority(metric)
            pct_change = ((value - bl["mean"]) / bl["mean"] * 100) if bl["mean"] != 0 else 0

            metric_label = metric.replace("_", " ").title()
            msg = (
                f"Dept {dept}: {metric_label} "
                f"{'en hausse' if direction == 'up' else 'en baisse'} significative "
                f"({pct_change:+.1f}%, z={z:.1f}). "
                f"Valeur: {value:.1f}, Moyenne: {bl['mean']:.1f}"
            )

            alerts.append(
                Alert(
                    department=dept,
                    metric=metric,
                    priority=priority,
                    current_value=value,
                    baseline_mean=bl["mean"],
                    baseline_std=bl["std"],
                    z_score=round(z, 2),
                    direction=direction,
                    message=msg,
                    detected_at=now,
                )
            )

    # Sort by priority then z-score
    prio_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: (prio_order.get(a.priority, 3), -abs(a.z_score)))

    return alerts


async def store_alerts(conn, alerts: list[Alert]) -> int:
    """Store new alerts, skip duplicates from last 24h."""
    if not alerts:
        return 0

    cutoff = datetime.now() - timedelta(hours=24)
    stored = 0

    for a in alerts:
        # Check for recent duplicate
        existing = await conn.fetchval(
            """
            SELECT id FROM watcher_alerts
            WHERE department = $1 AND metric = $2 AND detected_at > $3
            LIMIT 1
        """,
            a.department,
            a.metric,
            cutoff,
        )

        if existing:
            continue

        await conn.execute(
            """
            INSERT INTO watcher_alerts (department, metric, priority, current_value,
                baseline_mean, baseline_std, z_score, direction, message, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            a.department,
            a.metric,
            a.priority,
            a.current_value,
            a.baseline_mean,
            a.baseline_std,
            a.z_score,
            a.direction,
            a.message,
            a.detected_at,
        )
        stored += 1

    return stored


async def run_once():
    """Single watch cycle."""
    import asyncpg

    conn = await asyncpg.connect(DB_URL)

    try:
        await ensure_table(conn)
        alerts = await detect_alerts(conn)

        if alerts:
            stored = await store_alerts(conn, alerts)
            logger.info(f"  {len(alerts)} alertes detectees, {stored} nouvelles stockees")

            # Log top alerts
            for a in alerts[:10]:
                icon = "!!" if a.priority == "high" else "!" if a.priority == "medium" else "."
                logger.info(f"  {icon} [{a.priority}] {a.message}")
        else:
            logger.info("  Aucune alerte detectee")

        return alerts
    finally:
        await conn.close()


async def run_daemon():
    """Continuous watch loop."""
    logger.info(
        f"Watcher demarrage  -  intervalle {WATCH_INTERVAL_MINUTES} min, seuil z={Z_THRESHOLD}"
    )

    while True:
        try:
            logger.info(f"\n{'=' * 50}")
            logger.info(f"Cycle de surveillance  -  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"{'=' * 50}")

            await run_once()

        except Exception as e:
            logger.error(f"Erreur watcher: {e}")

        logger.info(f"Prochain cycle dans {WATCH_INTERVAL_MINUTES} min...")
        await asyncio.sleep(WATCH_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watcher  -  Surveillance territoriale continue")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--interval", type=int, default=WATCH_INTERVAL_MINUTES, help="Interval in minutes"
    )
    parser.add_argument("--threshold", type=float, default=Z_THRESHOLD, help="Z-score threshold")
    args = parser.parse_args()

    WATCH_INTERVAL_MINUTES = args.interval
    Z_THRESHOLD = args.threshold

    if args.once:
        asyncio.run(run_once())
    else:
        asyncio.run(run_daemon())
