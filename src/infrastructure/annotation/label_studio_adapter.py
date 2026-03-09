"""
Label Studio Integration Adapter

Provides integration with Label Studio for data annotation.

Security: Includes SSRF protection (VULN-004)
"""

from typing import Any

import httpx
from loguru import logger

from src.infrastructure.security.validators import validate_url


class LabelStudioAdapter:
    """
    Adapter for Label Studio API integration.

    Handles:
    - Project creation and management
    - Data import for annotation
    - Annotation export
    - Task management
    """

    def __init__(
        self,
        url: str = "http://localhost:8082",
        api_key: str | None = None,
        allowed_domains: set[str] | None = None,
        allow_localhost: bool = True
    ):
        """
        Initialize Label Studio adapter.

        Args:
            url: Label Studio URL
            api_key: API key for authentication
            allowed_domains: Whitelist of allowed domains for SSRF protection
            allow_localhost: Allow localhost connections (for development)

        Raises:
            ValueError: If URL fails SSRF validation
        """
        # SECURITY FIX (VULN-004): Validate URL to prevent SSRF
        try:
            validated_url = validate_url(
                url,
                allowed_domains=allowed_domains,
                allow_private_ips=allow_localhost  # Only allow in dev
            )
            self.url = validated_url.rstrip("/")
        except ValueError as e:
            logger.error(f"Label Studio URL validation failed: {e}")
            raise ValueError(f"Invalid Label Studio URL (SSRF protection): {e}")

        self.api_key = api_key
        self.allowed_domains = allowed_domains
        self.allow_localhost = allow_localhost

        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Token {api_key}"

        logger.info(f"Label Studio adapter initialized: {self.url}")

    async def health_check(self) -> bool:
        """
        Check if Label Studio is accessible.

        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # SECURITY: Short timeout to prevent hanging on SSRF attempts
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.url}/api/health",
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: Prevent redirect-based SSRF
                )
                is_healthy = response.status_code == 200
                logger.info(f"Label Studio health check: {'OK' if is_healthy else 'FAILED'}")
                return is_healthy
        except httpx.TimeoutException:
            logger.error("Label Studio health check timed out (possible SSRF attempt)")
            return False
        except Exception as e:
            logger.error(f"Label Studio health check failed: {e}")
            return False

    async def create_project(
        self,
        title: str,
        description: str = "",
        label_config: str | None = None,
        task_type: str = "classification"
    ) -> dict[str, Any]:
        """
        Create a new Label Studio project.

        Args:
            title: Project title
            description: Project description
            label_config: Label config XML (if None, uses default)
            task_type: Type of annotation task

        Returns:
            dict: Created project data
        """
        # Default label configs for common task types
        default_configs = {
            "classification": """
<View>
  <Text name="text" value="$text"/>
  <Choices name="label" toName="text" choice="single">
    <Choice value="positive"/>
    <Choice value="negative"/>
    <Choice value="neutral"/>
  </Choices>
</View>
            """,
            "ner": """
<View>
  <Labels name="label" toName="text">
    <Label value="PERSON" background="red"/>
    <Label value="ORG" background="darkorange"/>
    <Label value="LOC" background="orange"/>
  </Labels>
  <Text name="text" value="$text"/>
</View>
            """,
            "image_classification": """
<View>
  <Image name="image" value="$image"/>
  <Choices name="choice" toName="image">
    <Choice value="cat"/>
    <Choice value="dog"/>
    <Choice value="other"/>
  </Choices>
</View>
            """
        }

        if not label_config:
            label_config = default_configs.get(task_type, default_configs["classification"])

        payload = {
            "title": title,
            "description": description,
            "label_config": label_config
        }

        try:
            # SECURITY: Short timeout, no redirects (SSRF protection)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.url}/api/projects",
                    json=payload,
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: Prevent redirect SSRF
                )
                response.raise_for_status()
                project = response.json()
                logger.info(f"Created Label Studio project: {project.get('id')} - {title}")
                return project
        except httpx.TimeoutException:
            logger.error("Request timed out (possible SSRF attempt)")
            raise
        except Exception as e:
            logger.error(f"Failed to create Label Studio project: {e}")
            raise

    async def get_project(self, project_id: int) -> dict[str, Any]:
        """
        Get project details.

        Args:
            project_id: Project ID

        Returns:
            dict: Project data
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.url}/api/projects/{project_id}",
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: SSRF protection
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise

    async def list_projects(self) -> list[dict[str, Any]]:
        """
        List all projects.

        Returns:
            list: List of projects
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.url}/api/projects",
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: SSRF protection
                )
                response.raise_for_status()
                data = response.json()
                # Handle paginated response from Label Studio
                if isinstance(data, dict) and "results" in data:
                    projects = data["results"]
                else:
                    projects = data if isinstance(data, list) else []
                logger.info(f"Found {len(projects)} Label Studio projects")
                return projects
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            raise

    async def import_tasks(
        self,
        project_id: int,
        tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Import tasks/data to a project for annotation.

        Args:
            project_id: Project ID
            tasks: List of tasks (each task is a dict with data)

        Returns:
            dict: Import result

        Example tasks format:
            [
                {"data": {"text": "Hello world"}},
                {"data": {"text": "Another example"}}
            ]
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.url}/api/projects/{project_id}/import",
                    json=tasks,
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: SSRF protection
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    f"Imported {result.get('task_count', len(tasks))} tasks "
                    f"to project {project_id}"
                )
                return result
        except Exception as e:
            logger.error(f"Failed to import tasks to project {project_id}: {e}")
            raise

    async def export_annotations(
        self,
        project_id: int,
        export_type: str = "JSON"
    ) -> list[dict[str, Any]]:
        """
        Export annotations from a project.

        Args:
            project_id: Project ID
            export_type: Export format (JSON, JSON_MIN, CSV, TSV, COCO, etc.)

        Returns:
            list: Exported annotations
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.url}/api/projects/{project_id}/export",
                    params={"exportType": export_type},
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: SSRF protection
                )
                response.raise_for_status()
                annotations = response.json()
                logger.info(
                    f"Exported {len(annotations)} annotations "
                    f"from project {project_id}"
                )
                return annotations
        except Exception as e:
            logger.error(
                f"Failed to export annotations from project {project_id}: {e}"
            )
            raise

    async def get_project_stats(self, project_id: int) -> dict[str, Any]:
        """
        Get project statistics.

        Args:
            project_id: Project ID

        Returns:
            dict: Project statistics (tasks, annotations, etc.)
        """
        try:
            project = await self.get_project(project_id)
            stats = {
                "total_tasks": project.get("task_number", 0),
                "total_annotations": project.get("num_tasks_with_annotations", 0),
                "completed": project.get("finished_task_number", 0),
                "pending": project.get("task_number", 0) - project.get("finished_task_number", 0)
            }
            logger.info(f"Project {project_id} stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats for project {project_id}: {e}")
            raise

    async def delete_project(self, project_id: int) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID

        Returns:
            bool: True if deleted successfully
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.url}/api/projects/{project_id}",
                    headers=self.headers,
                    follow_redirects=False  # SECURITY: SSRF protection
                )
                response.raise_for_status()
                logger.info(f"Deleted Label Studio project {project_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False

    async def transform_scraped_data_to_tasks(
        self,
        scraped_data: dict[str, Any],
        task_type: str = "classification"
    ) -> list[dict[str, Any]]:
        """
        Transform scraped data into Label Studio tasks format.

        Args:
            scraped_data: Scraped data from OpenManus/Skyvern
            task_type: Type of annotation task

        Returns:
            list: Tasks in Label Studio format
        """
        tasks = []

        data = scraped_data.get("data", {})

        # Handle different data structures
        if isinstance(data, list):
            # List of items
            for item in data:
                if isinstance(item, dict):
                    # Convert dict to task
                    task = {"data": item}
                    tasks.append(task)
                else:
                    # Simple value
                    task = {"data": {"text": str(item)}}
                    tasks.append(task)

        elif isinstance(data, dict):
            # Dict of lists (e.g., {"titles": [...], "scores": [...]})
            # Zip them together
            keys = list(data.keys())
            if keys and isinstance(data[keys[0]], list):
                length = len(data[keys[0]])
                for i in range(length):
                    task_data = {}
                    for key in keys:
                        if i < len(data[key]):
                            task_data[key] = data[key][i]

                    # Use first key as main text field
                    if "text" not in task_data and keys:
                        task_data["text"] = task_data.get(keys[0], "")

                    tasks.append({"data": task_data})
            else:
                # Single dict
                if "text" not in data:
                    # Use first value as text
                    first_key = list(data.keys())[0] if data else "content"
                    data["text"] = str(data.get(first_key, ""))
                tasks.append({"data": data})

        logger.info(f"Transformed scraped data into {len(tasks)} Label Studio tasks")
        return tasks
