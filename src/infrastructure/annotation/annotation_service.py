"""
Annotation Service Implementation.

Implements IAnnotationService using Label Studio adapter.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import aiofiles
from loguru import logger

from src.application.ports.annotation_ports import (
    AnnotationError,
    ExportError,
    IAnnotationService,
    ImportError,
    ProjectNotFoundError,
)
from src.domain.entities.dataset import DatasetStatus
from src.infrastructure.annotation.label_studio_adapter import LabelStudioAdapter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AnnotationService(IAnnotationService):
    """
    Annotation service using Label Studio.

    Implements IAnnotationService port using LabelStudioAdapter.
    """

    def __init__(
        self,
        label_studio_url: str = "http://localhost:8082",
        api_key: str | None = None,
        db_session: "AsyncSession | None" = None,
    ):
        """
        Initialize annotation service.

        Args:
            label_studio_url: Label Studio URL
            api_key: API key for Label Studio
            db_session: Optional database session for dataset operations
        """
        self.adapter = LabelStudioAdapter(url=label_studio_url, api_key=api_key)
        self._db_session = db_session
        logger.info(f"AnnotationService initialized with Label Studio: {label_studio_url}")

    async def health_check(self) -> bool:
        """Check if Label Studio is available."""
        return await self.adapter.health_check()

    async def create_annotation_project(
        self,
        name: str,
        description: str,
        task_type: str,
        label_config: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new annotation project.

        Args:
            name: Project name
            description: Project description
            task_type: Type of annotation
            label_config: Optional custom config

        Returns:
            dict: Created project info

        Raises:
            AnnotationError: If creation fails
        """
        try:
            project = await self.adapter.create_project(
                title=name,
                description=description,
                label_config=label_config,
                task_type=task_type,
            )

            return {
                "id": str(project.get("id")),
                "name": project.get("title"),
                "description": project.get("description"),
                "task_type": task_type,
                "created_at": project.get("created_at"),
                "label_config": project.get("label_config"),
            }

        except Exception as e:
            logger.error(f"Failed to create annotation project: {e}")
            raise AnnotationError(f"Failed to create project: {str(e)}")

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """
        Get project details.

        Args:
            project_id: Project ID

        Returns:
            dict: Project details

        Raises:
            ProjectNotFoundError: If project not found
        """
        try:
            project = await self.adapter.get_project(int(project_id))

            return {
                "id": str(project.get("id")),
                "name": project.get("title"),
                "description": project.get("description"),
                "total_tasks": project.get("task_number", 0),
                "annotated_tasks": project.get("num_tasks_with_annotations", 0),
                "completed_tasks": project.get("finished_task_number", 0),
                "created_at": project.get("created_at"),
            }

        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise ProjectNotFoundError(f"Project {project_id} not found")

    async def list_projects(self) -> list[dict[str, Any]]:
        """List all annotation projects."""
        try:
            projects = await self.adapter.list_projects()

            return [
                {
                    "id": str(p.get("id")),
                    "name": p.get("title", "Untitled"),
                    "description": p.get("description", ""),
                    "task_type": "classification",  # Default, Label Studio doesn't expose this
                    "total_tasks": p.get("task_number", 0),
                    "annotated_tasks": p.get("num_tasks_with_annotations", 0),
                    "completed_tasks": p.get("finished_task_number", 0),
                    "created_at": p.get("created_at"),
                }
                for p in projects
            ]

        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return []

    async def import_data_for_annotation(
        self,
        project_id: str,
        data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Import data for annotation.

        Args:
            project_id: Project ID
            data: List of data items

        Returns:
            dict: Import result

        Raises:
            ImportError: If import fails
        """
        try:
            # Transform data to Label Studio task format
            tasks = []
            for item in data:
                # Ensure data has required structure
                if "data" not in item:
                    # Wrap in data key
                    tasks.append({"data": item})
                else:
                    tasks.append(item)

            result = await self.adapter.import_tasks(int(project_id), tasks)

            return {
                "project_id": project_id,
                "tasks_imported": result.get("task_count", len(tasks)),
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Failed to import data to project {project_id}: {e}")
            raise ImportError(f"Failed to import data: {str(e)}")

    async def export_annotations(
        self,
        project_id: str,
        export_format: str = "JSON",
    ) -> list[dict[str, Any]]:
        """
        Export annotations.

        Args:
            project_id: Project ID
            export_format: Export format

        Returns:
            list: Exported annotations

        Raises:
            ExportError: If export fails
        """
        try:
            annotations = await self.adapter.export_annotations(
                int(project_id), export_type=export_format
            )

            logger.info(f"Exported {len(annotations)} annotations from project {project_id}")
            return annotations

        except Exception as e:
            logger.error(f"Failed to export annotations from project {project_id}: {e}")
            raise ExportError(f"Failed to export annotations: {str(e)}")

    async def get_project_statistics(self, project_id: str) -> dict[str, Any]:
        """Get project statistics."""
        try:
            stats = await self.adapter.get_project_stats(int(project_id))
            return stats

        except Exception as e:
            logger.error(f"Failed to get stats for project {project_id}: {e}")
            return {
                "total_tasks": 0,
                "total_annotations": 0,
                "completed": 0,
                "pending": 0,
            }

    async def delete_project(self, project_id: str) -> bool:
        """Delete annotation project."""
        try:
            return await self.adapter.delete_project(int(project_id))

        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False

    async def _get_dataset_repository(self):
        """Get dataset repository instance."""
        if not self._db_session:
            raise AnnotationError("Database session not configured")

        from src.infrastructure.persistence.repositories.dataset_repository import (
            SQLAlchemyDatasetRepository,
        )

        return SQLAlchemyDatasetRepository(self._db_session)

    async def _load_dataset_data(
        self,
        storage_path: str,
        data_format: str,
        sample_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Load data from dataset storage path.

        Args:
            storage_path: Path to dataset file
            data_format: Format (jsonl, json, csv)
            sample_size: Optional limit on samples

        Returns:
            List of data items
        """
        path = Path(storage_path)
        if not path.exists():
            raise AnnotationError(f"Dataset file not found: {storage_path}")

        data: list[dict[str, Any]] = []

        if data_format.lower() in ("jsonl", "ndjson"):
            async with aiofiles.open(path, encoding="utf-8") as f:
                line_count = 0
                async for line in f:
                    if line.strip():
                        data.append(json.loads(line))
                        line_count += 1
                        if sample_size and line_count >= sample_size:
                            break

        elif data_format.lower() == "json":
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
                loaded = json.loads(content)
                if isinstance(loaded, list):
                    data = loaded[:sample_size] if sample_size else loaded
                else:
                    data = [loaded]

        elif data_format.lower() == "csv":
            import csv
            import io

            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()

            reader = csv.DictReader(io.StringIO(content))
            for i, row in enumerate(reader):
                if sample_size and i >= sample_size:
                    break
                data.append(dict(row))

        else:
            raise AnnotationError(f"Unsupported format: {data_format}")

        logger.info(f"Loaded {len(data)} items from {storage_path}")
        return data

    async def prepare_dataset_for_annotation(
        self,
        dataset_id: UUID,
        sample_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Prepare a dataset for annotation.

        Loads data from database, creates Label Studio project,
        and imports data.

        Args:
            dataset_id: Dataset UUID
            sample_size: Optional sample size

        Returns:
            dict: Project info with status

        Raises:
            AnnotationError: If preparation fails
        """
        try:
            logger.info(f"Preparing dataset {dataset_id} for annotation (sample_size={sample_size})")

            # Load dataset from database
            repo = await self._get_dataset_repository()
            dataset = await repo.get_by_id(dataset_id)

            if not dataset:
                raise AnnotationError(f"Dataset {dataset_id} not found")

            if not dataset.storage_path:
                raise AnnotationError(f"Dataset {dataset_id} has no storage path")

            # Determine data format
            data_format = "jsonl"
            if dataset.metadata:
                data_format = dataset.metadata.format or "jsonl"

            # Load data from storage
            data = await self._load_dataset_data(
                dataset.storage_path,
                data_format,
                sample_size,
            )

            if not data:
                raise AnnotationError(f"No data found in dataset {dataset_id}")

            # Create annotation project
            project = await self.create_annotation_project(
                name=f"{dataset.name}",
                description=f"Annotation project for dataset {dataset.name}",
                task_type="classification",
            )

            # Import data into Label Studio
            import_result = await self.import_data_for_annotation(
                project_id=project["id"],
                data=data,
            )

            # Update dataset with Label Studio project ID
            dataset.link_label_studio_project(int(project["id"]))
            dataset._status = DatasetStatus.ANNOTATING
            await repo.save(dataset)
            await self._db_session.commit()

            logger.info(
                f"Dataset {dataset_id} prepared for annotation: "
                f"project={project['id']}, tasks={import_result['tasks_imported']}"
            )

            return {
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.name,
                "project_id": project["id"],
                "project_name": project["name"],
                "status": "ready",
                "tasks_imported": import_result["tasks_imported"],
            }

        except AnnotationError:
            raise
        except Exception as e:
            logger.error(f"Failed to prepare dataset {dataset_id} for annotation: {e}")
            raise AnnotationError(f"Failed to prepare dataset: {str(e)}")

    async def sync_annotations_to_dataset(
        self,
        project_id: str,
        dataset_id: UUID,
    ) -> dict[str, Any]:
        """
        Sync completed annotations back to dataset.

        Exports annotations from Label Studio and updates dataset.

        Args:
            project_id: Annotation project ID
            dataset_id: Dataset UUID

        Returns:
            dict: Sync result

        Raises:
            AnnotationError: If sync fails
        """
        try:
            logger.info(f"Syncing annotations from project {project_id} to dataset {dataset_id}")

            # Load dataset from database
            repo = await self._get_dataset_repository()
            dataset = await repo.get_by_id(dataset_id)

            if not dataset:
                raise AnnotationError(f"Dataset {dataset_id} not found")

            # Export annotations from Label Studio
            annotations = await self.export_annotations(project_id)

            # Count completed annotations (those with at least one annotation)
            completed_count = sum(
                1 for ann in annotations
                if ann.get("annotations") and len(ann["annotations"]) > 0
            )

            # Save annotations to a file alongside the dataset
            if dataset.storage_path:
                annotations_path = Path(dataset.storage_path).parent / f"{dataset.name}_annotations.json"
                async with aiofiles.open(annotations_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(annotations, indent=2, ensure_ascii=False))
                logger.info(f"Saved {len(annotations)} annotations to {annotations_path}")

            # Update dataset annotation progress
            dataset.update_annotation_progress(completed_count)

            # If all annotations complete, mark dataset as ready
            if dataset.metadata and completed_count >= dataset.metadata.size:
                dataset.mark_ready()
                logger.info(f"Dataset {dataset_id} fully annotated and marked ready")

            await repo.save(dataset)
            await self._db_session.commit()

            return {
                "project_id": project_id,
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.name,
                "annotations_exported": len(annotations),
                "annotations_completed": completed_count,
                "dataset_status": dataset.status.value,
                "status": "synced",
            }

        except AnnotationError:
            raise
        except Exception as e:
            logger.error(f"Failed to sync annotations: {e}")
            raise AnnotationError(f"Failed to sync annotations: {str(e)}")
