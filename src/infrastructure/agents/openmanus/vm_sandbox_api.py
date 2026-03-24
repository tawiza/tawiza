"""API REST pour VM Sandbox Manager.

Cette API fournit des endpoints pour gérer les machines virtuelles sandbox,
la surveillance, et l'exécution de tâches automatisées.
"""

import asyncio
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.infrastructure.agents.openmanus.vm_sandbox_adapter import VMSandboxAdapter


# Modèles Pydantic
class VMConfig(BaseModel):
    """Configuration VM."""

    provider: str = Field(default="docker", description="Fournisseur VM")
    memory: str = Field(default="2g", description="Mémoire VM")
    cpus: int = Field(default=2, description="Nombre de CPUs")
    disk_size: str = Field(default="20g", description="Taille disque")
    image: str = Field(default="ubuntu:22.04", description="Image Docker")
    timeout: int = Field(default=3600, description="Timeout en secondes")


class AutomationTask(BaseModel):
    """Tâche d'automation."""

    url: str = Field(..., description="URL cible")
    action: str = Field(..., description="Action à effectuer")
    selectors: dict[str, str] | None = Field(default=None, description="Sélecteurs CSS")
    data: dict[str, Any] | None = Field(default=None, description="Données pour l'action")
    options: dict[str, Any] | None = Field(default=None, description="Options supplémentaires")


class TaskRequest(BaseModel):
    """Requête d'exécution de tâche."""

    vm_config: VMConfig = Field(..., description="Configuration VM")
    automation_task: AutomationTask = Field(..., description="Tâche automation")
    cleanup_vm: bool = Field(default=True, description="Nettoyer VM après exécution")
    timeout: int | None = Field(default=None, description="Timeout personnalisé")


class TaskResponse(BaseModel):
    """Réponse d'exécution de tâche."""

    task_id: str
    vm_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    execution_time: float | None = None


class VMStatus(BaseModel):
    """Statut VM."""

    vm_id: str
    task_id: str
    status: str
    created_at: str
    uptime: float
    config: dict[str, Any]
    runtime_status: dict[str, Any]


class VMSandboxAPI:
    """API REST pour VM Sandbox Manager."""

    def __init__(self, adapter: VMSandboxAdapter):
        """Initialise l'API.

        Args:
            adapter: Adaptateur VM Sandbox
        """
        self.adapter = adapter
        self.app = FastAPI(
            title="VM Sandbox API",
            description="API pour gérer les machines virtuelles sandbox et l'exécution de tâches",
            version="1.0.0",
        )

        # Configuration CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()

        logger.info("VM Sandbox API initialisée")

    def _setup_routes(self) -> None:
        """Configure les routes API."""

        @self.app.get("/health")
        async def health_check():
            """Vérifie la santé du service."""
            try:
                # Vérifier Docker
                import docker

                client = docker.from_env()
                client.ping()

                # Vérifier l'adaptateur
                vm_count = len(self.adapter.active_vms)

                return {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "active_vms": vm_count,
                    "max_vms": self.adapter.max_vms,
                    "provider": self.adapter.vm_provider,
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

        @self.app.get("/vms", response_model=list[VMStatus])
        async def list_vms():
            """Liste toutes les VMs actives."""
            try:
                vm_statuses = []

                for vm_id in self.adapter.active_vms:
                    try:
                        status = await self.adapter.get_vm_status(vm_id)
                        vm_statuses.append(VMStatus(**status))
                    except Exception as e:
                        logger.warning(f"Erreur obtention statut VM {vm_id}: {e}")

                return vm_statuses

            except Exception as e:
                logger.error(f"Erreur liste VMs: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur liste VMs: {e}")

        @self.app.post("/vms", response_model=dict[str, Any])
        async def create_vm(config: VMConfig):
            """Crée une nouvelle VM."""
            try:
                # Générer un ID de tâche temporaire
                task_id = f"api-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Créer la VM
                vm_id = await self.adapter.create_vm(task_id, config.dict())

                return {
                    "vm_id": vm_id,
                    "task_id": task_id,
                    "status": "created",
                    "created_at": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Erreur création VM: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur création VM: {e}")

        @self.app.get("/vms/{vm_id}", response_model=VMStatus)
        async def get_vm_status(vm_id: str):
            """Obtient le statut d'une VM."""
            try:
                status = await self.adapter.get_vm_status(vm_id)
                return VMStatus(**status)
            except Exception as e:
                logger.error(f"Erreur obtention statut VM {vm_id}: {e}")
                raise HTTPException(status_code=404, detail=f"VM non trouvée: {e}")

        @self.app.delete("/vms/{vm_id}")
        async def destroy_vm(vm_id: str, background_tasks: BackgroundTasks):
            """Détruit une VM."""
            try:
                # Planifier la destruction en arrière-plan
                background_tasks.add_task(self.adapter.destroy_vm, vm_id)

                return {
                    "vm_id": vm_id,
                    "status": "destruction_scheduled",
                    "message": "Destruction de la VM planifiée",
                }

            except Exception as e:
                logger.error(f"Erreur destruction VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur destruction VM: {e}")

        @self.app.post("/tasks", response_model=TaskResponse)
        async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks):
            """Exécute une tâche dans une VM sandbox."""
            try:
                # Créer la configuration complète de la tâche
                task_config = {
                    "vm_config": request.vm_config.dict(),
                    "automation_task": request.automation_task.dict(),
                    "cleanup_vm": request.cleanup_vm,
                    "timeout": request.timeout,
                }

                # Planifier l'exécution en arrière-plan
                task_result = await self.adapter.execute_task(task_config)

                return TaskResponse(
                    task_id=task_result["task_id"],
                    vm_id=task_result.get("vm_id", "unknown"),
                    status=task_result["status"],
                    result=task_result.get("result"),
                    error=task_result.get("error"),
                    created_at=datetime.fromisoformat(task_result["created_at"]),
                    execution_time=task_result.get("execution_time"),
                )

            except Exception as e:
                logger.error(f"Erreur exécution tâche: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur exécution tâche: {e}")

        @self.app.get("/tasks/{task_id}")
        async def get_task_status(task_id: str):
            """Obtient le statut d'une tâche."""
            try:
                # Récupérer depuis l'adaptateur
                task_info = self.adapter.get_task(task_id)

                if not task_info:
                    raise HTTPException(status_code=404, detail="Tâche non trouvée")

                return {
                    "task_id": task_id,
                    "status": task_info.get("status"),
                    "result": task_info.get("result"),
                    "error": task_info.get("error"),
                    "created_at": task_info.get("created_at"),
                    "logs": task_info.get("logs", []),
                    "screenshots": task_info.get("screenshots", []),
                }

            except Exception as e:
                logger.error(f"Erreur obtention tâche {task_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur obtention tâche: {e}")

        @self.app.post("/vms/{vm_id}/execute")
        async def execute_in_vm(vm_id: str, task: AutomationTask):
            """Exécute une tâche dans une VM existante."""
            try:
                result = await self.adapter.execute_in_vm(vm_id, task.dict())

                return {
                    "vm_id": vm_id,
                    "status": "success",
                    "result": result,
                    "executed_at": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Erreur exécution dans VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur exécution VM: {e}")

        @self.app.get("/vms/{vm_id}/screenshots")
        async def get_vm_screenshots(vm_id: str):
            """Obtient les screenshots d'une VM."""
            try:
                # Capturer des screenshots
                screenshots = await self.adapter._capture_vm_screenshots(vm_id)

                return {
                    "vm_id": vm_id,
                    "screenshots": screenshots,
                    "captured_at": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Erreur capture screenshots VM {vm_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur capture screenshots: {e}")

        @self.app.get("/vms/{vm_id}/screenshots/{screenshot_id}")
        async def download_screenshot(vm_id: str, screenshot_id: str):
            """Télécharge un screenshot."""
            try:
                # Construire le chemin du screenshot
                screenshot_path = f"/tmp/{vm_id}_{screenshot_id}.png"

                if not Path(screenshot_path).exists():
                    raise HTTPException(status_code=404, detail="Screenshot non trouvé")

                return FileResponse(
                    screenshot_path, media_type="image/png", filename=f"{vm_id}_{screenshot_id}.png"
                )

            except Exception as e:
                logger.error(f"Erreur téléchargement screenshot {screenshot_id}: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Erreur téléchargement screenshot: {e}"
                )

        @self.app.post("/cleanup")
        async def cleanup_vms(background_tasks: BackgroundTasks):
            """Nettoie les VMs expirées."""
            try:
                # Planifier le nettoyage en arrière-plan
                background_tasks.add_task(self.adapter.cleanup_expired_vms)

                return {
                    "status": "cleanup_scheduled",
                    "message": "Nettoyage des VMs expirées planifié",
                }

            except Exception as e:
                logger.error(f"Erreur nettoyage VMs: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur nettoyage VMs: {e}")

        @self.app.get("/metrics")
        async def get_metrics():
            """Obtient les métriques du service."""
            try:
                metrics = {
                    "active_vms": len(self.adapter.active_vms),
                    "max_vms": self.adapter.max_vms,
                    "provider": self.adapter.vm_provider,
                    "uptime": (
                        datetime.now()
                        - datetime.fromtimestamp(
                            self.adapter._start_time
                            if hasattr(self.adapter, "_start_time")
                            else datetime.now().timestamp()
                        )
                    ).total_seconds()
                    if hasattr(self.adapter, "_start_time")
                    else 0,
                }

                # Ajouter des métriques détaillées
                vm_status_counts = {}
                for vm_info in self.adapter.active_vms.values():
                    status = vm_info.get("status", "unknown")
                    vm_status_counts[status] = vm_status_counts.get(status, 0) + 1

                metrics["vm_status_counts"] = vm_status_counts

                return metrics

            except Exception as e:
                logger.error(f"Erreur obtention métriques: {e}")
                raise HTTPException(status_code=500, detail=f"Erreur obtention métriques: {e}")

        @self.app.get("/config")
        async def get_config():
            """Obtient la configuration actuelle."""
            return {
                "provider": self.adapter.vm_provider,
                "max_vms": self.adapter.max_vms,
                "vm_timeout": self.adapter.vm_timeout,
                "vm_image_path": str(self.adapter.vm_image_path),
                "vm_storage_path": str(self.adapter.vm_storage_path),
                "headless": self.adapter.headless,
            }

    async def start(self, host: str = "0.0.0.0", port: int = 8085) -> None:
        """Démarre l'API.

        Args:
            host: Hôte d'écoute
            port: Port d'écoute
        """
        import uvicorn

        logger.info(f"Démarrage VM Sandbox API sur {host}:{port}")

        # Stocker le temps de démarrage pour les métriques
        self.adapter._start_time = datetime.now().timestamp()

        # Démarrer le serveur
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)

        # Démarrer dans une tâche
        self.server_task = asyncio.create_task(server.serve())

        logger.info("VM Sandbox API démarrée")

    async def stop(self) -> None:
        """Arrête l'API."""
        logger.info("Arrêt VM Sandbox API")

        if hasattr(self, "server_task"):
            self.server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.server_task

        logger.info("VM Sandbox API arrêtée")


# Configuration de test
if __name__ == "__main__":
    import asyncio

    async def test_api():
        """Test l'API."""
        # Créer un adaptateur factice pour le test
        from unittest.mock import Mock

        mock_adapter = Mock()
        mock_adapter.active_vms = {}
        mock_adapter.max_vms = 5
        mock_adapter.vm_provider = "docker"
        mock_adapter.vm_timeout = 3600
        mock_adapter.vm_image_path = Path("/tmp/vm-images")
        mock_adapter.vm_storage_path = Path("/tmp/vm-storage")
        mock_adapter.headless = True

        # Créer l'API
        api = VMSandboxAPI(mock_adapter)

        # Démarrer l'API
        await api.start(host="127.0.0.1", port=8085)

        # Attendre un peu
        await asyncio.sleep(2)

        # Arrêter l'API
        await api.stop()

    asyncio.run(test_api())
