"""Health check endpoints with detailed service status."""

import asyncio
import os
import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


class ServiceStatus(BaseModel):
    """Status of a single service."""

    name: str
    status: Literal["connected", "degraded", "disconnected", "checking"]
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class DetailedHealth(BaseModel):
    """Detailed health status of all services."""

    overall: Literal["healthy", "degraded", "unhealthy"]
    services: list[ServiceStatus]
    checked_at: str


async def check_backend() -> ServiceStatus:
    """Check backend API (always connected if we're responding)."""
    return ServiceStatus(
        name="backend",
        status="connected",
        latency_ms=0.1,
        message="API responding",
    )


async def check_ollama() -> ServiceStatus:
    """Check Ollama LLM service."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return ServiceStatus(
                    name="ollama",
                    status="connected",
                    latency_ms=round(latency, 1),
                    message=f"{len(models)} models available",
                    details={"models": models[:5], "url": ollama_url},
                )
            else:
                return ServiceStatus(
                    name="ollama",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    message=f"HTTP {resp.status_code}",
                )
    except httpx.TimeoutException:
        return ServiceStatus(
            name="ollama",
            status="disconnected",
            message="Connection timeout",
            details={"url": ollama_url},
        )
    except Exception as e:
        return ServiceStatus(
            name="ollama",
            status="disconnected",
            message=str(e)[:100],
            details={"url": ollama_url},
        )


async def check_neo4j() -> ServiceStatus:
    """Check Neo4j graph database."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")

    try:
        from neo4j import AsyncGraphDatabase

        start = time.time()
        driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "password"),
            ),
        )

        async with driver.session() as session:
            result = await session.run("RETURN 1 as n")
            await result.consume()

        await driver.close()
        latency = (time.time() - start) * 1000

        return ServiceStatus(
            name="neo4j",
            status="connected",
            latency_ms=round(latency, 1),
            message="Graph database ready",
            details={"uri": neo4j_uri},
        )
    except ImportError:
        return ServiceStatus(
            name="neo4j",
            status="disconnected",
            message="neo4j driver not installed",
        )
    except Exception as e:
        return ServiceStatus(
            name="neo4j",
            status="disconnected",
            message=str(e)[:100],
            details={"uri": neo4j_uri},
        )


async def check_postgresql() -> ServiceStatus:
    """Check PostgreSQL database."""
    db_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/tawiza")

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        # Convert to async URL
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(async_url, pool_pre_ping=True)

        start = time.time()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000

        await engine.dispose()

        return ServiceStatus(
            name="postgresql",
            status="connected",
            latency_ms=round(latency, 1),
            message="Database ready",
        )
    except ImportError:
        return ServiceStatus(
            name="postgresql",
            status="disconnected",
            message="asyncpg not installed",
        )
    except Exception as e:
        return ServiceStatus(
            name="postgresql",
            status="disconnected",
            message=str(e)[:100],
        )


async def check_websocket() -> ServiceStatus:
    """Check WebSocket server status."""
    try:
        from src.interfaces.api.websocket.server import get_ws_manager

        manager = get_ws_manager()
        return ServiceStatus(
            name="websocket",
            status="connected",
            latency_ms=0.1,
            message=f"{manager.connection_count} connections",
            details={"connections": manager.connection_count},
        )
    except Exception as e:
        return ServiceStatus(
            name="websocket",
            status="disconnected",
            message=str(e)[:100],
        )


async def check_scheduler() -> ServiceStatus:
    """Check TAJINE scheduler status."""
    try:
        from src.application.services.tajine_scheduler import get_tajine_scheduler

        scheduler = get_tajine_scheduler()
        is_running = scheduler._running if hasattr(scheduler, "_running") else False

        return ServiceStatus(
            name="scheduler",
            status="connected" if is_running else "degraded",
            latency_ms=0.1,
            message="Scheduler active" if is_running else "Scheduler stopped",
        )
    except Exception as e:
        return ServiceStatus(
            name="scheduler",
            status="disconnected",
            message=str(e)[:100],
        )


async def check_telemetry() -> ServiceStatus:
    """Check telemetry/metrics status."""
    # Check if Prometheus metrics are available
    try:
        # Simple check - telemetry is considered active if we can collect metrics
        import psutil

        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent

        return ServiceStatus(
            name="telemetry",
            status="connected",
            latency_ms=0.1,
            message="Metrics collecting",
            details={"cpu_percent": cpu, "memory_percent": memory},
        )
    except Exception as e:
        return ServiceStatus(
            name="telemetry",
            status="degraded",
            message=str(e)[:100],
        )


@router.get("/detailed", response_model=DetailedHealth)
async def get_detailed_health() -> DetailedHealth:
    """Get detailed health status of all services."""
    from datetime import datetime

    # Run all checks concurrently
    results = await asyncio.gather(
        check_backend(),
        check_ollama(),
        check_neo4j(),
        check_postgresql(),
        check_websocket(),
        check_scheduler(),
        check_telemetry(),
        return_exceptions=True,
    )

    # Process results
    services = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Health check failed: {result}")
            services.append(
                ServiceStatus(
                    name="unknown",
                    status="disconnected",
                    message=str(result)[:100],
                )
            )
        else:
            services.append(result)

    # Determine overall status
    statuses = [s.status for s in services]
    if all(s == "connected" for s in statuses):
        overall = "healthy"
    elif any(s == "disconnected" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return DetailedHealth(
        overall=overall,
        services=services,
        checked_at=datetime.now().isoformat(),
    )


@router.get("/services/{service_name}")
async def get_service_health(service_name: str) -> ServiceStatus:
    """Get health status of a specific service."""
    checkers = {
        "backend": check_backend,
        "ollama": check_ollama,
        "neo4j": check_neo4j,
        "postgresql": check_postgresql,
        "websocket": check_websocket,
        "scheduler": check_scheduler,
        "telemetry": check_telemetry,
    }

    if service_name not in checkers:
        return ServiceStatus(
            name=service_name,
            status="disconnected",
            message=f"Unknown service: {service_name}",
        )

    return await checkers[service_name]()
