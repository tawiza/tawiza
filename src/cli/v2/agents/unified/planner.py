"""LLM Planner for the ReAct agent."""

import contextlib
import json
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .models import ToolCall
from .prompts import REACT_SYSTEM_PROMPT


@dataclass
class PlanResult:
    """Result of planning the next action."""

    thought: str
    tool_call: ToolCall


class ReActPlanner:
    """LLM-based planner using ReAct prompting."""

    def __init__(self, ollama_client, model: str):
        """Initialize the planner.

        Args:
            ollama_client: Ollama client for LLM inference
            model: Model name to use (e.g., "qwen2.5-coder:7b")
        """
        self.ollama = ollama_client
        self.model = model

    async def plan_next_action(
        self,
        task: str,
        history: list[dict[str, Any]],
        tools_description: str,
        context: dict[str, Any],
    ) -> PlanResult:
        """Plan the next action using the LLM.

        Args:
            task: The task to accomplish
            history: List of previous steps (thought, tool_call, observation)
            tools_description: Description of available tools
            context: Additional context (current state, etc.)

        Returns:
            PlanResult with thought and tool_call
        """
        # Format the prompt
        prompt = REACT_SYSTEM_PROMPT.format(
            task=task,
            history=self._format_history(history),
            tools_description=tools_description,
            context=self._format_context(context),
        )

        logger.debug(f"Planning with model: {self.model}")

        # Call LLM
        response = await self.ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        # Handle both string response (real OllamaClient) and dict response (mock)
        if isinstance(response, str):
            content = response
        else:
            content = response.get("message", {}).get("content", str(response))

        logger.debug(f"LLM response: {content[:200]}...")

        # Parse response
        thought, tool_call = self._parse_response(content)

        return PlanResult(thought=thought, tool_call=tool_call)

    def _format_history(self, history: list[dict[str, Any]]) -> str:
        """Format the history for the prompt.

        Args:
            history: List of step dictionaries

        Returns:
            Formatted history string
        """
        if not history:
            return "No previous steps."

        lines = []
        for i, step in enumerate(history, 1):
            thought = step.get("thought", "")
            tool_call = step.get("tool_call")
            observation = step.get("observation", {})

            lines.append(f"Step {i}:")
            lines.append(f"  Thought: {thought}")

            if tool_call:
                tool_name = tool_call.name if hasattr(tool_call, "name") else str(tool_call)
                tool_params = tool_call.params if hasattr(tool_call, "params") else {}
                lines.append(f"  Action: {tool_name}({json.dumps(tool_params)})")

            if isinstance(observation, dict):
                result = observation.get("result", observation)
            else:
                result = observation

            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            lines.append(f"  Observation: {result_str}")

        return "\n".join(lines)

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context for the prompt.

        Args:
            context: Context dictionary

        Returns:
            Formatted context string
        """
        if not context:
            return "No additional context."

        return json.dumps(context, indent=2)

    def _parse_response(self, response: str) -> tuple[str, ToolCall]:
        """Parse the LLM response into thought and tool_call.

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (thought, tool_call)
        """
        # Remove markdown code blocks if present
        response = response.strip()
        if "```json" in response:
            # Extract JSON from markdown code block
            match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
            if match:
                response = match.group(1)
        elif "```" in response:
            # Generic code block
            match = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
            if match:
                response = match.group(1)

        # Try to parse JSON
        try:
            data = json.loads(response)
            thought = data.get("thought", "")
            tool_name = data.get("tool", "")
            params = data.get("params", {})

            tool_call = ToolCall(name=tool_name, params=params)

            logger.debug(f"Parsed: thought='{thought}', tool={tool_name}")
            return thought, tool_call

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")

            # Smart fallback - try multiple extraction strategies
            thought = ""
            tool_name = ""
            params = {}

            # Strategy 1: Extract JSON fields with regex (handles malformed JSON)
            tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', response)
            if tool_match:
                tool_name = tool_match.group(1)

            thought_match = re.search(r'"thought"\s*:\s*"([^"]*(?:[^"\\]|\\.)*)"', response)
            if thought_match:
                thought = thought_match.group(1)

            params_match = re.search(r'"params"\s*:\s*(\{[^}]*\})', response)
            if params_match:
                with contextlib.suppress(json.JSONDecodeError):
                    params = json.loads(params_match.group(1))

            # Strategy 2: If no tool found, analyze text for intent
            if not tool_name:
                response_lower = response.lower()

                # Check if LLM is explaining an error/limitation
                if any(
                    word in response_lower
                    for word in ["error", "cannot", "unable", "failed", "limitation"]
                ):
                    tool_name = "finish"
                    # Use the explanation as the answer
                    params = {"answer": f"Agent encountered an issue: {response[:300]}"}
                    thought = (
                        "LLM provided explanation instead of action - completing with findings"
                    )

                # Check if LLM is trying to finish
                elif any(
                    word in response_lower
                    for word in ["complete", "done", "finished", "result", "answer"]
                ):
                    tool_name = "finish"
                    params = {"answer": response[:500]}
                    thought = "LLM appears to be providing final answer"

                # Default: finish with the response
                else:
                    tool_name = "finish"
                    params = {"answer": f"Could not parse response. Raw: {response[:300]}"}
                    thought = "Fallback: LLM response was not valid JSON"

            # If we extracted a tool but no params for finish, use response
            if tool_name == "finish" and not params:
                params = {"answer": thought or response[:300]}

            tool_call = ToolCall(name=tool_name, params=params)
            logger.info(f"Fallback parse: tool={tool_name}, thought='{thought[:50]}...'")

            return thought, tool_call
