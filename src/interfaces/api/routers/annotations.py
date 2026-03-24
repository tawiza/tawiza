"""Annotations API routes for Label Studio integration."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.application.ports.annotation_ports import (
    AnnotationError,
    ExportError,
    ImportError,
    ProjectNotFoundError,
)
from src.infrastructure.annotation.annotation_service import AnnotationService

router = APIRouter()


# Initialize annotation service with credentials from settings
# The service is initialized when needed, not at module load
def get_annotation_service() -> AnnotationService:
    """Get annotation service with current settings."""
    import os

    from dotenv import load_dotenv

    # Load .env file to get latest values
    load_dotenv(override=True)

    # Read directly from environment to avoid caching issues
    url = os.getenv("LABEL_STUDIO__URL", "http://localhost:8082")
    api_key = os.getenv("LABEL_STUDIO__API_KEY", "")

    logger.debug(
        f"Initializing annotation service with URL: {url}, API key present: {bool(api_key)}"
    )

    return AnnotationService(
        label_studio_url=url,
        api_key=api_key,
    )


# Pydantic Models
class CreateProjectRequest(BaseModel):
    """Request model for creating annotation project."""

    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Project description")
    task_type: str = Field(
        default="classification",
        description="Type of annotation task (classification, ner, image_classification, etc.)",
    )
    label_config: str | None = Field(
        default=None, description="Optional custom label configuration XML"
    )


class ProjectResponse(BaseModel):
    """Response model for annotation project."""

    id: str
    name: str
    description: str
    task_type: str
    total_tasks: int = 0
    annotated_tasks: int = 0
    completed_tasks: int = 0
    created_at: str | None = None
    label_config: str | None = None


class ImportDataRequest(BaseModel):
    """Request model for importing data to annotation project."""

    data: list[dict[str, Any]] = Field(
        ..., description="List of data items to import for annotation"
    )


class ImportDataResponse(BaseModel):
    """Response model for data import."""

    project_id: str
    tasks_imported: int
    status: str


class PrepareDatasetRequest(BaseModel):
    """Request model for preparing dataset for annotation."""

    dataset_id: UUID = Field(..., description="Dataset UUID from database")
    sample_size: int | None = Field(
        default=None, description="Optional sample size for large datasets"
    )


class SyncAnnotationsRequest(BaseModel):
    """Request model for syncing annotations to dataset."""

    project_id: str = Field(..., description="Label Studio project ID")
    dataset_id: UUID = Field(..., description="Dataset UUID to sync to")


# Endpoints
@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Check annotation service health.

    Verifies connection to Label Studio.

    **Returns:**
    ```json
    {
        "status": "healthy",
        "service": "annotations",
        "label_studio": "connected"
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        is_healthy = await annotation_service.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "annotations",
            "label_studio": "connected" if is_healthy else "disconnected",
        }
    except Exception as e:
        logger.error(f"Annotation service health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "annotations",
            "label_studio": "disconnected",
            "error": str(e),
        }


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(request: CreateProjectRequest) -> ProjectResponse:
    """
    Create a new annotation project.

    Creates a new project in Label Studio for data annotation.

    **Request Body:**
    ```json
    {
        "name": "Product Classification",
        "description": "Classify product reviews",
        "task_type": "classification",
        "label_config": "<optional custom XML>"
    }
    ```

    **Response:**
    ```json
    {
        "id": "1",
        "name": "Product Classification",
        "description": "Classify product reviews",
        "task_type": "classification",
        "total_tasks": 0,
        "annotated_tasks": 0,
        "completed_tasks": 0,
        "created_at": "2025-01-13T10:00:00Z"
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        project = await annotation_service.create_annotation_project(
            name=request.name,
            description=request.description,
            task_type=request.task_type,
            label_config=request.label_config,
        )
        return ProjectResponse(**project)
    except AnnotationError as e:
        logger.error(f"Failed to create annotation project: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects() -> list[ProjectResponse]:
    """
    List all annotation projects.

    Returns a list of all Label Studio projects.

    **Response:**
    ```json
    [
        {
            "id": "1",
            "name": "Product Classification",
            "description": "Classify product reviews",
            "total_tasks": 100,
            "annotated_tasks": 45
        }
    ]
    ```
    """
    try:
        annotation_service = get_annotation_service()
        projects = await annotation_service.list_projects()
        return [ProjectResponse(**p) for p in projects]
    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """
    Get annotation project details.

    Retrieves detailed information about a specific project.

    **Path Parameters:**
    - `project_id`: Label Studio project ID

    **Response:**
    ```json
    {
        "id": "1",
        "name": "Product Classification",
        "description": "Classify product reviews",
        "total_tasks": 100,
        "annotated_tasks": 45,
        "completed_tasks": 40,
        "created_at": "2025-01-13T10:00:00Z"
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        project = await annotation_service.get_project(project_id)
        return ProjectResponse(**project)
    except ProjectNotFoundError as e:
        logger.warning(f"Project {project_id} not found")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/import", response_model=ImportDataResponse)
async def import_data(project_id: str, request: ImportDataRequest) -> ImportDataResponse:
    """
    Import data for annotation.

    Imports data items into a Label Studio project for annotation.

    **Path Parameters:**
    - `project_id`: Label Studio project ID

    **Request Body:**
    ```json
    {
        "data": [
            {"text": "Great product!"},
            {"text": "Not satisfied with quality"},
            {"text": "Excellent value for money"}
        ]
    }
    ```

    **Response:**
    ```json
    {
        "project_id": "1",
        "tasks_imported": 3,
        "status": "success"
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        result = await annotation_service.import_data_for_annotation(
            project_id=project_id, data=request.data
        )
        return ImportDataResponse(**result)
    except ImportError as e:
        logger.error(f"Failed to import data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error importing data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects/{project_id}/export")
async def export_annotations(
    project_id: str,
    format: str = Query(default="JSON", description="Export format (JSON, CSV, etc.)"),
) -> list[dict[str, Any]]:
    """
    Export completed annotations.

    Exports annotations from a Label Studio project.

    **Path Parameters:**
    - `project_id`: Label Studio project ID

    **Query Parameters:**
    - `format`: Export format (default: JSON)

    **Response:**
    ```json
    [
        {
            "id": 1,
            "data": {"text": "Great product!"},
            "annotations": [
                {
                    "result": [
                        {
                            "value": {"choices": ["positive"]},
                            "from_name": "sentiment",
                            "to_name": "text"
                        }
                    ]
                }
            ]
        }
    ]
    ```
    """
    try:
        annotation_service = get_annotation_service()
        annotations = await annotation_service.export_annotations(
            project_id=project_id, export_format=format
        )
        return annotations
    except ExportError as e:
        logger.error(f"Failed to export annotations: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error exporting annotations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects/{project_id}/stats")
async def get_project_statistics(project_id: str) -> dict[str, Any]:
    """
    Get project statistics.

    Retrieves annotation progress statistics for a project.

    **Path Parameters:**
    - `project_id`: Label Studio project ID

    **Response:**
    ```json
    {
        "total_tasks": 100,
        "total_annotations": 145,
        "completed": 40,
        "pending": 60
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        annotation_service = get_annotation_service()
        stats = await annotation_service.get_project_statistics(project_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get project stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str) -> None:
    """
    Delete annotation project.

    Deletes a Label Studio project and all its data.

    **Path Parameters:**
    - `project_id`: Label Studio project ID

    **Warning:** This action cannot be undone.
    """
    try:
        annotation_service = get_annotation_service()
        success = await annotation_service.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found or already deleted")
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/prepare-dataset", status_code=201)
async def prepare_dataset(request: PrepareDatasetRequest) -> dict[str, Any]:
    """
    Prepare dataset for annotation.

    Creates a Label Studio project and imports dataset for annotation.

    **Request Body:**
    ```json
    {
        "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
        "sample_size": 100
    }
    ```

    **Response:**
    ```json
    {
        "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
        "project_id": "1",
        "project_name": "Dataset 123e4567...",
        "status": "ready",
        "tasks_imported": 100
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        result = await annotation_service.prepare_dataset_for_annotation(
            dataset_id=request.dataset_id, sample_size=request.sample_size
        )
        return result
    except AnnotationError as e:
        logger.error(f"Failed to prepare dataset: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error preparing dataset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync", status_code=200)
async def sync_annotations(request: SyncAnnotationsRequest) -> dict[str, Any]:
    """
    Sync annotations to dataset.

    Exports completed annotations from Label Studio and updates dataset.

    **Request Body:**
    ```json
    {
        "project_id": "1",
        "dataset_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    ```

    **Response:**
    ```json
    {
        "project_id": "1",
        "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
        "annotations_exported": 45,
        "status": "synced"
    }
    ```
    """
    try:
        annotation_service = get_annotation_service()
        result = await annotation_service.sync_annotations_to_dataset(
            project_id=request.project_id, dataset_id=request.dataset_id
        )
        return result
    except AnnotationError as e:
        logger.error(f"Failed to sync annotations: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error syncing annotations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
