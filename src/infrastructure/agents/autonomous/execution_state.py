"""Execution state management for autonomous agent.

Handles state persistence for pause/resume functionality and execution tracking.
"""

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from loguru import logger


class PlanStatus(StrEnum):
    """Status of a plan execution."""
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionContext:
    """Current execution context/state."""
    plan_id: str
    current_url: str | None = None
    page_html: str | None = None
    last_screenshot_path: str | None = None
    extracted_data: dict[str, Any] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    current_step_index: int = 0
    status: str = PlanStatus.DRAFT.value
    started_at: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionContext":
        """Create from dictionary."""
        return cls(
            plan_id=data.get("plan_id", "unknown"),
            current_url=data.get("current_url"),
            page_html=data.get("page_html"),
            last_screenshot_path=data.get("last_screenshot_path"),
            extracted_data=data.get("extracted_data", {}),
            completed_steps=data.get("completed_steps", []),
            failed_steps=data.get("failed_steps", []),
            screenshots=data.get("screenshots", []),
            current_step_index=data.get("current_step_index", 0),
            status=data.get("status", PlanStatus.DRAFT.value),
            started_at=data.get("started_at"),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            error_message=data.get("error_message"),
        )

    def mark_step_completed(self, step_id: str, result_data: dict | None = None):
        """Mark a step as completed and store its result."""
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        if result_data:
            self.extracted_data[step_id] = result_data
        self.current_step_index += 1
        self.updated_at = datetime.utcnow().isoformat()

    def mark_step_failed(self, step_id: str, error: str):
        """Mark a step as failed."""
        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)
        self.error_message = error
        self.updated_at = datetime.utcnow().isoformat()

    def update_url(self, url: str):
        """Update current URL."""
        self.current_url = url
        self.updated_at = datetime.utcnow().isoformat()

    def add_screenshot(self, path: str):
        """Add screenshot path."""
        self.screenshots.append(path)
        self.last_screenshot_path = path
        self.updated_at = datetime.utcnow().isoformat()


@dataclass
class ExecutionRecord:
    """Record of a plan execution for history."""
    plan_id: str
    original_task: str
    status: str
    steps_total: int
    steps_completed: int
    started_at: str
    completed_at: str | None
    duration_seconds: float
    result_summary: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionRecord":
        """Create from dictionary."""
        return cls(
            plan_id=data.get("plan_id", "unknown"),
            original_task=data.get("original_task", ""),
            status=data.get("status", "unknown"),
            steps_total=data.get("steps_total", 0),
            steps_completed=data.get("steps_completed", 0),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds", 0.0),
            result_summary=data.get("result_summary"),
            error=data.get("error"),
        )


class ExecutionStateManager:
    """Manages execution state persistence.

    Handles:
    - Saving/loading execution state for pause/resume
    - Maintaining execution history
    - Providing recent execution listings
    """

    def __init__(
        self,
        state_dir: str = "/tmp/tawiza-agent-state",
        max_history: int = 50,
    ):
        """Initialize state manager.

        Args:
            state_dir: Directory for state files
            max_history: Maximum history records to keep
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history

        # Subdirectories
        self.contexts_dir = self.state_dir / "contexts"
        self.history_dir = self.state_dir / "history"
        self.plans_dir = self.state_dir / "plans"

        self.contexts_dir.mkdir(exist_ok=True)
        self.history_dir.mkdir(exist_ok=True)
        self.plans_dir.mkdir(exist_ok=True)

        logger.info(f"ExecutionStateManager initialized at {state_dir}")

    async def save_context(self, context: ExecutionContext) -> None:
        """Save execution context to disk.

        Args:
            context: Context to save
        """
        filepath = self.contexts_dir / f"{context.plan_id}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(context.to_dict(), f, indent=2)

            logger.debug(f"Saved context for plan {context.plan_id}")

        except Exception as e:
            logger.error(f"Failed to save context: {e}")
            raise

    async def load_context(self, plan_id: str) -> ExecutionContext | None:
        """Load execution context from disk.

        Args:
            plan_id: Plan ID to load

        Returns:
            ExecutionContext or None if not found
        """
        filepath = self.contexts_dir / f"{plan_id}.json"

        if not filepath.exists():
            logger.debug(f"No context found for plan {plan_id}")
            return None

        try:
            with open(filepath) as f:
                data = json.load(f)

            context = ExecutionContext.from_dict(data)
            logger.debug(f"Loaded context for plan {plan_id}")

            return context

        except Exception as e:
            logger.error(f"Failed to load context: {e}")
            return None

    async def delete_context(self, plan_id: str) -> bool:
        """Delete execution context.

        Args:
            plan_id: Plan ID to delete

        Returns:
            True if deleted
        """
        filepath = self.contexts_dir / f"{plan_id}.json"

        if filepath.exists():
            filepath.unlink()
            logger.debug(f"Deleted context for plan {plan_id}")
            return True

        return False

    async def save_plan(self, plan: Any) -> None:
        """Save plan to disk.

        Args:
            plan: TaskPlan to save
        """
        filepath = self.plans_dir / f"{plan.plan_id}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(plan.to_dict(), f, indent=2)

            logger.debug(f"Saved plan {plan.plan_id}")

        except Exception as e:
            logger.error(f"Failed to save plan: {e}")

    async def load_plan(self, plan_id: str) -> dict[str, Any] | None:
        """Load plan from disk.

        Args:
            plan_id: Plan ID to load

        Returns:
            Plan dict or None
        """
        filepath = self.plans_dir / f"{plan_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath) as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load plan: {e}")
            return None

    async def add_execution_record(self, record: ExecutionRecord) -> None:
        """Add execution record to history.

        Args:
            record: Record to add
        """
        filepath = self.history_dir / f"{record.plan_id}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(record.to_dict(), f, indent=2)

            # Cleanup old history
            await self._cleanup_history()

            logger.debug(f"Added execution record for {record.plan_id}")

        except Exception as e:
            logger.error(f"Failed to add execution record: {e}")

    async def get_recent_executions(
        self,
        limit: int = 10,
        status: str | None = None,
    ) -> list[ExecutionRecord]:
        """Get recent execution records.

        Args:
            limit: Maximum records to return
            status: Filter by status

        Returns:
            List of ExecutionRecord sorted by date (newest first)
        """
        records = []

        try:
            for filepath in self.history_dir.glob("*.json"):
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                        record = ExecutionRecord.from_dict(data)

                        if status is None or record.status == status:
                            records.append(record)

                except Exception as e:
                    logger.warning(f"Failed to load record {filepath}: {e}")

            # Sort by start time (newest first)
            records.sort(key=lambda r: r.started_at, reverse=True)

            return records[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent executions: {e}")
            return []

    async def get_execution_status(self, plan_id: str) -> dict[str, Any] | None:
        """Get status of a specific execution.

        Args:
            plan_id: Plan ID to check

        Returns:
            Status dict with context and/or record
        """
        result: dict[str, Any] = {"plan_id": plan_id}

        # Check for active context
        context = await self.load_context(plan_id)
        if context:
            result["context"] = context.to_dict()
            result["status"] = context.status
            result["is_active"] = context.status in [
                PlanStatus.EXECUTING.value,
                PlanStatus.PAUSED.value,
            ]

        # Check history
        history_path = self.history_dir / f"{plan_id}.json"
        if history_path.exists():
            with open(history_path) as f:
                result["record"] = json.load(f)
                if "status" not in result:
                    result["status"] = result["record"].get("status")

        if "status" not in result:
            return None

        return result

    async def get_active_executions(self) -> list[ExecutionContext]:
        """Get all currently active (executing/paused) executions.

        Returns:
            List of active ExecutionContext
        """
        active = []

        for filepath in self.contexts_dir.glob("*.json"):
            try:
                context = await self.load_context(filepath.stem)
                if context and context.status in [
                    PlanStatus.EXECUTING.value,
                    PlanStatus.PAUSED.value,
                ]:
                    active.append(context)

            except Exception as e:
                logger.warning(f"Failed to check context {filepath}: {e}")

        return active

    async def _cleanup_history(self) -> None:
        """Remove old history records beyond max_history."""
        try:
            records = await self.get_recent_executions(limit=self.max_history + 10)

            if len(records) > self.max_history:
                # Remove oldest records
                for record in records[self.max_history:]:
                    filepath = self.history_dir / f"{record.plan_id}.json"
                    if filepath.exists():
                        filepath.unlink()
                        logger.debug(f"Cleaned up old record: {record.plan_id}")

        except Exception as e:
            logger.warning(f"History cleanup failed: {e}")


# Convenience function for testing
async def test_state_manager():
    """Test the state manager."""
    manager = ExecutionStateManager()

    # Create test context
    context = ExecutionContext(
        plan_id="test-plan-123",
        current_url="https://example.com",
        status=PlanStatus.EXECUTING.value,
        started_at=datetime.utcnow().isoformat(),
    )

    # Save and load
    await manager.save_context(context)
    loaded = await manager.load_context("test-plan-123")

    print(f"Loaded context: {loaded}")

    # Add execution record
    record = ExecutionRecord(
        plan_id="test-plan-123",
        original_task="Test task",
        status=PlanStatus.COMPLETED.value,
        steps_total=5,
        steps_completed=5,
        started_at=datetime.utcnow().isoformat(),
        completed_at=datetime.utcnow().isoformat(),
        duration_seconds=10.5,
    )

    await manager.add_execution_record(record)

    # Get recent
    recent = await manager.get_recent_executions()
    print(f"Recent executions: {len(recent)}")


if __name__ == "__main__":
    asyncio.run(test_state_manager())
