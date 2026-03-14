"""Unified Agent Core with ReAct loop."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger

from .models import AgentResult, AgentStep, Observation, ToolCall
from .planner import ReActPlanner
from .tools import ToolRegistry


class AgentEvent(Enum):
    """Events emitted by the agent."""

    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class AgentCallback:
    """Callback data for agent events."""

    event: AgentEvent
    step: int
    total_steps: int
    thought: str = ""
    action: str = ""
    result: str = ""
    elapsed: float = 0.0
    progress: float = 0.0


class UnifiedAgent:
    """Unified agent using ReAct loop for task execution."""

    def __init__(
        self,
        planner: ReActPlanner,
        tools: ToolRegistry,
        max_steps: int = 20,
        verbose: bool = False,
        on_event: Callable[[AgentCallback], None] | None = None,
    ):
        """Initialize the unified agent.

        Args:
            planner: ReActPlanner instance for action planning
            tools: ToolRegistry instance for tool execution
            max_steps: Maximum number of steps before stopping
            verbose: Whether to log verbose output
            on_event: Optional callback for agent events
        """
        self.planner = planner
        self.tools = tools
        self.max_steps = max_steps
        self.verbose = verbose
        self.on_event = on_event

    def _emit(self, callback: AgentCallback):
        """Emit an event to the callback if set."""
        if self.on_event:
            self.on_event(callback)

    async def run(
        self,
        task: str,
        data: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute the task using ReAct loop.

        Args:
            task: The task description to accomplish
            data: Optional data context (e.g., file path)
            context: Optional additional context dictionary

        Returns:
            AgentResult with success status, answer, and execution history
        """
        start_time = time.time()

        # Initialize context
        if context is None:
            context = {}
        if data is not None:
            context["data"] = data

        # Initialize history
        history: list[dict[str, Any]] = []
        steps: list[AgentStep] = []

        logger.info(f"Starting agent task: {task}")

        # Get tools description once
        tools_description = self.tools.get_tools_description()

        # Main ReAct loop
        for step_num in range(1, self.max_steps + 1):
            elapsed = time.time() - start_time
            progress = step_num / self.max_steps

            if self.verbose:
                logger.info(f"--- Step {step_num}/{self.max_steps} ---")

            # Emit thinking event
            self._emit(
                AgentCallback(
                    event=AgentEvent.THINKING,
                    step=step_num,
                    total_steps=self.max_steps,
                    thought="Planning next action...",
                    elapsed=elapsed,
                    progress=progress,
                )
            )

            try:
                # Plan next action
                plan_result = await self.planner.plan_next_action(
                    task=task,
                    history=history,
                    tools_description=tools_description,
                    context=context,
                )

                thought = plan_result.thought
                tool_call = plan_result.tool_call

                if self.verbose:
                    logger.info(f"Thought: {thought}")
                    logger.info(f"Tool: {tool_call.name}({tool_call.params})")

                # Emit acting event with thought
                self._emit(
                    AgentCallback(
                        event=AgentEvent.ACTING,
                        step=step_num,
                        total_steps=self.max_steps,
                        thought=thought,
                        action=f"{tool_call.name}({tool_call.params})",
                        elapsed=time.time() - start_time,
                        progress=progress,
                    )
                )

                # Check if agent wants to finish
                if tool_call.name == "finish":
                    # Handle both "answer" and "result" params (LLM may use either)
                    answer = tool_call.params.get("answer") or tool_call.params.get("result", "")
                    if self.verbose:
                        logger.success(f"Agent finished: {answer}")

                    # Emit finished event
                    self._emit(
                        AgentCallback(
                            event=AgentEvent.FINISHED,
                            step=step_num,
                            total_steps=step_num,
                            thought=thought,
                            result=answer,
                            elapsed=time.time() - start_time,
                            progress=1.0,
                        )
                    )

                    # Create final step
                    observation = Observation(
                        tool_name="finish",
                        result=answer,
                        success=True,
                        duration_seconds=0.0,
                    )
                    final_step = AgentStep(
                        thought=thought,
                        tool_call=tool_call,
                        observation=observation,
                    )
                    steps.append(final_step)

                    duration = time.time() - start_time
                    return AgentResult(
                        success=True,
                        answer=answer,
                        steps=steps,
                        duration_seconds=duration,
                    )

                # Execute tool
                observation = await self._execute_tool(tool_call)

                # Emit observing event
                self._emit(
                    AgentCallback(
                        event=AgentEvent.OBSERVING,
                        step=step_num,
                        total_steps=self.max_steps,
                        thought=thought,
                        action=tool_call.name,
                        result=str(observation.result)[:100] if observation.result else "",
                        elapsed=time.time() - start_time,
                        progress=progress,
                    )
                )

                # Create and store step
                agent_step = AgentStep(
                    thought=thought,
                    tool_call=tool_call,
                    observation=observation,
                )
                steps.append(agent_step)

                # Add to history for next iteration
                history.append(
                    {
                        "thought": thought,
                        "tool_call": tool_call,
                        "observation": observation,
                    }
                )

                if self.verbose:
                    if observation.success:
                        logger.info(f"Observation: {observation.result}")
                    else:
                        logger.warning(f"Tool error: {observation.error}")

            except Exception as e:
                logger.error(f"Error in step {step_num}: {e}")
                duration = time.time() - start_time
                return AgentResult(
                    success=False,
                    error=f"Agent crashed: {str(e)}",
                    steps=steps,
                    duration_seconds=duration,
                )

        # Reached max steps without finishing
        logger.warning(f"Reached max steps ({self.max_steps}) without finishing")
        duration = time.time() - start_time
        return AgentResult(
            success=False,
            error=f"Reached max steps ({self.max_steps}) without completing the task",
            steps=steps,
            duration_seconds=duration,
        )

    async def _execute_tool(self, tool_call: ToolCall) -> Observation:
        """Execute a tool and return observation.

        Args:
            tool_call: The tool call to execute

        Returns:
            Observation with result or error
        """
        start_time = time.time()

        try:
            result = await self.tools.execute(tool_call.name, tool_call.params)
            duration = time.time() - start_time

            return Observation(
                tool_name=tool_call.name,
                result=result,
                success=True,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tool {tool_call.name} failed: {e}")

            return Observation(
                tool_name=tool_call.name,
                result=None,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )
