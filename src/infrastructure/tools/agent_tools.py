"""Agent Tools - Wrap advanced agents as callable tools.

This module provides adapters to expose existing agents as tools
that can be used by CAMEL, Manus, and S3 agents via the Tool Registry.
"""

import time
from typing import Any

from loguru import logger

from src.infrastructure.tools.base import BaseTool, ToolResult
from src.infrastructure.tools.registry import ToolRegistry


class AgentTool(BaseTool):
    """Wrapper that exposes an agent as a callable tool.

    This allows any BaseAgent-compatible class to be used as a tool
    in the unified Tool Registry.

    Example:
        >>> from src.infrastructure.agents.advanced import DataAnalystAgent
        >>>
        >>> tool = AgentTool(
        ...     agent_class=DataAnalystAgent,
        ...     tool_name="analyze_data",
        ...     tool_description="Analyze datasets and generate insights",
        ... )
        >>>
        >>> registry = ToolRegistry()
        >>> registry.register(tool)
    """

    def __init__(
        self,
        agent_class: type,
        tool_name: str,
        tool_description: str,
        agent_config: dict[str, Any] | None = None,
        custom_parameters_schema: dict[str, Any] | None = None,
        sandbox_required: bool = False,
    ):
        """Initialize agent tool wrapper.

        Args:
            agent_class: The agent class to wrap
            tool_name: Tool name for registry
            tool_description: Tool description for LLM
            agent_config: Configuration passed to agent constructor
            custom_parameters_schema: Custom JSON schema for parameters
            sandbox_required: Whether this tool needs sandbox execution
        """
        self._agent_class = agent_class
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._agent_config = agent_config or {}
        self._agent_instance: Any | None = None
        self._custom_parameters_schema = custom_parameters_schema
        self._sandbox_required = sandbox_required

    @property
    def name(self) -> str:
        return self._tool_name

    @property
    def description(self) -> str:
        return self._tool_description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        if self._custom_parameters_schema:
            return self._custom_parameters_schema

        # Default parameters for agent execution
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task to execute"},
                "context": {
                    "type": "object",
                    "description": "Additional context for the task",
                    "default": {},
                },
            },
            "required": ["task"],
        }

    @property
    def requires_sandbox(self) -> bool:
        return self._sandbox_required

    def _get_agent(self) -> Any:
        """Get or create the agent instance (lazy initialization)."""
        if self._agent_instance is None:
            self._agent_instance = self._agent_class(**self._agent_config)
            logger.debug(f"Created agent instance: {self._agent_class.__name__}")
        return self._agent_instance

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the agent with the given parameters.

        Args:
            **kwargs: Parameters including 'task' and optional 'context'

        Returns:
            ToolResult with agent execution outcome
        """
        import uuid
        from dataclasses import asdict, is_dataclass

        start_time = time.time()

        try:
            agent = self._get_agent()

            task = kwargs.get("task", "")
            context = kwargs.get("context", {})

            # Build task config
            task_config = {
                "prompt": task,
                "context": context,
                **{k: v for k, v in kwargs.items() if k not in ["task", "context"]},
            }

            # Special handling for BrowserAutomationAgent
            agent_class_name = self._agent_class.__name__
            result = None

            if agent_class_name == "BrowserAutomationAgent":
                # BrowserAutomationAgent needs AutomationTask dataclass
                from src.infrastructure.agents.advanced.browser_automation_agent import (
                    AutomationTask,
                )

                # Initialize browser if needed
                if not agent.browser:
                    await agent.initialize()

                # Normalize URL (add https:// if missing)
                url = kwargs.get("url", "https://example.com")
                if url and not url.startswith(("http://", "https://")):
                    url = f"https://{url}"

                automation_task = AutomationTask(
                    task_id=kwargs.get("task_id", str(uuid.uuid4())[:8]),
                    url=url,
                    objective=task or kwargs.get("objective", "Navigate and extract data"),
                    actions=[],  # Actions will be determined by the agent
                )
                result = await agent.execute_task(automation_task)

                # Cleanup browser
                await agent.cleanup()

            elif agent_class_name == "DeepResearchAgent":
                # DeepResearchAgent uses research() method with ResearchQuery
                from src.infrastructure.agents.advanced.deep_research_agent import ResearchQuery

                # Get query from multiple possible parameter names
                research_query = kwargs.get("topic") or kwargs.get("query") or task or ""
                logger.info(
                    f"DeepResearchAgent query: {research_query[:100] if research_query else 'EMPTY'}"
                )

                # Map depth string to integer
                depth_map = {"quick": 1, "standard": 2, "comprehensive": 3}
                depth_str = kwargs.get("depth", "standard")
                depth = depth_map.get(depth_str, 2) if isinstance(depth_str, str) else depth_str

                query = ResearchQuery(
                    query=research_query,
                    depth=depth,
                    max_sources=kwargs.get("max_sources", 5),
                )
                result = await agent.research(query)

            # Try different execution methods based on agent interface
            elif hasattr(agent, "execute_task"):
                result = await agent.execute_task(task_config)
            elif hasattr(agent, "run"):
                result = await agent.run(task_config)
            elif hasattr(agent, "process"):
                result = await agent.process(task)
            elif hasattr(agent, "analyze"):  # For DataAnalystAgent
                result = await agent.analyze(**kwargs)
            elif hasattr(agent, "generate"):  # For CodeGeneratorAgent
                result = await agent.generate(**kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Agent {agent_class_name} has no supported execute method",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Convert dataclass results to dict for JSON serialization
            if is_dataclass(result) and not isinstance(result, type):
                result = asdict(result)

            execution_time = (time.time() - start_time) * 1000

            return ToolResult(
                success=True,
                output=result,
                metadata={
                    "agent_class": self._agent_class.__name__,
                    "task": task[:100] if task else None,
                },
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.exception(f"Agent tool execution failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={
                    "agent_class": self._agent_class.__name__,
                    "exception_type": type(e).__name__,
                },
                execution_time_ms=execution_time,
            )


class AgentToolFactory:
    """Factory for creating and registering agent tools.

    Simplifies registration of multiple agents as tools.

    Example:
        >>> factory = AgentToolFactory()
        >>> registered = factory.register_advanced_agents()
        >>> print(f"Registered {len(registered)} agent tools")
    """

    def __init__(self, registry: ToolRegistry | None = None):
        """Initialize factory.

        Args:
            registry: Tool registry to use (creates new if not provided)
        """
        # Use 'is None' instead of 'or' because ToolRegistry.__len__ returns 0 when empty
        self.registry = registry if registry is not None else ToolRegistry()
        self._registered: list[str] = []

    def register_agent(
        self,
        agent_class: type,
        name: str,
        description: str,
        parameters_schema: dict[str, Any] | None = None,
        category: str = "agent",
        sandbox_required: bool = False,
        **agent_config,
    ) -> AgentTool:
        """Register an agent as a tool.

        Args:
            agent_class: Agent class to wrap
            name: Tool name
            description: Tool description
            parameters_schema: Custom JSON schema for parameters
            category: Tool category for organization
            sandbox_required: Whether sandbox execution is needed
            **agent_config: Config passed to agent constructor

        Returns:
            Created AgentTool
        """
        tool = AgentTool(
            agent_class=agent_class,
            tool_name=name,
            tool_description=description,
            agent_config=agent_config if agent_config else None,
            custom_parameters_schema=parameters_schema,
            sandbox_required=sandbox_required,
        )

        try:
            self.registry.register(tool, category=category)
            self._registered.append(name)
            logger.info(f"Registered agent as tool: {name}")
        except ValueError as e:
            logger.warning(f"Tool already registered: {name} - {e}")

        return tool

    def register_advanced_agents(self) -> list[str]:
        """Register all advanced agents as tools.

        Returns:
            List of registered tool names
        """
        registered = []

        # Import agents dynamically to avoid circular imports
        try:
            from src.infrastructure.agents.advanced import DataAnalystAgent

            self.register_agent(
                agent_class=DataAnalystAgent,
                name="analyze_data",
                description="Analyze datasets, generate statistics, create visualizations, and extract insights from data.",
                category="data",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": ["object", "array", "string"],
                            "description": "Data to analyze (dict, list, or file path)",
                        },
                        "analysis_type": {
                            "type": "string",
                            "description": "Type of analysis",
                            "enum": ["summary", "correlation", "trends", "visualization"],
                            "default": "summary",
                        },
                    },
                    "required": ["data"],
                },
            )
            registered.append("analyze_data")
        except ImportError as e:
            logger.warning(f"Could not import DataAnalystAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import MLEngineerAgent

            self.register_agent(
                agent_class=MLEngineerAgent,
                name="ml_pipeline",
                description="Build, train, and evaluate machine learning models. Supports training, fine-tuning, and prediction.",
                category="ml",
                sandbox_required=True,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "ML task to perform",
                            "enum": ["train", "predict", "evaluate", "fine-tune"],
                        },
                        "model_name": {"type": "string", "description": "Model name or path"},
                        "data_path": {
                            "type": "string",
                            "description": "Path to training/prediction data",
                        },
                    },
                    "required": ["task"],
                },
            )
            registered.append("ml_pipeline")
        except ImportError as e:
            logger.warning(f"Could not import MLEngineerAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import CodeGeneratorAgent

            self.register_agent(
                agent_class=CodeGeneratorAgent,
                name="generate_code",
                description="Generate code in Python, JavaScript, TypeScript, or other languages based on requirements.",
                category="code",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "requirements": {
                            "type": "string",
                            "description": "Description of what the code should do",
                        },
                        "language": {
                            "type": "string",
                            "description": "Programming language",
                            "enum": ["python", "javascript", "typescript", "bash", "sql"],
                            "default": "python",
                        },
                        "style": {
                            "type": "string",
                            "description": "Code style",
                            "enum": ["minimal", "documented", "production"],
                            "default": "documented",
                        },
                    },
                    "required": ["requirements"],
                },
            )
            registered.append("generate_code")
        except ImportError as e:
            logger.warning(f"Could not import CodeGeneratorAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import BrowserAutomationAgent

            self.register_agent(
                agent_class=BrowserAutomationAgent,
                name="browser_action",
                description="Automate browser actions: navigate, click, fill forms, extract content from web pages.",
                category="browser",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Browser action to perform",
                            "enum": ["navigate", "click", "type", "extract", "screenshot"],
                        },
                        "url": {"type": "string", "description": "URL to navigate to"},
                        "selector": {"type": "string", "description": "CSS selector for element"},
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["action"],
                },
            )
            registered.append("browser_action")
        except ImportError as e:
            logger.warning(f"Could not import BrowserAutomationAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import WebCrawlerAgent

            self.register_agent(
                agent_class=WebCrawlerAgent,
                name="crawl_web",
                description="Crawl websites, extract structured data, follow links, and build sitemaps.",
                category="web",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "start_url": {
                            "type": "string",
                            "description": "URL to start crawling from",
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "Maximum pages to crawl",
                            "default": 10,
                        },
                        "extract_pattern": {
                            "type": "string",
                            "description": "CSS selector for content extraction",
                        },
                    },
                    "required": ["start_url"],
                },
            )
            registered.append("crawl_web")
        except ImportError as e:
            logger.warning(f"Could not import WebCrawlerAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import DeepResearchAgent

            self.register_agent(
                agent_class=DeepResearchAgent,
                name="deep_research",
                description="Conduct deep research on a topic using multiple sources, synthesize findings, and generate reports.",
                category="search",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Research topic or question"},
                        "depth": {
                            "type": "string",
                            "description": "Research depth",
                            "enum": ["quick", "standard", "comprehensive"],
                            "default": "standard",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Preferred sources (URLs or source types)",
                        },
                    },
                    "required": ["topic"],
                },
            )
            registered.append("deep_research")
        except ImportError as e:
            logger.warning(f"Could not import DeepResearchAgent: {e}")

        try:
            from src.infrastructure.agents.advanced import S3StorageAgent

            self.register_agent(
                agent_class=S3StorageAgent,
                name="s3_storage",
                description="Store and retrieve files from S3-compatible storage (MinIO, AWS S3).",
                category="file",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Storage operation",
                            "enum": ["upload", "download", "list", "delete"],
                        },
                        "bucket": {"type": "string", "description": "S3 bucket name"},
                        "key": {"type": "string", "description": "Object key/path"},
                        "local_path": {
                            "type": "string",
                            "description": "Local file path for upload/download",
                        },
                    },
                    "required": ["operation", "bucket"],
                },
            )
            registered.append("s3_storage")
        except ImportError as e:
            logger.warning(f"Could not import S3StorageAgent: {e}")

        logger.info(f"Registered {len(registered)} advanced agents as tools")
        return registered

    def register_camel_agents(self) -> list[str]:
        """Register CAMEL workforce agents as tools.

        Exposes CAMEL territorial intelligence agents for use by other agents.

        Returns:
            List of registered tool names
        """
        registered = []

        try:
            from src.infrastructure.agents.camel.workforce import create_data_agent

            # Wrap the CAMEL ChatAgent factory
            self.register_agent(
                agent_class=_CamelAgentWrapper,
                name="territorial_data",
                description="Collect enterprise data from French public databases (Sirene INSEE). Searches by activity, location, and filters by size.",
                category="camel",
                factory_func=create_data_agent,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g., 'restaurants à Lyon', 'entreprises BTP Marseille')",
                        },
                        "commune": {"type": "string", "description": "City name (optional)"},
                        "code_naf": {
                            "type": "string",
                            "description": "NAF activity code (optional)",
                        },
                    },
                    "required": ["query"],
                },
            )
            registered.append("territorial_data")
        except ImportError as e:
            logger.warning(f"Could not import CAMEL DataAgent: {e}")

        try:
            from src.infrastructure.agents.camel.workforce import create_geo_agent

            self.register_agent(
                agent_class=_CamelAgentWrapper,
                name="territorial_geo",
                description="Analyze geographic distribution of enterprises on a territory. Creates maps and identifies clusters.",
                category="camel",
                factory_func=create_geo_agent,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "enterprises": {
                            "type": "array",
                            "description": "List of enterprise data with addresses",
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["distribution", "clusters", "density", "coverage"],
                            "default": "distribution",
                        },
                    },
                    "required": ["enterprises"],
                },
            )
            registered.append("territorial_geo")
        except ImportError as e:
            logger.warning(f"Could not import CAMEL GeoAgent: {e}")

        try:
            from src.infrastructure.agents.camel.workforce import create_analyst_agent

            self.register_agent(
                agent_class=_CamelAgentWrapper,
                name="territorial_analyst",
                description="Analyze collected territorial data. Identifies market trends, competitive landscape, and opportunities.",
                category="camel",
                factory_func=create_analyst_agent,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "object",
                            "description": "Collected data from DataAgent and GeoAgent",
                        },
                        "focus": {
                            "type": "string",
                            "description": "Analysis focus area",
                            "enum": [
                                "market_size",
                                "competition",
                                "opportunities",
                                "risks",
                                "full",
                            ],
                            "default": "full",
                        },
                    },
                    "required": ["data"],
                },
            )
            registered.append("territorial_analyst")
        except ImportError as e:
            logger.warning(f"Could not import CAMEL AnalystAgent: {e}")

        try:
            from src.infrastructure.agents.camel.workforce import create_web_agent

            self.register_agent(
                agent_class=_CamelAgentWrapper,
                name="territorial_web",
                description="Search web for additional context about enterprises and territories. News, events, local info.",
                category="camel",
                factory_func=create_web_agent,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Web search query"},
                        "territory": {
                            "type": "string",
                            "description": "Geographic focus (city, region)",
                        },
                    },
                    "required": ["query"],
                },
            )
            registered.append("territorial_web")
        except ImportError as e:
            logger.warning(f"Could not import CAMEL WebAgent: {e}")

        logger.info(f"Registered {len(registered)} CAMEL agents as tools")
        return registered

    def get_registered(self) -> list[str]:
        """Get list of registered tool names."""
        return self._registered.copy()


class _CamelAgentWrapper:
    """Wrapper to adapt CAMEL ChatAgent to our tool interface."""

    def __init__(self, factory_func=None, **kwargs):
        self._factory_func = factory_func
        self._agent = None
        self._kwargs = kwargs

    def _get_agent(self):
        if self._agent is None and self._factory_func:
            self._agent = self._factory_func()
        return self._agent

    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """Execute task using CAMEL agent."""
        agent = self._get_agent()
        if not agent:
            return {"success": False, "error": "Agent not initialized"}

        try:
            # CAMEL ChatAgent uses step() for single interaction
            query = task_config.get("query") or task_config.get("task", "")
            response = agent.step(query)

            return {
                "success": True,
                "result": response.msg.content if response.msg else str(response),
                "metadata": {
                    "agent_type": "camel",
                    "model": getattr(agent, "model_type", "unknown"),
                },
            }
        except Exception as e:
            logger.error(f"CAMEL agent execution failed: {e}")
            return {"success": False, "error": str(e)}


def create_unified_registry(
    include_advanced: bool = True,
    include_camel: bool = True,
) -> ToolRegistry:
    """Create a Tool Registry with all agent tools registered.

    This is the main entry point for getting a fully-configured registry.

    Args:
        include_advanced: Include advanced agents (DataAnalyst, MLEngineer, etc.)
        include_camel: Include CAMEL territorial agents

    Returns:
        ToolRegistry with all agent tools registered
    """
    registry = ToolRegistry()
    factory = AgentToolFactory(registry)

    if include_advanced:
        factory.register_advanced_agents()

    if include_camel:
        factory.register_camel_agents()

    # Register signals bridge tools (connects agent to collector DB)
    try:
        from src.infrastructure.agents.tajine.tools.signals_bridge import register_signals_tools

        register_signals_tools(registry)
    except Exception as e:
        logger.warning(f"Failed to register signals bridge tools: {e}")

    logger.info(f"Created unified registry with {len(registry)} tools")
    return registry
