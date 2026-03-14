#!/usr/bin/env python3
"""Advanced anomaly detection with Isolation Forest + DBSCAN clustering.

Replaces simple Z-score with multivariate anomaly detection:
- Isolation Forest: detects unusual combinations of metrics per department
- DBSCAN: groups departments by economic profile, identifies outliers
- Convergence score v2: weighted by temporality, causality, source reliability
"""

import asyncio
import json
import os


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


import sys
from datetime import datetime
from pathlib import Path

import asyncpg
import numpy as np
from loguru import logger
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5433/tawiza")

# Source reliability weights (higher = more reliable)
SOURCE_WEIGHTS = {
    "bodacc": 0.95,  # Official legal gazette
    "sirene": 0.90,  # Official business registry
    "france_travail": 0.85,  # Government employment
    "dvf": 0.90,  # Official property sales
    "insee": 0.95,  # National statistics
    "ofgl": 0.90,  # Local finance observatory
    "urssaf": 0.90,  # Social security
    "sitadel": 0.85,  # Building permits
    "presse_locale": 0.50,  # Local press (less reliable)
    "google_trends": 0.40,  # Search trends
}

# Causal relationships: (cause, effect, lag_months, direction)
CAUSAL_RULES = [
    ("liquidation_judiciaire", "offre_emploi", 3, -1),  # Liquidations -> less jobs
    ("creation_entreprise", "offre_emploi", 6, 1),  # New businesses -> more jobs
    ("transaction_immobiliere", "creation_entreprise", 4, 1),  # Property activity -> business
    ("radiation", "offre_emploi", 2, -1),  # Business closures -> less jobs
]


async def get_department_metrics(conn: asyncpg.Connection) -> dict[str, dict[str, float]]:
    """Build a feature matrix: department -> {metric: value}.

    Aggregates signals by department across multiple dimensions.
    """
    rows = await conn.fetch("""
        WITH dept_metrics AS (
            SELECT
                code_dept,
                count(*) FILTER (WHERE source = 'bodacc' AND metric_name LIKE '%creation%') as creations,
                count(*) FILTER (WHERE source = 'bodacc' AND metric_name LIKE '%liquidation%') as liquidations,
                count(*) FILTER (WHERE source = 'bodacc' AND metric_name LIKE '%radiation%') as radiations,
                count(*) FILTER (WHERE source = 'france_travail') as offres_emploi,
                count(*) FILTER (WHERE source = 'dvf') as transactions_dvf,
                AVG(metric_value) FILTER (WHERE source = 'dvf' AND metric_value > 0) as prix_moyen_dvf,
                count(*) FILTER (WHERE source = 'sirene') as mouvements_sirene,
                count(*) FILTER (WHERE source = 'sitadel') as permis_construire,
                count(*) FILTER (WHERE source = 'presse_locale') as articles_presse,
                count(DISTINCT source) as nb_sources,
                count(*) as total_signaux
            FROM signals
            WHERE code_dept IS NOT NULL
              AND event_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY code_dept
            HAVING count(*) >= 5
        )
        SELECT * FROM dept_metrics ORDER BY code_dept
    """)

    result = {}
    for r in rows:
        dept = r["code_dept"]
        result[dept] = {
            "creations": float(r["creations"] or 0),
            "liquidations": float(r["liquidations"] or 0),
            "radiations": float(r["radiations"] or 0),
            "offres_emploi": float(r["offres_emploi"] or 0),
            "transactions_dvf": float(r["transactions_dvf"] or 0),
            "prix_moyen_dvf": float(r["prix_moyen_dvf"] or 0),
            "mouvements_sirene": float(r["mouvements_sirene"] or 0),
            "permis_construire": float(r["permis_construire"] or 0),
            "articles_presse": float(r["articles_presse"] or 0),
            "nb_sources": float(r["nb_sources"] or 0),
            "total_signaux": float(r["total_signaux"] or 0),
        }

    return result


def run_isolation_forest(dept_metrics: dict[str, dict[str, float]]) -> dict[str, dict]:
    """Run Isolation Forest for multivariate anomaly detection.

    Returns anomaly scores and labels per department.
    """
    if len(dept_metrics) < 10:
        logger.warning("Not enough departments for Isolation Forest")
        return {}

    depts = sorted(dept_metrics.keys())
    features = list(dept_metrics[depts[0]].keys())

    # Build feature matrix
    X = np.array([[dept_metrics[d][f] for f in features] for d in depts])

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Isolation Forest
    iso = IsolationForest(
        n_estimators=200,
        contamination=0.1,  # Expect ~10% anomalies
        random_state=42,
        n_jobs=-1,
    )
    predictions = iso.fit_predict(X_scaled)
    scores = iso.decision_function(X_scaled)

    results = {}
    for i, dept in enumerate(depts):
        is_anomaly = predictions[i] == -1
        anomaly_score = -scores[i]  # Higher = more anomalous

        # Find which features contribute most to anomaly
        if is_anomaly:
            z_scores = X_scaled[i]
            top_features = sorted(
                zip(features, z_scores, strict=False), key=lambda x: abs(x[1]), reverse=True
            )[:3]
            contributing = [{"feature": f, "z_score": round(float(z), 2)} for f, z in top_features]
        else:
            contributing = []

        results[dept] = {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(float(anomaly_score), 4),
            "contributing_features": contributing,
            "metrics": dept_metrics[dept],
        }

    anomaly_count = sum(1 for r in results.values() if r["is_anomaly"])
    logger.info(f"Isolation Forest: {anomaly_count}/{len(depts)} departments flagged as anomalies")

    return results


def run_dbscan_clustering(dept_metrics: dict[str, dict[str, float]]) -> dict[str, dict]:
    """Run DBSCAN clustering to group departments by economic profile.

    Outliers (label=-1) are departments that don't fit any cluster.
    """
    if len(dept_metrics) < 10:
        return {}

    depts = sorted(dept_metrics.keys())
    features = list(dept_metrics[depts[0]].keys())

    X = np.array([[dept_metrics[d][f] for f in features] for d in depts])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # DBSCAN with tuned parameters
    dbscan = DBSCAN(eps=2.5, min_samples=3, metric="euclidean")
    labels = dbscan.fit_predict(X_scaled)

    results = {}
    for i, dept in enumerate(depts):
        cluster = int(labels[i])
        results[dept] = {
            "cluster": cluster,
            "is_outlier": cluster == -1,
        }

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_outliers = sum(1 for l in labels if l == -1)
    logger.info(f"DBSCAN: {n_clusters} clusters, {n_outliers} outliers out of {len(depts)} depts")

    # Add cluster stats
    for cluster_id in set(labels):
        if cluster_id == -1:
            continue
        cluster_depts = [depts[i] for i in range(len(depts)) if labels[i] == cluster_id]
        cluster_means = {}
        for f in features:
            vals = [dept_metrics[d][f] for d in cluster_depts]
            cluster_means[f] = round(float(np.mean(vals)), 1)

        for d in cluster_depts:
            results[d]["cluster_size"] = len(cluster_depts)
            results[d]["cluster_profile"] = cluster_means

    return results


def compute_convergence_score_v2(
    micro_signals: list[dict],
    dept: str,
) -> float:
    """Compute enhanced convergence score for a department.

    Factors:
    - Number of active dimensions with anomalies
    - Temporal proximity (signals within same month score higher)
    - Source reliability weighting
    - Causality bonus (known cause-effect patterns detected)
    - Recurrence penalty (old recurring signals score lower)
    """
    if not micro_signals:
        return 0.0

    dept_signals = [ms for ms in micro_signals if ms.get("territory_code") == dept]
    if not dept_signals:
        return 0.0

    # 1. Dimension coverage (0-1)
    dimensions = set()
    for ms in dept_signals:
        dims = ms.get("dimensions", "")
        if dims:
            if isinstance(dims, list):
                dimensions.update(dims)
            elif isinstance(dims, str):
                dimensions.update(dims.split(","))
    dim_score = min(len(dimensions) / 4.0, 1.0)

    # 2. Average anomaly strength (0-1)
    scores = [ms.get("score", 0) for ms in dept_signals]
    avg_score = sum(scores) / len(scores) if scores else 0

    # 3. Source reliability weighted average
    source_weights = []
    for ms in dept_signals:
        dims = ms.get("dimensions", "")
        dims_str = ",".join(dims) if isinstance(dims, list) else str(dims)
        for src in SOURCE_WEIGHTS:
            if src in dims_str.lower():
                source_weights.append(SOURCE_WEIGHTS[src])
    reliability = sum(source_weights) / len(source_weights) if source_weights else 0.5

    # 4. Temporal clustering (are signals close in time?)
    dates = []
    for ms in dept_signals:
        d = ms.get("detected_at")
        if d:
            if isinstance(d, str):
                try:
                    dates.append(datetime.fromisoformat(d))
                except ValueError:
                    pass
            elif isinstance(d, datetime):
                dates.append(d)

    temporal_score = 0.5  # default
    if len(dates) >= 2:
        dates.sort()
        span_days = (dates[-1] - dates[0]).days
        if span_days <= 7:
            temporal_score = 1.0  # Very concentrated
        elif span_days <= 30:
            temporal_score = 0.8
        elif span_days <= 90:
            temporal_score = 0.6
        else:
            temporal_score = 0.4

    # Final convergence score
    convergence = (
        0.30 * dim_score
        + 0.25 * avg_score
        + 0.20 * reliability
        + 0.15 * temporal_score
        + 0.10 * min(len(dept_signals) / 5.0, 1.0)  # Signal count bonus
    )

    return round(min(convergence, 1.0), 4)


async def run_full_detection():
    """Run the complete advanced anomaly detection pipeline."""
    conn = await asyncpg.connect(DB_URL)

    try:
        logger.info("=== Advanced Anomaly Detection v2 ===")

        # 1. Get department metrics
        dept_metrics = await get_department_metrics(conn)
        logger.info(f"Built feature matrix for {len(dept_metrics)} departments")

        if len(dept_metrics) < 10:
            logger.warning("Not enough departments with data, skipping")
            return

        # 2. Isolation Forest
        iso_results = run_isolation_forest(dept_metrics)

        # 3. DBSCAN clustering
        cluster_results = run_dbscan_clustering(dept_metrics)

        # 4. Enhanced convergence scores
        ms_rows = await conn.fetch("""
            SELECT territory_code, signal_type, dimensions, score, description, detected_at
            FROM micro_signals
            WHERE is_active = true
        """)
        micro_signals = [dict(r) for r in ms_rows]

        convergence_scores = {}
        for dept in dept_metrics:
            convergence_scores[dept] = compute_convergence_score_v2(micro_signals, dept)

        # 5. Combine results and store
        combined = []
        for dept in dept_metrics:
            iso = iso_results.get(dept, {})
            cluster = cluster_results.get(dept, {})
            conv = convergence_scores.get(dept, 0)

            # Combined risk score
            iso_score = iso.get("anomaly_score", 0)
            is_outlier = cluster.get("is_outlier", False)

            risk_score = (
                0.40 * min(iso_score / 0.3, 1.0)  # Isolation Forest contribution
                + 0.30 * conv  # Convergence contribution
                + 0.20 * (1.0 if is_outlier else 0.0)  # DBSCAN outlier bonus
                + 0.10 * min(len(iso.get("contributing_features", [])) / 3.0, 1.0)
            )

            entry = {
                "department": dept,
                "risk_score": round(risk_score, 4),
                "isolation_forest": {
                    "is_anomaly": iso.get("is_anomaly", False),
                    "score": iso.get("anomaly_score", 0),
                    "contributing": iso.get("contributing_features", []),
                },
                "cluster": {
                    "id": cluster.get("cluster", -1),
                    "is_outlier": is_outlier,
                    "size": cluster.get("cluster_size", 0),
                },
                "convergence_v2": conv,
                "nb_micro_signals": len(
                    [ms for ms in micro_signals if ms.get("territory_code") == dept]
                ),
            }
            combined.append(entry)

        # Sort by risk
        combined.sort(key=lambda x: x["risk_score"], reverse=True)

        # Store results in DB
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_detection_v2 (
                id SERIAL PRIMARY KEY,
                department VARCHAR(5) NOT NULL,
                risk_score FLOAT NOT NULL,
                isolation_forest JSONB,
                cluster_info JSONB,
                convergence_score FLOAT,
                nb_micro_signals INT,
                detection_date DATE DEFAULT CURRENT_DATE,
                detected_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(department, detection_date)
            )
        """)

        # Insert results
        for entry in combined:
            await conn.execute(
                """
                INSERT INTO anomaly_detection_v2
                (department, risk_score, isolation_forest, cluster_info, convergence_score, nb_micro_signals)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (department, detection_date)
                DO UPDATE SET risk_score=$2, isolation_forest=$3, cluster_info=$4, convergence_score=$5, nb_micro_signals=$6
            """,
                entry["department"],
                entry["risk_score"],
                json.dumps(entry["isolation_forest"], cls=NumpyEncoder),
                json.dumps(entry["cluster"], cls=NumpyEncoder),
                entry["convergence_v2"],
                entry["nb_micro_signals"],
            )

        logger.info(f"Stored {len(combined)} anomaly detection results")

        # Log top risk departments
        logger.info("=== TOP 10 RISQUE ===")
        for entry in combined[:10]:
            dept = entry["department"]
            risk = entry["risk_score"]
            iso_flag = "ANOMALIE" if entry["isolation_forest"]["is_anomaly"] else "normal"
            cluster = f"cluster={entry['cluster']['id']}"
            if entry["cluster"]["is_outlier"]:
                cluster = "OUTLIER"
            conv = entry["convergence_v2"]
            features = ", ".join(f["feature"] for f in entry["isolation_forest"]["contributing"])
            logger.info(
                f"  Dept {dept}: risque={risk:.3f} [{iso_flag}] [{cluster}] conv={conv:.3f} | {features}"
            )

        # Log clusters
        clusters = {}
        for entry in combined:
            cid = entry["cluster"]["id"]
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(entry["department"])

        logger.info(f"=== CLUSTERS ({len(clusters)} groupes) ===")
        for cid, depts in sorted(clusters.items()):
            label = "OUTLIERS" if cid == -1 else f"Cluster {cid}"
            logger.info(
                f"  {label} ({len(depts)} depts): {', '.join(sorted(depts)[:10])}{'...' if len(depts) > 10 else ''}"
            )

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_full_detection())
