"""API endpoints for signals and micro-signals."""

import os
import time
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

# Use environment variable, fallback to default
_DB_URL = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql+asyncpg://localhost:5433/tawiza",
).replace("+asyncpg", "")  # asyncpg.create_pool needs raw postgresql:// URL

# Connection pool (created lazily)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(_DB_URL, min_size=2, max_size=10, command_timeout=30)
    return _pool


# Simple TTL cache for expensive computations
_scores_cache: dict = {"data": None, "ts": 0}
_SCORES_TTL = 300  # 5 minutes


class SignalStats(BaseModel):
    source: str
    count: int
    departments: int


class MicroSignalResponse(BaseModel):
    id: int
    territory_code: str
    signal_type: str
    sources: list[str]
    dimensions: list[str]
    score: float
    confidence: float
    impact: float
    description: str
    detected_at: str


class TerritoryRadar(BaseModel):
    code_dept: str
    economie: float
    emploi: float
    immobilier: float
    finances: float
    demographie: float
    presse: float
    score_global: float


@router.get("/list", summary="Liste paginée des signaux avec détails")
async def list_signals(
    source: str | None = Query(None, description="Filtrer par source"),
    dept: str | None = Query(None, description="Filtrer par département"),
    metric: str | None = Query(None, description="Filtrer par metric_name (contient)"),
    q: str | None = Query(None, min_length=2, description="Recherche texte libre"),
    date_from: str | None = Query(None, description="Date début (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Date fin (YYYY-MM-DD)"),
    sort: str = Query("recent", description="Tri: recent, oldest, score"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
):
    """Liste les signaux bruts avec pagination, filtres et URLs sources."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where_clauses = []
        params: list = []
        idx = 1

        if source:
            where_clauses.append(f"source = ${idx}")
            params.append(source)
            idx += 1
        if dept:
            where_clauses.append(f"code_dept = ${idx}")
            params.append(dept)
            idx += 1
        if metric:
            where_clauses.append(f"metric_name ILIKE ${idx}")
            params.append(f"%{metric}%")
            idx += 1
        if q:
            where_clauses.append(f"extracted_text ILIKE ${idx}")
            params.append(f"%{q}%")
            idx += 1
        if date_from:
            where_clauses.append(f"event_date >= ${idx}::date")
            params.append(date_from)
            idx += 1
        if date_to:
            where_clauses.append(f"event_date <= ${idx}::date")
            params.append(date_to)
            idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Count
        total = await conn.fetchval(f"SELECT COUNT(*) FROM signals WHERE {where_sql}", *params)

        # Sort
        order = "event_date DESC NULLS LAST, id DESC"
        if sort == "oldest":
            order = "event_date ASC NULLS LAST, id ASC"
        elif sort == "score":
            order = "confidence DESC NULLS LAST, event_date DESC NULLS LAST"

        offset = (page - 1) * per_page
        rows = await conn.fetch(
            f"""
            SELECT id, source, source_url, event_date, code_dept, code_commune,
                   metric_name, metric_value, signal_type, confidence,
                   extracted_text, entities
            FROM signals
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            per_page,
            offset,
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total else 0,
            "signals": [
                {
                    "id": r["id"],
                    "source": r["source"],
                    "source_url": r["source_url"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "department": r["code_dept"],
                    "commune": r["code_commune"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "type": r["signal_type"],
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "excerpt": (r["extracted_text"] or "")[:500] or None,
                    "entities": r["entities"],
                }
                for r in rows
            ],
        }


@router.get("/detail/{signal_id}", summary="Détail complet d'un signal")
async def get_signal_detail(signal_id: int):
    """Retourne le détail complet d'un signal avec texte intégral."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM signals WHERE id = $1", signal_id)
        if not r:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Signal non trouvé")

        return {
            "id": r["id"],
            "source": r["source"],
            "source_url": r["source_url"],
            "collected_at": r["collected_at"].isoformat() if r["collected_at"] else None,
            "date": str(r["event_date"]) if r["event_date"] else None,
            "department": r["code_dept"],
            "commune": r["code_commune"],
            "epci": r["code_epci"],
            "latitude": float(r["latitude"]) if r["latitude"] else None,
            "longitude": float(r["longitude"]) if r["longitude"] else None,
            "metric": r["metric_name"],
            "value": float(r["metric_value"]) if r["metric_value"] else None,
            "type": r["signal_type"],
            "confidence": float(r["confidence"]) if r["confidence"] else None,
            "text": r["extracted_text"],
            "entities": r["entities"],
            "raw_data": r["raw_data"],
        }


@router.get("/stats", summary="Statistiques des signaux collectés")
async def get_signal_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT source, COUNT(*) as nb, COUNT(DISTINCT code_dept) as depts
            FROM signals GROUP BY source ORDER BY nb DESC
        """)
        total = await conn.fetchval("SELECT COUNT(*) FROM signals")
        micro = await conn.fetchval("SELECT COUNT(*) FROM micro_signals WHERE is_active = TRUE")

        return {
            "total_signals": total,
            "active_microsignals": micro,
            "by_source": [
                {"source": r["source"], "count": r["nb"], "departments": r["depts"]} for r in rows
            ],
        }


@router.get("/microsignals", summary="Micro-signaux actifs")
async def get_microsignals(
    min_score: Annotated[float, Query(ge=0, le=1)] = 0.0,
    signal_type: str | None = None,
    dept: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM micro_signals WHERE is_active = TRUE"
        params: list = []
        idx = 1

        if min_score > 0:
            query += f" AND score >= ${idx}"
            params.append(min_score)
            idx += 1
        if signal_type:
            query += f" AND signal_type = ${idx}"
            params.append(signal_type)
            idx += 1
        if dept:
            query += f" AND territory_code = ${idx}"
            params.append(dept)
            idx += 1

        query += f" ORDER BY score DESC LIMIT ${idx}"
        params.append(limit)

        rows = await conn.fetch(query, *params)

        return [
            {
                "id": r["id"],
                "territory_code": r["territory_code"],
                "signal_type": r["signal_type"],
                "sources": r["sources"],
                "dimensions": r["dimensions"],
                "score": round(r["score"], 3),
                "confidence": round(r["confidence"], 3),
                "impact": round(r["impact"], 3),
                "novelty": round(r["novelty"], 3),
                "description": r["description"],
                "detected_at": (r["detected_at"].isoformat() if r["detected_at"] else None),
            }
            for r in rows
        ]


@router.get("/radar/{dept}", summary="Radar territorial multi-dimensionnel")
async def get_territory_radar(dept: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source, metric_name, AVG(metric_value) as avg_val, COUNT(*) as cnt
            FROM signals
            WHERE code_dept = $1 AND metric_value IS NOT NULL
            GROUP BY source, metric_name
            """,
            dept,
        )

        pop_row = await conn.fetchrow(
            """
            SELECT metric_value FROM signals
            WHERE code_dept = $1 AND metric_name = 'population' AND source = 'insee'
            ORDER BY collected_at DESC LIMIT 1
            """,
            dept,
        )
        population = pop_row["metric_value"] if pop_row else None

        ms_rows = await conn.fetch(
            """
            SELECT signal_type, score, dimensions, description
            FROM micro_signals
            WHERE territory_code = $1 AND is_active = TRUE
            ORDER BY score DESC
            """,
            dept,
        )

        metrics = {}
        for r in rows:
            key = f"{r['source']}_{r['metric_name']}"
            metrics[key] = {"avg": round(float(r["avg_val"]), 2), "count": r["cnt"]}

        return {
            "code_dept": dept,
            "population": population,
            "nb_signals": sum(r["cnt"] for r in rows),
            "nb_microsignals": len(ms_rows),
            "metrics": metrics,
            "microsignals": [
                {
                    "type": r["signal_type"],
                    "score": round(r["score"], 3),
                    "dimensions": r["dimensions"],
                    "description": r["description"],
                }
                for r in ms_rows
            ],
        }


@router.get("/convergences", summary="Convergences multi-dimensionnelles")
async def get_convergences():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT territory_code, score, dimensions, sources, description, evidence, detected_at
            FROM micro_signals
            WHERE signal_type = 'convergence' AND is_active = TRUE
            ORDER BY score DESC
        """)

        return [
            {
                "territory_code": r["territory_code"],
                "score": round(r["score"], 3),
                "dimensions": r["dimensions"],
                "sources": r["sources"],
                "description": r["description"],
                "detected_at": (r["detected_at"].isoformat() if r["detected_at"] else None),
            }
            for r in rows
        ]


@router.get("/departments/scores", summary="Scores composites des départements")
async def get_department_scores_endpoint():
    """Scores multi-facteurs normalisés par population (cached 5 min)."""
    now = time.time()
    if _scores_cache["data"] and now - _scores_cache["ts"] < _SCORES_TTL:
        return _scores_cache["data"]

    from src.scripts.scoring_composite import get_department_scores

    scores = await get_department_scores()
    scores.sort(key=lambda x: x["score_composite"], reverse=True)

    _scores_cache["data"] = scores
    _scores_cache["ts"] = now
    return scores


@router.get("/departments/ranking", summary="Classement départemental")
async def get_department_ranking(
    limit: Annotated[int, Query(ge=1, le=101)] = 20,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH dept_scores AS (
                SELECT territory_code,
                       COUNT(*) as nb_signals,
                       AVG(score) as avg_score,
                       MAX(score) as max_score,
                       array_agg(DISTINCT signal_type) as types
                FROM micro_signals
                WHERE is_active = TRUE
                GROUP BY territory_code
            )
            SELECT * FROM dept_scores
            ORDER BY avg_score DESC
            LIMIT $1
            """,
            limit,
        )

        return [
            {
                "department": r["territory_code"],
                "nb_signals": r["nb_signals"],
                "avg_score": round(r["avg_score"], 3),
                "max_score": round(r["max_score"], 3),
                "signal_types": r["types"],
            }
            for r in rows
        ]


@router.get("/search", summary="Recherche sémantique dans les signaux")
async def semantic_search(
    q: str = Query(..., description="Requête de recherche"),
    limit: int = Query(20, ge=1, le=100),
):
    """Recherche sémantique via pgvector + nomic-embed-text."""
    import httpx

    OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # 1. Embed the query
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": "nomic-embed-text", "input": q},
        )
        resp.raise_for_status()
        query_emb = resp.json()["embeddings"][0]

    # 2. Search in pgvector
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check if embeddings exist
        count = await conn.fetchval("SELECT count(*) FROM signal_embeddings")
        if count == 0:
            return {
                "results": [],
                "total_embeddings": 0,
                "message": "Embeddings not yet generated. Run embed_signals.py first.",
            }

        rows = await conn.fetch(
            """
            SELECT se.signal_id, se.text_content,
                   1 - (se.embedding <=> $1::vector) as similarity,
                   s.source, s.code_dept, s.event_date, s.metric_name,
                   s.metric_value, s.signal_type
            FROM signal_embeddings se
            JOIN signals s ON s.id = se.signal_id
            ORDER BY se.embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_emb),
            limit,
        )

        return {
            "query": q,
            "total_embeddings": count,
            "results": [
                {
                    "signal_id": r["signal_id"],
                    "similarity": round(float(r["similarity"]), 4),
                    "source": r["source"],
                    "department": r["code_dept"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] is not None else None,
                    "type": r["signal_type"],
                    "text": r["text_content"][:200],
                }
                for r in rows
            ],
        }


@router.get("/epci/{code}", summary="Signaux par EPCI")
async def get_epci_signals(code: str, limit: int = Query(50, ge=1, le=500)):
    """Signaux agreges par EPCI."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT count(*) as total,
                   count(DISTINCT source) as sources,
                   count(DISTINCT code_dept) as depts,
                   count(DISTINCT code_commune) as communes
            FROM signals WHERE code_epci = $1
        """,
            code,
        )

        by_source = await conn.fetch(
            """
            SELECT source, count(*) as n FROM signals
            WHERE code_epci = $1 GROUP BY source ORDER BY n DESC
        """,
            code,
        )

        recent = await conn.fetch(
            """
            SELECT id, source, metric_name, metric_value, code_dept, code_commune, event_date
            FROM signals WHERE code_epci = $1
            ORDER BY event_date DESC NULLS LAST LIMIT $2
        """,
            code,
            limit,
        )

        return {
            "epci": code,
            "total_signals": stats["total"],
            "sources": stats["sources"],
            "departments": stats["depts"],
            "communes": stats["communes"],
            "by_source": [{"source": r["source"], "count": r["n"]} for r in by_source],
            "recent_signals": [
                {
                    "id": r["id"],
                    "source": r["source"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "department": r["code_dept"],
                    "commune": r["code_commune"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                }
                for r in recent
            ],
        }


@router.get("/communes", summary="Recherche de communes")
async def search_communes(
    q: str = Query(..., min_length=2, description="Recherche par nom ou code"),
    limit: int = Query(20, ge=1, le=100),
):
    """Recherche de communes dans le referentiel geo."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT g.code_commune, g.nom_commune, g.code_dept, g.code_epci,
                   count(s.id) as nb_signals
            FROM geo_communes g
            LEFT JOIN signals s ON s.code_commune = g.code_commune
            WHERE g.nom_commune ILIKE $1 OR g.code_commune LIKE $2
            GROUP BY g.code_commune, g.nom_commune, g.code_dept, g.code_epci
            ORDER BY nb_signals DESC
            LIMIT $3
        """,
            f"%{q}%",
            f"{q}%",
            limit,
        )

        return [
            {
                "code": r["code_commune"],
                "name": r["nom_commune"],
                "department": r["code_dept"],
                "epci": r["code_epci"],
                "signals": r["nb_signals"],
            }
            for r in rows
        ]


@router.get("/predictions", summary="Predictions Prophet par departement")
async def get_predictions(
    dept: str | None = Query(None, description="Code departement"),
    metric: str | None = Query(None, description="Metric filter"),
    limit: int = Query(50, ge=1, le=200),
):
    """Predictions temporelles via Facebook Prophet.

    Retourne les previsions a 3 mois avec intervalles de confiance.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if dept:
            rows = await conn.fetch(
                """
                SELECT department, source, metric, metric_label,
                       trend_direction, trend_change_pct, changepoints,
                       forecast, last_actual, data_points, prediction_date
                FROM predictions_prophet
                WHERE department = $1
                  AND prediction_date = (SELECT MAX(prediction_date) FROM predictions_prophet WHERE department = $1)
                ORDER BY ABS(trend_change_pct) DESC
                LIMIT $2
            """,
                dept,
                limit,
            )
        elif metric:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (department)
                       department, source, metric, metric_label,
                       trend_direction, trend_change_pct, changepoints,
                       forecast, last_actual, data_points, prediction_date
                FROM predictions_prophet
                WHERE metric = $1
                ORDER BY department, prediction_date DESC
                LIMIT $2
            """,
                metric,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT department, source, metric, metric_label,
                       trend_direction, trend_change_pct, changepoints,
                       forecast, last_actual, data_points, prediction_date
                FROM predictions_prophet
                WHERE prediction_date = (SELECT MAX(prediction_date) FROM predictions_prophet)
                ORDER BY ABS(trend_change_pct) DESC
                LIMIT $1
            """,
                limit,
            )

        return {
            "count": len(rows),
            "predictions": [
                {
                    "department": r["department"],
                    "source": r["source"],
                    "metric": r["metric"],
                    "label": r["metric_label"],
                    "trend": r["trend_direction"],
                    "change_pct": round(float(r["trend_change_pct"]), 1),
                    "data_points": r["data_points"],
                    "forecast": r["forecast"],
                    "last_actual": r["last_actual"],
                    "changepoints": r["changepoints"],
                    "date": str(r["prediction_date"]),
                }
                for r in rows
            ],
        }


@router.get("/anomalies/v2", summary="Detection d'anomalies avancee (Isolation Forest + DBSCAN)")
async def get_anomalies_v2(
    limit: int = Query(20, ge=1, le=102),
    min_risk: float = Query(0.0, ge=0.0, le=1.0),
):
    """Resultats de la detection d'anomalies multivariee.

    Combine Isolation Forest, DBSCAN clustering, et convergence v2.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT department, risk_score, isolation_forest, cluster_info,
                   convergence_score, nb_micro_signals, detected_at
            FROM anomaly_detection_v2
            WHERE detection_date = CURRENT_DATE
              AND risk_score >= $1
            ORDER BY risk_score DESC
            LIMIT $2
        """,
            min_risk,
            limit,
        )

        if not rows:
            # Fallback to latest detection run
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (department)
                    department, risk_score, isolation_forest, cluster_info,
                    convergence_score, nb_micro_signals, detected_at
                FROM anomaly_detection_v2
                WHERE risk_score >= $1
                ORDER BY department, detected_at DESC
                LIMIT $2
            """,
                min_risk,
                limit,
            )

        return {
            "count": len(rows),
            "results": [
                {
                    "department": r["department"],
                    "risk_score": round(float(r["risk_score"]), 4),
                    "isolation_forest": r["isolation_forest"],
                    "cluster": r["cluster_info"],
                    "convergence_score": round(float(r["convergence_score"]), 4)
                    if r["convergence_score"]
                    else 0,
                    "nb_micro_signals": r["nb_micro_signals"],
                    "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                }
                for r in rows
            ],
        }


@router.get("/clusters", summary="Clusters de departements (DBSCAN)")
async def get_clusters():
    """Groupement des departements par profil economique."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT department, cluster_info, risk_score
            FROM anomaly_detection_v2
            WHERE detection_date = (SELECT MAX(detection_date) FROM anomaly_detection_v2)
            ORDER BY department
        """)

        import json as _json

        clusters: dict = {}
        for r in rows:
            info = r["cluster_info"]
            if isinstance(info, str):
                try:
                    info = _json.loads(info)
                except Exception:
                    info = {}
            cid = info.get("id", -1) if isinstance(info, dict) else -1
            if cid not in clusters:
                clusters[cid] = {"id": cid, "departments": [], "is_outlier_group": cid == -1}
            clusters[cid]["departments"].append(
                {
                    "code": r["department"],
                    "risk_score": round(float(r["risk_score"]), 4),
                }
            )
            if (
                isinstance(info, dict)
                and "cluster_profile" in info
                and "profile" not in clusters[cid]
            ):
                clusters[cid]["profile"] = info["cluster_profile"]

        return {
            "nb_clusters": len([c for c in clusters.values() if not c["is_outlier_group"]]),
            "nb_outliers": len(clusters.get(-1, {}).get("departments", [])),
            "clusters": list(clusters.values()),
        }


@router.get("/department/{dept}/signals/recent", summary="Signaux recents par departement")
async def get_department_recent_signals(
    dept: str,
    limit: int = Query(15, ge=1, le=100),
):
    """Retourne les signaux les plus recents pour un departement."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, source, source_url, event_date, code_dept, code_commune,
                   metric_name, metric_value, signal_type, confidence,
                   extracted_text
            FROM signals
            WHERE code_dept = $1
            ORDER BY event_date DESC NULLS LAST, id DESC
            LIMIT $2
            """,
            dept,
            limit,
        )

        return {
            "department": dept,
            "count": len(rows),
            "signals": [
                {
                    "id": r["id"],
                    "source": r["source"],
                    "source_url": r["source_url"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "commune": r["code_commune"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "type": r["signal_type"],
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "excerpt": (r["extracted_text"] or "")[:300] or None,
                }
                for r in rows
            ],
        }


@router.get("/department/{dept}/timeline", summary="Timeline des signaux par departement")
async def get_department_timeline(
    dept: str,
    days: int = Query(180, ge=7, le=730),
):
    """Retourne la timeline aggregee des signaux pour un departement."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date_trunc('week', event_date)::date as week,
                   source,
                   COUNT(*) as count
            FROM signals
            WHERE code_dept = $1
              AND event_date >= CURRENT_DATE - $2::int * INTERVAL '1 day'
              AND event_date IS NOT NULL
            GROUP BY week, source
            ORDER BY week
            """,
            dept,
            days,
        )

        timeline: dict = {}
        for r in rows:
            w = str(r["week"])
            if w not in timeline:
                timeline[w] = {"date": w, "total": 0, "by_source": {}}
            timeline[w]["total"] += r["count"]
            timeline[w]["by_source"][r["source"]] = r["count"]

        return {
            "department": dept,
            "days": days,
            "timeline": list(timeline.values()),
        }


@router.get("/alerts", summary="Alertes signaux actives")
async def get_signal_alerts():
    """Retourne les alertes actives basees sur les micro-signaux a haut score."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, territory_code, signal_type, score, confidence,
                   impact, description, sources, dimensions, detected_at
            FROM micro_signals
            WHERE is_active = TRUE AND score >= 0.7
            ORDER BY score DESC
            LIMIT 50
        """)

        return {
            "count": len(rows),
            "alerts": [
                {
                    "id": r["id"],
                    "department": r["territory_code"],
                    "type": r["signal_type"],
                    "score": round(r["score"], 3),
                    "confidence": round(r["confidence"], 3),
                    "impact": round(r["impact"], 3),
                    "description": r["description"],
                    "sources": r["sources"],
                    "dimensions": r["dimensions"],
                    "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                }
                for r in rows
            ],
        }
