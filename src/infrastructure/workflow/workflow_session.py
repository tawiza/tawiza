"""
Multi-step workflow automation with session memory.

Features:
- Session state management across multiple steps
- Conditional logic and branching
- Loop support (retry, iterate over items)
- Error recovery and rollback
- Workflow persistence and resumption
- Variables and data passing between steps
"""

import ast
import asyncio
import json
import operator
from collections.abc import Callable
from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel, Field


class SafeExpressionEvaluator:
    """
    Safe expression evaluator that prevents arbitrary code execution.

    Only allows:
    - Comparison operators: ==, !=, <, >, <=, >=
    - Boolean operators: and, or, not
    - Arithmetic operators: +, -, *, /, %, **
    - Literals: numbers, strings, booleans, None
    - Variable references (from session memory)
    """

    # Allowed operators
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Not: operator.not_,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(self, variables: dict[str, Any]):
        """
        Initialize evaluator with available variables.

        Args:
            variables: Dictionary of variable names to values
        """
        self.variables = variables

    def evaluate(self, expression: str) -> Any:
        """
        Safely evaluate an expression.

        Args:
            expression: Expression to evaluate

        Returns:
            Evaluation result

        Raises:
            ValueError: If expression contains disallowed operations
            SyntaxError: If expression is invalid Python
        """
        # Parse expression into AST
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {e}")

        # Evaluate the AST
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Constant):
            # Literal value (number, string, True, False, None)
            return node.value

        elif isinstance(node, ast.Name):
            # Variable reference
            var_name = node.id
            if var_name not in self.variables:
                raise ValueError(f"Undefined variable: {var_name}")
            return self.variables[var_name]

        elif isinstance(node, ast.BinOp):
            # Binary operation (a + b, a == b, etc.)
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ValueError(f"Disallowed operator: {op_type.__name__}")

            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.OPERATORS[op_type](left, right)

        elif isinstance(node, ast.UnaryOp):
            # Unary operation (not a, -a, etc.)
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ValueError(f"Disallowed operator: {op_type.__name__}")

            operand = self._eval_node(node.operand)
            return self.OPERATORS[op_type](operand)

        elif isinstance(node, ast.Compare):
            # Comparison (a < b, a == b, etc.)
            left = self._eval_node(node.left)

            # Handle chained comparisons (a < b < c)
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                op_type = type(op)
                if op_type not in self.OPERATORS:
                    raise ValueError(f"Disallowed operator: {op_type.__name__}")

                right = self._eval_node(comparator)
                result = self.OPERATORS[op_type](left, right)

                if not result:
                    return False

                left = right

            return True

        elif isinstance(node, ast.BoolOp):
            # Boolean operation (a and b, a or b)
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ValueError(f"Disallowed operator: {op_type.__name__}")

            # Evaluate all values
            values = [self._eval_node(v) for v in node.values]

            # Apply operator
            if isinstance(node.op, ast.And):
                return all(values)
            elif isinstance(node.op, ast.Or):
                return any(values)

        else:
            raise ValueError(f"Disallowed AST node type: {type(node).__name__}")

    @staticmethod
    def validate_expression(expression: str) -> bool:
        """
        Validate expression syntax without evaluating.

        Args:
            expression: Expression to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            ast.parse(expression, mode='eval')
            return True
        except SyntaxError:
            return False


class WorkflowState(StrEnum):
    """Workflow execution state."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    step_id: str
    name: str
    description: str | None = None
    action: str  # The action to perform
    params: dict[str, Any] = Field(default_factory=dict)
    condition: str | None = None  # JavaScript condition to check before executing
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    on_success: str | None = None  # Next step ID on success
    on_failure: str | None = None  # Next step ID on failure
    status: str = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SessionMemory(BaseModel):
    """Session memory for storing data between steps."""

    variables: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """Set a variable in session memory."""
        self.variables[key] = value
        logger.debug(f"Session variable set: {key} = {value}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a variable from session memory."""
        return self.variables.get(key, default)

    def has(self, key: str) -> bool:
        """Check if variable exists."""
        return key in self.variables

    def delete(self, key: str) -> bool:
        """Delete a variable."""
        if key in self.variables:
            del self.variables[key]
            logger.debug(f"Session variable deleted: {key}")
            return True
        return False

    def record_action(
        self,
        action: str,
        data: dict[str, Any],
    ) -> None:
        """Record an action in history."""
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "data": data,
        })

    def clear(self) -> None:
        """Clear all session data."""
        self.variables.clear()
        self.history.clear()
        logger.info("Session memory cleared")


class WorkflowSession:
    """
    Manage complex multi-step workflows with session state.

    Features:
    - Sequential and conditional step execution
    - Loop support for retries and iterations
    - Session memory for data persistence
    - Checkpoint and resume capability
    - Error recovery strategies
    """

    def __init__(
        self,
        session_id: UUID | None = None,
        name: str | None = None,
        persist_dir: Path | None = None,
    ):
        """
        Initialize workflow session.

        Args:
            session_id: Unique session identifier
            name: Human-readable session name
            persist_dir: Directory for persisting session state
        """
        self.session_id = session_id or uuid4()
        self.name = name or f"workflow_{self.session_id}"
        self.persist_dir = persist_dir or Path("./.workflow_sessions")
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.state = WorkflowState.PENDING
        self.steps: list[WorkflowStep] = []
        self.current_step_index = 0
        self.memory = SessionMemory()

        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

        logger.info(f"WorkflowSession created: {self.name} ({self.session_id})")

    def add_step(
        self,
        name: str,
        action: str,
        params: dict[str, Any] | None = None,
        **kwargs
    ) -> WorkflowStep:
        """
        Add a step to the workflow.

        Args:
            name: Step name
            action: Action to perform
            params: Action parameters
            **kwargs: Additional step configuration

        Returns:
            Created WorkflowStep
        """
        step = WorkflowStep(
            step_id=f"step_{len(self.steps) + 1}",
            name=name,
            action=action,
            params=params or {},
            **kwargs
        )

        self.steps.append(step)
        logger.info(f"Added step: {step.name} ({step.step_id})")

        return step

    def add_loop(
        self,
        items: list[Any],
        action: str,
        item_var_name: str = "item",
    ) -> list[WorkflowStep]:
        """
        Add a loop over items.

        Args:
            items: List of items to iterate over
            action: Action to perform for each item
            item_var_name: Variable name for current item

        Returns:
            List of created steps
        """
        created_steps = []

        for i, item in enumerate(items):
            step = self.add_step(
                name=f"Loop iteration {i + 1}",
                action=action,
                params={item_var_name: item},
            )
            created_steps.append(step)

        logger.info(f"Added loop with {len(items)} iterations")
        return created_steps

    def add_conditional_branch(
        self,
        condition: str,
        if_true_action: str,
        if_false_action: str | None = None,
    ) -> tuple[WorkflowStep, WorkflowStep | None]:
        """
        Add a conditional branch.

        Args:
            condition: JavaScript condition to evaluate
            if_true_action: Action if condition is true
            if_false_action: Action if condition is false

        Returns:
            Tuple of (true_step, false_step)
        """
        true_step = self.add_step(
            name="Condition: True branch",
            action=if_true_action,
            condition=condition,
        )

        false_step = None
        if if_false_action:
            false_step = self.add_step(
                name="Condition: False branch",
                action=if_false_action,
                condition=f"!({condition})",
            )

        logger.info("Added conditional branch")
        return (true_step, false_step)

    async def execute(
        self,
        executor: Callable[[WorkflowStep, SessionMemory], Any],
        auto_save: bool = True,
    ) -> bool:
        """
        Execute the workflow.

        Args:
            executor: Async function that executes a step
            auto_save: Automatically save session state after each step

        Returns:
            True if completed successfully, False otherwise
        """
        self.state = WorkflowState.RUNNING
        self.started_at = datetime.now()

        logger.info(f"Starting workflow: {self.name} ({len(self.steps)} steps)")

        try:
            while self.current_step_index < len(self.steps):
                step = self.steps[self.current_step_index]

                # Check if step should be executed (condition)
                if step.condition:
                    should_execute = await self._evaluate_condition(step.condition)
                    if not should_execute:
                        logger.info(f"Skipping step {step.name} (condition not met)")
                        step.status = "skipped"
                        self.current_step_index += 1
                        continue

                # Execute step with retry logic
                success = await self._execute_step(step, executor)

                # Save session state if auto_save enabled
                if auto_save:
                    self.save()

                # Handle step result
                if success:
                    if step.on_success:
                        # Jump to specific step
                        self.current_step_index = self._find_step_index(step.on_success)
                    else:
                        # Move to next step
                        self.current_step_index += 1
                else:
                    if step.on_failure:
                        # Jump to failure handler
                        self.current_step_index = self._find_step_index(step.on_failure)
                    else:
                        # Workflow failed
                        logger.error(f"Workflow failed at step: {step.name}")
                        self.state = WorkflowState.FAILED
                        return False

            # All steps completed
            self.state = WorkflowState.COMPLETED
            self.completed_at = datetime.now()

            duration = (self.completed_at - self.started_at).total_seconds()
            logger.success(f"Workflow completed in {duration:.1f}s")

            return True

        except Exception as e:
            logger.exception(f"Workflow error: {e}")
            self.state = WorkflowState.FAILED
            return False

    async def _execute_step(
        self,
        step: WorkflowStep,
        executor: Callable,
    ) -> bool:
        """Execute a single step with retry logic."""
        step.status = "running"
        step.started_at = datetime.now()

        logger.info(f"Executing step: {step.name}")

        for attempt in range(step.max_retries + 1):
            try:
                # Execute step
                result = await asyncio.wait_for(
                    executor(step, self.memory),
                    timeout=step.timeout
                )

                # Store result
                step.result = result if isinstance(result, dict) else {"value": result}
                step.status = "completed"
                step.completed_at = datetime.now()

                # Record in memory
                self.memory.record_action(step.action, step.result)

                logger.success(f"Step completed: {step.name}")
                return True

            except TimeoutError:
                logger.warning(f"Step timeout: {step.name} (attempt {attempt + 1})")
                step.error = f"Timeout after {step.timeout}s"

            except Exception as e:
                logger.warning(f"Step error: {step.name} (attempt {attempt + 1}): {e}")
                step.error = str(e)

            # Retry if not last attempt
            if attempt < step.max_retries:
                step.retry_count += 1
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries exhausted
        step.status = "failed"
        step.completed_at = datetime.now()
        logger.error(f"Step failed after {step.max_retries + 1} attempts: {step.name}")
        return False

    async def _evaluate_condition(self, condition: str) -> bool:
        """
        Safely evaluate a condition using session memory.

        Uses SafeExpressionEvaluator to prevent arbitrary code execution.
        Only allows safe operations: comparisons, arithmetic, boolean logic.

        Args:
            condition: Python expression to evaluate

        Returns:
            Boolean result of evaluation
        """
        try:
            # Create safe evaluator with session variables
            evaluator = SafeExpressionEvaluator(self.memory.variables)

            # Evaluate condition safely
            result = evaluator.evaluate(condition)
            return bool(result)

        except (ValueError, SyntaxError) as e:
            logger.error(f"Condition evaluation error: {e}")
            logger.warning(f"Potentially unsafe or invalid condition: {condition}")
            return False
        except Exception as e:
            logger.error(f"Unexpected condition evaluation error: {e}")
            return False

    def _find_step_index(self, step_id: str) -> int:
        """Find step index by ID."""
        for i, step in enumerate(self.steps):
            if step.step_id == step_id:
                return i

        raise ValueError(f"Step not found: {step_id}")

    def pause(self) -> None:
        """Pause workflow execution."""
        self.state = WorkflowState.PAUSED
        logger.info(f"Workflow paused: {self.name}")

    def resume(self) -> None:
        """Resume paused workflow."""
        if self.state == WorkflowState.PAUSED:
            self.state = WorkflowState.RUNNING
            logger.info(f"Workflow resumed: {self.name}")

    def cancel(self) -> None:
        """Cancel workflow execution."""
        self.state = WorkflowState.CANCELLED
        logger.info(f"Workflow cancelled: {self.name}")

    def save(self) -> Path:
        """
        Save workflow session to disk.

        Returns:
            Path to saved session file
        """
        session_file = self.persist_dir / f"{self.session_id}.json"

        data = {
            "session_id": str(self.session_id),
            "name": self.name,
            "state": self.state,
            "steps": [step.model_dump() for step in self.steps],
            "current_step_index": self.current_step_index,
            "memory": self.memory.model_dump(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

        session_file.write_text(json.dumps(data, indent=2))
        logger.debug(f"Session saved: {session_file}")

        return session_file

    @classmethod
    def load(cls, session_id: UUID, persist_dir: Path | None = None) -> "WorkflowSession":
        """
        Load workflow session from disk.

        Args:
            session_id: Session ID to load
            persist_dir: Directory containing session files

        Returns:
            Loaded WorkflowSession
        """
        persist_dir = persist_dir or Path("./.workflow_sessions")
        session_file = persist_dir / f"{session_id}.json"

        if not session_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        data = json.loads(session_file.read_text())

        session = cls(
            session_id=UUID(data["session_id"]),
            name=data["name"],
            persist_dir=persist_dir,
        )

        session.state = WorkflowState(data["state"])
        session.steps = [WorkflowStep(**step) for step in data["steps"]]
        session.current_step_index = data["current_step_index"]
        session.memory = SessionMemory(**data["memory"])

        session.created_at = datetime.fromisoformat(data["created_at"])
        if data["started_at"]:
            session.started_at = datetime.fromisoformat(data["started_at"])
        if data["completed_at"]:
            session.completed_at = datetime.fromisoformat(data["completed_at"])

        logger.info(f"Session loaded: {session.name} ({session_id})")
        return session

    def get_progress(self) -> dict[str, Any]:
        """Get workflow progress information."""
        completed_steps = sum(1 for s in self.steps if s.status == "completed")
        failed_steps = sum(1 for s in self.steps if s.status == "failed")
        total_steps = len(self.steps)

        return {
            "total_steps": total_steps,
            "completed": completed_steps,
            "failed": failed_steps,
            "current_step": self.current_step_index + 1,
            "progress_percent": round((completed_steps / total_steps) * 100, 1) if total_steps > 0 else 0,
            "state": self.state,
        }


# Convenience function
_active_sessions: dict[UUID, WorkflowSession] = {}


def get_workflow_session(
    session_id: UUID | None = None,
    name: str | None = None,
) -> WorkflowSession:
    """
    Get or create a workflow session.

    Args:
        session_id: Existing session ID to retrieve, or None for new session
        name: Session name (for new sessions)

    Returns:
        WorkflowSession instance
    """
    if session_id and session_id in _active_sessions:
        return _active_sessions[session_id]

    session = WorkflowSession(session_id=session_id, name=name)
    _active_sessions[session.session_id] = session

    return session


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def example_executor(step: WorkflowStep, memory: SessionMemory) -> dict[str, Any]:
        """Example step executor."""
        logger.info(f"Executing: {step.action} with {step.params}")
        await asyncio.sleep(1)  # Simulate work

        # Access memory
        count = memory.get("counter", 0)
        memory.set("counter", count + 1)

        return {"success": True, "count": count + 1}

    async def demo():
        # Create workflow
        session = WorkflowSession(name="Example Workflow")

        # Add steps
        session.add_step("Initialize", "init", {"config": "value"})
        session.add_step("Process data", "process", {"data": [1, 2, 3]})
        session.add_step("Save results", "save", {"output": "results.json"})

        # Execute
        success = await session.execute(example_executor)
        print(f"Workflow completed: {success}")
        print(f"Progress: {session.get_progress()}")

        # Save session
        session.save()

    # asyncio.run(demo())
