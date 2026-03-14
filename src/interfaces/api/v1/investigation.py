"""Investigation API — entity search, signal drill-down, risk analysis.

Provides endpoints for the Investigation page to search entities,
view their signal history, and run LLM-powered risk assessments.
"""

import os
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/investigation", tags=["Investigation"])

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza",
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


# ── Models ───────────────────────────────────────────────────


class EntityProfile(BaseModel):
    siren: str
    name: str | None = None
    department: str | None = None
    signal_count: int = 0
    sources: list[str] = []
    first_seen: str | None = None
    last_seen: str | None = None
    risk_indicators: list[dict[str, Any]] = []


class InvestigationResult(BaseModel):
    query: str
    total_results: int
    entities: list[dict[str, Any]]
    signals: list[dict[str, Any]]


# ── Helpers ──────────────────────────────────────────────────


async def _get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DB_DSN.replace("+asyncpg", ""))


# ── Routes ───────────────────────────────────────────────────


@router.get("/search")
async def search_investigation(
    q: str = Query(..., min_length=2, description="Search query (text, SIREN, department, etc.)"),
    limit: int = Query(30, ge=1, le=100),
):
    """Search signals by text, SIREN, entity name, or department code."""
    conn = await _get_db()
    try:
        # Multi-strategy search: exact dept, SIREN in raw_data, or text search
        results = []

        # 1. Check if query is a department code
        if len(q) <= 3 and q.replace("A", "").replace("B", "").isdigit():
            rows = await conn.fetch(
                """
                SELECT id, source, metric_name, metric_value, code_dept, event_date,
                       signal_type, extracted_text, raw_data, collected_at
                FROM signals
                WHERE code_dept = $1
                ORDER BY collected_at DESC
                LIMIT $2
            """,
                q,
                limit,
            )
            results = [dict(r) for r in rows]

        # 2. SIREN/SIRET search (9+ digits) — extract SIREN from SIRET if needed
        elif q.isdigit() and len(q) >= 9:
            # If SIRET (14 digits), extract SIREN (first 9)
            siren = q[:9] if len(q) >= 14 else q
            rows = await conn.fetch(
                """
                SELECT id, source, metric_name, metric_value, code_dept, event_date,
                       signal_type, extracted_text, raw_data, collected_at
                FROM signals
                WHERE raw_data->>'siren' = $1
                   OR raw_data->>'siren' = $3
                   OR raw_data->>'registre' ILIKE '%' || $3 || '%'
                ORDER BY collected_at DESC
                LIMIT $2
            """,
                q,
                limit,
                siren,
            )
            results = [dict(r) for r in rows]

        # 3. Text search in extracted_text and metric_name
        if not results:
            rows = await conn.fetch(
                """
                SELECT id, source, metric_name, metric_value, code_dept, event_date,
                       signal_type, extracted_text, raw_data, collected_at
                FROM signals
                WHERE extracted_text ILIKE '%' || $1 || '%'
                   OR metric_name ILIKE '%' || $1 || '%'
                   OR raw_data->>'commercant' ILIKE '%' || $1 || '%'
                   OR raw_data->>'nom' ILIKE '%' || $1 || '%'
                ORDER BY collected_at DESC
                LIMIT $2
            """,
                q,
                limit,
            )
            results = [dict(r) for r in rows]

        # Format results
        formatted = []
        for r in results:
            # Build readable text from available data
            text = (r["extracted_text"] or "")[:200]
            if not text.strip() or text.startswith("{"):
                # Try to build from raw_data
                rd = r.get("raw_data") or {}
                if isinstance(rd, dict):
                    parts = []
                    for key in (
                        "denomination",
                        "nom",
                        "name",
                        "titre",
                        "title",
                        "registreCommerce",
                        "ville",
                        "cp",
                        "activite",
                        "familleAvis",
                    ):
                        if key in rd and rd[key]:
                            parts.append(f"{key}: {rd[key]}")
                    if parts:
                        text = " | ".join(parts[:4])
                if not text.strip():
                    text = r["metric_name"] or ""

            formatted.append(
                {
                    "signal_id": r["id"],
                    "source": r["source"],
                    "metric": r["metric_name"],
                    "value": float(r["metric_value"]) if r["metric_value"] else None,
                    "department": r["code_dept"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "type": r["signal_type"],
                    "text": text,
                    "collected_at": r["collected_at"].isoformat() if r["collected_at"] else None,
                }
            )

        # If SIREN search returned nothing, try external API
        if not formatted and q.isdigit() and len(q) >= 9:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    # Try data.gouv.fr SIRENE API
                    resp = await client.get(
                        f"https://recherche-entreprises.api.gouv.fr/search?q={q}&page=1&per_page=5"
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for r in data.get("results", []):
                            formatted.append(
                                {
                                    "signal_id": 0,
                                    "source": "sirene_api",
                                    "metric": r.get("nom_complet", ""),
                                    "value": None,
                                    "department": r.get("siege", {}).get("departement", ""),
                                    "date": r.get("date_creation", ""),
                                    "type": "external",
                                    "text": f"{r.get('nom_complet', '')} — {r.get('siege', {}).get('libelle_commune', '')} — NAF: {r.get('activite_principale', '')} — {r.get('nature_juridique', '')}",
                                    "collected_at": None,
                                }
                            )
            except Exception as e:
                logger.debug(f"External SIRENE lookup failed: {e}")

        return {
            "query": q,
            "total_results": len(formatted),
            "results": formatted,
        }
    finally:
        await conn.close()


@router.get("/entity/{identifier}")
async def get_entity_profile(identifier: str):
    """Get a signal profile for an entity (SIREN, company name, etc.)."""
    conn = await _get_db()
    try:
        # Search signals related to this entity
        rows = await conn.fetch(
            """
            SELECT id, source, metric_name, metric_value, code_dept, event_date,
                   signal_type, extracted_text, raw_data, collected_at
            FROM signals
            WHERE raw_data::text ILIKE '%' || $1 || '%'
               OR extracted_text ILIKE '%' || $1 || '%'
            ORDER BY event_date DESC
            LIMIT 50
        """,
            identifier,
        )

        if not rows:
            raise HTTPException(404, f"No signals found for entity '{identifier}'")

        # Build profile
        sources = list({r["source"] for r in rows})
        depts = list({r["code_dept"] for r in rows if r["code_dept"]})
        dates = [r["event_date"] for r in rows if r["event_date"]]

        # Detect risk indicators
        risk_indicators = []
        for r in rows:
            if r["signal_type"] in ("liquidation", "procedure_collective", "radiation"):
                risk_indicators.append(
                    {
                        "type": r["signal_type"],
                        "date": str(r["event_date"]) if r["event_date"] else None,
                        "source": r["source"],
                        "detail": (r["extracted_text"] or "")[:150],
                    }
                )

        signals_list = [
            {
                "id": r["id"],
                "source": r["source"],
                "metric": r["metric_name"],
                "value": float(r["metric_value"]) if r["metric_value"] else None,
                "department": r["code_dept"],
                "date": str(r["event_date"]) if r["event_date"] else None,
                "type": r["signal_type"],
                "text": (r["extracted_text"] or "")[:200],
            }
            for r in rows
        ]

        return {
            "identifier": identifier,
            "signal_count": len(rows),
            "sources": sources,
            "departments": depts,
            "first_seen": str(min(dates)) if dates else None,
            "last_seen": str(max(dates)) if dates else None,
            "risk_indicators": risk_indicators,
            "risk_level": "high"
            if len(risk_indicators) >= 3
            else "medium"
            if risk_indicators
            else "low",
            "signals": signals_list,
        }
    finally:
        await conn.close()


@router.get("/department/{dept}/overview")
async def department_investigation(dept: str, days: int = Query(90, ge=7, le=365)):
    """Deep investigation overview for a department."""
    conn = await _get_db()
    try:
        # Signal breakdown by type
        by_type = await conn.fetch(
            """
            SELECT signal_type, count(*) as cnt
            FROM signals
            WHERE code_dept = $1 AND event_date > now() - make_interval(days => $2)
            GROUP BY signal_type
            ORDER BY cnt DESC
        """,
            dept,
            days,
        )

        # Risk signals (liquidations, procedures collectives)
        risk_signals = await conn.fetch(
            """
            SELECT id, source, metric_name, event_date, signal_type, extracted_text
            FROM signals
            WHERE code_dept = $1
              AND signal_type IN ('liquidation', 'procedure_collective', 'radiation')
              AND event_date > now() - make_interval(days => $2)
            ORDER BY event_date DESC
            LIMIT 20
        """,
            dept,
            days,
        )

        # Active micro-signals
        microsignals = await conn.fetch(
            """
            SELECT id, signal_type, score, description, detected_at
            FROM micro_signals
            WHERE territory_code = $1 AND is_active = true
            ORDER BY score DESC
            LIMIT 10
        """,
            dept,
        )

        # Monthly trend
        monthly = await conn.fetch(
            """
            SELECT date_trunc('month', event_date) as month,
                   count(*) as total,
                   count(*) FILTER (WHERE signal_type IN ('liquidation','procedure_collective','radiation')) as risk_count
            FROM signals
            WHERE code_dept = $1 AND event_date > now() - make_interval(days => $2)
            GROUP BY month
            ORDER BY month
        """,
            dept,
            days,
        )

        return {
            "department": dept,
            "period_days": days,
            "signal_breakdown": [{"type": r["signal_type"], "count": r["cnt"]} for r in by_type],
            "risk_signals": [
                {
                    "id": r["id"],
                    "source": r["source"],
                    "type": r["signal_type"],
                    "date": str(r["event_date"]) if r["event_date"] else None,
                    "text": (r["extracted_text"] or "")[:150],
                }
                for r in risk_signals
            ],
            "micro_signals": [
                {
                    "id": r["id"],
                    "type": r["signal_type"],
                    "score": float(r["score"]),
                    "description": r["description"],
                    "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                }
                for r in microsignals
            ],
            "monthly_trend": [
                {
                    "month": r["month"].strftime("%Y-%m"),
                    "total": r["total"],
                    "risk_count": r["risk_count"],
                }
                for r in monthly
            ],
        }
    finally:
        await conn.close()


@router.post("/analyze")
async def analyze_entity(identifier: str = Query(...), context: str = Query("")):
    """LLM-powered analysis of an entity or department's signal pattern."""
    import httpx

    conn = await _get_db()
    try:
        # Gather context signals
        rows = await conn.fetch(
            """
            SELECT source, metric_name, metric_value, event_date, signal_type, extracted_text
            FROM signals
            WHERE (raw_data::text ILIKE '%' || $1 || '%'
               OR extracted_text ILIKE '%' || $1 || '%'
               OR code_dept = $1)
            ORDER BY event_date DESC
            LIMIT 20
        """,
            identifier,
        )

        if not rows:
            raise HTTPException(404, f"No data found for '{identifier}'")

        # Build context for LLM
        signal_lines = []
        for r in rows:
            line = f"[{r['source']}] {r['event_date']} — {r['metric_name']}"
            if r["metric_value"]:
                line += f" = {r['metric_value']}"
            if r["signal_type"]:
                line += f" ({r['signal_type']})"
            if r["extracted_text"]:
                line += f" | {r['extracted_text'][:100]}"
            signal_lines.append(line)

        prompt = f"""Analyse les signaux suivants pour '{identifier}'. {context}

Signaux ({len(signal_lines)}):
{chr(10).join(signal_lines[:15])}

Reponds en francais. Structure:
1. Synthese (2-3 phrases)
2. Points de vigilance
3. Tendance generale (positive/negative/neutre)
4. Recommandations"""

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": "qwen3.5:27b",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_ctx": 4096},
                    "think": False,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                analysis = data.get("message", {}).get("content", "Analyse indisponible")
            else:
                analysis = f"Erreur LLM: {resp.status_code}"

        return {
            "identifier": identifier,
            "signal_count": len(rows),
            "analysis": analysis,
        }
    finally:
        await conn.close()
