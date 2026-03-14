"""
OpenManus Core API - FastAPI Application
Version: 2.0
Date: 2025-11-19

API principale pour OpenManus Intelligence Platform.
Gère l'orchestration des agents, les tâches, et la coordination.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

# Configure logging
logging.basicConfig(level=logging.INFO)

# ============================
# Models
# ============================


class TaskAction(StrEnum):
    """Actions disponibles pour les tâches."""

    NAVIGATE = "navigate"
    EXTRACT = "extract"
    FILL_FORM = "fill_form"
    CLICK = "click"
    SCREENSHOT = "screenshot"
    CUSTOM = "custom"


class TaskStatus(StrEnum):
    """Status des tâches."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(StrEnum):
    """Types d'agents disponibles."""

    BROWSER_USE = "browser_use"
    LAVAGUE = "lavague"
    SKYVERN = "skyvern"
    AGENT_E = "agent_e"
    AUTO = "auto"  # Sélection automatique


class TaskRequest(BaseModel):
    """Requête pour créer une tâche."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "command": "Va sur Amazon et trouve le prix du livre 'Python Deep Learning'",
                    "agent": "auto",
                },
                {
                    "url": "https://example.com",
                    "action": "extract",
                    "data": {"selectors": {"title": "h1", "content": ".main-content"}},
                },
            ]
        }
    )

    # Commande en langage naturel (recommandé)
    command: str | None = Field(
        None,
        description="Commande en langage naturel (ex: 'Va sur Amazon et trouve le prix du livre X')",
    )

    # OU configuration manuelle
    url: str | None = Field(None, description="URL cible")
    action: TaskAction | None = Field(None, description="Action à effectuer")

    # Configuration agent
    agent: AgentType = Field(
        AgentType.AUTO, description="Agent à utiliser (auto = sélection automatique)"
    )

    # Données additionnelles
    data: dict[str, Any] | None = Field(
        None, description="Données pour l'action (selecteurs, valeurs de formulaire, etc.)"
    )

    # Options
    timeout: int = Field(300, description="Timeout en secondes")
    wait_for_completion: bool = Field(False, description="Attendre la fin de la tâche")
    cleanup_vm: bool = Field(True, description="Nettoyer la VM après exécution")


class TaskResponse(BaseModel):
    """Réponse pour une tâche."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task-123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "agent_used": "browser_use",
                "created_at": "2025-11-19T10:00:00Z",
                "updated_at": "2025-11-19T10:00:15Z",
                "result": {
                    "success": True,
                    "data": {"price": "$45.99"},
                    "screenshot": "base64_encoded_image",
                },
            }
        }
    )

    task_id: str
    status: TaskStatus
    agent_used: str | None = None
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Réponse du health check."""

    status: str
    version: str
    timestamp: datetime
    services: dict[str, str]
    active_tasks: int


# ============================
# In-Memory Storage (à remplacer par Redis/DB)
# ============================


class TaskStore:
    """Store temporaire pour les tâches (à remplacer par Redis)."""

    def __init__(self):
        self.tasks: dict[str, dict[str, Any]] = {}

    def create_task(self, task_data: dict[str, Any]) -> str:
        """Crée une nouvelle tâche."""
        task_id = f"task-{uuid.uuid4()}"
        self.tasks[task_id] = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            **task_data,
        }
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Récupère une tâche."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, updates: dict[str, Any]):
        """Met à jour une tâche."""
        if task_id in self.tasks:
            self.tasks[task_id].update(updates)
            self.tasks[task_id]["updated_at"] = datetime.now()

    def list_tasks(self, status: TaskStatus | None = None) -> list[dict[str, Any]]:
        """Liste les tâches."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        return sorted(tasks, key=lambda x: x["created_at"], reverse=True)

    def get_active_tasks_count(self) -> int:
        """Compte les tâches actives."""
        return len(
            [
                t
                for t in self.tasks.values()
                if t["status"] in [TaskStatus.PENDING, TaskStatus.RUNNING]
            ]
        )


# Global task store
task_store = TaskStore()


# ============================
# FastAPI Application
# ============================

app = FastAPI(
    title="OpenManus Intelligence Platform API",
    description="API pour l'automatisation web intelligente avec multi-agents",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Server start time for uptime tracking
_server_start_time: datetime | None = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production: spécifier les origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================
# Task Execution (placeholder)
# ============================


async def execute_task_async(task_id: str, task_request: TaskRequest):
    """
    Exécute une tâche de manière asynchrone.
    TODO: Intégrer les vrais agents ici.
    """
    try:
        # Update status to running
        task_store.update_task(
            task_id, {"status": TaskStatus.RUNNING, "agent_used": task_request.agent.value}
        )

        logger.info(f"Démarrage de la tâche {task_id}")

        # Simuler l'exécution (à remplacer par vraie logique)
        await asyncio.sleep(2)

        # Mock result
        result = {
            "success": True,
            "message": "Tâche exécutée avec succès (mock)",
            "data": {
                "url": task_request.url or "N/A",
                "action": task_request.action.value if task_request.action else "N/A",
                "command": task_request.command or "N/A",
            },
        }

        # Update with success
        task_store.update_task(task_id, {"status": TaskStatus.COMPLETED, "result": result})

        logger.info(f"Tâche {task_id} terminée avec succès")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche {task_id}: {e}")
        task_store.update_task(task_id, {"status": TaskStatus.FAILED, "error": str(e)})


# ============================
# API Endpoints
# ============================


@app.get("/", response_model=dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "name": "OpenManus Intelligence Platform API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.now(),
        services={
            "api": "operational",
            "task_queue": "operational",
            "browser_pool": "operational",
            "storage": "operational",
        },
        active_tasks=task_store.get_active_tasks_count(),
    )


@app.post("/api/v1/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """
    Crée une nouvelle tâche d'automatisation.

    Deux modes d'utilisation:
    1. **Langage naturel** (recommandé): Utilisez `command`
       - Exemple: "Va sur Amazon et trouve le prix du livre X"

    2. **Configuration manuelle**: Utilisez `url` + `action` + `data`
       - Exemple: url="https://example.com", action="extract", data={...}
    """

    # Validation
    if not task_request.command and not task_request.url:
        raise HTTPException(
            status_code=400, detail="Vous devez fournir soit 'command' (langage naturel) soit 'url'"
        )

    # Créer la tâche
    task_data = {
        "command": task_request.command,
        "url": task_request.url,
        "action": task_request.action.value if task_request.action else None,
        "agent": task_request.agent.value,
        "data": task_request.data,
        "timeout": task_request.timeout,
    }

    task_id = task_store.create_task(task_data)

    # Lancer l'exécution en arrière-plan
    background_tasks.add_task(execute_task_async, task_id, task_request)

    # Retourner la tâche créée
    task = task_store.get_task(task_id)

    return TaskResponse(
        task_id=task["task_id"],
        status=task["status"],
        agent_used=task.get("agent_used"),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        result=task.get("result"),
        error=task.get("error"),
    )


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Récupère le status d'une tâche."""
    task = task_store.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    return TaskResponse(
        task_id=task["task_id"],
        status=task["status"],
        agent_used=task.get("agent_used"),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
        result=task.get("result"),
        error=task.get("error"),
    )


@app.get("/api/v1/tasks", response_model=list[TaskResponse])
async def list_tasks(status: TaskStatus | None = None, limit: int = 50):
    """Liste les tâches."""
    tasks = task_store.list_tasks(status)[:limit]

    return [
        TaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            agent_used=task.get("agent_used"),
            created_at=task["created_at"],
            updated_at=task["updated_at"],
            result=task.get("result"),
            error=task.get("error"),
        )
        for task in tasks
    ]


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Annule une tâche en cours."""
    task = task_store.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible d'annuler une tâche avec le status: {task['status']}",
        )

    task_store.update_task(task_id, {"status": TaskStatus.CANCELLED})

    return {"message": "Tâche annulée", "task_id": task_id}


@app.get("/api/v1/agents")
async def list_agents():
    """Liste les agents disponibles."""
    return {
        "agents": [
            {
                "id": "browser_use",
                "name": "Browser-Use",
                "description": "LLM-guided browsing, bon pour tâches conversationnelles",
                "status": "available",
                "best_for": ["exploration", "chat-like tasks"],
            },
            {
                "id": "lavague",
                "name": "LaVague",
                "description": "Large Action Model, excellent pour workflows complexes",
                "status": "planned",
                "best_for": ["multi-step workflows", "automation"],
            },
            {
                "id": "skyvern",
                "name": "Skyvern",
                "description": "Vision + LLM, s'adapte aux sites dynamiques",
                "status": "planned",
                "best_for": ["dynamic sites", "SPAs", "vision-based"],
            },
            {
                "id": "agent_e",
                "name": "Agent-E",
                "description": "Expert DOM, précis pour les formulaires",
                "status": "planned",
                "best_for": ["forms", "precise clicks"],
            },
        ]
    }


@app.get("/api/v1/stats")
async def get_stats():
    """Statistiques de la plateforme."""
    tasks = task_store.list_tasks()

    total_tasks = len(tasks)
    completed = len([t for t in tasks if t["status"] == TaskStatus.COMPLETED])
    failed = len([t for t in tasks if t["status"] == TaskStatus.FAILED])
    active = task_store.get_active_tasks_count()

    return {
        "total_tasks": total_tasks,
        "active_tasks": active,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "success_rate": (completed / total_tasks * 100) if total_tasks > 0 else 0,
        "uptime_seconds": int((datetime.now() - _server_start_time).total_seconds())
        if _server_start_time
        else 0,
    }


# ============================
# Startup/Shutdown
# ============================


@app.on_event("startup")
async def startup_event():
    """Événement de démarrage."""
    global _server_start_time
    _server_start_time = datetime.now()
    logger.info("🚀 OpenManus Core API démarrée")
    logger.info("📖 Documentation: http://localhost:8085/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt."""
    logger.info("🛑 OpenManus Core API arrêtée")


# ============================
# Main (pour exécution directe)
# ============================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_core:app", host="0.0.0.0", port=8085, reload=True, log_level="info")
