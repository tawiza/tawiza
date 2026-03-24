"""Health Check Endpoints - System health and readiness probes.

Provides endpoints for:
- /health/live: Liveness probe (is the app running?)
- /health/ready: Readiness probe (can the app serve traffic?)
- /health/startup: Startup probe (has the app finished initializing?)
- /health/full: Detailed health check with all dependencies

Usage with Kubernetes:
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8000
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8000
"""

import asyncio
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response, status
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["Health"])


# =============================================================================
# Response Models
# =============================================================================


class HealthStatus(BaseModel):
    """Health status response."""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str = "2.0.3"
    uptime_seconds: float


class DependencyHealth(BaseModel):
    """Health status of a dependency."""

    name: str
    status: str  # "up", "down", "degraded"
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class FullHealthResponse(BaseModel):
    """Full health check response."""

    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    dependencies: list[DependencyHealth]


# =============================================================================
# State
# =============================================================================

_start_time = time.time()
_startup_complete = False


def mark_startup_complete():
    """Mark the application as fully started."""
    global _startup_complete
    _startup_complete = True
    logger.info("Application startup complete")


def get_uptime() -> float:
    """Get application uptime in seconds."""
    return time.time() - _start_time


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_database() -> DependencyHealth:
    """Check database connectivity."""
    start = time.time()
    try:
        from src.infrastructure.persistence.database import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="database",
            status="up",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="database",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e),
        )


async def check_ollama() -> DependencyHealth:
    """Check Ollama LLM service."""
    start = time.time()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()

        latency = (time.time() - start) * 1000
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]

        return DependencyHealth(
            name="ollama",
            status="up",
            latency_ms=round(latency, 2),
            details={"models_loaded": len(models)},
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="ollama",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e),
        )


async def check_redis() -> DependencyHealth:
    """Check Redis cache service."""
    start = time.time()
    try:
        import redis.asyncio as redis

        client = redis.from_url("redis://localhost:6379")
        await client.ping()
        await client.close()

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="redis",
            status="up",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        # Redis is optional, so degraded instead of down
        return DependencyHealth(
            name="redis",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"Redis unavailable: {e}",
        )


async def check_disk_space() -> DependencyHealth:
    """Check available disk space."""
    try:
        import shutil

        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        used_percent = (used / total) * 100

        if free_gb < 1:
            status = "down"
            message = f"Critical: only {free_gb:.1f}GB free"
        elif free_gb < 5:
            status = "degraded"
            message = f"Warning: only {free_gb:.1f}GB free"
        else:
            status = "up"
            message = None

        return DependencyHealth(
            name="disk",
            status=status,
            message=message,
            details={
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_percent, 1),
            },
        )
    except Exception as e:
        return DependencyHealth(
            name="disk",
            status="degraded",
            message=str(e),
        )


async def check_memory() -> DependencyHealth:
    """Check available memory."""
    try:
        import psutil

        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        used_percent = memory.percent

        if used_percent > 95:
            status = "down"
            message = f"Critical: {used_percent}% memory used"
        elif used_percent > 85:
            status = "degraded"
            message = f"Warning: {used_percent}% memory used"
        else:
            status = "up"
            message = None

        return DependencyHealth(
            name="memory",
            status=status,
            message=message,
            details={
                "available_gb": round(available_gb, 2),
                "used_percent": round(used_percent, 1),
            },
        )
    except Exception as e:
        return DependencyHealth(
            name="memory",
            status="degraded",
            message=str(e),
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/live", response_model=HealthStatus)
async def liveness_probe():
    """Liveness probe - is the application running?

    Returns 200 if the process is alive.
    Used by Kubernetes to determine if the container should be restarted.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(get_uptime(), 2),
    )


@router.get("/ready", response_model=HealthStatus)
async def readiness_probe(response: Response):
    """Readiness probe - can the application serve traffic?

    Returns 200 if ready to accept requests, 503 otherwise.
    Used by Kubernetes to determine if traffic should be routed to this pod.
    """
    # Check critical dependencies concurrently
    db_health, ollama_health = await asyncio.gather(
        check_database(),
        check_ollama(),
    )

    # Determine overall status
    critical_deps = [db_health, ollama_health]
    all_up = all(d.status == "up" for d in critical_deps)

    if all_up:
        status_str = "healthy"
    else:
        status_str = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthStatus(
        status=status_str,
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(get_uptime(), 2),
    )


@router.get("/startup", response_model=HealthStatus)
async def startup_probe(response: Response):
    """Startup probe - has the application finished initializing?

    Returns 200 if startup is complete, 503 otherwise.
    Used by Kubernetes during initial startup.
    """
    if _startup_complete:
        return HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=round(get_uptime(), 2),
        )
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(
            status="starting",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=round(get_uptime(), 2),
        )


@router.get("/full", response_model=FullHealthResponse)
async def full_health_check(response: Response):
    """Full health check with all dependencies.

    Returns detailed status of all system components.
    Use for debugging and monitoring dashboards.
    """
    # Check all dependencies concurrently
    checks = await asyncio.gather(
        check_database(),
        check_ollama(),
        check_redis(),
        check_disk_space(),
        check_memory(),
        return_exceptions=True,
    )

    # Process results
    dependencies = []
    for check in checks:
        if isinstance(check, Exception):
            dependencies.append(
                DependencyHealth(
                    name="unknown",
                    status="down",
                    message=str(check),
                )
            )
        else:
            dependencies.append(check)

    # Determine overall status
    statuses = [d.status for d in dependencies]
    if all(s == "up" for s in statuses):
        overall = "healthy"
    elif any(s == "down" for s in statuses):
        overall = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall = "degraded"

    return FullHealthResponse(
        status=overall,
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.3",
        uptime_seconds=round(get_uptime(), 2),
        dependencies=dependencies,
    )


@router.get("/", response_model=HealthStatus)
async def health_check():
    """Simple health check (alias for /live)."""
    return await liveness_probe()


# =============================================================================
# Data Sources Health Check
# =============================================================================


async def check_sirene_api() -> DependencyHealth:
    """Check INSEE SIRENE API availability."""
    start = time.time()
    try:
        import httpx

        # Test SIRENE API with a simple count query
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.insee.fr/api-sirene/3.11/siren",
                params={"q": "siren:552032534", "nombre": 1},
                headers={"Accept": "application/json"},
            )
            # 401 is expected without auth, but means API is reachable
            if response.status_code in (200, 401, 403):
                latency = (time.time() - start) * 1000
                return DependencyHealth(
                    name="SIRENE (INSEE)",
                    status="up",
                    latency_ms=round(latency, 2),
                    details={"endpoint": "api.insee.fr"},
                )

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="SIRENE (INSEE)",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="SIRENE (INSEE)",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e)[:100],
        )


async def check_dvf_api() -> DependencyHealth:
    """Check DVF (Demandes de Valeurs Foncieres) API."""
    start = time.time()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.cquest.org/dvf",
                params={"code_postal": "75001", "nature_mutation": "Vente"},
            )
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                data = response.json()
                return DependencyHealth(
                    name="DVF (Immobilier)",
                    status="up",
                    latency_ms=round(latency, 2),
                    details={"records_sample": len(data.get("resultats", []))},
                )

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="DVF (Immobilier)",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="DVF (Immobilier)",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e)[:100],
        )


async def check_ban_api() -> DependencyHealth:
    """Check Base Adresse Nationale API."""
    start = time.time()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api-adresse.data.gouv.fr/search/",
                params={"q": "1 rue de la paix paris", "limit": 1},
            )
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                return DependencyHealth(
                    name="BAN (Geocodage)",
                    status="up",
                    latency_ms=round(latency, 2),
                    details={"endpoint": "api-adresse.data.gouv.fr"},
                )

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="BAN (Geocodage)",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="BAN (Geocodage)",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e)[:100],
        )


async def check_france_travail_api() -> DependencyHealth:
    """Check France Travail API availability."""
    start = time.time()
    try:
        import httpx

        # Test the public endpoint
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.francetravail.io/partenaire/infotravail/v1/metiers",
                headers={"Accept": "application/json"},
            )
            # 401 expected without auth, but API is reachable
            if response.status_code in (200, 401, 403):
                latency = (time.time() - start) * 1000
                return DependencyHealth(
                    name="France Travail",
                    status="up",
                    latency_ms=round(latency, 2),
                    details={"endpoint": "api.francetravail.io"},
                )

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="France Travail",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="France Travail",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e)[:100],
        )


async def check_ofgl_api() -> DependencyHealth:
    """Check OFGL (Finances Locales) API."""
    start = time.time()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets",
                params={"limit": 1},
            )
            if response.status_code == 200:
                latency = (time.time() - start) * 1000
                return DependencyHealth(
                    name="OFGL (Finances)",
                    status="up",
                    latency_ms=round(latency, 2),
                    details={"endpoint": "data.ofgl.fr"},
                )

        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="OFGL (Finances)",
            status="degraded",
            latency_ms=round(latency, 2),
            message=f"HTTP {response.status_code}",
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="OFGL (Finances)",
            status="down",
            latency_ms=round(latency, 2),
            message=str(e)[:100],
        )


class SourcesHealthResponse(BaseModel):
    """Data sources health response."""

    status: str
    timestamp: str
    sources: list[DependencyHealth]
    online_count: int
    total_count: int


@router.get("/sources", response_model=SourcesHealthResponse)
async def data_sources_health(response: Response):
    """Check health of all external data source APIs.

    Tests connectivity and latency to:
    - SIRENE (INSEE enterprise database)
    - DVF (Real estate transactions)
    - BAN (Address geocoding)
    - France Travail (Employment data)
    - OFGL (Local finances)
    """
    # Check all sources concurrently
    checks = await asyncio.gather(
        check_sirene_api(),
        check_dvf_api(),
        check_ban_api(),
        check_france_travail_api(),
        check_ofgl_api(),
        return_exceptions=True,
    )

    # Process results
    sources = []
    for check in checks:
        if isinstance(check, Exception):
            sources.append(
                DependencyHealth(
                    name="unknown",
                    status="down",
                    message=str(check)[:100],
                )
            )
        else:
            sources.append(check)

    # Count online sources
    online_count = sum(1 for s in sources if s.status == "up")
    total_count = len(sources)

    # Determine overall status
    if online_count == total_count:
        overall = "healthy"
    elif online_count == 0:
        overall = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall = "degraded"

    return SourcesHealthResponse(
        status=overall,
        timestamp=datetime.utcnow().isoformat(),
        sources=sources,
        online_count=online_count,
        total_count=total_count,
    )
