"""API endpoints for model storage and versioning."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.ports.storage_ports import (
    IModelStorageService,
    IModelVersioningService,
)
from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.config.settings import get_settings
from src.infrastructure.storage import MinIOStorageAdapter, ModelVersioningService

router = APIRouter()

# Get settings
settings = get_settings()

# Initialize storage and versioning services
storage_service: IModelStorageService | None = None
versioning_service: IModelVersioningService | None = None

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


# Pydantic Models
class VersionInfo(BaseModel):
    """Version information."""

    model_name: str
    version: str
    base_model: str
    accuracy: float | None = None
    training_examples: int = 0
    task_type: str = "classification"
    created_at: str
    is_active: bool = False
    storage_path: str | None = None
    size_bytes: int = 0
    mlflow_run_id: str | None = None


class VersionList(BaseModel):
    """List of versions."""

    model_name: str
    versions: list[VersionInfo]
    total: int
    latest_version: str | None = None


class VersionComparison(BaseModel):
    """Comparison between two versions."""

    model_name: str
    version_a: str
    version_b: str
    metrics_diff: dict[str, Any]
    hyperparameters_diff: dict[str, Any]
    summary: dict[str, Any]


class RollbackRequest(BaseModel):
    """Request to rollback a model."""

    target_version: str = Field(..., description="Version to rollback to")
    reason: str = Field(default="Manual rollback", description="Reason for rollback")


class TagRequest(BaseModel):
    """Request to tag a version."""

    tag_key: str = Field(..., description="Tag key")
    tag_value: str = Field(..., description="Tag value")


class PromoteRequest(BaseModel):
    """Request to promote a version."""

    environment: str = Field(..., description="Target environment (dev, staging, production)")


class StorageStats(BaseModel):
    """Storage statistics."""

    total_size_bytes: int
    total_versions: int
    models: dict[str, Any]


# Endpoints
@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check model storage service health."""
    if storage_service is None:
        return {
            "status": "unhealthy",
            "error": "Storage service not initialized",
        }

    try:
        # Try to get storage stats
        stats = await storage_service.get_storage_stats()
        return {
            "status": "healthy",
            "storage_initialized": True,
            "total_models": len(stats.get("models", {})),
            "total_versions": stats.get("total_versions", 0),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.post("/initialize")
async def initialize_storage() -> dict[str, str]:
    """Initialize storage bucket in MinIO."""
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        await storage_service.initialize_bucket()
        return {"status": "success", "message": "Storage bucket initialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.get("/{model_name}/versions", response_model=VersionList)
async def list_model_versions(
    model_name: str,
    include_inactive: bool = Query(default=False, description="Include inactive versions"),
) -> VersionList:
    """List all versions of a model.

    Args:
        model_name: Name of the model
        include_inactive: Include inactive/archived versions

    Returns:
        List of versions with metadata
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        versions = await storage_service.list_versions(model_name, include_inactive)

        # Convert to response model
        version_infos = [
            VersionInfo(
                model_name=v.model_name,
                version=str(v.version),
                base_model=v.base_model,
                accuracy=v.accuracy,
                training_examples=v.training_examples,
                task_type=v.task_type,
                created_at=v.created_at.isoformat(),
                is_active=v.is_active,
                storage_path=v.storage_path,
                size_bytes=v.modelfile_size_bytes,
                mlflow_run_id=v.mlflow_run_id,
            )
            for v in versions
        ]

        latest = versions[0] if versions else None

        return VersionList(
            model_name=model_name,
            versions=version_infos,
            total=len(version_infos),
            latest_version=str(latest.version) if latest else None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list versions: {str(e)}")


@router.get("/{model_name}/versions/{version}", response_model=VersionInfo)
async def get_version_details(model_name: str, version: str) -> VersionInfo:
    """Get details of a specific version.

    Args:
        model_name: Name of the model
        version: Version number (e.g., "v1", "1")

    Returns:
        Version metadata
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        metadata = await storage_service.get_version_metadata(model_name, version_obj)

        return VersionInfo(
            model_name=metadata.model_name,
            version=str(metadata.version),
            base_model=metadata.base_model,
            accuracy=metadata.accuracy,
            training_examples=metadata.training_examples,
            task_type=metadata.task_type,
            created_at=metadata.created_at.isoformat(),
            is_active=metadata.is_active,
            storage_path=metadata.storage_path,
            size_bytes=metadata.modelfile_size_bytes,
            mlflow_run_id=metadata.mlflow_run_id,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Version not found: {str(e)}")


@router.get("/{model_name}/versions/{version}/download")
async def download_version(model_name: str, version: str) -> dict[str, Any]:
    """Download a specific version's modelfile.

    Args:
        model_name: Name of the model
        version: Version number

    Returns:
        Modelfile content and metadata
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        modelfile_content, metadata = await storage_service.retrieve_model(model_name, version_obj)

        return {
            "model_name": model_name,
            "version": version,
            "modelfile": modelfile_content,
            "metadata": {
                "base_model": metadata.base_model,
                "accuracy": metadata.accuracy,
                "training_examples": metadata.training_examples,
                "created_at": metadata.created_at.isoformat(),
                "size_bytes": metadata.modelfile_size_bytes,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Version not found: {str(e)}")


@router.delete("/{model_name}/versions/{version}")
async def delete_version(model_name: str, version: str) -> dict[str, str]:
    """Delete a specific model version.

    Args:
        model_name: Name of the model
        version: Version to delete

    Returns:
        Success message
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        await storage_service.delete_version(model_name, version_obj)

        return {
            "status": "success",
            "message": f"Version {version} of {model_name} deleted",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.post("/{model_name}/rollback", response_model=VersionInfo)
async def rollback_model(
    model_name: str,
    request: RollbackRequest,
) -> VersionInfo:
    """Rollback a model to a previous version.

    This creates a new version based on the target version.

    Args:
        model_name: Name of the model
        request: Rollback request with target version and reason

    Returns:
        New version metadata (copy of target version)
    """
    if versioning_service is None:
        raise HTTPException(status_code=500, detail="Versioning service not initialized")

    try:
        target_version = AutoIncrementVersion.from_string(request.target_version)
        metadata = await versioning_service.rollback_to_version(
            model_name, target_version, request.reason
        )

        return VersionInfo(
            model_name=metadata.model_name,
            version=str(metadata.version),
            base_model=metadata.base_model,
            accuracy=metadata.accuracy,
            training_examples=metadata.training_examples,
            task_type=metadata.task_type,
            created_at=metadata.created_at.isoformat(),
            is_active=metadata.is_active,
            storage_path=metadata.storage_path,
            size_bytes=metadata.modelfile_size_bytes,
            mlflow_run_id=metadata.mlflow_run_id,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.post("/{model_name}/versions/{version}/activate")
async def activate_version(model_name: str, version: str) -> dict[str, str]:
    """Set a version as the active/current version.

    Args:
        model_name: Name of the model
        version: Version to activate

    Returns:
        Success message
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        await storage_service.set_active_version(model_name, version_obj)

        return {
            "status": "success",
            "message": f"Version {version} activated for {model_name}",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")


@router.get("/{model_name}/active", response_model=VersionInfo | None)
async def get_active_version(model_name: str) -> VersionInfo | None:
    """Get the currently active version of a model.

    Args:
        model_name: Name of the model

    Returns:
        Active version metadata or None
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        metadata = await storage_service.get_active_version(model_name)

        if metadata is None:
            return None

        return VersionInfo(
            model_name=metadata.model_name,
            version=str(metadata.version),
            base_model=metadata.base_model,
            accuracy=metadata.accuracy,
            training_examples=metadata.training_examples,
            task_type=metadata.task_type,
            created_at=metadata.created_at.isoformat(),
            is_active=metadata.is_active,
            storage_path=metadata.storage_path,
            size_bytes=metadata.modelfile_size_bytes,
            mlflow_run_id=metadata.mlflow_run_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active version: {str(e)}")


@router.get("/{model_name}/compare")
async def compare_versions(
    model_name: str,
    version_a: str = Query(..., description="First version to compare"),
    version_b: str = Query(..., description="Second version to compare"),
) -> VersionComparison:
    """Compare two versions of a model.

    Args:
        model_name: Name of the model
        version_a: First version
        version_b: Second version

    Returns:
        Comparison results
    """
    if versioning_service is None:
        raise HTTPException(status_code=500, detail="Versioning service not initialized")

    try:
        ver_a = AutoIncrementVersion.from_string(version_a)
        ver_b = AutoIncrementVersion.from_string(version_b)

        comparison = await versioning_service.compare_versions(model_name, ver_a, ver_b)

        return VersionComparison(
            model_name=model_name,
            version_a=version_a,
            version_b=version_b,
            metrics_diff=comparison["metrics_diff"],
            hyperparameters_diff=comparison["hyperparameters_diff"],
            summary={
                "base_model_changed": comparison["base_model_changed"],
                "training_examples_diff": comparison["training_examples_diff"],
                "size_diff_bytes": comparison["size_diff_bytes"],
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.post("/{model_name}/versions/{version}/tag")
async def tag_version(
    model_name: str,
    version: str,
    request: TagRequest,
) -> dict[str, str]:
    """Add a tag to a model version.

    Args:
        model_name: Name of the model
        version: Version to tag
        request: Tag request with key and value

    Returns:
        Success message
    """
    if versioning_service is None:
        raise HTTPException(status_code=500, detail="Versioning service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        await versioning_service.tag_version(
            model_name, version_obj, request.tag_key, request.tag_value
        )

        return {
            "status": "success",
            "message": f"Tagged {model_name} {version} with {request.tag_key}={request.tag_value}",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tagging failed: {str(e)}")


@router.post("/{model_name}/versions/{version}/promote")
async def promote_version(
    model_name: str,
    version: str,
    request: PromoteRequest,
) -> dict[str, str]:
    """Promote a version to an environment.

    Args:
        model_name: Name of the model
        version: Version to promote
        request: Promotion request with target environment

    Returns:
        Success message
    """
    if versioning_service is None:
        raise HTTPException(status_code=500, detail="Versioning service not initialized")

    try:
        version_obj = AutoIncrementVersion.from_string(version)
        await versioning_service.promote_version(model_name, version_obj, request.environment)

        return {
            "status": "success",
            "message": f"Promoted {model_name} {version} to {request.environment}",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid version format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Promotion failed: {str(e)}")


@router.get("/stats", response_model=StorageStats)
async def get_storage_stats(
    model_name: str | None = Query(None, description="Filter by model name"),
) -> StorageStats:
    """Get storage statistics.

    Args:
        model_name: Optional model name filter

    Returns:
        Storage statistics
    """
    if storage_service is None:
        raise HTTPException(status_code=500, detail="Storage service not initialized")

    try:
        stats = await storage_service.get_storage_stats(model_name)

        return StorageStats(
            total_size_bytes=stats["total_size_bytes"],
            total_versions=stats["total_versions"],
            models=stats["models"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
