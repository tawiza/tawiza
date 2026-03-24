"""Autonomous agent service for orchestrating intelligent web automation.

This service coordinates:
- Task planning via LLM
- Plan validation by user
- Step-by-step execution with progress callbacks
- Error handling and recovery
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.agents.autonomous.execution_state import (
    ExecutionContext,
    ExecutionRecord,
    ExecutionStateManager,
    PlanStatus,
)
from src.infrastructure.agents.autonomous.step_executor import StepExecutor, StepResult
from src.infrastructure.agents.autonomous.task_planner import (
    PlannedStep,
    TaskPlan,
    TaskPlanningEngine,
)


class AutonomousAgentService:
    """Orchestrates autonomous web automation tasks.

    Coordinates planning, execution, and state management for
    LLM-guided browser automation.

    Usage:
        service = AutonomousAgentService(planner, executor, state_manager)

        # Create plan from natural language
        plan = await service.plan_task("Extract top articles from HackerNews")

        # Execute with callbacks
        result = await service.execute_plan(plan, callbacks={
            "on_step_start": lambda step: print(f"Starting {step.step_id}"),
            "on_step_complete": lambda step, result: print(f"Done {step.step_id}"),
            "on_error": lambda step, error: print(f"Error: {error}"),
        })
    """

    def __init__(
        self,
        planner: TaskPlanningEngine,
        executor: StepExecutor,
        state_manager: ExecutionStateManager,
    ):
        """Initialize autonomous agent service.

        Args:
            planner: Task planning engine
            executor: Step executor
            state_manager: Execution state manager
        """
        self.planner = planner
        self.executor = executor
        self.state_manager = state_manager

        # Active executions (plan_id -> context)
        self._active_contexts: dict[str, ExecutionContext] = {}
        self._cancel_flags: dict[str, bool] = {}

        logger.info("AutonomousAgentService initialized")

    async def plan_task(
        self,
        task: str,
        starting_url: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskPlan:
        """Create execution plan from natural language task.

        Args:
            task: Natural language task description
            starting_url: Optional starting URL
            context: Additional context

        Returns:
            TaskPlan with executable steps
        """
        logger.info(f"Planning task: {task[:100]}...")

        plan = await self.planner.create_plan(
            task_description=task,
            starting_url=starting_url,
            context=context,
        )

        # Save plan for future reference
        await self.state_manager.save_plan(plan)

        logger.info(f"Created plan {plan.plan_id} with {len(plan.steps)} steps")

        return plan

    async def execute_plan(
        self,
        plan: TaskPlan,
        callbacks: dict[str, Callable] | None = None,
        dry_run: bool = False,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Execute a validated plan.

        Args:
            plan: Plan to execute
            callbacks: Optional callbacks for UI updates:
                - on_step_start(step: PlannedStep)
                - on_step_complete(step: PlannedStep, result: StepResult)
                - on_error(step: PlannedStep, error: str)
                - on_progress(current: int, total: int, step: PlannedStep)
            dry_run: If True, simulate without browser interaction
            max_retries: Max retries per failed step

        Returns:
            Execution result dict with status and data
        """
        callbacks = callbacks or {}

        # Initialize execution context
        context = ExecutionContext(
            plan_id=plan.plan_id,
            status=PlanStatus.EXECUTING.value,
            started_at=datetime.utcnow().isoformat(),
        )

        self._active_contexts[plan.plan_id] = context
        self._cancel_flags[plan.plan_id] = False

        # Save initial state
        await self.state_manager.save_context(context)

        total_steps = len(plan.steps)
        results: dict[str, StepResult] = {}
        start_time = datetime.utcnow()

        logger.info(
            f"Starting execution of plan {plan.plan_id} ({total_steps} steps, dry_run={dry_run})"
        )

        try:
            for i, step in enumerate(plan.steps):
                # Check for cancellation
                if self._cancel_flags.get(plan.plan_id, False):
                    logger.info(f"Execution cancelled at step {step.step_id}")
                    context.status = PlanStatus.CANCELLED.value
                    break

                # Progress callback
                if "on_progress" in callbacks:
                    callbacks["on_progress"](i + 1, total_steps, step)

                # Start callback
                if "on_step_start" in callbacks:
                    callbacks["on_step_start"](step)

                # Execute with retries
                result = await self._execute_step_with_retry(
                    step=step,
                    context=context,
                    dry_run=dry_run,
                    max_retries=max_retries,
                    on_error=callbacks.get("on_error"),
                )

                results[step.step_id] = result

                # Update context based on result
                if result.is_success:
                    context.mark_step_completed(step.step_id, result.result_data)

                    # Update URL if navigate action
                    if result.result_data and "url" in result.result_data:
                        context.update_url(result.result_data["url"])

                    # Store screenshot
                    if result.screenshot_path:
                        context.add_screenshot(result.screenshot_path)

                else:
                    context.mark_step_failed(step.step_id, result.error_message or "Unknown error")

                    # Error callback
                    if "on_error" in callbacks:
                        callbacks["on_error"](step, result.error_message)

                    # Continue or stop based on step criticality
                    # For now, continue on error
                    logger.warning(f"Step {step.step_id} failed, continuing...")

                # Complete callback
                if "on_step_complete" in callbacks:
                    callbacks["on_step_complete"](step, result)

                # Save state after each step
                await self.state_manager.save_context(context)

            # Determine final status
            if context.status != PlanStatus.CANCELLED.value:
                failed_count = len(context.failed_steps)
                if failed_count == 0:
                    context.status = PlanStatus.COMPLETED.value
                elif failed_count < total_steps:
                    context.status = PlanStatus.COMPLETED.value  # Partial success
                else:
                    context.status = PlanStatus.FAILED.value

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            context.status = PlanStatus.FAILED.value
            context.error_message = str(e)

        finally:
            # Calculate duration
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            # Save final context
            context.updated_at = end_time.isoformat()
            await self.state_manager.save_context(context)

            # Create execution record
            record = ExecutionRecord(
                plan_id=plan.plan_id,
                original_task=plan.original_task,
                status=context.status,
                steps_total=total_steps,
                steps_completed=len(context.completed_steps),
                started_at=context.started_at or start_time.isoformat(),
                completed_at=end_time.isoformat(),
                duration_seconds=duration,
                result_summary={
                    "extracted_data": context.extracted_data,
                    "screenshots": context.screenshots,
                },
                error=context.error_message,
            )

            await self.state_manager.add_execution_record(record)

            # Cleanup
            if plan.plan_id in self._active_contexts:
                del self._active_contexts[plan.plan_id]
            if plan.plan_id in self._cancel_flags:
                del self._cancel_flags[plan.plan_id]

        logger.info(
            f"Execution completed: {context.status} "
            f"({len(context.completed_steps)}/{total_steps} steps in {duration:.1f}s)"
        )

        return {
            "plan_id": plan.plan_id,
            "status": context.status,
            "steps_completed": len(context.completed_steps),
            "steps_failed": len(context.failed_steps),
            "steps_total": total_steps,
            "duration_seconds": duration,
            "extracted_data": context.extracted_data,
            "screenshots": context.screenshots,
            "error": context.error_message,
            "results": {k: v.to_dict() for k, v in results.items()},
        }

    async def _execute_step_with_retry(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        dry_run: bool,
        max_retries: int,
        on_error: Callable | None = None,
    ) -> StepResult:
        """Execute step with retry logic.

        Args:
            step: Step to execute
            context: Current execution context
            dry_run: Dry run mode
            max_retries: Maximum retry attempts
            on_error: Error callback

        Returns:
            StepResult
        """
        last_result = None

        for attempt in range(max_retries + 1):
            result = await self.executor.execute_step(
                step=step,
                context=context,
                dry_run=dry_run,
            )

            if result.is_success:
                return result

            last_result = result

            if attempt < max_retries:
                logger.warning(
                    f"Step {step.step_id} failed (attempt {attempt + 1}/{max_retries + 1}), retrying..."
                )

                # Get recovery suggestion
                suggestion = await self.executor.get_recovery_suggestion(
                    step=step,
                    error=result.error_message or "Unknown error",
                    context=context,
                )

                logger.info(f"Recovery suggestion: {suggestion}")

                # Wait before retry
                await asyncio.sleep(1.0 * (attempt + 1))

        return last_result

    async def cancel_execution(self, plan_id: str) -> bool:
        """Cancel a running execution.

        Args:
            plan_id: Plan ID to cancel

        Returns:
            True if cancellation was requested
        """
        if plan_id in self._active_contexts:
            self._cancel_flags[plan_id] = True
            logger.info(f"Cancellation requested for {plan_id}")
            return True

        # Check if there's a saved context we can update
        context = await self.state_manager.load_context(plan_id)
        if context and context.status == PlanStatus.EXECUTING.value:
            context.status = PlanStatus.CANCELLED.value
            await self.state_manager.save_context(context)
            logger.info(f"Marked {plan_id} as cancelled")
            return True

        return False

    async def pause_execution(self, plan_id: str) -> bool:
        """Pause a running execution.

        Args:
            plan_id: Plan ID to pause

        Returns:
            True if paused
        """
        if plan_id in self._active_contexts:
            context = self._active_contexts[plan_id]
            context.status = PlanStatus.PAUSED.value
            await self.state_manager.save_context(context)

            self._cancel_flags[plan_id] = True  # Stop the loop
            logger.info(f"Paused execution {plan_id}")

            return True

        return False

    async def resume_execution(
        self,
        plan_id: str,
        callbacks: dict[str, Callable] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Resume a paused execution.

        Args:
            plan_id: Plan ID to resume
            callbacks: Callbacks for UI updates
            dry_run: Dry run mode

        Returns:
            Execution result
        """
        # Load context
        context = await self.state_manager.load_context(plan_id)
        if not context:
            raise ValueError(f"No saved context for plan {plan_id}")

        if context.status not in [PlanStatus.PAUSED.value, PlanStatus.FAILED.value]:
            raise ValueError(f"Cannot resume plan with status {context.status}")

        # Load plan
        plan_data = await self.state_manager.load_plan(plan_id)
        if not plan_data:
            raise ValueError(f"No saved plan for {plan_id}")

        plan = TaskPlan.from_dict(plan_data)

        # Filter remaining steps
        remaining_steps = [s for s in plan.steps if s.step_id not in context.completed_steps]

        if not remaining_steps:
            return {
                "plan_id": plan_id,
                "status": PlanStatus.COMPLETED.value,
                "message": "All steps already completed",
            }

        # Create new plan with remaining steps
        resume_plan = TaskPlan(
            plan_id=plan_id,
            original_task=plan.original_task,
            steps=remaining_steps,
            confidence_score=plan.confidence_score,
        )

        # Update context status
        context.status = PlanStatus.EXECUTING.value
        self._active_contexts[plan_id] = context

        logger.info(f"Resuming execution of {plan_id} from step {context.current_step_index}")

        return await self.execute_plan(
            plan=resume_plan,
            callbacks=callbacks,
            dry_run=dry_run,
        )

    async def get_execution_status(self, plan_id: str) -> dict[str, Any] | None:
        """Get status of an execution.

        Args:
            plan_id: Plan ID to check

        Returns:
            Status dict or None
        """
        # Check active context first
        if plan_id in self._active_contexts:
            context = self._active_contexts[plan_id]
            return {
                "plan_id": plan_id,
                "status": context.status,
                "is_active": True,
                "current_step_index": context.current_step_index,
                "completed_steps": len(context.completed_steps),
                "failed_steps": len(context.failed_steps),
            }

        # Fall back to state manager
        return await self.state_manager.get_execution_status(plan_id)

    async def list_recent_executions(
        self,
        limit: int = 10,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent executions.

        Args:
            limit: Maximum records
            status: Filter by status

        Returns:
            List of execution records
        """
        records = await self.state_manager.get_recent_executions(
            limit=limit,
            status=status,
        )

        return [r.to_dict() for r in records]


# Factory function for easy service creation
async def create_autonomous_agent_service(
    model: str = "qwen2.5:7b",
    headless: bool = True,
    state_dir: str = "/tmp/tawiza-agent-state",
) -> AutonomousAgentService:
    """Create autonomous agent service with default components.

    Args:
        model: LLM model to use
        headless: Browser headless mode
        state_dir: State directory

    Returns:
        Configured AutonomousAgentService
    """
    from src.infrastructure.agents.openmanus.openmanus_adapter import OpenManusAdapter
    from src.infrastructure.llm.ollama_client import OllamaClient

    # Create components with extended timeout for CoT models
    llm_client = OllamaClient(model=model, timeout=300)
    browser_agent = OpenManusAdapter(headless=headless, llm_client=llm_client)

    planner = TaskPlanningEngine(llm_client=llm_client, model=model)
    executor = StepExecutor(browser_agent=browser_agent, llm_client=llm_client)
    state_manager = ExecutionStateManager(state_dir=state_dir)

    return AutonomousAgentService(
        planner=planner,
        executor=executor,
        state_manager=state_manager,
    )
