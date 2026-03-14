"""Fine-tuning API endpoints."""

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.infrastructure.config.settings import get_settings

# Lazy imports pour éviter de charger torch/transformers au démarrage
if TYPE_CHECKING:
    from src.infrastructure.ml.fine_tuning import FineTuningService

router = APIRouter()


@lru_cache
def get_fine_tuning_service() -> "FineTuningService":
    """Lazy-load the fine-tuning service (loads torch/transformers on first call)."""
    from src.infrastructure.ml.fine_tuning import FineTuningService
    from src.infrastructure.storage import MinIOStorageAdapter, ModelVersioningService

    settings = get_settings()

    # Initialize storage services
    try:
        storage_service = MinIOStorageAdapter(
            endpoint=settings.minio.endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            bucket_name=settings.minio.ollama_models_bucket,
            secure=settings.minio.secure,
        )
        versioning_service = ModelVersioningService(storage_service)
    except Exception as e:
        print(f"Warning: Failed to initialize storage services: {e}")
        storage_service = None
        versioning_service = None

    return FineTuningService(
        ollama_url=settings.ollama.url,
        mlflow_tracking_uri=settings.mlflow.tracking_uri,
        storage_service=storage_service,
        versioning_service=versioning_service,
    )


# Modèles Pydantic
class FineTuningRequest(BaseModel):
    """Requête pour démarrer un fine-tuning."""

    project_id: str = Field(..., description="ID du projet Label Studio")
    base_model: str = Field(default="qwen3-coder:30b", description="Modèle de base")
    task_type: str = Field(default="classification", description="Type de tâche")
    model_name: str | None = Field(None, description="Nom du modèle fine-tuné")
    annotations: list[dict[str, Any]] = Field(
        default_factory=list, description="Annotations (optionnel)"
    )


class FineTuningResponse(BaseModel):
    """Réponse du démarrage de fine-tuning."""

    job_id: str
    project_id: str
    base_model: str
    model_name: str
    status: str
    training_examples: int
    created_at: str


class JobStatusResponse(BaseModel):
    """Statut d'un job de fine-tuning."""

    job_id: str
    status: str
    project_id: str
    base_model: str
    model_name: str
    training_examples: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    error: str | None = None
    test_result: dict[str, Any] | None = None


class ModelListResponse(BaseModel):
    """Liste des modèles fine-tunés."""

    models: list[dict[str, Any]]
    total: int


# Endpoints
@router.post("/start", response_model=FineTuningResponse, status_code=202)
async def start_fine_tuning(request: FineTuningRequest) -> FineTuningResponse:
    """
    Démarre un job de fine-tuning.

    Exemple:
    ```json
    {
        "project_id": "1",
        "base_model": "qwen3-coder:30b",
        "task_type": "classification",
        "annotations": [
            {
                "data": {"text": "Great product!"},
                "annotations": [{
                    "result": [{
                        "value": {"choices": ["positive"]}
                    }]
                }]
            }
        ]
    }
    ```
    """
    try:
        job_info = await get_fine_tuning_service().start_fine_tuning(
            project_id=request.project_id,
            base_model=request.base_model,
            annotations=request.annotations,
            task_type=request.task_type,
            model_name=request.model_name,
        )

        return FineTuningResponse(**job_info)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fine-tuning failed: {str(e)}")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Récupère le statut d'un job de fine-tuning.

    Args:
        job_id: ID du job

    Returns:
        Statut détaillé du job
    """
    job_status = await get_fine_tuning_service().get_job_status(job_id)

    if job_status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(**job_status)


@router.get("/jobs", response_model=list[JobStatusResponse])
async def list_jobs(project_id: str | None = None) -> list[JobStatusResponse]:
    """
    Liste tous les jobs de fine-tuning.

    Args:
        project_id: Filtrer par projet (optionnel)

    Returns:
        Liste des jobs
    """
    jobs = await get_fine_tuning_service().list_jobs(project_id=project_id)
    return [JobStatusResponse(**job) for job in jobs]


@router.get("/models", response_model=ModelListResponse)
async def list_fine_tuned_models() -> ModelListResponse:
    """
    Liste tous les modèles fine-tunés disponibles.

    Returns:
        Liste des modèles avec leurs métadonnées
    """
    models = await get_fine_tuning_service().list_fine_tuned_models()
    return ModelListResponse(models=models, total=len(models))


@router.delete("/models/{model_name}")
async def delete_model(model_name: str) -> dict[str, Any]:
    """
    Supprime un modèle fine-tuné.

    Args:
        model_name: Nom du modèle à supprimer

    Returns:
        Résultat de la suppression
    """
    result = await get_fine_tuning_service().delete_model(model_name)

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/models/{model_name}/export")
async def export_model(model_name: str, export_path: str | None = None) -> dict[str, Any]:
    """
    Exporte un modèle fine-tuné (POST - retourne JSON).

    Args:
        model_name: Nom du modèle
        export_path: Chemin d'export (optionnel)

    Returns:
        Informations sur l'export
    """
    if export_path is None:
        export_path = f"/tmp/{model_name}_modelfile.txt"

    result = await get_fine_tuning_service().export_model(
        model_name=model_name, export_path=Path(export_path)
    )

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/models/{model_name}/export")
async def download_exported_model(model_name: str):
    """Exporte et telecharge un modele fine-tune (GET - retourne fichier)."""
    export_path = f"/tmp/{model_name}_modelfile.txt"

    result = await get_fine_tuning_service().export_model(
        model_name=model_name, export_path=Path(export_path)
    )

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result["error"])

    file_path = Path(export_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not generated")

    return FileResponse(
        path=str(file_path),
        filename=f"{model_name}_modelfile.txt",
        media_type="text/plain",
    )


@router.post("/from-label-studio")
async def fine_tune_from_label_studio(
    project_id: str,
    base_model: str = "qwen3-coder:30b",
    task_type: str = "classification",
    model_name: str | None = None,
) -> FineTuningResponse:
    """
    Démarre un fine-tuning directement depuis un projet Label Studio.

    Cette endpoint récupère automatiquement les annotations depuis Label Studio.

    Args:
        project_id: ID du projet Label Studio
        base_model: Modèle de base
        task_type: Type de tâche
        model_name: Nom du modèle (optionnel)

    Returns:
        Informations sur le job créé
    """
    from src.infrastructure.annotation.annotation_service import AnnotationService

    settings = get_settings()

    # Initialize AnnotationService
    annotation_service = AnnotationService(
        label_studio_url=settings.label_studio.url,
        api_key=settings.label_studio.api_key,
    )

    try:
        # Check if Label Studio is available
        if not await annotation_service.health_check():
            raise HTTPException(
                status_code=503,
                detail="Label Studio is not available. Please check the connection.",
            )

        # Export annotations from Label Studio
        annotations = await annotation_service.export_annotations(
            project_id=project_id,
            export_format="JSON",
        )

        if not annotations:
            raise HTTPException(
                status_code=400,
                detail=f"No annotations found in project {project_id}. "
                "Please annotate some data first.",
            )

        # Filter to only include completed annotations
        completed_annotations = [
            ann for ann in annotations if ann.get("annotations") and len(ann["annotations"]) > 0
        ]

        if not completed_annotations:
            raise HTTPException(
                status_code=400,
                detail=f"No completed annotations found in project {project_id}. "
                "Please complete some annotations first.",
            )

        # Start fine-tuning with the exported annotations
        job_info = await get_fine_tuning_service().start_fine_tuning(
            project_id=project_id,
            base_model=base_model,
            annotations=completed_annotations,
            task_type=task_type,
            model_name=model_name,
        )

        return FineTuningResponse(**job_info)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fine-tuning from Label Studio failed: {str(e)}",
        )


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    lines: int = 100,
) -> dict[str, Any]:
    """
    Récupère les logs d'un job de fine-tuning.

    Args:
        job_id: ID du job
        lines: Nombre de lignes à retourner (default: 100)

    Returns:
        Logs du job
    """
    try:
        # Check if job exists
        job_status = await get_fine_tuning_service().get_job_status(job_id)
        if job_status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Get logs from MLflow via service
        logs_result = await get_fine_tuning_service().get_mlflow_logs(job_id)

        if logs_result.get("status") == "success":
            return {
                "job_id": job_id,
                "content": logs_result.get("content", ""),
                "lines": lines,
                "mlflow_run_id": logs_result.get("mlflow_run_id"),
                "metrics": logs_result.get("metrics", {}),
            }
        elif logs_result.get("status") == "no_mlflow":
            return {
                "job_id": job_id,
                "content": f"Job {job_id} status: {job_status['status']}\nNo MLflow run associated.",
                "lines": lines,
            }
        else:
            return {
                "job_id": job_id,
                "content": f"Job {job_id} status: {job_status['status']}\n{logs_result.get('message', 'No logs available')}",
                "lines": lines,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """
    Annule un job de fine-tuning en cours.

    Args:
        job_id: ID du job à annuler

    Returns:
        Résultat de l'annulation
    """
    try:
        # Check if job exists
        job_status = await get_fine_tuning_service().get_job_status(job_id)
        if job_status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Cancel the job via service
        result = await get_fine_tuning_service().cancel_job(job_id)

        if result.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Cannot cancel job"),
            )

        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": result.get("message", f"Job {job_id} cancelled"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Vérifie que le service de fine-tuning est opérationnel.

    Returns:
        Statut du service
    """
    try:
        # Vérifier qu'Ollama est accessible
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{get_fine_tuning_service().ollama_url}/api/tags")

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "ollama_url": get_fine_tuning_service().ollama_url,
                    "ollama_connected": True,
                }
            else:
                return {
                    "status": "degraded",
                    "ollama_url": get_fine_tuning_service().ollama_url,
                    "ollama_connected": False,
                    "error": f"HTTP {response.status_code}",
                }

    except Exception as e:
        return {
            "status": "unhealthy",
            "ollama_url": get_fine_tuning_service().ollama_url,
            "ollama_connected": False,
            "error": str(e),
        }
