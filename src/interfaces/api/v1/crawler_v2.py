"""Crawler management API — configuration, status, manual triggers.

Exposes the unified collector (collect_all_v2.py) as a controllable service.
"""

import asyncio
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/crawler", tags=["Crawler"])

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ── In-memory state ──────────────────────────────────────────
_state: dict[str, Any] = {
    "is_running": False,
    "current_source": None,
    "started_at": None,
    "last_run": None,
    "last_run_stats": None,
    "error": None,
}

# ── Source definitions ───────────────────────────────────────
SOURCES = [
    {"id": "bodacc", "name": "BODACC", "type": "api", "description": "Annonces legales (creations, liquidations, radiations)", "schedule": "daily", "enabled": True},
    {"id": "france_travail", "name": "France Travail", "type": "api", "description": "Offres d'emploi par departement", "schedule": "daily", "enabled": True},
    {"id": "sirene", "name": "SIRENE", "type": "api", "description": "Creations d'entreprises (data.gouv.fr)", "schedule": "daily", "enabled": True},
    {"id": "insee", "name": "INSEE", "type": "api", "description": "Chomage, population", "schedule": "weekly", "enabled": True},
    {"id": "ofgl", "name": "OFGL", "type": "api", "description": "Finances locales", "schedule": "weekly", "enabled": True},
    {"id": "dvf", "name": "DVF", "type": "api", "description": "Transactions immobilieres", "schedule": "daily", "enabled": True},
    {"id": "banque_france", "name": "Banque de France", "type": "api", "description": "Defaillances d'entreprises", "schedule": "weekly", "enabled": False},
    {"id": "presse_locale", "name": "Presse Locale", "type": "rss", "description": "Flux RSS presse regionale", "schedule": "6h", "enabled": True},
    {"id": "urssaf", "name": "URSSAF", "type": "api", "description": "Declarations d'embauche", "schedule": "weekly", "enabled": True},
    {"id": "google_trends", "name": "Google Trends", "type": "scraper", "description": "Tendances de recherche", "schedule": "daily", "enabled": True},
    {"id": "sitadel", "name": "Sitadel", "type": "api", "description": "Permis de construire (SDES DiDo)", "schedule": "monthly", "enabled": True},
    {"id": "gdelt", "name": "GDELT", "type": "api", "description": "Evenements mediatiques internationaux", "schedule": "daily", "enabled": False},
]


# ── Models ───────────────────────────────────────────────────
class CrawlerConfig(BaseModel):
    sources: list[dict[str, Any]]
    schedule_enabled: bool = True
    default_days_back: int = 30
    max_concurrent: int = 3


class CrawlTriggerRequest(BaseModel):
    source: str | None = None
    departments: list[str] | None = None
    days_back: int = 30


# ── Helpers ──────────────────────────────────────────────────
async def _get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DB_DSN.replace("+asyncpg", ""))


async def _run_collection(source: str | None, departments: list[str] | None, days_back: int):
    """Run the collector script in a subprocess."""
    global _state
    _state["is_running"] = True
    _state["current_source"] = source or "all"
    _state["started_at"] = datetime.now(timezone.utc).isoformat()
    _state["error"] = None

    try:
        cmd = ["python3", str(PROJECT_ROOT / "src" / "scripts" / "collect_all_v2.py")]
        if source:
            cmd += ["--source", source]
        if departments:
            cmd += ["--depts", ",".join(departments)]
        cmd += ["--days", str(days_back)]

        logger.info(f"Starting collection: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await proc.communicate()

        _state["last_run"] = datetime.now(timezone.utc).isoformat()
        if proc.returncode == 0:
            _state["last_run_stats"] = {"status": "success", "output": stdout.decode()[-500:]}
        else:
            _state["error"] = stderr.decode()[-500:]
            _state["last_run_stats"] = {"status": "error", "returncode": proc.returncode}
    except Exception as e:
        _state["error"] = str(e)
        logger.error(f"Collection failed: {e}")
    finally:
        _state["is_running"] = False
        _state["current_source"] = None


# ── Routes ───────────────────────────────────────────────────

@router.get("/config")
async def get_config() -> CrawlerConfig:
    """Return crawler configuration (sources and schedules)."""
    return CrawlerConfig(sources=SOURCES)


@router.put("/config/source/{source_id}")
async def update_source_config(source_id: str, enabled: bool = True):
    """Enable/disable a source."""
    for s in SOURCES:
        if s["id"] == source_id:
            s["enabled"] = enabled
            return {"ok": True, "source": s}
    raise HTTPException(404, f"Source {source_id} not found")


@router.get("/status")
async def get_status():
    """Return crawler running status."""
    return {
        "is_running": _state["is_running"],
        "current_source": _state["current_source"],
        "started_at": _state["started_at"],
        "last_run": _state["last_run"],
        "error": _state["error"],
    }


@router.get("/stats")
async def get_stats():
    """Return collection statistics from DB."""
    conn = await _get_db()
    try:
        total = await conn.fetchval("SELECT count(*) FROM signals")
        by_source = await conn.fetch(
            "SELECT source, count(*) as cnt, max(collected_at) as last_collected "
            "FROM signals GROUP BY source ORDER BY cnt DESC"
        )
        recent_24h = await conn.fetchval(
            "SELECT count(*) FROM signals WHERE collected_at > now() - interval '24 hours'"
        )
        depts_covered = await conn.fetchval(
            "SELECT count(DISTINCT code_dept) FROM signals WHERE code_dept IS NOT NULL"
        )
        date_range = await conn.fetch(
            "SELECT min(event_date) as min_date, max(event_date) as max_date FROM signals"
        )

        sources_stats = []
        for row in by_source:
            sources_stats.append({
                "source": row["source"],
                "count": row["cnt"],
                "last_collected": row["last_collected"].isoformat() if row["last_collected"] else None,
            })

        return {
            "total_signals": total,
            "recent_24h": recent_24h,
            "departments_covered": depts_covered,
            "date_range": {
                "min": str(date_range[0]["min_date"]) if date_range else None,
                "max": str(date_range[0]["max_date"]) if date_range else None,
            },
            "by_source": sources_stats,
        }
    finally:
        await conn.close()


@router.post("/run")
async def trigger_collection(req: CrawlTriggerRequest, bg: BackgroundTasks):
    """Trigger a collection run (all or specific source)."""
    if _state["is_running"]:
        raise HTTPException(409, "A collection is already running")

    bg.add_task(_run_collection, req.source, req.departments, req.days_back)
    return {
        "status": "started",
        "source": req.source or "all",
        "departments": req.departments,
        "days_back": req.days_back,
    }


@router.get("/history")
async def collection_history(limit: int = 20):
    """Return recent signal collection activity (grouped by collection batch)."""
    conn = await _get_db()
    try:
        rows = await conn.fetch("""
            SELECT 
                source,
                date_trunc('hour', collected_at) as batch_time,
                count(*) as count,
                count(DISTINCT code_dept) as depts
            FROM signals
            WHERE collected_at > now() - interval '7 days'
            GROUP BY source, date_trunc('hour', collected_at)
            ORDER BY batch_time DESC
            LIMIT $1
        """, limit)
        return [
            {
                "source": r["source"],
                "batch_time": r["batch_time"].isoformat(),
                "count": r["count"],
                "departments": r["depts"],
            }
            for r in rows
        ]
    finally:
        await conn.close()
