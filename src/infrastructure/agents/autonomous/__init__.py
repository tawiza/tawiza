"""Autonomous agent infrastructure for intelligent web automation.

This module provides:
- TaskPlanningEngine: LLM-based task decomposition
- StepExecutor: Step-by-step execution with error recovery
- ExecutionStateManager: State persistence for pause/resume
"""

from src.infrastructure.agents.autonomous.execution_state import (
    ExecutionContext,
    ExecutionStateManager,
)
from src.infrastructure.agents.autonomous.step_executor import (
    StepExecutor,
    StepResult,
)
from src.infrastructure.agents.autonomous.task_planner import (
    PlannedStep,
    TaskPlan,
    TaskPlanningEngine,
)

__all__ = [
    "TaskPlanningEngine",
    "TaskPlan",
    "PlannedStep",
    "StepExecutor",
    "StepResult",
    "ExecutionStateManager",
    "ExecutionContext",
]
