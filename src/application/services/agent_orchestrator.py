"""Agent Orchestrator - Routes requests to appropriate agents or LLMs.

Extended for TUI WebSocket integration with real agent support.
"""

import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger

from src.infrastructure.llm.ollama_client import OllamaClient
from src.interfaces.api.v1.openai_compatible.schemas import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
)

# =============================================================================
# Event types for WebSocket communication
# =============================================================================


class TaskEventType(StrEnum):
    """Types of events emitted during task execution."""

    STARTED = "started"
    THINKING = "thinking"
    PROGRESS = "progress"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STREAMING = "streaming"
    TERMINAL_OUTPUT = "terminal_output"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class TaskEvent:
    """Event emitted during task execution."""

    type: TaskEventType
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            **self.data,
        }


# Type alias for event callback
EventCallback = Callable[[TaskEvent], Awaitable[None]]


class AgentOrchestrator:
    """
    Orchestrates requests between Tawiza agents and Ollama models.

    Routing logic:
    - Models starting with "tawiza-" -> Route to Tawiza agents
    - Other models -> Forward to Ollama

    Available Tawiza agents:
    - tawiza-analyst: Strategic analysis and territorial intelligence
    - tawiza-data: Sirene data collection
    - tawiza-geo: Mapping and geolocation
    - tawiza-veille: Market monitoring (BODACC, BOAMP)
    - tawiza-finance: Financial data analysis
    - tawiza-simulation: Scenario simulation
    - tawiza-prospection: B2B lead generation
    - tawiza-comparison: Territory comparison
    - tawiza-business-plan: Business plan generation
    """

    def __init__(self):
        """Initialize the orchestrator."""
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_client = OllamaClient(base_url=self.ollama_url)

        # Tawiza agent registry
        self.tawiza_agents = {
            "tawiza-analyst": {
                "name": "Tawiza Analyst Agent",
                "description": "Strategic analysis and territorial intelligence",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-data": {
                "name": "Tawiza Data Agent",
                "description": "Sirene data collection and processing",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-geo": {
                "name": "Tawiza Geo Agent",
                "description": "Mapping, geolocation, and spatial analysis",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-veille": {
                "name": "Tawiza Veille Agent",
                "description": "Market monitoring (BODACC, BOAMP)",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-finance": {
                "name": "Tawiza Finance Agent",
                "description": "Financial data analysis",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-simulation": {
                "name": "Tawiza Simulation Agent",
                "description": "Scenario simulation and forecasting",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-prospection": {
                "name": "Tawiza Prospection Agent",
                "description": "B2B lead generation and prospection",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-comparison": {
                "name": "Tawiza Comparison Agent",
                "description": "Territory comparison and benchmarking",
                "base_model": "qwen2.5:7b",
            },
            "tawiza-business-plan": {
                "name": "Tawiza Business Plan Agent",
                "description": "Business plan generation and analysis",
                "base_model": "qwen2.5:7b",
            },
        }

        # Real agent instances (lazy loaded)
        self._real_agents: dict[str, Any] = {}
        self._agents_initialized = False

        # Event callback for WebSocket notifications
        self._event_callback: EventCallback | None = None

        # TUI agent types mapping
        self.tui_agents = {
            "manus": {
                "name": "Manus Agent",
                "description": "Reasoning agent with think-execute cycle",
                "capabilities": ["reasoning", "tools", "browser", "code"],
            },
            "general": {
                "name": "General Assistant",
                "description": "General purpose conversational agent",
                "capabilities": ["chat", "reasoning"],
            },
            "browser": {
                "name": "Browser Automation Agent",
                "description": "Web automation and scraping",
                "capabilities": ["browser", "scraping", "automation"],
            },
            "coder": {
                "name": "Code Generator Agent",
                "description": "Code generation and analysis",
                "capabilities": ["code", "analysis"],
            },
            "research": {
                "name": "Deep Research Agent",
                "description": "In-depth research and analysis",
                "capabilities": ["research", "analysis", "web"],
            },
            "data": {
                "name": "Data Analyst Agent",
                "description": "Data analysis and visualization",
                "capabilities": ["data", "analysis", "visualization"],
            },
            "tajine": {
                "name": "TAJINE Agent",
                "description": "Cognitive meta-agent with PERCEIVE-PLAN-DELEGATE-SYNTHESIZE-LEARN cycle",
                "capabilities": ["cognitive", "territorial", "analysis", "planning", "synthesis"],
            },
        }

        logger.info(
            f"AgentOrchestrator initialized with {len(self.tawiza_agents)} Tawiza agents "
            f"and {len(self.tui_agents)} TUI agents"
        )

    # =========================================================================
    # TUI/WebSocket Integration Methods
    # =========================================================================

    def set_event_callback(self, callback: EventCallback) -> None:
        """Set callback for WebSocket event notifications.

        Args:
            callback: Async function to call with TaskEvent
        """
        self._event_callback = callback
        logger.debug("Event callback registered")

    async def _emit_event(self, event: TaskEvent) -> None:
        """Emit an event to the registered callback."""
        if self._event_callback:
            try:
                await self._event_callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    async def _forward_tajine_event(self, event_data: dict[str, Any]) -> None:
        """Forward TAJINE events to WebSocket handler.

        Converts TAJINECallback events to TaskEvents for unified handling.
        """
        try:
            from src.interfaces.api.websocket.handlers import get_tajine_handler

            handler = get_tajine_handler()
            await handler._handle_tajine_event(
                task_id=event_data.get("task_id", "unknown"), event_data=event_data
            )
        except Exception as e:
            logger.debug(f"TAJINE event forward failed: {e}")

    async def initialize_agents(self) -> dict[str, bool]:
        """Initialize real agent instances.

        Initializes all available agents with graceful fallback.
        Agents that fail to initialize will use Ollama fallback.

        Returns:
            Dict mapping agent name to initialization success
        """
        if self._agents_initialized:
            return dict.fromkeys(self._real_agents, True)

        results = {}

        # 1. Initialize ManusAgent with ToolRegistry
        try:
            from src.infrastructure.agents.manus.manus_agent import ManusAgent
            from src.infrastructure.tools import ToolRegistry

            # Create a basic tool registry (without heavy dependencies)
            tool_registry = ToolRegistry()

            self._real_agents["manus"] = ManusAgent(
                llm_client=self.ollama_client,
                tool_registry=tool_registry,
                max_iterations=10,
                model="qwen3.5:27b",
            )
            results["manus"] = True
            logger.info("ManusAgent initialized with ToolRegistry")
        except Exception as e:
            logger.warning(f"ManusAgent init failed (will use Ollama fallback): {e}")
            results["manus"] = False

        # 2. Initialize BrowserAutomationAgent (optional - requires Playwright)
        try:
            from src.infrastructure.agents.advanced import BrowserAutomationAgent

            browser_agent = BrowserAutomationAgent()
            # Don't call initialize() here - it's async and starts browser
            # We'll initialize lazily on first use
            self._real_agents["browser"] = browser_agent
            results["browser"] = True
            logger.info("BrowserAutomationAgent registered (lazy init)")
        except Exception as e:
            logger.warning(f"BrowserAutomationAgent unavailable: {e}")
            results["browser"] = False

        # 3. Initialize DeepResearchAgent (optional - requires Qdrant)
        try:
            from src.infrastructure.agents.advanced import DeepResearchAgent

            research_agent = DeepResearchAgent(
                ollama_url=self.ollama_url,
                ollama_model="qwen3.5:27b",
            )
            self._real_agents["research"] = research_agent
            results["research"] = True
            logger.info("DeepResearchAgent initialized")
        except Exception as e:
            logger.warning(f"DeepResearchAgent unavailable: {e}")
            results["research"] = False

        # 4. Initialize CodeGeneratorAgent
        try:
            from src.infrastructure.agents.advanced import CodeGeneratorAgent

            code_agent = CodeGeneratorAgent()
            self._real_agents["coder"] = code_agent
            results["coder"] = True
            logger.info("CodeGeneratorAgent initialized")
        except Exception as e:
            logger.warning(f"CodeGeneratorAgent unavailable: {e}")
            results["coder"] = False

        # 5. Initialize DataAnalystAgent
        try:
            from src.infrastructure.agents.advanced import DataAnalystAgent

            data_agent = DataAnalystAgent()
            self._real_agents["data"] = data_agent
            results["data"] = True
            logger.info("DataAnalystAgent initialized")
        except Exception as e:
            logger.warning(f"DataAnalystAgent unavailable: {e}")
            results["data"] = False

        # 6. Initialize TAJINEAgent (cognitive meta-agent)
        try:
            from src.infrastructure.agents.tajine import TAJINEAgent

            tajine_agent = TAJINEAgent(
                name="tajine_main",
                local_model="qwen3.5:27b",
                powerful_model="qwen2.5:7b",
                ollama_host=self.ollama_url,
            )
            await tajine_agent.initialize()

            # Connect TAJINE events to WebSocket handler
            try:
                from src.interfaces.api.websocket.handlers import get_tajine_handler

                get_tajine_handler()
                # Register a global task ID for broadcasting
                tajine_agent.on_ws(lambda event: self._forward_tajine_event(event))
                logger.debug("TAJINEAgent connected to WebSocket handler")
            except ImportError:
                logger.debug("WebSocket handlers not available for TAJINE")

            self._real_agents["tajine"] = tajine_agent
            results["tajine"] = True
            logger.info("TAJINEAgent initialized with PPDSL cycle")
        except Exception as e:
            logger.warning(f"TAJINEAgent unavailable: {e}")
            results["tajine"] = False

        # General agent always uses Ollama (no special agent)
        results["general"] = True

        self._agents_initialized = True
        active_agents = [k for k, v in results.items() if v]
        logger.info(f"Agents initialized: {len(active_agents)}/{len(results)} active")
        logger.debug(f"Agent status: {results}")
        return results

    def get_tui_agent_info(self, agent_type: str) -> dict[str, Any] | None:
        """Get TUI agent information."""
        return self.tui_agents.get(agent_type)

    def list_tui_agents(self) -> list[dict[str, Any]]:
        """List all TUI agents with their info."""
        return [{"id": agent_id, **info} for agent_id, info in self.tui_agents.items()]

    async def execute_task(
        self,
        task_id: str,
        agent_type: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[TaskEvent]:
        """Execute a task and yield events.

        This is the main entry point for TUI task execution.

        Args:
            task_id: Unique task identifier
            agent_type: Type of agent to use
            prompt: User's task prompt
            context: Optional additional context

        Yields:
            TaskEvent objects for WebSocket broadcast
        """
        context = context or {}
        start_time = time.time()

        # Emit started event
        yield TaskEvent(
            type=TaskEventType.STARTED,
            task_id=task_id,
            data={"agent": agent_type, "prompt": prompt[:100]},
        )

        try:
            # Check if we have a real agent for this type
            real_agent = self._real_agents.get(agent_type)
            use_ollama_fallback = False

            if real_agent:
                # Try the real agent first
                try:
                    async for event in self._execute_with_real_agent(
                        task_id, real_agent, prompt, context
                    ):
                        yield event
                except NotImplementedError as e:
                    # Agent doesn't support this operation, fallback to Ollama
                    logger.info(f"Agent {agent_type} fallback: {e}")
                    use_ollama_fallback = True
            else:
                use_ollama_fallback = True

            if use_ollama_fallback:
                # Fallback to Ollama-based execution
                async for event in self._execute_with_ollama(task_id, agent_type, prompt, context):
                    yield event

            # Emit completed event
            duration = time.time() - start_time
            yield TaskEvent(
                type=TaskEventType.COMPLETED, task_id=task_id, data={"duration_seconds": duration}
            )

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            yield TaskEvent(type=TaskEventType.ERROR, task_id=task_id, data={"error": str(e)})

    async def _execute_with_real_agent(
        self,
        task_id: str,
        agent: Any,
        prompt: str,
        context: dict[str, Any],
    ) -> AsyncIterator[TaskEvent]:
        """Execute task using a real agent instance.

        Supports different agent interfaces:
        - ManusAgent: execute_task(task_config) -> Dict
        - BrowserAutomationAgent: execute_automation(task) -> AutomationResult
        - DeepResearchAgent: research(query) -> ResearchResult
        - CodeGeneratorAgent: generate_code(request) -> GeneratedCode
        - DataAnalystAgent: analyze(data_path) -> DataAnalysisReport
        """
        agent_name = agent.__class__.__name__
        agent_type = getattr(agent, "agent_type", "unknown")

        yield TaskEvent(
            type=TaskEventType.THINKING, task_id=task_id, data={"content": f"Using {agent_name}..."}
        )

        try:
            result = None

            # Route to appropriate agent method based on agent type
            if agent_type == "manus" or hasattr(agent, "execute_task"):
                # ManusAgent - uses execute_task with task_config
                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 1, "total_steps": 3, "message": "Reasoning..."},
                )

                task_config = {"prompt": prompt, "task_id": task_id, **context}
                result = await agent.execute_task(task_config)

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 2, "total_steps": 3, "message": "Processing..."},
                )

                # Extract response from ManusAgent result
                if isinstance(result, dict):
                    response = result.get("response") or result.get("result", str(result))
                else:
                    response = str(result)

                yield TaskEvent(
                    type=TaskEventType.THINKING,
                    task_id=task_id,
                    data={"content": str(response)[:1000]},
                )

            elif agent_type == "browser_automation":
                # BrowserAutomationAgent - uses execute_from_prompt
                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 1, "total_steps": 4, "message": "Initializing browser..."},
                )

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 2, "total_steps": 4, "message": "Planning automation..."},
                )

                # Use execute_from_prompt method
                result = await agent.execute_from_prompt(prompt)

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 3, "total_steps": 4, "message": "Executing browser actions..."},
                )

                # Format the result
                if result.get("success"):
                    data = result.get("data", {})
                    response = "Browser task completed successfully.\n"
                    response += f"URL: {result.get('final_url', result.get('url', 'N/A'))}\n"
                    response += f"Actions performed: {result.get('actions_performed', 0)}\n"
                    if data.get("title"):
                        response += f"Page title: {data.get('title')}\n"
                    if data.get("links"):
                        response += f"Links found: {len(data.get('links', []))}\n"
                else:
                    response = f"Browser task failed: {result.get('error', 'Unknown error')}"

                yield TaskEvent(
                    type=TaskEventType.THINKING, task_id=task_id, data={"content": response}
                )

            elif agent_type == "research" or agent_type == "deep_research":
                # DeepResearchAgent - uses execute_from_prompt
                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 1, "total_steps": 4, "message": "Starting research..."},
                )

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 2, "total_steps": 4, "message": "Crawling sources..."},
                )

                # Use execute_from_prompt for natural language interface
                result = await agent.execute_from_prompt(prompt)

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 3, "total_steps": 4, "message": "Synthesizing..."},
                )

                # Format research results
                if result.get("success"):
                    response = "**Research Results**\n\n"
                    response += f"{result.get('synthesis', 'No synthesis available.')}\n\n"
                    if result.get("key_findings"):
                        response += "**Key Findings:**\n"
                        for finding in result.get("key_findings", [])[:5]:
                            response += f"- {finding}\n"
                    response += f"\n_Sources analyzed: {result.get('sources_count', 0)}_"
                else:
                    response = f"Research failed: {result.get('error', 'Unknown error')}"

                yield TaskEvent(
                    type=TaskEventType.THINKING, task_id=task_id, data={"content": response[:1500]}
                )

            elif agent_type == "coder" or agent_type == "code_generator":
                # CodeGeneratorAgent - uses execute_from_prompt
                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 1, "total_steps": 3, "message": "Analyzing request..."},
                )

                # Use execute_from_prompt for natural language interface
                result = await agent.execute_from_prompt(prompt)

                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 2, "total_steps": 3, "message": "Generating code..."},
                )

                # Format code generation results
                if result.get("success"):
                    response = f"**Generated Code ({result.get('language', 'unknown')})**\n\n"
                    response += f"```{result.get('language', 'python')}\n"
                    response += result.get("code", "# No code generated")[:2000]
                    response += "\n```\n\n"
                    response += f"Quality Score: {result.get('quality_score', 0):.1f}/100\n"
                    response += f"Functions: {result.get('functions_count', 0)}, Classes: {result.get('classes_count', 0)}"
                else:
                    response = f"Code generation failed: {result.get('error', 'Unknown error')}"

                yield TaskEvent(
                    type=TaskEventType.THINKING, task_id=task_id, data={"content": response[:2000]}
                )

            elif agent_type == "data_analyst":
                # DataAnalystAgent - needs data path
                yield TaskEvent(
                    type=TaskEventType.THINKING,
                    task_id=task_id,
                    data={
                        "content": "DataAnalystAgent requires a data file. Using LLM fallback..."
                    },
                )
                # Fallback to Ollama for general data questions
                raise NotImplementedError("DataAnalyst needs data file")

            elif agent_type == "tajine":
                # TAJINEAgent - full PPDSL cognitive cycle
                yield TaskEvent(
                    type=TaskEventType.PROGRESS,
                    task_id=task_id,
                    data={"step": 1, "total_steps": 5, "message": "PERCEIVE: Analyzing query..."},
                )

                # Execute full PPDSL cycle via TAJINEAgent
                task_config = {"prompt": prompt, "task_id": task_id, **context}
                result = await agent.execute_task(task_config)

                # Emit progress for each PPDSL phase
                phases = ["PERCEIVE", "PLAN", "DELEGATE", "SYNTHESIZE", "LEARN"]
                for i, phase in enumerate(phases, 1):
                    yield TaskEvent(
                        type=TaskEventType.PROGRESS,
                        task_id=task_id,
                        data={"step": i, "total_steps": 5, "message": f"{phase} phase"},
                    )

                # Format TAJINE result
                if result.get("status") == "completed":
                    analysis = result.get("result", {})
                    confidence = result.get("confidence", 0)
                    cognitive_levels = result.get("cognitive_levels", {})

                    response = f"**Analyse TAJINE (Confiance: {confidence:.1%})**\n\n"

                    # Add cognitive levels summary
                    for level, data in cognitive_levels.items():
                        if isinstance(data, dict):
                            summary = data.get("summary", str(data)[:200])
                        else:
                            summary = str(data)[:200]
                        response += f"**{level.title()}:** {summary}\n\n"

                    if isinstance(analysis, dict):
                        response += (
                            f"\n**Conclusion:** {analysis.get('summary', 'Analyse terminée')}"
                        )
                    else:
                        response += f"\n**Résultat:** {str(analysis)[:500]}"
                else:
                    response = f"Analyse TAJINE échouée: {result.get('error', 'Erreur inconnue')}"

                yield TaskEvent(
                    type=TaskEventType.THINKING, task_id=task_id, data={"content": response[:2000]}
                )

            else:
                # Unknown agent type - try generic execute
                if hasattr(agent, "execute"):
                    result = await agent.execute(prompt)
                elif hasattr(agent, "run"):
                    result = await agent.run(prompt)
                else:
                    raise NotImplementedError(f"Unknown agent interface: {agent_type}")

                yield TaskEvent(
                    type=TaskEventType.THINKING,
                    task_id=task_id,
                    data={"content": str(result)[:500]},
                )

            yield TaskEvent(
                type=TaskEventType.PROGRESS,
                task_id=task_id,
                data={"step": 3, "total_steps": 3, "message": "Complete!"},
            )

        except NotImplementedError as e:
            # Fallback to Ollama for unsupported operations
            logger.info(f"Agent fallback to Ollama: {e}")
            raise  # Will trigger Ollama fallback in execute_task

        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            raise Exception(f"Agent execution error: {e}")

    async def _execute_with_ollama(
        self,
        task_id: str,
        agent_type: str,
        prompt: str,
        context: dict[str, Any],
    ) -> AsyncIterator[TaskEvent]:
        """Execute task using Ollama directly with streaming."""
        # Get system prompt for agent type
        system_prompts = {
            "general": "You are a helpful AI assistant. Be concise and clear.",
            "manus": "You are ManusAgent, a reasoning agent. Think step by step and explain your process.",
            "browser": "You are a browser automation agent. Describe web actions clearly and precisely.",
            "coder": "You are an expert coder. Write clean, well-documented code with explanations.",
            "research": "You are a research agent. Provide thorough, well-sourced analysis.",
            "data": "You are a data analyst. Provide insights with clear explanations.",
        }

        system = system_prompts.get(agent_type, system_prompts["general"])

        # Get best available model
        model = await self._get_best_model()

        yield TaskEvent(
            type=TaskEventType.PROGRESS,
            task_id=task_id,
            data={"step": 1, "total_steps": 3, "message": f"Using {model}..."},
        )

        # Build messages
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

        yield TaskEvent(
            type=TaskEventType.PROGRESS,
            task_id=task_id,
            data={"step": 2, "total_steps": 3, "message": "Generating response..."},
        )

        # Stream response
        full_response = ""
        try:
            async for chunk in self.ollama_client._chat_stream(
                {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.7},
                }
            ):
                full_response += chunk
                yield TaskEvent(
                    type=TaskEventType.STREAMING,
                    task_id=task_id,
                    data={"content": chunk, "full_content": full_response},
                )
        except Exception as e:
            # Fallback to non-streaming
            logger.warning(f"Streaming failed, using non-streaming: {e}")
            full_response = await self.ollama_client.chat(
                messages=messages,
                model=model,
                temperature=0.7,
                stream=False,
            )

        yield TaskEvent(
            type=TaskEventType.PROGRESS,
            task_id=task_id,
            data={"step": 3, "total_steps": 3, "message": "Complete!"},
        )

        yield TaskEvent(
            type=TaskEventType.THINKING, task_id=task_id, data={"content": full_response[:1000]}
        )

    async def _get_best_model(self) -> str:
        """Get the best available Ollama model."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                models = resp.json().get("models", [])

                # Filter out embedding models
                chat_models = [
                    m["name"]
                    for m in models
                    if "embed" not in m["name"].lower() and "nomic" not in m["name"].lower()
                ]

                # Prefer certain models
                preferred = ["qwen3.5:27b", "qwen3-coder", "llama", "mistral"]
                for pref in preferred:
                    for m in chat_models:
                        if pref in m.lower():
                            return m

                return chat_models[0] if chat_models else "qwen3.5:27b"
        except Exception:
            return "qwen3.5:27b"

    # =========================================================================
    # Original OpenAI-compatible API methods (unchanged)
    # =========================================================================

    def is_tawiza_agent(self, model: str) -> bool:
        """Check if model is a Tawiza agent."""
        return model.startswith("tawiza-")

    def get_agent_info(self, model: str) -> dict[str, str] | None:
        """Get agent information."""
        return self.tawiza_agents.get(model)

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        Process chat completion request.

        Args:
            request: Chat completion request

        Returns:
            Chat completion response
        """
        if self.is_tawiza_agent(request.model):
            return await self._tawiza_agent_completion(request)
        else:
            return await self._ollama_completion(request)

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """
        Process streaming chat completion request.

        Args:
            request: Chat completion request

        Yields:
            Server-Sent Events formatted chunks
        """
        if self.is_tawiza_agent(request.model):
            async for chunk in self._tawiza_agent_completion_stream(request):
                yield chunk
        else:
            async for chunk in self._ollama_completion_stream(request):
                yield chunk

    async def _tawiza_agent_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Process Tawiza agent request."""
        agent_info = self.get_agent_info(request.model)
        if not agent_info:
            raise ValueError(f"Unknown Tawiza agent: {request.model}")

        logger.info(f"Processing request with {agent_info['name']}")

        # Build system prompt for the agent
        system_prompt = self._build_agent_system_prompt(request.model, agent_info)

        # Convert messages to Ollama format
        ollama_messages = self._convert_messages_to_ollama(request.messages, system_prompt)

        # Call underlying Ollama model with agent context
        base_model = agent_info["base_model"]
        response_text = await self.ollama_client.chat(
            messages=ollama_messages,
            model=base_model,
            temperature=request.temperature or 0.7,
            stream=False,
        )

        # Build OpenAI-compatible response
        completion_id = f"chatcmpl-{int(time.time())}"
        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=self._estimate_tokens(str(ollama_messages)),
                completion_tokens=self._estimate_tokens(response_text),
                total_tokens=self._estimate_tokens(str(ollama_messages))
                + self._estimate_tokens(response_text),
            ),
        )

    async def _tawiza_agent_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """Process streaming Tawiza agent request."""
        agent_info = self.get_agent_info(request.model)
        if not agent_info:
            raise ValueError(f"Unknown Tawiza agent: {request.model}")

        logger.info(f"Processing streaming request with {agent_info['name']}")

        # Build system prompt for the agent
        system_prompt = self._build_agent_system_prompt(request.model, agent_info)

        # Convert messages to Ollama format
        ollama_messages = self._convert_messages_to_ollama(request.messages, system_prompt)

        # Stream from underlying Ollama model
        base_model = agent_info["base_model"]
        completion_id = f"chatcmpl-{int(time.time())}"

        async for chunk_text in self.ollama_client._chat_stream(
            {
                "model": base_model,
                "messages": ollama_messages,
                "stream": True,
                "options": {"temperature": request.temperature or 0.7},
            }
        ):
            # Format as OpenAI SSE chunk
            chunk = ChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=int(time.time()),
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": None,
                    }
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

        # Send final chunk
        final_chunk = ChatCompletionChunk(
            id=completion_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=request.model,
            choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    async def _ollama_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Forward request to Ollama."""
        logger.info(f"Forwarding request to Ollama model: {request.model}")

        # Convert messages to Ollama format
        ollama_messages = self._convert_messages_to_ollama(request.messages)

        # Call Ollama
        response_text = await self.ollama_client.chat(
            messages=ollama_messages,
            model=request.model,
            temperature=request.temperature or 0.7,
            stream=False,
        )

        # Build OpenAI-compatible response
        completion_id = f"chatcmpl-{int(time.time())}"
        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=self._estimate_tokens(str(ollama_messages)),
                completion_tokens=self._estimate_tokens(response_text),
                total_tokens=self._estimate_tokens(str(ollama_messages))
                + self._estimate_tokens(response_text),
            ),
        )

    async def _ollama_completion_stream(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        """Forward streaming request to Ollama."""
        logger.info(f"Forwarding streaming request to Ollama model: {request.model}")

        # Convert messages to Ollama format
        ollama_messages = self._convert_messages_to_ollama(request.messages)

        # Stream from Ollama
        completion_id = f"chatcmpl-{int(time.time())}"

        async for chunk_text in self.ollama_client._chat_stream(
            {
                "model": request.model,
                "messages": ollama_messages,
                "stream": True,
                "options": {"temperature": request.temperature or 0.7},
            }
        ):
            # Format as OpenAI SSE chunk
            chunk = ChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=int(time.time()),
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": None,
                    }
                ],
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

        # Send final chunk
        final_chunk = ChatCompletionChunk(
            id=completion_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=request.model,
            choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    def _build_agent_system_prompt(self, model: str, agent_info: dict[str, str]) -> str:
        """Build system prompt for Tawiza agent."""
        agent_prompts = {
            "tawiza-analyst": """You are the Tawiza Analyst Agent, an expert in strategic analysis and territorial intelligence for French territories.

Your expertise includes:
- Economic analysis of French territories
- Market intelligence and competitive analysis
- Strategic recommendations for business development
- Data-driven insights using French administrative data (Sirene, BODACC, BOAMP)

You provide clear, actionable insights with proper citations and data sources.
Always respond in French unless asked otherwise.""",
            "tawiza-data": """You are the Tawiza Data Agent, specialized in collecting and processing data from the Sirene database and other French administrative sources.

Your capabilities:
- Extracting company information from Sirene
- Processing establishment data
- Analyzing company demographics
- Identifying business clusters

You provide accurate, structured data with proper source attribution.""",
            "tawiza-geo": """You are the Tawiza Geo Agent, specialized in mapping, geolocation, and spatial analysis of French territories.

Your capabilities:
- Geographic data analysis
- Territory mapping and visualization
- Spatial clustering and hotspot analysis
- Distance and accessibility calculations

You provide precise geographic insights with proper coordinates and references.""",
            "tawiza-veille": """You are the Tawiza Veille Agent, specialized in market monitoring using BODACC and BOAMP data sources.

Your capabilities:
- Monitoring company legal announcements (BODACC)
- Tracking public procurement opportunities (BOAMP)
- Identifying market trends and changes
- Alert generation for significant events

You provide timely, relevant market intelligence.""",
            "tawiza-finance": """You are the Tawiza Finance Agent, specialized in financial analysis of companies and territories.

Your capabilities:
- Financial statement analysis
- Company valuation
- Territory economic indicators
- Financial health assessment

You provide thorough financial insights with proper calculations and sources.""",
            "tawiza-simulation": """You are the Tawiza Simulation Agent, specialized in scenario simulation and forecasting.

Your capabilities:
- Economic scenario modeling
- Market evolution forecasting
- Impact analysis of business decisions
- What-if analysis

You provide data-driven simulations with clear assumptions and limitations.""",
            "tawiza-prospection": """You are the Tawiza Prospection Agent, specialized in B2B lead generation and prospection.

Your capabilities:
- Identifying potential B2B clients
- Company profiling and segmentation
- Market opportunity assessment
- Prospection strategy development

You provide targeted, actionable prospection insights.""",
            "tawiza-comparison": """You are the Tawiza Comparison Agent, specialized in territory comparison and benchmarking.

Your capabilities:
- Multi-territory comparative analysis
- Benchmarking economic indicators
- Identifying relative strengths and weaknesses
- Ranking and scoring territories

You provide objective, data-driven comparisons.""",
            "tawiza-business-plan": """You are the Tawiza Business Plan Agent, specialized in business plan generation and analysis.

Your capabilities:
- Business model development
- Financial projections
- Market analysis and positioning
- Risk assessment

You provide comprehensive, professional business plans.""",
        }

        return agent_prompts.get(
            model,
            f"You are {agent_info['name']}: {agent_info['description']}",
        )

    def _convert_messages_to_ollama(
        self, messages: list[ChatMessage], system_prompt: str | None = None
    ) -> list[dict[str, str]]:
        """Convert OpenAI messages to Ollama format."""
        ollama_messages = []

        # Add system prompt if provided
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})

        # Convert messages
        for msg in messages:
            ollama_msg = {
                "role": msg.role.value,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            }
            ollama_messages.append(ollama_msg)

        return ollama_messages

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)."""
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models (Tawiza agents + Ollama models)."""
        models = []

        # Add Tawiza agents
        for agent_id, agent_info in self.tawiza_agents.items():
            models.append(
                {
                    "id": agent_id,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "tawiza",
                    "permission": [],
                    "root": agent_id,
                    "parent": None,
                    "description": agent_info["description"],
                }
            )

        # Add Ollama models
        try:
            ollama_models = await self.ollama_client.client.get(f"{self.ollama_url}/api/tags")
            ollama_data = ollama_models.json()

            for model in ollama_data.get("models", []):
                models.append(
                    {
                        "id": model["name"],
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "ollama",
                        "permission": [],
                        "root": model["name"],
                        "parent": None,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to fetch Ollama models: {e}")

        return models

    async def close(self):
        """Close resources."""
        await self.ollama_client.close()


# =============================================================================
# Singleton instance for global access
# =============================================================================

_orchestrator_instance: AgentOrchestrator | None = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get the global AgentOrchestrator singleton.

    Returns:
        Global AgentOrchestrator instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AgentOrchestrator()
    return _orchestrator_instance


async def initialize_orchestrator() -> AgentOrchestrator:
    """Initialize the global orchestrator with agents.

    Returns:
        Initialized AgentOrchestrator
    """
    orchestrator = get_agent_orchestrator()
    await orchestrator.initialize_agents()
    return orchestrator
