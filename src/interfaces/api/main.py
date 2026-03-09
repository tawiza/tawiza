"""Tawiza v2 API - FastAPI Backend."""

import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from loguru import logger
from src.core.telemetry import capture_startup, shutdown as telemetry_shutdown
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

# Monitoring & error handling middlewares
from src.infrastructure.monitoring.middleware import PrometheusMiddleware
from src.interfaces.api.middleware.error_handler import (
    ErrorHandlerMiddleware,
    register_exception_handlers,
)
from src.interfaces.api.middleware.request_id import RequestIDMiddleware

# Sentry error tracking (optional)
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "development"),
        )
        logger.info("Sentry error tracking initialized")
except ImportError:
    pass  # sentry-sdk not installed

# Import AgentOrchestrator
# Rate limiting with slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.application.services.agent_orchestrator import initialize_orchestrator

# Import Crawler Scheduler
from src.application.services.crawler_scheduler import get_crawler_scheduler

# Import TAJINE Scheduler
from src.application.services.tajine_scheduler import get_tajine_scheduler

# Collector micro-signals
from src.collector.api import router as collector_router

# Import Collector Scheduler (micro-signals)
from src.collector.scheduler.jobs import CollectorScheduler
from src.interfaces.api.routers.annotations import router as annotations_router
from src.interfaces.api.routers.browser import router as browser_router
from src.interfaces.api.routers.fine_tuning import router as fine_tuning_router
from src.interfaces.api.v1.agents.routes import router as agents_router
from src.interfaces.api.v1.alerts.routes import router as alerts_router
from src.interfaces.api.v1.auth.routes import router as auth_router
from src.interfaces.api.v1.conversations.routes import router as conversations_router
from src.interfaces.api.v1.crawler.routes import router as crawler_router
from src.interfaces.api.v1.export.routes import router as export_router
from src.interfaces.api.v1.health.routes import router as health_router
from src.interfaces.api.v1.ollama.routes import router as ollama_router

# Import routers
from src.interfaces.api.v1.openai_compatible.routes import router as openai_router
from src.interfaces.api.v1.orchestration.routes import router as orchestration_router
from src.interfaces.api.v1.schedules.routes import router as schedules_router
from src.interfaces.api.v1.sources.routes import router as sources_router
from src.interfaces.api.v1.tajine.routes import router as tajine_router
from src.interfaces.api.v1.territorial.routes import router as territorial_router
from src.interfaces.api.v1.watcher.routes import router as watcher_router
from src.interfaces.api.websocket.handlers import setup_handlers

# Import WebSocket components
from src.interfaces.api.websocket.server import WebSocketManager, get_ws_manager

# Global WebSocket manager
_ws_manager: WebSocketManager = None
_tajine_scheduler = None
_crawler_scheduler = None
_collector_scheduler: CollectorScheduler | None = None
_news_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _ws_manager
    # Configure structured logging
    from src.core.logging_config import configure_logging

    app_env = os.getenv("APP_ENV", "development")
    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_logs=(app_env == "production"),
    )

    # Startup
    logger.info("Tawiza v2 API starting...")
    capture_startup()
    logger.info("Initializing OpenAI-compatible endpoints for LobeChat integration")

    # Initialize database
    from src.infrastructure.persistence.database import close_db, init_db

    try:
        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    # Initialize AgentOrchestrator with all agents
    logger.info("Initializing AgentOrchestrator...")
    orchestrator = await initialize_orchestrator()
    logger.info(f"AgentOrchestrator ready with {len(orchestrator._real_agents)} agents")

    # Initialize WebSocket
    _ws_manager = get_ws_manager()
    setup_handlers(_ws_manager)
    await _ws_manager.start_metrics_broadcast(interval=5.0)
    logger.info("WebSocket server initialized on /ws")

    # Initialize TAJINE Scheduler
    global _tajine_scheduler
    _tajine_scheduler = get_tajine_scheduler()
    try:
        await _tajine_scheduler.start()
        logger.info("TAJINE Scheduler initialized")
    except Exception as e:
        logger.warning(f"TAJINE Scheduler initialization skipped: {e}")

    # Initialize Crawler Scheduler
    global _crawler_scheduler
    _crawler_scheduler = get_crawler_scheduler()
    try:
        await _crawler_scheduler.start()
        logger.info("Crawler Scheduler initialized")
    except Exception as e:
        logger.warning(f"Crawler Scheduler initialization skipped: {e}")

    # Initialize Collector Scheduler (micro-signals pipeline)
    global _collector_scheduler
    _collector_scheduler = CollectorScheduler()
    try:
        await _collector_scheduler.start()
        logger.info("Collector Scheduler initialized (micro-signals)")
    except Exception as e:
        logger.warning(f"Collector Scheduler initialization skipped: {e}")

    # Initialize News Intelligence Scheduler (sync + enrich + focal points + alerts)
    global _news_scheduler
    try:
        from src.application.services.news_scheduler import news_scheduler

        _news_scheduler = news_scheduler
        await _news_scheduler.start()
        logger.info("News Intelligence Scheduler initialized (6h interval)")
    except Exception as e:
        logger.warning(f"News Intelligence Scheduler initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Tawiza v2 API shutting down...")
    telemetry_shutdown()
    if _ws_manager:
        await _ws_manager.stop_metrics_broadcast()

    # Stop TAJINE Scheduler
    if _tajine_scheduler:
        await _tajine_scheduler.stop()

    # Stop Crawler Scheduler
    if _crawler_scheduler:
        await _crawler_scheduler.stop()

    # Stop Collector Scheduler
    if _collector_scheduler:
        await _collector_scheduler.stop()

    # Stop News Intelligence Scheduler
    if _news_scheduler:
        _news_scheduler.stop()

    # Close relation services connection pool
    from src.application.services._db_pool import close_pool

    with suppress(Exception):
        await close_pool()

    # Close database
    with suppress(Exception):
        await close_db()


app = FastAPI(
    title="Tawiza API",
    description="API for Tawiza Territorial Intelligence Platform with OpenAI-compatible endpoints",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware - configure via CORS_ORIGINS env var (comma-separated)
_default_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]
_env_origins = os.getenv("CORS_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monitoring & error handling middlewares (LIFO: last added = first executed)
app.add_middleware(PrometheusMiddleware)  # 3rd: measures request duration
app.add_middleware(ErrorHandlerMiddleware)  # 2nd: catches unhandled exceptions
app.add_middleware(RequestIDMiddleware)  # 1st: generates X-Request-ID

# Register FastAPI exception handlers
register_exception_handlers(app)

# Rate limiting with slowapi
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(openai_router)  # OpenAI-compatible endpoints (/v1/chat/completions, etc.)
app.include_router(agents_router)  # Tawiza-specific agent endpoints
app.include_router(orchestration_router)  # Pipeline orchestration endpoints
app.include_router(watcher_router)  # Watcher daemon and alerts
app.include_router(tajine_router)  # TAJINE meta-agent
app.include_router(auth_router, prefix="/api/v1")  # Authentication
app.include_router(conversations_router, prefix="/api/v1")  # Conversations
app.include_router(schedules_router, prefix="/api/v1")  # Scheduled Analyses
app.include_router(territorial_router)  # Territorial dashboard widgets
app.include_router(sources_router)  # Data sources health and monitoring
app.include_router(annotations_router, prefix="/api/v1/annotations", tags=["Annotations"])
app.include_router(browser_router, prefix="/api/v1/browser", tags=["Browser Automation"])
app.include_router(fine_tuning_router, prefix="/api/v1/fine-tuning", tags=["Fine-Tuning"])
app.include_router(health_router)  # Detailed health checks
app.include_router(ollama_router)  # Ollama model management
app.include_router(crawler_router)  # Crawler configuration
app.include_router(alerts_router)  # Territorial alerts
app.include_router(export_router)  # PDF/Markdown export
app.include_router(collector_router)  # Micro-signals collector

# Signals V2 API (signals + micro-signals from tawiza DB)
from src.interfaces.api.v1.signals import router as signals_v2_router

app.include_router(signals_v2_router, prefix="/api/v1/signals", tags=["Signals V2"])

# New V2 APIs: crawler management, investigation, microsignals management
from src.interfaces.api.v1.crawler_v2 import router as crawler_v2_router
from src.interfaces.api.v1.investigation import router as investigation_v2_router
from src.interfaces.api.v1.microsignals import router as microsignals_v2_router
from src.interfaces.api.v1.relations import router as relations_router
from src.interfaces.api.v1.training import router as training_v2_router

app.include_router(crawler_v2_router, tags=["Crawler V2"])

# CrawlIntel - Common Crawl Intelligence
from src.interfaces.api.v1.crawler.commoncrawl_routes import router as commoncrawl_router

app.include_router(commoncrawl_router, prefix="/api/v1/crawler", tags=["CrawlIntel"])
app.include_router(investigation_v2_router, tags=["Investigation"])
app.include_router(microsignals_v2_router, tags=["Micro-Signals Management"])
app.include_router(training_v2_router, tags=["Training Data"])
app.include_router(relations_router, tags=["Relations"])

# Decisions & Stakeholders
from src.interfaces.api.v1.decisions.routes import router as decisions_router

app.include_router(decisions_router)

# Frontend error reporting
from src.interfaces.api.v1.errors.routes import router as errors_router

app.include_router(errors_router)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    """Root endpoint."""
    return {
        "name": "Tawiza v2 API",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request):
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/evaluations")
@limiter.limit("60/minute")
async def list_evaluations(request: Request):
    """List all evaluations."""
    return {"evaluations": [], "total": 0}


@app.post("/api/v1/evaluations")
@limiter.limit("60/minute")
async def create_evaluation(request: Request, question: str):
    """Create a new evaluation."""
    return {
        "id": "eval-001",
        "question": question,
        "status": "pending",
    }


@app.get("/api/v1/evaluations/{evaluation_id}")
@limiter.limit("60/minute")
async def get_evaluation(request: Request, evaluation_id: str):
    """Get evaluation details."""
    return {
        "id": evaluation_id,
        "status": "pending",
        "progress": 0,
    }


@app.get("/api/v1/system/status")
@limiter.limit("60/minute")
async def system_status(request: Request):
    """Get system status."""
    import psutil

    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


# ============================================================================
# WebSocket Endpoint for TUI
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str | None = Query(None)):
    """WebSocket endpoint for TUI real-time communication."""
    manager = get_ws_manager()
    origin = websocket.headers.get("origin")
    logger.info(f"WS connect: origin={origin}, session_id={session_id}")
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)


@app.get("/ws/status")
@limiter.limit("60/minute")
async def ws_status(request: Request):
    """WebSocket server status."""
    manager = get_ws_manager()
    return {
        "status": "running",
        "connections": manager.connection_count,
    }
