"""Datasets API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from src.domain.exceptions import EntityNotFoundError, InfrastructureError
from src.infrastructure.di.container import get_container

router = APIRouter()


class DatasetResponse(BaseModel):
    """Dataset response model."""

    id: str
    name: str
    description: str | None = None
    size: int = 0
    format: str = "unknown"
    num_samples: int = 0
    created_at: str
    updated_at: str
    status: str = "unknown"


class DatasetsListResponse(BaseModel):
    """Datasets list response."""

    datasets: list[DatasetResponse]
    total: int
    page: int
    page_size: int


@router.get("/health")
async def health_check():
    """Datasets service health check."""
    return {"status": "healthy", "service": "datasets"}


@router.get("", response_model=DatasetsListResponse)
@router.get("/", response_model=DatasetsListResponse)
async def list_datasets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """List all datasets.

    Returns a paginated list of datasets available in the system.

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 10, max: 100)

    **Example Response:**
    ```json
    {
        "datasets": [
            {
                "id": "dataset-1",
                "name": "Training Data",
                "description": "Main training dataset",
                "size": 10000,
                "format": "csv",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10
    }
    ```
    """
    try:
        # Get datasets from repository
        container = get_container()
        repo = container.dataset_repository()

        # Calculate pagination offset
        skip = (page - 1) * page_size

        # Fetch datasets with pagination
        dataset_entities = await repo.get_all(skip=skip, limit=page_size)
        total_count = await repo.count()

        # Convert to response models
        datasets = []
        for dataset in dataset_entities:
            metadata = dataset.metadata
            datasets.append(
                DatasetResponse(
                    id=str(dataset.id),
                    name=dataset.name,
                    description=metadata.source if metadata else None,
                    format=metadata.format if metadata else "unknown",
                    size=metadata.size if metadata else 0,
                    num_samples=metadata.size if metadata else 0,
                    created_at=dataset.created_at.isoformat() if dataset.created_at else "",
                    updated_at=dataset.updated_at.isoformat() if dataset.updated_at else "",
                    status=dataset.status.value,
                )
            )

        return DatasetsListResponse(
            datasets=datasets, total=total_count, page=page, page_size=page_size
        )

    except InfrastructureError as e:
        logger.error(f"Failed to list datasets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error listing datasets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: str):
    """Get dataset by ID.

    Returns detailed information about a specific dataset.

    **Path Parameters:**
    - `dataset_id`: Unique dataset identifier
    """
    try:
        # Parse UUID
        try:
            dataset_uuid = UUID(dataset_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid dataset ID format: {dataset_id}")

        # Get dataset from repository
        container = get_container()
        repo = container.dataset_repository()
        dataset = await repo.get_by_id(dataset_uuid)

        if dataset is None:
            raise EntityNotFoundError("Dataset", dataset_id)

        # Build response
        metadata = dataset.metadata
        return DatasetResponse(
            id=str(dataset.id),
            name=dataset.name,
            description=metadata.source if metadata else None,
            format=metadata.format if metadata else "unknown",
            size=metadata.size if metadata else 0,
            num_samples=metadata.size if metadata else 0,
            created_at=dataset.created_at.isoformat() if dataset.created_at else "",
            updated_at=dataset.updated_at.isoformat() if dataset.updated_at else "",
            status=dataset.status.value,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch dataset: {str(e)}")
