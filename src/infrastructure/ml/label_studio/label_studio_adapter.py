"""Label Studio adapter for data annotation.

This adapter integrates with Label Studio for:
- Creating annotation projects
- Importing tasks
- Exporting annotations
- Setting up ML backends for pre-annotation
"""

from typing import Any

import httpx
from loguru import logger

from src.application.ports.ml_ports import IDataAnnotator
from src.infrastructure.config.settings import Settings


class LabelStudioAdapter(IDataAnnotator):
    """Adapter for Label Studio annotation platform.

    Label Studio provides:
    - Multi-modal annotation (text, images, audio, etc.)
    - ML-assisted annotation (pre-annotation)
    - Active learning
    - Collaborative annotation
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Label Studio adapter.

        Args:
            settings: Application settings
        """
        self.url = settings.label_studio.url.rstrip("/")
        self.api_key = settings.label_studio.api_key
        self.default_project_id = settings.label_studio.project_id
        self.timeout = 30

        # Headers for API requests
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"Initialized Label Studio adapter (URL: {self.url})")

    async def create_project(
        self,
        project_name: str,
        labeling_config: str,
    ) -> int:
        """Create an annotation project.

        Args:
            project_name: Name of the project
            labeling_config: Label Studio labeling configuration XML

        Returns:
            Project ID

        Example labeling config for text classification:
            ```xml
            <View>
              <Text name="text" value="$text"/>
              <Choices name="sentiment" toName="text" choice="single">
                <Choice value="Positive"/>
                <Choice value="Negative"/>
                <Choice value="Neutral"/>
              </Choices>
            </View>
            ```
        """
        logger.info(f"Creating Label Studio project: {project_name}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.url}/api/projects/",
                headers=self.headers,
                json={
                    "title": project_name,
                    "label_config": labeling_config,
                },
            )
            response.raise_for_status()
            result = response.json()

        project_id = result["id"]
        logger.info(f"Created project {project_name} with ID {project_id}")

        return project_id

    async def import_tasks(
        self,
        project_id: int,
        tasks: list[dict[str, Any]],
    ) -> list[int]:
        """Import tasks for annotation.

        Args:
            project_id: Project ID
            tasks: List of tasks to import

        Returns:
            List of task IDs

        Example task format:
            ```python
            {
                "data": {
                    "text": "This is a sample text to annotate"
                },
                "predictions": [],  # Optional pre-annotations
                "meta": {}  # Optional metadata
            }
            ```
        """
        logger.info(f"Importing {len(tasks)} tasks to project {project_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.url}/api/projects/{project_id}/import",
                headers=self.headers,
                json=tasks,
            )
            response.raise_for_status()
            result = response.json()

        task_ids = result.get("task_ids", [])
        logger.info(f"Imported {len(task_ids)} tasks successfully")

        return task_ids

    async def get_annotations(
        self,
        project_id: int,
    ) -> list[dict[str, Any]]:
        """Get annotations from a project.

        Args:
            project_id: Project ID

        Returns:
            List of annotations

        Each annotation contains:
        - task: Original task data
        - annotations: List of annotations (can be multiple per task)
        - predictions: ML predictions (if any)
        """
        logger.info(f"Fetching annotations from project {project_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.url}/api/projects/{project_id}/export",
                headers=self.headers,
                params={"exportType": "JSON"},
            )
            response.raise_for_status()
            annotations = response.json()

        logger.info(f"Fetched {len(annotations)} annotations")

        return annotations

    async def get_annotation_progress(
        self,
        project_id: int,
    ) -> dict[str, int]:
        """Get annotation progress for a project.

        Args:
            project_id: Project ID

        Returns:
            Progress information with keys:
            - total: Total number of tasks
            - completed: Number of completed tasks
            - skipped: Number of skipped tasks
            - in_progress: Number of tasks in progress
        """
        logger.info(f"Getting annotation progress for project {project_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Get project details
            response = await client.get(
                f"{self.url}/api/projects/{project_id}/",
                headers=self.headers,
            )
            response.raise_for_status()
            project = response.json()

        progress = {
            "total": project.get("task_number", 0),
            "completed": project.get("num_tasks_with_annotations", 0),
            "skipped": project.get("skipped_annotations_number", 0),
            "in_progress": 0,  # Label Studio doesn't directly provide this
        }

        # Calculate in_progress
        progress["in_progress"] = (
            progress["total"] - progress["completed"] - progress["skipped"]
        )

        logger.info(
            f"Progress: {progress['completed']}/{progress['total']} completed "
            f"({progress['completed']/progress['total']*100:.1f}%)"
            if progress["total"] > 0
            else "Progress: No tasks"
        )

        return progress

    async def enable_ml_backend(
        self,
        project_id: int,
        model_url: str,
    ) -> None:
        """Enable ML backend for auto-annotation.

        Args:
            project_id: Project ID
            model_url: URL of the ML backend server

        Note:
            The ML backend should implement Label Studio's ML Backend API.
            It will be called to generate predictions for new tasks.
        """
        logger.info(
            f"Enabling ML backend for project {project_id} at {model_url}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # First, create the ML backend
            response = await client.post(
                f"{self.url}/api/ml",
                headers=self.headers,
                json={
                    "url": model_url,
                    "title": f"ML Backend for Project {project_id}",
                },
            )
            response.raise_for_status()
            ml_backend = response.json()
            ml_backend_id = ml_backend["id"]

            # Connect ML backend to project
            response = await client.patch(
                f"{self.url}/api/projects/{project_id}/",
                headers=self.headers,
                json={
                    "model_version": ml_backend_id,
                },
            )
            response.raise_for_status()

        logger.info(f"ML backend {ml_backend_id} enabled for project {project_id}")

    async def get_project_info(self, project_id: int) -> dict[str, Any]:
        """Get project information.

        Args:
            project_id: Project ID

        Returns:
            Project information dictionary
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.url}/api/projects/{project_id}/",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def delete_project(self, project_id: int) -> None:
        """Delete a project.

        Args:
            project_id: Project ID
        """
        logger.warning(f"Deleting project {project_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.url}/api/projects/{project_id}/",
                headers=self.headers,
            )
            response.raise_for_status()

        logger.info(f"Deleted project {project_id}")

    async def create_pre_annotations(
        self,
        project_id: int,
        task_id: int,
        predictions: list[dict[str, Any]],
    ) -> None:
        """Create pre-annotations for a task.

        Args:
            project_id: Project ID
            task_id: Task ID
            predictions: List of predictions

        Example prediction format:
            ```python
            {
                "model_version": "v1",
                "score": 0.95,
                "result": [
                    {
                        "from_name": "sentiment",
                        "to_name": "text",
                        "type": "choices",
                        "value": {
                            "choices": ["Positive"]
                        }
                    }
                ]
            }
            ```
        """
        logger.info(f"Creating pre-annotations for task {task_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for prediction in predictions:
                response = await client.post(
                    f"{self.url}/api/predictions/",
                    headers=self.headers,
                    json={
                        "task": task_id,
                        **prediction,
                    },
                )
                response.raise_for_status()

        logger.info(f"Created {len(predictions)} pre-annotations")

    # Helper methods for common labeling configs

    @staticmethod
    def text_classification_config(
        classes: list[str],
        field_name: str = "text",
    ) -> str:
        """Generate text classification labeling config.

        Args:
            classes: List of class names
            field_name: Name of the text field

        Returns:
            XML labeling configuration
        """
        choices = "\n    ".join(
            f'<Choice value="{cls}"/>' for cls in classes
        )

        return f"""<View>
  <Text name="{field_name}" value="${field_name}"/>
  <Choices name="label" toName="{field_name}" choice="single">
    {choices}
  </Choices>
</View>"""

    @staticmethod
    def named_entity_recognition_config(
        entity_types: list[str],
        field_name: str = "text",
    ) -> str:
        """Generate NER labeling config.

        Args:
            entity_types: List of entity types
            field_name: Name of the text field

        Returns:
            XML labeling configuration
        """
        labels = "\n    ".join(
            f'<Label value="{entity}" background="#{hash(entity) % 0xFFFFFF:06x}"/>'
            for entity in entity_types
        )

        return f"""<View>
  <Text name="{field_name}" value="${field_name}"/>
  <Labels name="label" toName="{field_name}">
    {labels}
  </Labels>
</View>"""

    @staticmethod
    def text_generation_config(field_name: str = "text") -> str:
        """Generate text generation labeling config.

        Args:
            field_name: Name of the text field

        Returns:
            XML labeling configuration
        """
        return f"""<View>
  <Text name="{field_name}" value="${field_name}"/>
  <TextArea name="response" toName="{field_name}"
            placeholder="Enter generated text..."
            maxSubmissions="1"/>
  <Rating name="quality" toName="{field_name}" maxRating="5"/>
</View>"""
