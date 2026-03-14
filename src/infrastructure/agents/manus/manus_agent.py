"""ManusAgent - OpenManus-inspired reasoning agent.

This agent implements a think-execute cycle with context enrichment,
inspired by the OpenManus project. It supports:
- Browser automation
- Code execution (Python/Bash) via VM sandbox
- MCP tool integration
- Context-aware reasoning based on recent tool usage
"""

import asyncio
import json
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.application.ports.agent_ports import (
    AgentExecutionError,
    AgentType,
    TaskStatus,
)
from src.infrastructure.agents.base_agent import BaseAgent

if TYPE_CHECKING:
    from src.infrastructure.llm.ollama_client import OllamaClient
    from src.infrastructure.tools.registry import ToolRegistry


class AgentAction(StrEnum):
    """Types of actions the agent can take."""

    THINK = "think"
    USE_TOOL = "use_tool"
    RESPOND = "respond"
    DELEGATE = "delegate"
    ERROR = "error"


class AgentContext:
    """Context container for agent reasoning.

    Holds the conversation history, tool results, and other
    contextual information needed for the reasoning loop.
    """

    def __init__(
        self,
        messages: list[dict[str, Any]],
        available_tools: list[str] | None = None,
        recent_tool_results: list[dict[str, Any]] | None = None,
        task_config: dict[str, Any] | None = None,
    ):
        """Initialize agent context.

        Args:
            messages: Conversation history
            available_tools: List of tool names available to agent
            recent_tool_results: Results from recently executed tools
            task_config: Original task configuration
        """
        self.messages = messages or []
        self.available_tools = available_tools or []
        self.recent_tool_results = recent_tool_results or []
        self.task_config = task_config or {}
        self.metadata = {}

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append(
            {"role": role, "content": content, "timestamp": datetime.utcnow().isoformat()}
        )

    def add_tool_result(self, tool_name: str, result: Any, success: bool) -> None:
        """Add a tool execution result to context."""
        self.recent_tool_results.append(
            {
                "tool_name": tool_name,
                "result": result,
                "success": success,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Keep only last 5 tool results to avoid context bloat
        if len(self.recent_tool_results) > 5:
            self.recent_tool_results = self.recent_tool_results[-5:]


class ManusAgent(BaseAgent):
    """Manus Agent - Reasoning agent with think-execute cycle.

    This agent implements a reasoning loop inspired by OpenManus:
    1. Think: Analyze the task and context
    2. Execute: Use tools or respond
    3. Reflect: Update context with results
    4. Repeat until task complete

    Features:
    - Context enrichment based on recent tool usage
    - Support for multiple tool types (browser, code, MCP)
    - Streaming progress updates
    - Error handling and recovery
    """

    def __init__(
        self,
        llm_client: Optional["OllamaClient"] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        max_iterations: int = 10,
        model: str = "qwen3-coder:30b",
        config: dict[str, Any] | None = None,
    ):
        """Initialize Manus Agent.

        Args:
            llm_client: LLM client for reasoning (OllamaClient instance)
            tool_registry: Tool registry for tool discovery and execution
            max_iterations: Maximum reasoning loop iterations
            model: LLM model to use for reasoning
            config: Additional agent configuration
        """
        super().__init__(agent_type=AgentType.CUSTOM, config=config or {})

        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        self.model = model

        # System prompt for the agent
        self.system_prompt = self._build_system_prompt()

        logger.info(f"Initialized ManusAgent with max_iterations={max_iterations}, model={model}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent.

        Returns:
            System prompt string
        """
        return """You are Manus, an advanced reasoning agent capable of using tools to accomplish tasks.

Your capabilities:
- Browser automation using Playwright
- Python code execution (sandboxed)
- Bash command execution (sandboxed)
- MCP tool integration
- File operations

Your reasoning process:
1. Analyze the task and current context
2. Decide on the best action (use a tool, respond to user, etc.)
3. Execute the action
4. Reflect on the results
5. Iterate until task is complete

Guidelines:
- Break complex tasks into smaller steps
- Use tools when needed, but prefer direct responses for simple queries
- Learn from recent tool results to improve your approach
- Always explain your reasoning
- If you encounter errors, try alternative approaches

When using tools:
- Choose the most appropriate tool for the task
- Provide clear, well-formed arguments
- Handle errors gracefully

When responding:
- Be clear and concise
- Explain what you did and why
- Mention any limitations or caveats
"""

    def _enrich_with_context(self, context: AgentContext) -> str:
        """Enrich system prompt with current context.

        This adds information about recent tool usage and results
        to help the agent make better decisions.

        Args:
            context: Current agent context

        Returns:
            Enriched system prompt
        """
        enriched = self.system_prompt

        # Add available tools
        if context.available_tools:
            enriched += f"\n\nAvailable tools: {', '.join(context.available_tools)}"

        # Add recent tool results for learning
        if context.recent_tool_results:
            enriched += "\n\nRecent tool executions:"
            for result in context.recent_tool_results[-3:]:
                status = "success" if result["success"] else "failed"
                enriched += f"\n- {result['tool_name']}: {status}"

        # Add task-specific context
        if context.task_config:
            task_type = context.task_config.get("action_type", "unknown")
            enriched += f"\n\nCurrent task type: {task_type}"

        return enriched

    async def think(self, context: AgentContext) -> dict[str, Any]:
        """Think step: Analyze task and decide on action.

        Uses the LLM to reason about the task and determine
        the next action to take.

        Args:
            context: Current agent context

        Returns:
            Action decision containing:
                - action: Action type
                - reasoning: Explanation of decision
                - tool_name: Tool to use (if action is USE_TOOL)
                - tool_args: Arguments for tool (if action is USE_TOOL)
                - response: Response text (if action is RESPOND)
        """
        try:
            # If no LLM client, use fallback
            if not self.llm_client:
                logger.warning("No LLM client configured, using fallback")
                return self._fallback_think(context)

            # Enrich system prompt with context
            enriched_prompt = self._enrich_with_context(context)

            # Build messages for LLM
            messages = [
                {"role": "system", "content": enriched_prompt},
            ]

            # Add context messages (filter out timestamps for LLM)
            for msg in context.messages:
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )

            # Get tool schemas if tool registry available
            tool_schemas = []
            if self.tool_registry:
                tool_schemas = self.tool_registry.get_all_schemas()

            # Call LLM with tools
            logger.debug(f"Calling LLM with {len(messages)} messages and {len(tool_schemas)} tools")

            response = await self.llm_client.chat(
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                model=self.model,
                temperature=0.7,
            )

            # Parse the LLM response
            return self._parse_llm_response(response, context)

        except Exception as e:
            logger.error(f"Error in think step: {e}")
            return {
                "action": AgentAction.ERROR,
                "reasoning": f"Failed to reason: {str(e)}",
                "error": str(e),
            }

    def _fallback_think(self, context: AgentContext) -> dict[str, Any]:
        """Fallback thinking when LLM is not available.

        Uses simple heuristics to decide on action.

        Args:
            context: Current agent context

        Returns:
            Action decision
        """
        # Simple heuristic: if we have messages, respond
        if context.messages:
            last_message = context.messages[-1]
            if last_message.get("role") == "user":
                return {
                    "action": AgentAction.RESPOND,
                    "reasoning": "Responding to user query",
                    "response": "I received your request and will process it.",
                }

        return {
            "action": AgentAction.RESPOND,
            "reasoning": "No specific action needed",
            "response": "Task initialized",
        }

    def _parse_llm_response(
        self, response: dict[str, Any], context: AgentContext
    ) -> dict[str, Any]:
        """Parse LLM response into action decision.

        Handles both text responses and tool calls from the LLM.

        Args:
            response: LLM response dict with 'content' and 'tool_calls'
            context: Current agent context

        Returns:
            Parsed action decision
        """
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        # If LLM wants to use a tool
        if tool_calls:
            # Take the first tool call
            tool_call = tool_calls[0]
            function_info = tool_call.get("function", {})
            tool_name = function_info.get("name", "")
            tool_args_str = function_info.get("arguments", "{}")

            # Parse arguments (might be string or dict)
            if isinstance(tool_args_str, str):
                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {"raw": tool_args_str}
            else:
                tool_args = tool_args_str

            logger.info(f"LLM decided to use tool: {tool_name}")

            return {
                "action": AgentAction.USE_TOOL,
                "reasoning": content or f"Using tool {tool_name} to accomplish the task",
                "tool_name": tool_name,
                "tool_args": tool_args,
            }

        # If LLM provided a text response
        if content:
            # Check if the response indicates task completion
            # Look for common completion patterns
            completion_indicators = [
                "here is",
                "the answer is",
                "i found",
                "the result",
                "completed",
                "done",
                "finished",
            ]

            is_final = any(indicator in content.lower() for indicator in completion_indicators)

            if is_final or len(context.recent_tool_results) > 0:
                # This looks like a final response
                return {
                    "action": AgentAction.RESPOND,
                    "reasoning": "Providing final response to user",
                    "response": content,
                }
            else:
                # Continue reasoning - add to context and keep going
                context.add_message("assistant", content)
                return {
                    "action": AgentAction.THINK,
                    "reasoning": content,
                }

        # Fallback - no content or tools
        return {
            "action": AgentAction.RESPOND,
            "reasoning": "No specific action determined",
            "response": "I'm not sure how to proceed with this task.",
        }

    async def execute_action(self, action: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute the decided action.

        Args:
            action: Action decision from think step
            context: Current agent context

        Returns:
            Action result
        """
        action_type = action.get("action")

        try:
            if action_type == AgentAction.USE_TOOL:
                return await self._execute_tool(action, context)

            elif action_type == AgentAction.RESPOND:
                return {
                    "success": True,
                    "response": action.get("response", ""),
                    "is_final": True,
                }

            elif action_type == AgentAction.THINK:
                # Continue thinking - not an error, not final
                return {
                    "success": True,
                    "reasoning": action.get("reasoning", ""),
                    "is_final": False,
                }

            elif action_type == AgentAction.ERROR:
                return {
                    "success": False,
                    "error": action.get("error", "Unknown error"),
                    "is_final": True,
                }

            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                    "is_final": True,
                }

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {
                "success": False,
                "error": str(e),
                "is_final": True,
            }

    async def _execute_tool(self, action: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute a tool based on action decision.

        Args:
            action: Action containing tool_name and tool_args
            context: Current agent context

        Returns:
            Tool execution result
        """
        tool_name = action.get("tool_name")
        tool_args = action.get("tool_args", {})

        if not self.tool_registry:
            return {"success": False, "error": "Tool registry not available"}

        try:
            # Execute tool via registry
            result = await self.tool_registry.execute(tool_name, tool_args)

            # Convert ToolResult to dict if needed
            if hasattr(result, "to_dict"):
                result_dict = result.to_dict()
                result_output = result_dict.get("output", result_dict)
            else:
                result_output = result

            # Add to context
            context.add_tool_result(tool_name=tool_name, result=result_output, success=True)

            return {"success": True, "tool_name": tool_name, "result": result_output}

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")

            # Add failure to context
            context.add_tool_result(tool_name=tool_name, result=str(e), success=False)

            return {"success": False, "tool_name": tool_name, "error": str(e)}

    async def reasoning_loop(self, task_config: dict[str, Any], task_id: str) -> dict[str, Any]:
        """Main reasoning loop: think -> execute -> reflect.

        Args:
            task_config: Task configuration
            task_id: Task identifier for progress tracking

        Returns:
            Final result
        """
        # Initialize context
        context = AgentContext(
            messages=[
                {
                    "role": "user",
                    "content": task_config.get("prompt", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
            available_tools=self.tool_registry.list_tools() if self.tool_registry else [],
            task_config=task_config,
        )

        iteration = 0
        final_response = None
        all_tool_results = []

        while iteration < self.max_iterations:
            iteration += 1

            self._update_progress(
                task_id=task_id,
                progress=int((iteration / self.max_iterations) * 100),
                current_step=f"Reasoning iteration {iteration}/{self.max_iterations}",
            )

            logger.info(f"Reasoning iteration {iteration}/{self.max_iterations}")

            # Think step
            action = await self.think(context)

            action_type = action.get("action")
            self._add_log(
                task_id=task_id,
                message=f"Action: {action_type} - {action.get('reasoning', '')[:100]}",
                level="info",
            )

            # Execute action
            result = await self.execute_action(action, context)

            # Check if this is a final response
            if result.get("is_final", False):
                if action_type == AgentAction.RESPOND:
                    final_response = result.get("response")
                elif action_type == AgentAction.ERROR:
                    final_response = f"Error: {result.get('error')}"
                break

            # Handle tool execution results
            if action_type == AgentAction.USE_TOOL:
                tool_name = action.get("tool_name")
                tool_result = result.get("result")

                # Add tool result to context for next iteration
                if result.get("success"):
                    all_tool_results.append(
                        {
                            "tool": tool_name,
                            "result": tool_result,
                        }
                    )

                    # Add tool result as assistant message for LLM context
                    result_str = (
                        json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result
                    )
                    context.add_message(
                        "assistant", f"Tool '{tool_name}' returned: {result_str[:500]}"
                    )
                else:
                    # Tool failed - add error to context
                    context.add_message(
                        "assistant", f"Tool '{tool_name}' failed: {result.get('error')}"
                    )

            # Check if we hit an error
            if not result.get("success"):
                self._add_log(
                    task_id=task_id, message=f"Error: {result.get('error')}", level="error"
                )
                # Continue to next iteration to try recovery

            # Add small delay to avoid tight loops
            await asyncio.sleep(0.1)

        return {
            "success": final_response is not None,
            "response": final_response,
            "iterations": iteration,
            "tool_results": all_tool_results,
            "context": {
                "messages": len(context.messages),
                "tool_results": len(context.recent_tool_results),
            },
        }

    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """Execute a task using the reasoning loop.

        This is the main entry point called by the framework.

        Args:
            task_config: Task configuration containing:
                - prompt: User's task description
                - max_iterations: Optional iteration override
                - tools: Optional list of allowed tools

        Returns:
            Task result
        """
        # Create task entry
        task_id = self._create_task(task_config)

        try:
            # Update status
            self._update_task(task_id, {"status": TaskStatus.RUNNING})

            self._add_log(
                task_id=task_id, message="Starting Manus Agent reasoning loop", level="info"
            )

            # Override max iterations if specified
            original_max_iterations = self.max_iterations
            if "max_iterations" in task_config:
                self.max_iterations = task_config["max_iterations"]

            # Run reasoning loop
            result = await self.reasoning_loop(task_config, task_id)

            # Restore original max iterations
            self.max_iterations = original_max_iterations

            # Update task with result
            self._update_task(
                task_id,
                {
                    "status": TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED,
                    "result": result,
                    "progress": 100,
                },
            )

            self._add_log(
                task_id=task_id,
                message=f"Task completed in {result['iterations']} iterations",
                level="info",
            )

            return await self.get_task_result(task_id)

        except Exception as e:
            logger.error(f"Task execution failed: {e}")

            self._update_task(task_id, {"status": TaskStatus.FAILED, "error": str(e)})

            self._add_log(task_id=task_id, message=f"Task failed: {str(e)}", level="error")

            raise AgentExecutionError(f"Task execution failed: {str(e)}")

    def set_llm_client(self, llm_client: Any) -> None:
        """Set the LLM client for reasoning.

        Args:
            llm_client: LLM client instance
        """
        self.llm_client = llm_client
        logger.info("LLM client configured")

    def set_tool_registry(self, tool_registry: Any) -> None:
        """Set the tool registry for tool access.

        Args:
            tool_registry: Tool registry instance
        """
        self.tool_registry = tool_registry
        logger.info("Tool registry configured")

    async def health_check(self) -> bool:
        """Check if agent is ready to operate.

        Returns:
            True if agent is healthy
        """
        # Basic checks
        checks = {
            "llm_client": self.llm_client is not None,
            "tool_registry": self.tool_registry is not None,
        }

        all_healthy = all(checks.values())

        if not all_healthy:
            logger.warning(f"Health check failed: {checks}")

        return all_healthy

    def get_capabilities(self) -> dict[str, Any]:
        """Get agent capabilities.

        Returns:
            Dictionary describing agent capabilities
        """
        return {
            "name": "ManusAgent",
            "type": "reasoning",
            "features": [
                "think-execute reasoning loop",
                "context enrichment",
                "tool integration",
                "browser automation",
                "code execution",
                "MCP tools",
            ],
            "max_iterations": self.max_iterations,
            "model": self.model,
            "has_llm": self.llm_client is not None,
            "has_tools": self.tool_registry is not None,
        }


async def create_manus_agent(
    model: str = "qwen3-coder:30b",
    ollama_host: str = "http://localhost:11434",
    max_iterations: int = 10,
    include_advanced_tools: bool = True,
) -> ManusAgent:
    """Factory function to create a fully configured ManusAgent.

    Creates a ManusAgent with:
    - OllamaClient for LLM reasoning
    - ToolRegistry with all advanced agents registered

    Args:
        model: Ollama model to use for reasoning
        ollama_host: Ollama server URL
        max_iterations: Maximum reasoning iterations
        include_advanced_tools: Whether to register advanced agents as tools

    Returns:
        Configured ManusAgent ready to use

    Example:
        >>> agent = await create_manus_agent()
        >>> result = await agent.execute_task({"prompt": "Analyze sales data"})
    """
    from src.infrastructure.llm.ollama_client import OllamaClient
    from src.infrastructure.tools import create_unified_registry

    # Create LLM client
    llm_client = OllamaClient(
        base_url=ollama_host,
        model=model,
    )

    # Create tool registry
    if include_advanced_tools:
        tool_registry = create_unified_registry()
    else:
        from src.infrastructure.tools import ToolRegistry

        tool_registry = ToolRegistry()

    # Create agent
    agent = ManusAgent(
        llm_client=llm_client,
        tool_registry=tool_registry,
        max_iterations=max_iterations,
        model=model,
    )

    # Health check
    healthy = await llm_client.health_check()
    if not healthy:
        logger.warning(f"Ollama health check failed for model {model}")

    logger.info(
        f"Created ManusAgent with {len(tool_registry)} tools, "
        f"model={model}, max_iterations={max_iterations}"
    )

    return agent
