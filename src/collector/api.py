"""FastAPI endpoints for the collector - signals & anomalies dashboard."""

import os
from datetime import UTC, date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query, Request
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text

from .storage.repository import SignalRepository

router = APIRouter(prefix="/api/collector", tags=["collector"])

# Rate limiter for collector endpoints
limiter = Limiter(key_func=get_remote_address)

_repo: SignalRepository | None = None


def get_repo() -> SignalRepository:
    """Get or create repository singleton."""
    global _repo
    if _repo is None:
        db_url = os.getenv(
            "COLLECTOR_DATABASE_URL",
            "postgresql+asyncpg://localhost:5433/tawiza",
        )
        _repo = SignalRepository(db_url)
    return _repo


@router.get("/signals")
@limiter.limit("60/minute")
async def get_signals(
    request: Request,
    code_dept: str | None = Query(None, description="Department code"),
    code_commune: str | None = Query(None, description="Commune INSEE code"),
    source: str | None = Query(None, description="Source filter"),
    metric: str | None = Query(None, description="Metric name filter"),
    days: int = Query(30, description="Lookback days"),
    limit: int = Query(100, description="Max results"),
) -> dict[str, Any]:
    """Get collected signals with filters."""
    repo = get_repo()
    since = date.today() - timedelta(days=days)

    signals = await repo.get_signals(
        code_dept=code_dept,
        code_commune=code_commune,
        source=source,
        metric_name=metric,
        since=since,
        limit=limit,
    )

    return {
        "count": len(signals),
        "signals": [
            {
                "id": s.id,
                "source": s.source,
                "event_date": s.event_date.isoformat() if s.event_date else None,
                "code_commune": s.code_commune,
                "code_dept": s.code_dept,
                "metric_name": s.metric_name,
                "metric_value": s.metric_value,
                "signal_type": s.signal_type,
                "confidence": s.confidence,
                "raw_data": s.raw_data,
            }
            for s in signals
        ],
    }


@router.get("/signals/summary")
@limiter.limit("60/minute")
async def get_signals_summary(
    request: Request,
    code_dept: str | None = Query(None),
    days: int = Query(30),
) -> dict[str, Any]:
    """Get aggregated signal summary for dashboard widgets."""
    repo = get_repo()
    since = date.today() - timedelta(days=days)

    signals = await repo.get_signals(code_dept=code_dept, since=since, limit=50000)

    # Aggregate by source
    by_source: dict[str, int] = {}
    by_metric: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_dept: dict[str, int] = {}

    for s in signals:
        by_source[s.source] = by_source.get(s.source, 0) + 1
        by_metric[s.metric_name] = by_metric.get(s.metric_name, 0) + 1
        by_type[s.signal_type or "neutre"] = by_type.get(s.signal_type or "neutre", 0) + 1
        if s.code_dept:
            by_dept[s.code_dept] = by_dept.get(s.code_dept, 0) + 1

    return {
        "total": len(signals),
        "period_days": days,
        "by_source": dict(sorted(by_source.items(), key=lambda x: -x[1])),
        "by_metric": dict(sorted(by_metric.items(), key=lambda x: -x[1])),
        "by_type": by_type,
        "by_department": dict(sorted(by_dept.items(), key=lambda x: -x[1])[:10]),
    }


@router.get("/health")
@limiter.limit("60/minute")
async def collector_health(request: Request) -> dict[str, Any]:
    """Health check for collector system."""
    repo = get_repo()

    try:
        # Check DB connectivity
        signals = await repo.get_signals(limit=1)
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "collectors": ["sirene", "france_travail", "presse_locale"],
    }


@router.get("/anomalies")
@limiter.limit("60/minute")
async def get_anomalies(
    request: Request,
    days: int = Query(7, description="Window days for detection"),
    contextualize: bool = Query(False, description="Add LLM analysis (slower)"),
) -> dict[str, Any]:
    """Run cross-source detection and return micro-signals."""
    from .crawling.crossref import run_cross_source_detection

    repo = get_repo()
    micro_signals = await run_cross_source_detection(repo, window_days=days, baseline_days=days * 4)

    results = [
        {
            "signal_type": ms.signal_type,
            "code_dept": ms.code_dept,
            "score": ms.score,
            "sources": ms.sources,
            "metrics": ms.metrics,
            "description": ms.description,
            "detected_at": ms.detected_at.isoformat(),
        }
        for ms in micro_signals
    ]

    # Persist anomalies to DB
    persisted = 0
    for ms in micro_signals:
        try:
            await repo.insert_anomaly(**ms.to_anomaly_dict())
            persisted += 1
        except Exception as e:
            logger.debug(f"Anomaly insert error: {e}")

    # Optional: LLM contextualisation via Ollama
    if contextualize and results:
        try:
            from .processing.contextualizer import contextualize_batch

            results = await contextualize_batch(results)
        except Exception as e:
            logger.warning(f"Contextualisation failed: {e}")

    return {
        "count": len(results),
        "persisted": persisted,
        "window_days": days,
        "micro_signals": results,
    }


@router.get("/scheduler/status")
@limiter.limit("60/minute")
async def scheduler_status(request: Request) -> dict[str, Any]:
    """Get scheduler status and next run times."""
    from src.interfaces.api.main import _collector_scheduler

    if _collector_scheduler is None:
        return {"status": "not_initialized"}
    return _collector_scheduler.get_status()


@router.post("/run/{collector_name}")
@limiter.limit("60/minute")
async def run_collector(
    request: Request,
    collector_name: str,
    code_dept: str | None = Query(None),
) -> dict[str, Any]:
    """Manually trigger a collector run."""
    from src.interfaces.api.main import _collector_scheduler

    if _collector_scheduler:
        count = await _collector_scheduler.run_now(collector_name, code_dept=code_dept)
    else:
        from .scheduler.jobs import CollectorScheduler

        scheduler = CollectorScheduler()
        count = await scheduler.run_now(collector_name, code_dept=code_dept)

    return {
        "collector": collector_name,
        "department": code_dept,
        "signals_stored": count,
    }


@router.get("/departments/heatmap")
@limiter.limit("60/minute")
async def get_departments_heatmap(
    request: Request, days: int = Query(90, description="Lookback days for signals")
) -> dict[str, Any]:
    """Get aggregated signals and anomalies by department for map heatmap."""
    repo = get_repo()
    since = date.today() - timedelta(days=days)

    # Direct SQL query for efficient aggregation
    query = text("""
        WITH signal_stats AS (
            SELECT
                code_dept,
                COUNT(*) as total_signals,
                json_object_agg(source, count) as sources,
                MAX(event_date) as latest_signal
            FROM (
                SELECT
                    code_dept,
                    source,
                    COUNT(*) as count,
                    event_date
                FROM signals
                WHERE code_dept IS NOT NULL
                  AND event_date >= :since_date
                GROUP BY code_dept, source, event_date
            ) source_counts
            GROUP BY code_dept
        ),
        anomaly_stats AS (
            SELECT
                LEFT(code_commune, 2) as code_dept,
                COUNT(*) as anomalies
            FROM anomalies
            WHERE detected_at >= :since_datetime
              AND code_commune IS NOT NULL
            GROUP BY LEFT(code_commune, 2)
        )
        SELECT
            s.code_dept as code,
            s.total_signals,
            COALESCE(s.sources, '{}') as sources,
            s.latest_signal,
            COALESCE(a.anomalies, 0) as anomalies
        FROM signal_stats s
        LEFT JOIN anomaly_stats a ON s.code_dept = a.code_dept
        ORDER BY s.total_signals DESC
    """)

    # Execute query
    async with repo._engine.begin() as conn:
        result = await conn.execute(query, {"since_date": since, "since_datetime": since})
        rows = result.fetchall()

    departments = []
    for row in rows:
        departments.append(
            {
                "code": row.code,
                "total_signals": row.total_signals,
                "sources": row.sources or {},
                "anomalies": row.anomalies,
                "latest_signal": row.latest_signal.isoformat() if row.latest_signal else None,
            }
        )

    return {
        "departments": departments,
        "period_days": days,
        "total_departments": len(departments),
    }


@router.get("/ranking")
@limiter.limit("60/minute")
async def get_territorial_ranking(request: Request) -> dict[str, Any]:
    """Get Phase 2 territorial ranking based on signal analysis."""

    # Population INSEE 2024 (top départements)
    POPULATIONS = {
        "75": 2161,
        "13": 2043,
        "69": 1914,
        "59": 2615,
        "33": 1690,
        "92": 1654,
        "93": 1704,
        "94": 1426,
        "77": 1468,
        "78": 1485,
        "31": 1471,
        "44": 1487,
        "34": 1230,
        "06": 1128,
        "67": 1163,
        "38": 1298,
        "76": 1260,
        "35": 1120,
        "62": 1457,
        "83": 1119,
        "91": 1316,
        "95": 1260,
        "54": 733,
        "45": 684,
        "57": 1048,
    }  # en milliers

    DEPT_NAMES = {
        "75": "Paris",
        "13": "Bouches-du-Rhône",
        "69": "Rhône",
        "59": "Nord",
        "33": "Gironde",
        "92": "Hauts-de-Seine",
        "93": "Seine-Saint-Denis",
        "94": "Val-de-Marne",
        "77": "Seine-et-Marne",
        "78": "Yvelines",
        "31": "Haute-Garonne",
        "44": "Loire-Atlantique",
        "34": "Hérault",
        "06": "Alpes-Maritimes",
        "67": "Bas-Rhin",
        "38": "Isère",
        "76": "Seine-Maritime",
        "35": "Ille-et-Vilaine",
        "62": "Pas-de-Calais",
        "83": "Var",
        "91": "Essonne",
        "95": "Val-d'Oise",
        "54": "Meurthe-et-Moselle",
        "45": "Loiret",
        "57": "Moselle",
    }

    # Get metrics per department using direct SQL
    query = text("""
    SELECT
        code_dept,
        -- Créations (SIRENE)
        SUM(CASE WHEN source='sirene' AND metric_name='creation_entreprise' THEN metric_value ELSE 0 END) as creations,
        -- Fermetures (SIRENE)
        SUM(CASE WHEN source='sirene' AND metric_name='fermeture_entreprise' THEN metric_value ELSE 0 END) as fermetures,
        -- Liquidations (BODACC)
        SUM(CASE WHEN source='bodacc' AND metric_name='liquidation_judiciaire' THEN metric_value ELSE 0 END) as liquidations,
        -- Procédures collectives (BODACC, toutes confondues)
        SUM(CASE WHEN source='bodacc' THEN metric_value ELSE 0 END) as procedures_total,
        -- Offres emploi (France Travail)
        SUM(CASE WHEN source='france_travail' AND metric_name='offres_emploi' THEN metric_value ELSE 0 END) as offres_emploi,
        -- Transactions immobilières (DVF)
        SUM(CASE WHEN source='dvf' AND metric_name='transactions_immobilieres' THEN metric_value ELSE 0 END) as tx_immo,
        -- Prix m² moyen (DVF)
        AVG(CASE WHEN source='dvf' AND metric_name='prix_m2_moyen' THEN metric_value ELSE NULL END) as prix_m2,
        -- Logements autorisés (Sitadel)
        SUM(CASE WHEN source='sitadel' AND metric_name LIKE 'logements_autorises%%' THEN metric_value ELSE 0 END) as logements_autorises,
        -- Presse positive vs négative
        SUM(CASE WHEN source='presse_locale' AND metric_name IN ('presse_positif','presse_creation','presse_emploi_positif','presse_investissement','presse_construction') THEN 1 ELSE 0 END) as presse_positive,
        SUM(CASE WHEN source='presse_locale' AND metric_name IN ('presse_negatif','presse_crise','presse_emploi_negatif','presse_fermeture') THEN 1 ELSE 0 END) as presse_negative,
        -- Sources count
        COUNT(DISTINCT source) as nb_sources
    FROM signals
    WHERE code_dept IS NOT NULL
    GROUP BY code_dept
    ORDER BY code_dept
    """)

    repo = get_repo()

    async with repo._engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    def winsorize(values, lower=5, upper=95):
        """Clip values at percentiles to remove outliers."""
        if len(values) == 0:
            return values
        lo = np.nanpercentile(values, lower)
        hi = np.nanpercentile(values, upper)
        return np.clip(values, lo, hi)

    def percentile_rank(values):
        """Rank values as percentiles (0-100). Higher = better."""
        n = len(values)
        if n <= 1:
            return [50.0] * n
        order = np.argsort(values)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.linspace(0, 100, n)
        return ranks

    depts = []
    for row in rows:
        code = row[0]
        pop = POPULATIONS.get(code)
        if not pop:
            continue  # Skip departments we don't have population for

        creations = float(row[1] or 0)
        fermetures = float(row[2] or 0)
        liquidations = float(row[3] or 0)
        procedures = float(row[4] or 0)
        offres = float(row[5] or 0)
        tx_immo = float(row[6] or 0)
        prix_m2 = float(row[7]) if row[7] else None
        logements = float(row[8] or 0)
        presse_pos = float(row[9] or 0)
        presse_neg = float(row[10] or 0)
        nb_sources = int(row[11] or 0)

        # Normalisation pour 10k habitants
        pop_10k = pop / 10  # pop est en milliers, donc /10 = pour 10k

        # Facteurs alpha
        f_sante = creations / (liquidations + 1)  # ratio créations/liquidations
        f_declin = (liquidations + procedures) / pop_10k  # procédures pour 10k hab
        f_emploi = offres / pop_10k  # offres pour 10k hab
        f_immo = tx_immo / pop_10k  # transactions pour 10k hab
        f_construction = logements / pop_10k  # logements autorisés pour 10k hab
        f_presse = (presse_pos + 1) / (presse_neg + 1)  # ratio positif/négatif

        confidence = nb_sources / 10.0  # 10 sources max maintenant

        depts.append(
            {
                "code": code,
                "name": DEPT_NAMES.get(code, f"Dept {code}"),
                "pop": pop,
                "f_sante": f_sante,
                "f_declin": f_declin,
                "f_emploi": f_emploi,
                "f_immo": f_immo,
                "f_construction": f_construction,
                "f_presse": f_presse,
                "confidence": confidence,
                "nb_sources": nb_sources,
            }
        )

    if not depts:
        return {"ranking": [], "total_departments": 0}

    # Scoring composite par percentile ranking
    n = len(depts)

    sante_vals = np.array([d["f_sante"] for d in depts])
    declin_vals = np.array([d["f_declin"] for d in depts])
    emploi_vals = np.array([d["f_emploi"] for d in depts])
    immo_vals = np.array([d["f_immo"] for d in depts])
    constr_vals = np.array([d["f_construction"] for d in depts])
    presse_vals = np.array([d["f_presse"] for d in depts])

    # Winsorize
    sante_w = winsorize(sante_vals)
    declin_w = winsorize(declin_vals)
    emploi_w = winsorize(emploi_vals)
    immo_w = winsorize(immo_vals)
    constr_w = winsorize(constr_vals)
    presse_w = winsorize(presse_vals)

    # Percentile ranks
    r_sante = percentile_rank(sante_w)
    r_declin = 100 - percentile_rank(declin_w)  # invert: less decline = better
    r_emploi = percentile_rank(emploi_w)
    r_immo = percentile_rank(immo_w)
    r_constr = percentile_rank(constr_w)
    r_presse = percentile_rank(presse_w)

    # Pondération
    weights = {
        "sante": 0.25,  # santé entreprises (créa/liq)
        "declin": 0.25,  # procédures collectives
        "emploi": 0.20,  # offres d'emploi
        "immo": 0.10,  # dynamisme immobilier
        "construction": 0.10,  # construction neuve
        "presse": 0.10,  # sentiment presse
    }

    ranking = []
    for i, d in enumerate(depts):
        score = (
            weights["sante"] * r_sante[i]
            + weights["declin"] * r_declin[i]
            + weights["emploi"] * r_emploi[i]
            + weights["immo"] * r_immo[i]
            + weights["construction"] * r_constr[i]
            + weights["presse"] * r_presse[i]
        )
        # Bonus/malus confiance (±5 points max)
        conf_adj = (d["confidence"] - 0.5) * 10  # de -5 à +5
        score = max(0, min(100, score + conf_adj))

        ranking.append(
            {
                "code": d["code"],
                "name": d["name"],
                "score": round(score, 1),
                "confidence": round(d["confidence"], 2),
                "population": d["pop"] * 1000,  # convert to actual population
                "factors": {
                    "sante": round(r_sante[i], 1),
                    "declin": round(r_declin[i], 1),
                    "emploi": round(r_emploi[i], 1),
                    "immo": round(r_immo[i], 1),
                    "construction": round(r_constr[i], 1),
                    "presse": round(r_presse[i], 1),
                },
            }
        )

    # Sort by score descending
    ranking.sort(key=lambda d: d["score"], reverse=True)

    return {
        "ranking": ranking,
        "total_departments": len(ranking),
    }


@router.get("/sources-summary")
@limiter.limit("60/minute")
async def get_sources_summary(request: Request) -> dict[str, Any]:
    """Get summary of signals count and last collection time per source."""
    from datetime import datetime, timezone

    query = text("""
    SELECT
        source,
        COUNT(*) as count,
        MAX(collected_at) as last_collected
    FROM signals
    GROUP BY source
    ORDER BY COUNT(*) DESC
    """)

    repo = get_repo()

    async with repo._engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    now = datetime.now(UTC)
    sources = []

    for row in rows:
        last_collected = row.last_collected
        if last_collected and last_collected.tzinfo is None:
            last_collected = last_collected.replace(tzinfo=UTC)

        # Status: green if < 24h, yellow if < 7 days, red otherwise
        status = "offline"
        if last_collected:
            hours_since = (now - last_collected).total_seconds() / 3600
            if hours_since < 24:
                status = "online"
            elif hours_since < 24 * 7:
                status = "degraded"

        sources.append(
            {
                "source": row.source,
                "count": row.count,
                "last_collected": last_collected.isoformat() if last_collected else None,
                "status": status,
            }
        )

    return {
        "sources": sources,
        "total_signals": sum(s["count"] for s in sources),
        "total_sources": len(sources),
    }


@router.get("/trends")
@limiter.limit("60/minute")
async def get_google_trends_data(
    request: Request, limit: int = Query(20, description="Max trends to return")
) -> dict[str, Any]:
    """Get Google Trends data from signals."""
    query = text("""
    SELECT
        metric_name,
        code_dept,
        AVG(metric_value) as avg_value,
        COUNT(*) as count,
        MAX(collected_at) as latest
    FROM signals
    WHERE source = 'google_trends'
      AND metric_name IS NOT NULL
    GROUP BY metric_name, code_dept
    ORDER BY avg_value DESC, count DESC
    LIMIT :limit
    """)

    repo = get_repo()

    async with repo._engine.begin() as conn:
        result = await conn.execute(query, {"limit": limit})
        rows = result.fetchall()

    trends = []
    for row in rows:
        trends.append(
            {
                "keyword": row.metric_name,
                "department": row.code_dept,
                "avg_value": round(float(row.avg_value), 2),
                "count": row.count,
                "latest": row.latest.isoformat() if row.latest else None,
            }
        )

    # Group by keyword for summary
    keyword_summary = {}
    for trend in trends:
        keyword = trend["keyword"]
        if keyword not in keyword_summary:
            keyword_summary[keyword] = {
                "keyword": keyword,
                "total_value": 0,
                "department_count": 0,
                "latest": trend["latest"],
            }
        keyword_summary[keyword]["total_value"] += trend["avg_value"]
        keyword_summary[keyword]["department_count"] += 1

    # Convert to list and sort
    top_keywords = sorted(keyword_summary.values(), key=lambda x: x["total_value"], reverse=True)[
        :10
    ]

    return {
        "trends": trends,
        "top_keywords": top_keywords,
        "total_trends": len(trends),
    }


@router.get("/departments/scores")
@limiter.limit("30/minute")
async def get_department_scores(
    request: Request,
) -> dict[str, Any]:
    """Get territorial health scores for all departments."""
    from .quant.scoring import get_department_rankings

    repo = get_repo()
    db_url = repo._engine.url.render_as_string(hide_password=False)

    try:
        rankings = await get_department_rankings(db_url)

        return {
            "status": "success",
            "count": len(rankings),
            "rankings": rankings,
            "algorithm": "Tawiza-V2 Phase 2",
            "factors": [
                "factor_sante_entreprises",
                "factor_tension_emploi",
                "factor_dynamisme_immo",
                "factor_construction",
                "factor_declin_ratio",
                "factor_presse_sentiment",
            ],
        }
    except Exception as e:
        logger.error(f"Error computing department scores: {e}")
        return {"status": "error", "message": str(e), "rankings": []}


@router.get("/departments/{dept}/factors")
@limiter.limit("60/minute")
async def get_department_factors(
    request: Request,
    dept: str,
) -> dict[str, Any]:
    """Get detailed alpha factors for a specific department."""
    from .quant.population import get_department_population
    from .quant.scoring import compute_territorial_scores

    repo = get_repo()
    db_url = repo._engine.url.render_as_string(hide_password=False)

    try:
        # Get all scores
        all_scores = await compute_territorial_scores(db_url)

        if dept not in all_scores:
            return {
                "status": "error",
                "message": f"Department {dept} not found",
                "department": dept,
            }

        dept_data = all_scores[dept]
        population = get_department_population(dept)

        return {
            "status": "success",
            "department": dept,
            "population": population,
            "composite_score": dept_data.get("composite_score"),
            "health_category": dept_data.get("health_category"),
            "confidence": dept_data.get("confidence"),
            "factor_count": dept_data.get("factor_count"),
            "total_factors": dept_data.get("total_factors"),
            "individual_factors": dept_data.get("individual_scores", {}),
            "algorithm": "Tawiza-V2 Phase 2",
        }
    except Exception as e:
        logger.error(f"Error getting factors for department {dept}: {e}")
        return {"status": "error", "message": str(e), "department": dept}


@router.get("/departments/{dept}/trends")
@limiter.limit("30/minute")
async def get_department_trends(
    request: Request,
    dept: str,
    metric: str | None = Query(None, description="Specific metric to analyze"),
) -> dict[str, Any]:
    """Get temporal trends analysis for a specific department."""
    from .quant.temporal import compute_moving_averages, compute_rate_of_change
    from .quant.trends import _generate_trend_alert

    repo = get_repo()
    db_url = repo._engine.url.render_as_string(hide_password=False)

    try:
        logger.info(f"Getting trends for department {dept}")

        # Get rate of change for all metrics
        roc_data = await compute_rate_of_change(db_url, dept, periods=[3, 6, 12])

        trends = {}
        alerts = []

        if metric:
            # Specific metric analysis
            if metric in roc_data:
                ma_data = await compute_moving_averages(db_url, dept, metric)

                alert = await _generate_trend_alert(
                    dept, metric, ma_data, roc_data[metric], ma_data.get("data_points", 0)
                )

                trends[metric] = {"moving_averages": ma_data, "rate_of_change": roc_data[metric]}

                if alert:
                    alerts.append(alert)
        else:
            # All metrics overview
            for metric_name, roc_values in roc_data.items():
                if roc_values and roc_values.get("alert"):
                    ma_data = await compute_moving_averages(db_url, dept, metric_name)

                    alert = await _generate_trend_alert(
                        dept, metric_name, ma_data, roc_values, ma_data.get("data_points", 0)
                    )

                    if alert:
                        alerts.append(alert)

        return {
            "status": "success",
            "department": dept,
            "metric_filter": metric,
            "trends": trends,
            "alerts": alerts,
            "alert_count": len(alerts),
            "roc_summary": roc_data,
            "algorithm": "Tawiza-V2 Phase 3",
        }

    except Exception as e:
        logger.error(f"Error getting trends for department {dept}: {e}")
        return {"status": "error", "message": str(e), "department": dept}


@router.get("/trends/alerts")
@limiter.limit("20/minute")
async def get_trends_alerts(
    request: Request,
    confidence_threshold: float = Query(0.5, description="Minimum confidence for alerts"),
    trend_type: str | None = Query(None, description="Filter by trend type"),
) -> dict[str, Any]:
    """Get all active trend alerts across all departments."""
    from .quant.trends import detect_trends

    repo = get_repo()
    db_url = repo._engine.url.render_as_string(hide_password=False)

    try:
        logger.info("Getting comprehensive trend alerts")

        # Get all trend alerts
        all_alerts = await detect_trends(db_url)

        # Filter by confidence and trend type
        filtered_alerts = [
            alert for alert in all_alerts if alert.get("confidence", 0) >= confidence_threshold
        ]

        if trend_type:
            filtered_alerts = [
                alert for alert in filtered_alerts if alert.get("trend_type") == trend_type
            ]

        # Group by trend type for summary
        trend_summary = {}
        for alert in filtered_alerts:
            t_type = alert.get("trend_type", "unknown")
            if t_type not in trend_summary:
                trend_summary[t_type] = {"count": 0, "departments": set(), "avg_confidence": 0}
            trend_summary[t_type]["count"] += 1
            trend_summary[t_type]["departments"].add(alert.get("dept"))
            trend_summary[t_type]["avg_confidence"] += alert.get("confidence", 0)

        # Calculate averages and convert sets to lists
        for t_type in trend_summary:
            count = trend_summary[t_type]["count"]
            trend_summary[t_type]["avg_confidence"] /= count if count > 0 else 1
            trend_summary[t_type]["departments"] = list(trend_summary[t_type]["departments"])

        # Sort alerts by confidence
        filtered_alerts.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        return {
            "status": "success",
            "total_alerts": len(filtered_alerts),
            "confidence_threshold": confidence_threshold,
            "trend_type_filter": trend_type,
            "alerts": filtered_alerts,
            "trend_summary": trend_summary,
            "algorithm": "Tawiza-V2 Phase 3",
            "generated_at": date.today().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting trend alerts: {e}")
        return {"status": "error", "message": str(e), "alerts": []}


@router.get("/correlations")
@limiter.limit("10/minute")
async def get_lag_correlations(
    request: Request,
) -> dict[str, Any]:
    """Get cross-source lag correlations analysis."""
    from .quant.temporal import compute_lag_correlations

    repo = get_repo()
    db_url = repo._engine.url.render_as_string(hide_password=False)

    try:
        logger.info("Computing cross-source lag correlations")

        correlations = await compute_lag_correlations(db_url)

        # Extract significant correlations
        significant_correlations = []
        for pair_name, corr_data in correlations.items():
            if not corr_data.get("insufficient_data") and corr_data.get("significant"):
                significant_correlations.append(
                    {
                        "pair": pair_name,
                        "best_correlation": corr_data.get("best_correlation"),
                        "best_lag_months": corr_data.get("best_lag_months"),
                        "strength": "strong"
                        if abs(corr_data.get("best_correlation", 0)) > 0.6
                        else "moderate",
                    }
                )

        # Sort by correlation strength
        significant_correlations.sort(key=lambda x: abs(x.get("best_correlation", 0)), reverse=True)

        return {
            "status": "success",
            "total_pairs_analyzed": len(correlations),
            "significant_correlations": len(significant_correlations),
            "correlations": correlations,
            "significant_only": significant_correlations,
            "algorithm": "Tawiza-V2 Phase 3",
            "interpretation": {
                "strong": "> 0.6 correlation coefficient",
                "moderate": "0.3 - 0.6 correlation coefficient",
                "lag_months": "time delay between source 1 signal and source 2 response",
            },
        }

    except Exception as e:
        logger.error(f"Error computing lag correlations: {e}")
        return {"status": "error", "message": str(e), "correlations": {}}


# ============================================================================
# Phase 4: Machine Learning Endpoints
# ============================================================================


@router.get("/ml/anomalies")
@limiter.limit("30/minute")
async def get_ml_anomalies(
    request: Request,
    method: str | None = Query(
        None, description="ML method filter (isolation_forest, hdbscan, dbscan)"
    ),
    days: int = Query(30, description="Lookback days"),
    limit: int = Query(100, description="Max results"),
) -> dict[str, Any]:
    """Get ML-detected anomalies from Isolation Forest and clustering."""
    repo = get_repo()

    try:
        # Query ML anomalies table
        base_query = f"""
        SELECT
            id, code_dept, detected_at, anomaly_score, is_anomaly,
            method, features_used, feature_values, description,
            cluster_id, cluster_size, created_at
        FROM ml_anomalies
        WHERE detected_at >= CURRENT_DATE - INTERVAL '{days} days'
        """

        params = {}
        if method:
            base_query += " AND method = :method"
            params["method"] = method

        base_query += (
            f" ORDER BY detected_at DESC, ABS(anomaly_score) DESC NULLS LAST LIMIT {limit}"
        )

        async with repo._engine.begin() as conn:
            result = await conn.execute(text(base_query), params)
            rows = result.fetchall()

        # Format results
        anomalies = []
        for row in rows:
            anomaly = {
                "id": row.id,
                "code_dept": row.code_dept,
                "detected_at": row.detected_at.isoformat() if row.detected_at else None,
                "anomaly_score": row.anomaly_score,
                "is_anomaly": row.is_anomaly,
                "method": row.method,
                "features_used": row.features_used,
                "feature_values": row.feature_values,
                "description": row.description,
                "cluster_info": {"cluster_id": row.cluster_id, "cluster_size": row.cluster_size}
                if row.cluster_id is not None
                else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            anomalies.append(anomaly)

        # Summary statistics
        total_anomalies = len(anomalies)
        method_breakdown = {}
        dept_breakdown = {}

        for anomaly in anomalies:
            method_name = anomaly["method"]
            dept = anomaly["code_dept"]

            method_breakdown[method_name] = method_breakdown.get(method_name, 0) + 1
            dept_breakdown[dept] = dept_breakdown.get(dept, 0) + 1

        return {
            "status": "success",
            "total_anomalies": total_anomalies,
            "days_lookback": days,
            "method_filter": method,
            "anomalies": anomalies,
            "summary": {
                "by_method": method_breakdown,
                "by_department": dict(
                    sorted(dept_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
                ),
            },
            "algorithm": "Tawiza-V2 Phase 4 - ML Detection",
        }

    except Exception as e:
        logger.error(f"Error getting ML anomalies: {e}")
        return {"status": "error", "message": str(e), "anomalies": []}


@router.get("/ml/clusters")
@limiter.limit("20/minute")
async def get_ml_clusters(
    request: Request,
    method: str | None = Query("hdbscan", description="Clustering method (hdbscan, dbscan)"),
    days: int = Query(7, description="Lookback days"),
) -> dict[str, Any]:
    """Get departments grouped by ML clustering profiles."""
    repo = get_repo()

    try:
        # Query clustering results
        query = f"""
        SELECT
            code_dept, method, cluster_id, cluster_size,
            feature_values, description, detected_at
        FROM ml_anomalies
        WHERE method = :method
            AND cluster_id IS NOT NULL
            AND detected_at >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY cluster_id, code_dept;
        """

        async with repo._engine.begin() as conn:
            result = await conn.execute(text(query), {"method": method})
            rows = result.fetchall()

        if not rows:
            return {
                "status": "success",
                "message": "No clustering data found",
                "method": method,
                "clusters": {},
                "total_departments": 0,
            }

        # Group by cluster_id
        clusters = {}
        isolated_departments = []

        for row in rows:
            cluster_id = row.cluster_id
            dept_data = {
                "code_dept": row.code_dept,
                "cluster_size": row.cluster_size,
                "feature_values": row.feature_values,
                "description": row.description,
                "detected_at": row.detected_at.isoformat() if row.detected_at else None,
            }

            if cluster_id == -1:  # Noise/isolated
                isolated_departments.append(dept_data)
            else:
                if cluster_id not in clusters:
                    clusters[cluster_id] = {
                        "cluster_id": cluster_id,
                        "size": row.cluster_size,
                        "departments": [],
                    }
                clusters[cluster_id]["departments"].append(dept_data)

        # Calculate cluster statistics
        cluster_summary = {}
        for cluster_id, cluster_data in clusters.items():
            depts = cluster_data["departments"]
            cluster_summary[f"cluster_{cluster_id}"] = {
                "size": len(depts),
                "department_codes": [d["code_dept"] for d in depts],
                "profile": "Similar economic characteristics",
            }

        return {
            "status": "success",
            "method": method,
            "days_lookback": days,
            "total_departments": len(rows),
            "total_clusters": len(clusters),
            "isolated_departments_count": len(isolated_departments),
            "clusters": cluster_summary,
            "cluster_details": clusters,
            "isolated_departments": isolated_departments,
            "algorithm": f"Tawiza-V2 Phase 4 - {method.upper()} Clustering",
        }

    except Exception as e:
        logger.error(f"Error getting ML clusters: {e}")
        return {"status": "error", "message": str(e), "clusters": {}}


@router.get("/ml/factors")
@limiter.limit("10/minute")
async def get_discovered_factors(
    request: Request,
    min_ic: float = Query(0.2, description="Minimum Information Coefficient threshold"),
    significant_only: bool = Query(True, description="Only statistically significant factors"),
) -> dict[str, Any]:
    """Get factors discovered by LLM factor mining with Information Coefficients."""
    from .quant.factor_mining import FactorMining

    try:
        logger.info("Running Factor Mining for API request...")

        # Initialize factor mining
        repo = get_repo()
        db_url = repo._engine.url.render_as_string(hide_password=False)
        factor_miner = FactorMining(db_url=db_url)

        # Run factor mining
        mining_results = await factor_miner.run_factor_mining()

        if "error" in mining_results:
            return {"status": "error", "message": mining_results["error"], "factors": []}

        # Filter factors by IC threshold and significance
        ic_results = mining_results.get("information_coefficients", [])
        filtered_factors = []

        for factor_result in ic_results:
            ic_spearman = factor_result.get("ic_spearman")
            ic_pearson = factor_result.get("ic_pearson")
            p_val_spearman = factor_result.get("p_value_spearman", 1.0)
            p_val_pearson = factor_result.get("p_value_pearson", 1.0)

            # Check IC threshold
            if ic_spearman is None or abs(ic_spearman) < min_ic:
                continue

            # Check significance if required
            if significant_only:
                if p_val_spearman >= 0.05 and p_val_pearson >= 0.05:
                    continue

            # Add interpretation
            factor_result["interpretation"] = {
                "ic_strength": "strong"
                if abs(ic_spearman) > 0.5
                else "moderate"
                if abs(ic_spearman) > 0.3
                else "weak",
                "direction": "positive" if ic_spearman > 0 else "negative",
                "statistical_significance": "significant"
                if min(p_val_spearman, p_val_pearson) < 0.05
                else "not_significant",
            }

            filtered_factors.append(factor_result)

        # Sort by absolute IC
        filtered_factors.sort(key=lambda x: abs(x.get("ic_spearman", 0)), reverse=True)

        return {
            "status": "success",
            "total_hypotheses_generated": len(mining_results.get("factor_hypotheses", [])),
            "total_factors_tested": len(ic_results),
            "factors_meeting_criteria": len(filtered_factors),
            "min_ic_threshold": min_ic,
            "significant_only": significant_only,
            "top_bottom_departments": mining_results.get("top_bottom_departments", {}),
            "factors": filtered_factors,
            "best_factors": filtered_factors[:5],  # Top 5
            "algorithm": "Tawiza-V2 Phase 4 - LLM Factor Mining",
            "generated_at": mining_results.get("timestamp"),
            "interpretation": {
                "ic_spearman": "Spearman rank correlation coefficient (non-linear relationships)",
                "ic_pearson": "Pearson correlation coefficient (linear relationships)",
                "p_value": "Statistical significance (< 0.05 considered significant)",
                "sample_size": "Number of departments used in calculation",
            },
        }

    except Exception as e:
        logger.error(f"Error getting discovered factors: {e}")
        return {"status": "error", "message": str(e), "factors": []}


@router.post("/ml/run-detection")
@limiter.limit("5/minute")
async def trigger_ml_detection(
    request: Request,
    contamination: float = Query(0.1, description="Isolation Forest contamination rate"),
    use_hdbscan: bool = Query(True, description="Use HDBSCAN instead of DBSCAN"),
) -> dict[str, Any]:
    """Manually trigger ML anomaly detection and clustering."""
    from .quant.ml_detection import MLDetection

    try:
        logger.info(
            f"Manual ML detection triggered - contamination={contamination}, hdbscan={use_hdbscan}"
        )

        # Initialize ML detection
        repo = get_repo()
        db_url = repo._engine.url.render_as_string(hide_password=False)
        ml_detector = MLDetection(db_url=db_url)

        # Run full detection
        detection_results = await ml_detector.run_full_detection()

        if "error" in detection_results:
            return {"status": "error", "message": detection_results["error"]}

        # Extract summary statistics
        iso_results = detection_results.get("isolation_forest", {})
        cluster_results = detection_results.get("clustering", {})

        return {
            "status": "success",
            "message": "ML detection completed successfully",
            "timestamp": detection_results.get("timestamp"),
            "isolation_forest": {
                "anomalies_detected": len(iso_results.get("anomalies", [])),
                "total_departments": iso_results.get("total_departments", 0),
                "contamination_used": contamination,
            },
            "clustering": {
                "method": cluster_results.get("method", "unknown"),
                "clusters_formed": len(cluster_results.get("clusters", {})),
                "isolated_departments": len(cluster_results.get("anomalies", [])),
                "total_departments": cluster_results.get("total_departments", 0),
            },
            "algorithm": "Tawiza-V2 Phase 4 - ML Detection Suite",
        }

    except Exception as e:
        logger.error(f"Error triggering ML detection: {e}")
        return {"status": "error", "message": str(e)}


# QLib DataHandler endpoints
@router.get("/qlib/expressions")
@limiter.limit("30/minute")
async def get_alpha_expressions(request: Request) -> dict[str, Any]:
    """Get available alpha expressions for territorial intelligence."""
    try:
        from .quant.qlib.expressions import (
            ALPHA_EXPRESSIONS,
            EXPRESSION_CATEGORIES,
            describe_expression,
        )

        # Return expressions grouped by category
        result = {
            "status": "success",
            "total_expressions": len(ALPHA_EXPRESSIONS),
            "categories": {},
        }

        for category, expr_names in EXPRESSION_CATEGORIES.items():
            result["categories"][category] = []
            for expr_name in expr_names:
                try:
                    description = describe_expression(expr_name)
                    result["categories"][category].append(
                        {
                            "name": expr_name,
                            "formula": description["formula"],
                            "required_metrics": description["required_metrics"],
                            "description": description.get("description", ""),
                            "interpretation": description.get("interpretation", ""),
                        }
                    )
                except Exception:
                    # Skip expressions that have errors
                    continue

        return result

    except Exception as e:
        logger.error(f"Error retrieving alpha expressions: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/qlib/features")
@limiter.limit("20/minute")
async def compute_alpha_features(
    request: Request,
    departments: str = Query(..., description="Comma-separated department codes (e.g., 75,93,59)"),
    expressions: str | None = Query(None, description="Comma-separated expression names"),
    months_back: int = Query(6, description="Months of historical data to use"),
    data_key: str = Query("infer", description="Data processing level (raw/infer/learn)"),
) -> dict[str, Any]:
    """Compute alpha features for specified departments."""
    try:
        from datetime import datetime, timedelta

        from .quant.qlib.expressions import ALPHA_EXPRESSIONS, get_compatible_expressions
        from .quant.qlib.handler import DataHandlerConfig, TerritorialDataHandler

        # Parse parameters
        dept_list = [d.strip() for d in departments.split(",")]
        if len(dept_list) > 20:  # Limit for performance
            return {"status": "error", "message": "Too many departments requested (max 20)"}

        expr_list = None
        if expressions:
            expr_list = [e.strip() for e in expressions.split(",")]
            # Validate expressions exist
            invalid_exprs = [e for e in expr_list if e not in ALPHA_EXPRESSIONS]
            if invalid_exprs:
                return {"status": "error", "message": f"Unknown expressions: {invalid_exprs}"}

        # Set date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=months_back * 30)

        # Create data handler
        config = DataHandlerConfig(
            db_url=os.getenv("COLLECTOR_DATABASE_URL", "postgresql://localhost:5433/tawiza"),
            territories=dept_list,
            start_date=str(start_date),
            end_date=str(end_date),
            alpha_expressions=expr_list,
        )

        handler = TerritorialDataHandler(config)

        # Prepare dataset
        dataset = await handler.prepare_dataset(data_key=data_key, alpha_expressions=expr_list)

        # Convert to dict format for API response
        result = {
            "status": "success",
            "metadata": {
                "departments": dept_list,
                "date_range": [str(start_date), str(end_date)],
                "expressions_computed": expr_list or "auto-detected",
                "processing_level": data_key,
                "samples": len(dataset),
                "features": len(dataset.feature_names),
            },
            "feature_names": dataset.feature_names,
            "territories": dataset.territories,
            "dates": [str(d) for d in dataset.dates] if dataset.dates else [],
        }

        # Add sample data (latest period for each department)
        if len(dataset) > 0:
            latest_data = dataset.get_latest_data(1)
            features_dict = latest_data.features.to_dict("index")

            # Format data by department
            result["latest_features"] = {}
            for (date, dept), features in features_dict.items():
                if dept not in result["latest_features"]:
                    result["latest_features"][dept] = {}
                result["latest_features"][dept] = {
                    "date": str(date),
                    "features": {
                        k: float(v) if not pd.isna(v) else None for k, v in features.items()
                    },
                }

        return result

    except Exception as e:
        logger.error(f"Error computing alpha features: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/qlib/anomalies")
@limiter.limit("10/minute")
async def detect_qlib_anomalies(
    request: Request,
    departments: str = Query(..., description="Comma-separated department codes"),
    method: str = Query("isolation_forest", description="Detection method"),
    contamination: float = Query(0.1, description="Expected proportion of outliers"),
) -> dict[str, Any]:
    """Detect anomalies using QLib-enhanced features."""
    try:
        import pandas as pd

        from .quant.qlib.handler import DataHandlerConfig, TerritorialDataHandler

        # Parse departments
        dept_list = [d.strip() for d in departments.split(",")]
        if len(dept_list) > 15:
            return {
                "status": "error",
                "message": "Too many departments for anomaly detection (max 15)",
            }

        # Set up data handler
        config = DataHandlerConfig(
            db_url=os.getenv("COLLECTOR_DATABASE_URL", "postgresql://localhost:5433/tawiza"),
            territories=dept_list,
        )

        handler = TerritorialDataHandler(config)

        # Detect anomalies
        anomalies = await handler.detect_anomalies(method=method, contamination=contamination)

        if anomalies.empty:
            return {"status": "warning", "message": "No anomalies detected or insufficient data"}

        # Format results
        anomaly_list = []
        for idx, row in anomalies.iterrows():
            if row["is_anomaly"] == 1:
                anomaly_list.append(
                    {
                        "territory": row["territory"],
                        "anomaly_score": float(row["anomaly_score"]),
                        "date": str(idx[0]) if isinstance(idx, tuple) else str(idx),
                        "severity": "high" if row["anomaly_score"] < -0.5 else "medium",
                    }
                )

        return {
            "status": "success",
            "method": method,
            "contamination": contamination,
            "total_anomalies": len(anomaly_list),
            "departments_analyzed": len(dept_list),
            "anomalies": sorted(anomaly_list, key=lambda x: x["anomaly_score"]),
        }

    except Exception as e:
        logger.error(f"Error in QLib anomaly detection: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/timeline")
@limiter.limit("60/minute")
async def get_timeline_data(
    request: Request, days: int = Query(90, description="Lookback days for timeline data")
) -> dict[str, Any]:
    """Get temporal data grouped by week for charts - BODACC liquidations, SIRENE créations."""
    repo = get_repo()
    since = date.today() - timedelta(days=days)

    query = text("""
    SELECT
        date_trunc('week', event_date)::date as semaine,
        source,
        metric_name,
        SUM(metric_value) as total_value,
        COUNT(*) as nb_signals
    FROM signals
    WHERE event_date IS NOT NULL
      AND event_date >= :since_date
      AND (
          (source = 'bodacc' AND metric_name = 'liquidation_judiciaire') OR
          (source = 'sirene' AND metric_name IN ('creation_entreprise', 'fermeture_entreprise'))
      )
    GROUP BY 1, 2, 3
    ORDER BY 1, 2, 3
    """)

    async with repo._engine.begin() as conn:
        result = await conn.execute(query, {"since_date": since})
        rows = result.fetchall()

    # Format data for recharts
    timeline_data = []
    weeks_dict = {}

    for row in rows:
        week = row.semaine.isoformat()
        source = row.source
        metric = row.metric_name
        value = int(row.total_value or 0)

        if week not in weeks_dict:
            weeks_dict[week] = {"semaine": week, "liquidations": 0, "creations": 0, "fermetures": 0}

        if source == "bodacc" and metric == "liquidation_judiciaire":
            weeks_dict[week]["liquidations"] += value
        elif source == "sirene" and metric == "creation_entreprise":
            weeks_dict[week]["creations"] += value
        elif source == "sirene" and metric == "fermeture_entreprise":
            weeks_dict[week]["fermetures"] += value

    timeline_data = sorted(weeks_dict.values(), key=lambda x: x["semaine"])

    return {
        "timeline": timeline_data,
        "period_days": days,
        "total_weeks": len(timeline_data),
        "metrics_tracked": ["liquidations", "creations", "fermetures"],
    }


@router.get("/departments/compare")
@limiter.limit("60/minute")
async def get_departments_compare(
    request: Request, limit: int = Query(50, description="Max departments to return")
) -> dict[str, Any]:
    """Get departments comparison data for charts - liquidations, créations, emploi, prix m²."""

    # Mapping département codes vers noms
    DEPT_NAMES = {
        "75": "Paris",
        "13": "Bouches-du-Rhône",
        "69": "Rhône",
        "59": "Nord",
        "33": "Gironde",
        "92": "Hauts-de-Seine",
        "93": "Seine-Saint-Denis",
        "94": "Val-de-Marne",
        "77": "Seine-et-Marne",
        "78": "Yvelines",
        "31": "Haute-Garonne",
        "44": "Loire-Atlantique",
        "34": "Hérault",
        "06": "Alpes-Maritimes",
        "67": "Bas-Rhin",
        "38": "Isère",
        "76": "Seine-Maritime",
        "35": "Ille-et-Vilaine",
        "62": "Pas-de-Calais",
        "83": "Var",
        "91": "Essonne",
        "95": "Val-d'Oise",
        "54": "Meurthe-et-Moselle",
        "45": "Loiret",
        "57": "Moselle",
        "42": "Loire",
        "14": "Calvados",
        "29": "Finistère",
        "56": "Morbihan",
        "17": "Charente-Maritime",
        "37": "Indre-et-Loire",
        "21": "Côte-d'Or",
        "51": "Marne",
        "74": "Haute-Savoie",
        "73": "Savoie",
        "84": "Vaucluse",
        "30": "Gard",
        "64": "Pyrénées-Atlantiques",
        "66": "Pyrénées-Orientales",
        "81": "Tarn",
        "82": "Tarn-et-Garonne",
        "32": "Gers",
        "09": "Ariège",
        "11": "Aude",
        "48": "Lozère",
        "07": "Ardèche",
        "26": "Drôme",
        "04": "Alpes-de-Haute-Provence",
        "05": "Hautes-Alpes",
        "88": "Vosges",
        "68": "Haut-Rhin",
        "25": "Doubs",
        "39": "Jura",
        "70": "Haute-Saône",
        "90": "Territoire de Belfort",
        "71": "Saône-et-Loire",
        "01": "Ain",
        "03": "Allier",
        "15": "Cantal",
        "43": "Haute-Loire",
        "63": "Puy-de-Dôme",
        "87": "Haute-Vienne",
        "19": "Corrèze",
        "23": "Creuse",
        "16": "Charente",
        "24": "Dordogne",
        "47": "Lot-et-Garonne",
        "40": "Landes",
        "65": "Hautes-Pyrénées",
        "12": "Aveyron",
        "46": "Lot",
        "86": "Vienne",
        "79": "Deux-Sèvres",
        "85": "Vendée",
        "49": "Maine-et-Loire",
        "72": "Sarthe",
        "53": "Mayenne",
        "61": "Orne",
        "50": "Manche",
        "27": "Eure",
        "28": "Eure-et-Loir",
        "41": "Loir-et-Cher",
        "18": "Cher",
        "36": "Indre",
        "08": "Ardennes",
        "10": "Aube",
        "52": "Haute-Marne",
        "55": "Meuse",
        "80": "Somme",
        "02": "Aisne",
        "60": "Oise",
    }

    repo = get_repo()

    query = text("""
    SELECT
        code_dept,
        SUM(CASE WHEN source='bodacc' AND metric_name='liquidation_judiciaire' THEN metric_value ELSE 0 END) as liquidations,
        SUM(CASE WHEN source='sirene' AND metric_name='creation_entreprise' THEN metric_value ELSE 0 END) as creations,
        SUM(CASE WHEN source='sirene' AND metric_name='fermeture_entreprise' THEN metric_value ELSE 0 END) as fermetures,
        SUM(CASE WHEN source='france_travail' THEN metric_value ELSE 0 END) as offres_emploi,
        AVG(CASE WHEN source='dvf' AND metric_name='prix_m2_moyen' THEN metric_value ELSE NULL END) as prix_m2
    FROM signals
    WHERE code_dept IS NOT NULL
    GROUP BY code_dept
    ORDER BY liquidations DESC
    LIMIT :limit
    """)

    async with repo._engine.begin() as conn:
        result = await conn.execute(query, {"limit": limit})
        rows = result.fetchall()

    departments = []
    for row in rows:
        code = row.code_dept
        name = DEPT_NAMES.get(code, f"Département {code}")

        departments.append(
            {
                "code": code,
                "name": name,
                "liquidations": int(row.liquidations or 0),
                "creations": int(row.creations or 0),
                "fermetures": int(row.fermetures or 0),
                "offres_emploi": int(row.offres_emploi or 0),
                "prix_m2": round(float(row.prix_m2), 0) if row.prix_m2 else None,
                "ratio_creation_liquidation": round(
                    float(row.creations or 0) / max(float(row.liquidations or 0), 1), 2
                ),
            }
        )

    return {
        "departments": departments,
        "total_departments": len(departments),
        "metrics": ["liquidations", "creations", "fermetures", "offres_emploi", "prix_m2"],
    }


# ─── EPCI Endpoints ─────────────────────────────────────────────────────


@router.post("/epci/enrich")
@limiter.limit("10/minute")
async def enrich_epci(request: Request) -> dict[str, Any]:
    """Add code_epci to signals that have code_commune."""
    from .epci.enrichment import add_epci_column, enrich_all_signals

    repo = get_repo()
    await add_epci_column(repo._engine)
    count = await enrich_all_signals(repo._engine)
    return {"status": "success", "signals_enriched": count}


@router.get("/epci/scores")
@limiter.limit("60/minute")
async def get_epci_scores_endpoint(
    request: Request,
    code_dept: str | None = Query(None, description="Filter by department"),
    days: int = Query(180, description="Lookback days"),
) -> dict[str, Any]:
    """Get composite scores for EPCIs."""
    from .epci.scoring import get_epci_scores

    repo = get_repo()
    scores = await get_epci_scores(repo._engine, code_dept=code_dept, days=days)
    return {
        "status": "success",
        "count": len(scores),
        "department_filter": code_dept,
        "epcis": scores,
    }


@router.get("/epci/{code_epci}/signals")
@limiter.limit("60/minute")
async def get_epci_signals_endpoint(
    request: Request,
    code_epci: str,
    days: int = Query(90, description="Lookback days"),
    limit: int = Query(100, description="Max results"),
) -> dict[str, Any]:
    """Get signals for a specific EPCI."""
    from .epci.referentiel import get_referentiel
    from .epci.scoring import get_epci_signals

    repo = get_repo()
    ref = await get_referentiel()
    signals = await get_epci_signals(repo._engine, code_epci, days=days, limit=limit)
    return {
        "status": "success",
        "code_epci": code_epci,
        "nom": ref.epci_name(code_epci),
        "population": ref.epci_population(code_epci),
        "count": len(signals),
        "signals": signals,
    }


@router.get("/epci/list")
@limiter.limit("60/minute")
async def list_epcis(
    request: Request,
    code_dept: str | None = Query(None, description="Filter by department"),
) -> dict[str, Any]:
    """List all EPCIs, optionally filtered by department."""
    from .epci.referentiel import get_referentiel

    ref = await get_referentiel()
    all_epcis = ref.all_epcis()

    if code_dept:
        epci_codes = ref.epcis_in_department(code_dept)
        filtered = {k: v for k, v in all_epcis.items() if k in epci_codes}
    else:
        filtered = all_epcis

    epcis = [
        {
            "code": code,
            "nom": info["nom"],
            "population": info.get("pop", 0),
            "departments": info.get("depts", []),
        }
        for code, info in filtered.items()
    ]
    epcis.sort(key=lambda x: x["population"], reverse=True)

    return {
        "status": "success",
        "count": len(epcis),
        "department_filter": code_dept,
        "epcis": epcis,
    }
