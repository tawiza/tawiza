"""Micro-signals management API — detection, history, validation, stats.

Extends the basic microsignals endpoint in signals.py with management features.
"""

import asyncio
import os
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/microsignals", tags=["Micro-Signals"])

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_detection_state: dict[str, Any] = {
    "is_running": False,
    "last_run": None,
    "last_count": None,
    "error": None,
}


async def _get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DB_DSN.replace("+asyncpg", ""))


# ── Background detection ─────────────────────────────────────


async def _run_detection():
    global _detection_state
    _detection_state["is_running"] = True
    _detection_state["error"] = None
    try:
        script = PROJECT_ROOT / "src" / "scripts" / "detect_microsignals_v2.py"
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await proc.communicate()
        _detection_state["last_run"] = datetime.now(UTC).isoformat()
        if proc.returncode == 0:
            # Try to parse count from output
            output = stdout.decode()
            _detection_state["last_count"] = (
                output.strip().split("\n")[-1] if output.strip() else "done"
            )
        else:
            _detection_state["error"] = stderr.decode()[-300:]
    except Exception as e:
        _detection_state["error"] = str(e)
    finally:
        _detection_state["is_running"] = False


# ── Routes ───────────────────────────────────────────────────


@router.get("/active")
async def get_active_microsignals(
    dept: str | None = None,
    min_score: float = Query(0, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Get active micro-signals with optional filters."""
    conn = await _get_db()
    try:
        where_clauses = ["is_active = true", "score >= $1"]
        params: list[Any] = [min_score]

        if dept:
            params.append(dept)
            where_clauses.append(f"territory_code = ${len(params)}")

        params.append(limit)
        query = f"""
            SELECT id, territory_code, signal_type, sources, dimensions,
                   score, confidence, impact, novelty, description,
                   detected_at, event_period
            FROM micro_signals
            WHERE {" AND ".join(where_clauses)}
            ORDER BY score DESC
            LIMIT ${len(params)}
        """

        rows = await conn.fetch(query, *params)
        return {
            "total": len(rows),
            "microsignals": [
                {
                    "id": r["id"],
                    "territory_code": r["territory_code"],
                    "signal_type": r["signal_type"],
                    "sources": r["sources"],
                    "dimensions": r["dimensions"],
                    "score": float(r["score"]),
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "impact": float(r["impact"]) if r["impact"] else None,
                    "novelty": float(r["novelty"]) if r["novelty"] else None,
                    "description": r["description"],
                    "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                    "event_period": r["event_period"],
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/stats")
async def microsignal_stats():
    """Aggregated micro-signal statistics."""
    conn = await _get_db()
    try:
        total = await conn.fetchval("SELECT count(*) FROM micro_signals WHERE is_active = true")
        by_type = await conn.fetch("""
            SELECT signal_type, count(*) as cnt, avg(score) as avg_score
            FROM micro_signals WHERE is_active = true
            GROUP BY signal_type ORDER BY cnt DESC
        """)
        by_dept = await conn.fetch("""
            SELECT territory_code, count(*) as cnt, max(score) as max_score
            FROM micro_signals WHERE is_active = true
            GROUP BY territory_code ORDER BY cnt DESC
            LIMIT 20
        """)
        severity_dist = await conn.fetch("""
            SELECT
                CASE
                    WHEN score >= 0.8 THEN 'critical'
                    WHEN score >= 0.6 THEN 'high'
                    WHEN score >= 0.4 THEN 'medium'
                    ELSE 'low'
                END as severity,
                count(*) as cnt
            FROM micro_signals WHERE is_active = true
            GROUP BY severity ORDER BY cnt DESC
        """)

        return {
            "total_active": total,
            "by_type": [
                {
                    "type": r["signal_type"],
                    "count": r["cnt"],
                    "avg_score": round(float(r["avg_score"]), 3),
                }
                for r in by_type
            ],
            "by_department": [
                {
                    "department": r["territory_code"],
                    "count": r["cnt"],
                    "max_score": round(float(r["max_score"]), 3),
                }
                for r in by_dept
            ],
            "severity_distribution": [
                {"severity": r["severity"], "count": r["cnt"]} for r in severity_dist
            ],
        }
    finally:
        await conn.close()


@router.get("/history")
async def microsignal_history(
    dept: str | None = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
):
    """Historical micro-signals (including resolved ones)."""
    conn = await _get_db()
    try:
        params: list[Any] = [days, limit]
        where = "detected_at > now() - make_interval(days => $1)"

        if dept:
            params.append(dept)
            where += f" AND territory_code = ${len(params)}"

        rows = await conn.fetch(
            f"""
            SELECT id, territory_code, signal_type, score, description,
                   detected_at, is_active, validated_by, validation_date
            FROM micro_signals
            WHERE {where}
            ORDER BY detected_at DESC
            LIMIT $2
        """,
            *params,
        )

        return {
            "total": len(rows),
            "history": [
                {
                    "id": r["id"],
                    "territory_code": r["territory_code"],
                    "signal_type": r["signal_type"],
                    "score": float(r["score"]),
                    "description": r["description"],
                    "detected_at": r["detected_at"].isoformat() if r["detected_at"] else None,
                    "is_active": r["is_active"],
                    "validated_by": r["validated_by"],
                    "validation_date": r["validation_date"].isoformat()
                    if r["validation_date"]
                    else None,
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.post("/{ms_id}/validate")
async def validate_microsignal(ms_id: int, relevant: bool = True, user: str = "admin"):
    """Mark a micro-signal as validated/rejected."""
    conn = await _get_db()
    try:
        result = await conn.execute(
            """
            UPDATE micro_signals
            SET validated_by = $1,
                validation_date = now(),
                is_active = $2
            WHERE id = $3
        """,
            user if relevant else f"rejected:{user}",
            relevant,
            ms_id,
        )

        if result == "UPDATE 0":
            raise HTTPException(404, f"Micro-signal {ms_id} not found")

        return {"ok": True, "id": ms_id, "validated": relevant}
    finally:
        await conn.close()


@router.post("/detect")
async def trigger_detection(bg: BackgroundTasks):
    """Trigger micro-signal detection (background task)."""
    if _detection_state["is_running"]:
        raise HTTPException(409, "Detection already running")

    bg.add_task(_run_detection)
    return {"status": "started", "message": "Detection lancee en arriere-plan"}


@router.get("/detect/status")
async def detection_status():
    """Status of the last detection run."""
    return _detection_state
