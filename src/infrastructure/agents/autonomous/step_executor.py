"""Step executor for autonomous agent.

Executes individual steps from a plan with error handling and validation.
"""

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.infrastructure.agents.autonomous.task_planner import ActionType, PlannedStep


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_id: str
    status: str  # completed, failed, skipped
    result_data: dict[str, Any] | None = None
    screenshot_path: str | None = None
    error_message: str | None = None
    execution_time_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @property
    def is_success(self) -> bool:
        """Check if step succeeded."""
        return self.status == "completed"


class StepExecutor:
    """Executes individual steps using browser agent and LLM.

    Handles:
    - Step execution via OpenManusAdapter
    - Result validation via LLM
    - Screenshot capture
    - Error recovery suggestions
    - Dry-run simulation mode
    """

    def __init__(
        self,
        browser_agent: Any,  # OpenManusAdapter
        llm_client: Any,  # OllamaClient
        screenshots_dir: str = "/tmp/tawiza-agent-screenshots",
    ):
        """Initialize step executor.

        Args:
            browser_agent: OpenManus adapter for browser automation
            llm_client: Ollama client for LLM guidance
            screenshots_dir: Directory to save screenshots
        """
        self.browser_agent = browser_agent
        self.llm_client = llm_client
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"StepExecutor initialized (screenshots: {screenshots_dir})")

    async def execute_step(
        self,
        step: PlannedStep,
        context: "ExecutionContext",
        dry_run: bool = False,
    ) -> StepResult:
        """Execute a single step.

        Args:
            step: Step to execute
            context: Current execution context
            dry_run: If True, simulate without actual browser interaction

        Returns:
            StepResult with execution outcome
        """
        logger.info(f"Executing step {step.step_id}: {step.action} - {step.description}")

        start_time = asyncio.get_event_loop().time()

        if dry_run:
            return await self._simulate_step(step)

        try:
            # Build task config for browser agent
            task_config = self._build_task_config(step, context)

            # Execute via browser agent
            result = await self.browser_agent.execute_task(task_config)

            # Extract result data
            result_data = self._extract_result_data(step, result)

            # Get screenshot path if available
            screenshot_path = None
            if result.get("screenshots"):
                screenshot_path = result["screenshots"][-1].get("url")

            execution_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Step {step.step_id} completed in {execution_time:.2f}s")

            return StepResult(
                step_id=step.step_id,
                status="completed",
                result_data=result_data,
                screenshot_path=screenshot_path,
                execution_time_seconds=execution_time,
            )

        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Step {step.step_id} failed: {e}")

            return StepResult(
                step_id=step.step_id,
                status="failed",
                error_message=str(e),
                execution_time_seconds=execution_time,
            )

    async def _simulate_step(self, step: PlannedStep) -> StepResult:
        """Simulate step execution without browser interaction.

        Args:
            step: Step to simulate

        Returns:
            Simulated StepResult
        """
        logger.info(f"[DRY-RUN] Simulating step {step.step_id}: {step.action}")

        # Simulate execution time
        await asyncio.sleep(min(step.estimated_duration_seconds, 2.0))

        # Generate mock result based on action type
        mock_data = self._generate_mock_data(step)

        return StepResult(
            step_id=step.step_id,
            status="completed",
            result_data={
                "simulated": True,
                "action": step.action,
                "description": step.description,
                **mock_data,
            },
            screenshot_path=None,
            execution_time_seconds=step.estimated_duration_seconds,
        )

    def _generate_mock_data(self, step: PlannedStep) -> dict[str, Any]:
        """Generate mock data for dry-run mode.

        Args:
            step: Step being simulated

        Returns:
            Mock data appropriate for the action type
        """
        action = step.action.lower()

        if action == ActionType.NAVIGATE.value:
            return {
                "url": step.url or "https://example.com",
                "title": "Simulated Page Title",
                "status": "navigated",
            }

        elif action == ActionType.EXTRACT.value:
            target = step.data.get("target", "data") if step.data else "data"
            limit = step.data.get("limit", 5) if step.data else 5
            return {
                "items": [f"Sample {target} item {i + 1}" for i in range(limit)],
                "count": limit,
                "selector_used": step.selector,
            }

        elif action == ActionType.FILL_FORM.value:
            return {
                "fields_filled": list(step.data.keys()) if step.data else ["field1"],
                "form_submitted": False,
            }

        elif action == ActionType.CLICK.value:
            return {
                "element_clicked": step.selector or "button",
                "new_url": None,
            }

        elif action == ActionType.SCREENSHOT.value:
            return {
                "screenshot_path": f"/tmp/dry-run-{step.step_id}.png",
            }

        else:
            return {"action_completed": True}

    def _build_task_config(
        self,
        step: PlannedStep,
        context: "ExecutionContext",
    ) -> dict[str, Any]:
        """Build task config for browser agent.

        Args:
            step: Step to execute
            context: Current execution context

        Returns:
            Task configuration dict for OpenManusAdapter
        """
        action = step.action.lower()

        # Base config
        config: dict[str, Any] = {
            "action": action,
        }

        # Add URL (from step or context)
        if step.url:
            config["url"] = step.url
        elif context.current_url:
            config["url"] = context.current_url

        # Action-specific config
        if action == ActionType.NAVIGATE.value:
            if not config.get("url"):
                config["url"] = step.url or "about:blank"

        elif action == ActionType.EXTRACT.value:
            if step.selector:
                config["selectors"] = {"main": step.selector}
            if step.data:
                config["data"] = step.data

        elif action == ActionType.FILL_FORM.value:
            if step.selector and step.data:
                # Map field names to selectors
                config["selectors"] = dict.fromkeys(step.data.keys(), step.selector)
                config["data"] = step.data
            elif step.data:
                config["data"] = step.data

        elif action == ActionType.CLICK.value:
            if step.selector:
                config["selector"] = step.selector

        elif action == ActionType.SCROLL.value:
            config["options"] = step.data or {"direction": "down", "amount": 500}

        elif action == ActionType.WAIT.value:
            config["options"] = step.data or {"timeout": 2000}

        return config

    def _extract_result_data(
        self,
        step: PlannedStep,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract relevant data from browser agent result.

        Args:
            step: Executed step
            result: Raw result from browser agent

        Returns:
            Cleaned result data
        """
        action = step.action.lower()

        # Base data
        data = {
            "action": action,
            "status": result.get("status", "unknown"),
        }

        # Extract action-specific data
        if action == ActionType.NAVIGATE.value:
            data["url"] = result.get("result", {}).get("url")
            data["title"] = result.get("result", {}).get("title")

        elif action == ActionType.EXTRACT.value:
            extracted = result.get("result", {}).get("data", {})
            data["items"] = extracted
            data["count"] = len(extracted) if isinstance(extracted, list) else 1

        elif action == ActionType.FILL_FORM.value:
            form_result = result.get("result", {})
            data["filled_fields"] = form_result.get("filled_fields", [])
            data["submitted"] = form_result.get("submitted", False)

        elif action == ActionType.CLICK.value:
            click_result = result.get("result", {})
            data["url_after"] = click_result.get("url")
            data["title_after"] = click_result.get("title")

        return data

    async def validate_step_completion(
        self,
        step: PlannedStep,
        result: StepResult,
        context: "ExecutionContext",
    ) -> bool:
        """Validate if step achieved its goal using LLM.

        Args:
            step: Executed step
            result: Execution result
            context: Current execution context

        Returns:
            True if step is validated as successful
        """
        if not result.is_success:
            return False

        # For simple actions, trust the result
        simple_actions = {
            ActionType.NAVIGATE.value,
            ActionType.SCREENSHOT.value,
            ActionType.WAIT.value,
        }
        if step.action.lower() in simple_actions:
            return True

        # For extract/fill_form, use LLM to validate
        try:
            validation_prompt = f"""Validate if this step was successful:

Step: {step.description}
Action: {step.action}
Expected: {json.dumps(step.data) if step.data else "Complete the action"}

Result: {json.dumps(result.result_data, indent=2)}

Respond with only "VALID" or "INVALID" followed by a brief reason."""

            response = await self.llm_client.generate(
                prompt=validation_prompt,
                temperature=0.1,
            )

            is_valid = "VALID" in response.upper()
            logger.debug(f"Step validation: {is_valid} - {response[:100]}")

            return is_valid

        except Exception as e:
            logger.warning(f"Validation failed, assuming success: {e}")
            return True

    async def get_recovery_suggestion(
        self,
        step: PlannedStep,
        error: str,
        context: "ExecutionContext",
    ) -> str:
        """Get LLM suggestion for recovering from error.

        Args:
            step: Failed step
            error: Error message
            context: Current execution context

        Returns:
            Recovery suggestion string
        """
        try:
            prompt = f"""A web automation step failed. Suggest a recovery approach.

Failed Step: {step.description}
Action: {step.action}
Selector: {step.selector}
URL: {step.url or context.current_url}

Error: {error}

Suggest one specific action to recover (e.g., "Try alternative selector .article h2",
"Wait for page load", "Navigate to different URL").
Be concise (1-2 sentences max)."""

            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.3,
            )

            return response.strip()

        except Exception as e:
            logger.warning(f"Failed to get recovery suggestion: {e}")
            return "Retry the step or skip to next step."


# Import ExecutionContext here to avoid circular import
from src.infrastructure.agents.autonomous.execution_state import ExecutionContext
