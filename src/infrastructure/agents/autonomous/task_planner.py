"""Task planning engine using LLM for intelligent decomposition.

Transforms natural language task descriptions into executable step-by-step plans.
"""

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger


class ActionType(StrEnum):
    """Supported browser automation actions."""

    NAVIGATE = "navigate"
    EXTRACT = "extract"
    FILL_FORM = "fill_form"
    CLICK = "click"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


@dataclass
class PlannedStep:
    """A single step in the execution plan."""

    step_id: str
    action: str
    description: str
    url: str | None = None
    selector: str | None = None
    data: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)
    estimated_duration_seconds: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlannedStep":
        """Create from dictionary."""
        return cls(
            step_id=data.get("step_id", f"step-{uuid.uuid4().hex[:6]}"),
            action=data.get("action", "navigate"),
            description=data.get("description", ""),
            url=data.get("url"),
            selector=data.get("selector"),
            data=data.get("data"),
            depends_on=data.get("depends_on", []),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 5),
        )


@dataclass
class TaskPlan:
    """Complete execution plan for a task."""

    plan_id: str
    original_task: str
    steps: list[PlannedStep]
    confidence_score: float = 0.8
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    estimated_total_duration: int = 0

    def __post_init__(self):
        """Calculate total duration after init."""
        if self.estimated_total_duration == 0:
            self.estimated_total_duration = sum(s.estimated_duration_seconds for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "original_task": self.original_task,
            "steps": [s.to_dict() for s in self.steps],
            "confidence_score": self.confidence_score,
            "created_at": self.created_at,
            "estimated_total_duration": self.estimated_total_duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskPlan":
        """Create from dictionary."""
        steps = [PlannedStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            plan_id=data.get("plan_id", f"plan-{uuid.uuid4().hex[:8]}"),
            original_task=data.get("original_task", ""),
            steps=steps,
            confidence_score=data.get("confidence_score", 0.8),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            estimated_total_duration=data.get("estimated_total_duration", 0),
        )


# System prompt for task planning
PLANNING_SYSTEM_PROMPT = """You are an expert web automation planner. Your job is to break down user tasks into precise, executable steps.

AVAILABLE ACTIONS:
- navigate: Go to a URL
- extract: Extract data from the page (requires selector or target description)
- fill_form: Fill form fields (requires selector and data)
- click: Click an element (requires selector)
- scroll: Scroll the page
- wait: Wait for an element or condition
- screenshot: Take a screenshot

RULES:
1. Each step must have a unique step_id (step-1, step-2, etc.)
2. Each step must have exactly ONE action
3. Use CSS selectors when known, or describe the element for AI detection
4. Set depends_on to reference previous step IDs when order matters
5. Be specific in descriptions for debugging
6. Estimate realistic durations (navigate: 3-5s, extract: 2-5s, click: 1-2s)

OUTPUT FORMAT (JSON only, no markdown):
{
  "plan_id": "plan-<short-uuid>",
  "original_task": "<user's original task>",
  "confidence_score": 0.0-1.0,
  "steps": [
    {
      "step_id": "step-1",
      "action": "navigate",
      "description": "Navigate to the website",
      "url": "https://example.com",
      "selector": null,
      "data": null,
      "depends_on": [],
      "estimated_duration_seconds": 3
    },
    {
      "step_id": "step-2",
      "action": "extract",
      "description": "Extract article titles",
      "url": null,
      "selector": ".article-title",
      "data": {"target": "article titles", "limit": 5},
      "depends_on": ["step-1"],
      "estimated_duration_seconds": 5
    }
  ]
}"""


REFINE_SYSTEM_PROMPT = """You are refining an existing automation plan based on user feedback.

CURRENT PLAN:
{current_plan}

USER FEEDBACK:
{feedback}

Update the plan to address the feedback. Keep the same JSON format.
Only modify steps that need changes. You can add, remove, or modify steps."""


REPLAN_SYSTEM_PROMPT = """You are creating a recovery plan after a step failed.

ORIGINAL PLAN:
{original_plan}

FAILED STEP:
{failed_step}

ERROR MESSAGE:
{error}

COMPLETED STEPS SO FAR:
{completed_steps}

Create a new plan that:
1. Starts from the current state (after completed steps)
2. Works around the failure
3. Still achieves the original goal
4. Uses alternative approaches if needed

Output the recovery plan in the same JSON format."""


class TaskPlanningEngine:
    """LLM-based task planning engine.

    Decomposes natural language tasks into executable step-by-step plans
    using Ollama LLM for intelligent planning.
    """

    def __init__(
        self,
        llm_client: Any,  # OllamaClient
        model: str | None = None,
        temperature: float = 0.3,
        max_steps: int = 20,
    ):
        """Initialize planning engine.

        Args:
            llm_client: Ollama client instance
            model: Override model (uses client default if None)
            temperature: LLM temperature (lower = more deterministic)
            max_steps: Maximum steps allowed in a plan
        """
        self.llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_steps = max_steps

        logger.info(f"TaskPlanningEngine initialized (max_steps={max_steps})")

    async def create_plan(
        self,
        task_description: str,
        starting_url: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskPlan:
        """Create execution plan from natural language task.

        Args:
            task_description: User's task in natural language
            starting_url: Optional starting URL
            context: Additional context (previous data, page info, etc.)

        Returns:
            TaskPlan with executable steps
        """
        logger.info(f"Creating plan for task: {task_description[:100]}...")

        # Build the user prompt
        user_prompt = f"Task: {task_description}"

        if starting_url:
            user_prompt += f"\n\nStarting URL: {starting_url}"

        if context:
            user_prompt += f"\n\nAdditional context: {json.dumps(context, indent=2)}"

        user_prompt += f"\n\nCreate a detailed execution plan (max {self.max_steps} steps)."

        # Call LLM
        response = await self.llm_client.generate(
            prompt=user_prompt,
            system=PLANNING_SYSTEM_PROMPT,
            model=self.model,
            temperature=self.temperature,
        )

        # Parse response
        plan = self._parse_plan_response(response, task_description)

        # Validate and fix
        plan = self._validate_plan(plan, starting_url)

        logger.info(
            f"Created plan {plan.plan_id} with {len(plan.steps)} steps "
            f"(confidence: {plan.confidence_score:.2f})"
        )

        return plan

    async def refine_plan(
        self,
        plan: TaskPlan,
        feedback: str,
    ) -> TaskPlan:
        """Refine existing plan based on user feedback.

        Args:
            plan: Current plan to refine
            feedback: User's feedback/corrections

        Returns:
            Updated TaskPlan
        """
        logger.info(f"Refining plan {plan.plan_id} with feedback: {feedback[:50]}...")

        system_prompt = REFINE_SYSTEM_PROMPT.format(
            current_plan=json.dumps(plan.to_dict(), indent=2),
            feedback=feedback,
        )

        response = await self.llm_client.generate(
            prompt="Provide the updated plan based on the feedback.",
            system=system_prompt,
            model=self.model,
            temperature=self.temperature,
        )

        # Parse and validate
        refined_plan = self._parse_plan_response(response, plan.original_task)
        refined_plan.plan_id = plan.plan_id  # Keep same plan ID

        logger.info(f"Refined plan now has {len(refined_plan.steps)} steps")

        return refined_plan

    async def replan_from_step(
        self,
        plan: TaskPlan,
        failed_step_id: str,
        error: str,
        completed_steps: list[str],
    ) -> TaskPlan:
        """Create recovery plan after step failure.

        Args:
            plan: Original plan
            failed_step_id: ID of the step that failed
            error: Error message
            completed_steps: List of completed step IDs

        Returns:
            Recovery TaskPlan
        """
        logger.info(f"Creating recovery plan after {failed_step_id} failed: {error[:50]}...")

        # Find failed step
        failed_step = None
        for step in plan.steps:
            if step.step_id == failed_step_id:
                failed_step = step
                break

        system_prompt = REPLAN_SYSTEM_PROMPT.format(
            original_plan=json.dumps(plan.to_dict(), indent=2),
            failed_step=json.dumps(failed_step.to_dict() if failed_step else {}, indent=2),
            error=error,
            completed_steps=json.dumps(completed_steps),
        )

        response = await self.llm_client.generate(
            prompt="Create a recovery plan to complete the task.",
            system=system_prompt,
            model=self.model,
            temperature=self.temperature,
        )

        # Parse recovery plan
        recovery_plan = self._parse_plan_response(response, plan.original_task)
        recovery_plan.plan_id = f"{plan.plan_id}-recovery"

        logger.info(f"Created recovery plan with {len(recovery_plan.steps)} steps")

        return recovery_plan

    def _parse_plan_response(
        self,
        response: str,
        original_task: str,
    ) -> TaskPlan:
        """Parse LLM response into TaskPlan.

        Args:
            response: Raw LLM response
            original_task: Original task description

        Returns:
            Parsed TaskPlan
        """
        # Try to extract JSON from response
        try:
            # Clean response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove markdown code block
                lines = cleaned.split("\n")
                # Skip first line (```json) and last line (```)
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                cleaned = "\n".join(json_lines)

            # Parse JSON
            data = json.loads(cleaned)
            return TaskPlan.from_dict(data)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")

            # Create minimal fallback plan
            return TaskPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                original_task=original_task,
                steps=[
                    PlannedStep(
                        step_id="step-1",
                        action="navigate",
                        description=f"Attempt task: {original_task}",
                        data={"raw_response": response[:500]},
                    )
                ],
                confidence_score=0.3,
            )

    def _validate_plan(
        self,
        plan: TaskPlan,
        starting_url: str | None,
    ) -> TaskPlan:
        """Validate and fix plan issues.

        Args:
            plan: Plan to validate
            starting_url: Expected starting URL

        Returns:
            Validated/fixed TaskPlan
        """
        # Ensure first step is navigate if URL provided and not already present
        if starting_url and plan.steps:
            first_step = plan.steps[0]
            if first_step.action != "navigate" or not first_step.url:
                # Insert navigate step at beginning
                nav_step = PlannedStep(
                    step_id="step-0",
                    action="navigate",
                    description="Navigate to starting URL",
                    url=starting_url,
                    estimated_duration_seconds=3,
                )
                plan.steps.insert(0, nav_step)

                # Update depends_on for step-1
                if len(plan.steps) > 1:
                    plan.steps[1].depends_on = ["step-0"]

        # Ensure unique step IDs
        seen_ids = set()
        for i, step in enumerate(plan.steps):
            if step.step_id in seen_ids:
                step.step_id = f"step-{i + 1}"
            seen_ids.add(step.step_id)

        # Enforce max steps
        if len(plan.steps) > self.max_steps:
            logger.warning(
                f"Plan exceeds max steps ({len(plan.steps)} > {self.max_steps}), truncating"
            )
            plan.steps = plan.steps[: self.max_steps]

        # Recalculate total duration
        plan.estimated_total_duration = sum(s.estimated_duration_seconds for s in plan.steps)

        return plan


# Convenience function for testing
async def test_planner():
    """Test the planning engine."""
    from src.infrastructure.llm.ollama_client import OllamaClient

    client = OllamaClient()
    planner = TaskPlanningEngine(llm_client=client)

    # Test planning
    plan = await planner.create_plan(
        task_description="Go to news.ycombinator.com and extract the top 5 article titles",
        starting_url="https://news.ycombinator.com",
    )

    print(json.dumps(plan.to_dict(), indent=2))

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_planner())
