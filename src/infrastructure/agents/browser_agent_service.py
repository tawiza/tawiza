"""
Browser Agent Service - Implements IWebAgent port.

This service provides web automation capabilities using browser-use
integrated with Ollama for LLM-powered automation.

Enhanced with:
- Automatic retry on transient failures
- Exponential backoff for browser operations
- Better error handling and recovery
"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from loguru import logger

from src.application.ports.agent_ports import (
    IWebAgent,
    TaskNotFoundError,
    TaskStatus,
)
from src.infrastructure.agents.browser_use_adapter import BrowserUseAdapter
from src.infrastructure.agents.ollama_browser_chat_model import OllamaBrowserChatModel
from src.infrastructure.ml.ollama import OllamaAdapter
from src.infrastructure.prompts import get_prompt_manager
from src.infrastructure.streaming import ProgressStatus, ProgressTracker
from src.infrastructure.utils.retry import RetryConfig, with_retry


class BrowserAgentService(IWebAgent):
    """
    Browser automation service implementing IWebAgent.

    Uses browser-use with Ollama for LLM-powered web automation.
    """

    def __init__(
        self,
        ollama_adapter: OllamaAdapter,
        progress_tracker: ProgressTracker | None = None,
        default_model: str = "qwen3-coder:30b",
        headless: bool = True,
        use_prompt_templates: bool = True,
    ):
        """
        Initialize browser agent service.

        Args:
            ollama_adapter: Ollama adapter for LLM
            progress_tracker: Progress tracker for real-time updates (optional)
            default_model: Default Ollama model to use
            headless: Run browser in headless mode
            use_prompt_templates: Use PromptManager for dynamic prompts (optional)
        """
        self.ollama = ollama_adapter
        self.default_model = default_model
        self.use_prompt_templates = use_prompt_templates

        # Initialize or use provided progress tracker
        self.progress_tracker = progress_tracker or ProgressTracker()

        # Initialize prompt manager if enabled
        if self.use_prompt_templates:
            self.prompt_manager = get_prompt_manager()
            logger.info("PromptManager enabled for browser tasks")
        else:
            self.prompt_manager = None

        # Create Ollama chat model wrapper for browser-use
        self.llm_model = OllamaBrowserChatModel(
            ollama_adapter=self.ollama,
            model=default_model,
        )

        # Create browser-use adapter with Ollama LLM
        self.browser_adapter = BrowserUseAdapter(
            llm_client=self.llm_model,
            headless=headless,
            browser_type="chromium",
        )

        logger.info(
            f"BrowserAgentService initialized (model={default_model}, "
            f"headless={headless}, progress_tracking=enabled, "
            f"prompt_templates={use_prompt_templates})"
        )

    def _build_task_description(self, task_config: dict[str, Any]) -> str:
        """
        Build task description using PromptManager if available.

        Args:
            task_config: Task configuration

        Returns:
            str: Task description formatted as prompt
        """
        description = task_config.get("description", "")
        url = task_config.get("url")
        context = task_config.get("context", "")

        # Use prompt templates if enabled
        if self.prompt_manager and self.use_prompt_templates:
            try:
                # Try detailed template first
                if url and context:
                    return self.prompt_manager.render(
                        "browser_task_detailed", url=url, task=description, context=context
                    )
                # Use navigation template if URL provided
                elif url:
                    return self.prompt_manager.render(
                        "browser_navigation", url=url, action=description
                    )
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to use prompt template: {e}, falling back to default")

        # Fallback to simple string formatting
        if url:
            return f"Navigate to {url} and {description}"
        return description

    @with_retry(
        RetryConfig(
            max_attempts=3,
            base_delay=3.0,
            max_delay=60.0,
            exceptions=(ConnectionError, TimeoutError, RuntimeError),
        )
    )
    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a web automation task with real-time progress tracking.

        Automatically retries on transient failures with exponential backoff.

        Args:
            task_config: Task configuration containing:
                - task_id: UUID (optional, will be generated)
                - description: Natural language task description
                - url: Starting URL (optional)
                - max_actions: Maximum actions (default: 50)
                - timeout: Timeout in seconds (default: 300)

        Returns:
            Task result dictionary with task_id for progress streaming

        Raises:
            AgentExecutionError: If task fails after retries
        """
        # Build task description (with or without prompt templates)
        task_description = self._build_task_description(task_config)

        # Create progress tracking task
        progress_task_id = await self.progress_tracker.create_task(
            task_id=task_config.get("task_id"),
            metadata={
                "description": task_description,
                "url": task_config.get("url"),
                "max_actions": task_config.get("max_actions", 50),
            },
        )

        try:
            # Update: Task starting
            await self.progress_tracker.update_progress(
                task_id=progress_task_id,
                status=ProgressStatus.RUNNING,
                progress=5,
                current_step=f"Initializing browser for: {task_description[:60]}...",
            )

            logger.info(f"Executing browser task {progress_task_id}: {task_description[:100]}...")

            # Update: Browser initialized
            await self.progress_tracker.update_progress(
                task_id=progress_task_id,
                status=ProgressStatus.RUNNING,
                progress=10,
                current_step="Browser initialized, starting task execution",
            )

            # Execute using browser-use adapter
            task = await self.browser_adapter.execute_task(
                task_description=task_description,
                max_actions=task_config.get("max_actions", 50),
                timeout=task_config.get("timeout", 300),
            )

            # Update: Task executing (mid-progress)
            await self.progress_tracker.update_progress(
                task_id=progress_task_id,
                status=ProgressStatus.RUNNING,
                progress=70,
                current_step="Processing task results and extracting data",
            )

            logger.info(f"Task completed: {task.task_id} (status: {task.status})")

            # Convert to expected format
            result = {
                "task_id": progress_task_id,  # Use progress task_id for consistency
                "browser_task_id": str(task.task_id),
                "status": task.status,
                "result": task.result or {},
                "screenshots": [],  # TODO: Extract screenshots from history
                "logs": task.history,
                "error": task.error,
            }

            # Update: Task completed successfully
            await self.progress_tracker.update_progress(
                task_id=progress_task_id,
                status=ProgressStatus.COMPLETED,
                progress=100,
                current_step=f"Task completed successfully: {task.status}",
                metadata={"result_size": len(str(task.result or {}))},
            )

            return result

        except Exception as e:
            logger.error(f"Browser task failed: {e}")

            # Update: Task failed
            await self.progress_tracker.update_progress(
                task_id=progress_task_id,
                status=ProgressStatus.FAILED,
                progress=0,
                current_step="Task failed",
                error=str(e),
            )

            raise

    async def stream_progress(self, task_id: str) -> AsyncGenerator[dict[str, Any]]:
        """
        Stream real-time task execution progress using Server-Sent Events.

        Args:
            task_id: Task identifier

        Yields:
            Progress updates with status, progress %, current step, etc.

        Raises:
            TaskNotFoundError: If task not found in progress tracker
        """
        # Verify task exists
        latest = await self.progress_tracker.get_latest_progress(task_id)
        if not latest:
            raise TaskNotFoundError(f"Task {task_id} not found in progress tracker")

        # Stream progress updates from tracker
        async for event in self.progress_tracker.stream_progress(task_id, send_history=True):
            yield {
                "task_id": task_id,
                "status": event.status.value,
                "progress": event.progress,
                "current_step": event.current_step,
                "screenshot_url": event.screenshot_url,
                "timestamp": event.timestamp.isoformat(),
                "error": event.error,
                "metadata": event.metadata,
            }

    @with_retry(
        RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exceptions=(ConnectionError, TimeoutError),
        )
    )
    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """
        Get current task status.

        Automatically retries on transient failures.

        Args:
            task_id: Task identifier

        Returns:
            Task status dictionary

        Raises:
            TaskNotFoundError: If task not found
        """
        try:
            task_uuid = UUID(task_id)
            task = await self.browser_adapter.get_task_status(task_uuid)

            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")

            return {
                "task_id": task_id,
                "description": task.description,
                "status": task.status,
                "result": task.result,
                "error": task.error,
                "history": task.history,
            }
        except TaskNotFoundError:
            # Don't retry on not found errors
            raise
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            raise

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled successfully

        Raises:
            TaskNotFoundError: If task not found
        """
        task_uuid = UUID(task_id)
        return await self.browser_adapter.cancel_task(task_uuid)

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        """
        Get task result.

        Args:
            task_id: Task identifier

        Returns:
            Task result dictionary

        Raises:
            TaskNotFoundError: If task not found
            TaskNotCompletedError: If task not completed
        """
        task_uuid = UUID(task_id)
        task = await self.browser_adapter.get_task_status(task_uuid)

        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        if task.status != "completed":
            from src.application.ports.agent_ports import TaskNotCompletedError

            raise TaskNotCompletedError(f"Task {task_id} has not completed (status: {task.status})")

        return {
            "task_id": task_id,
            "result": task.result or {},
            "history": task.history,
        }

    @with_retry(
        RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exceptions=(ConnectionError, TimeoutError),
        )
    )
    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List tasks with optional filtering.

        Automatically retries on transient failures.

        Args:
            status: Filter by status
            limit: Maximum tasks to return
            offset: Offset for pagination

        Returns:
            List of task summaries
        """
        try:
            # Get tasks from browser adapter
            status_str = status.value if status else None
            tasks = await self.browser_adapter.list_tasks(
                status=status_str,
                limit=limit + offset,  # Get more to handle offset
            )

            # Apply offset and convert to expected format
            tasks = tasks[offset : offset + limit]

            return [
                {
                    "task_id": str(task.task_id),
                    "description": task.description,
                    "status": task.status,
                    "result_preview": (str(task.result)[:100] + "..." if task.result else None),
                    "error": task.error,
                }
                for task in tasks
            ]
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            raise

    @with_retry(
        RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            exceptions=(ConnectionError, TimeoutError),
        )
    )
    async def health_check(self) -> bool:
        """
        Check if browser automation is available.

        Automatically retries on transient failures.

        Returns:
            True if healthy
        """
        try:
            result = await self.browser_adapter.health_check()
            logger.info(f"Browser agent health check: {'OK' if result else 'FAILED'}")
            return result
        except Exception as e:
            logger.error(f"Browser agent health check failed: {e}")
