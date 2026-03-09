"""Unified agent executor for Tawiza CLI v2.

Provides a single interface to run all agent types:
- browser: Web automation with browser-use + Ollama
- analyst: Data analysis with pandas/sklearn
- coder: Code generation with AI
- ml: Machine learning pipelines
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class AgentResult:
    """Result from agent execution."""

    agent: str
    task: str
    status: str  # success, error, cancelled
    result: dict[str, Any] | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    logs: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)  # File paths created


class AgentExecutor:
    """Unified executor for all Tawiza agents."""

    # Agent metadata
    AGENTS = {
        "browser": {
            "name": "Browser Agent",
            "description": "Web automation and scraping with AI",
            "capabilities": ["navigate", "extract", "fill_form", "screenshot"],
            "requires": ["ollama"],
        },
        "analyst": {
            "name": "Data Analyst Agent",
            "description": "Data analysis, anomaly detection, preprocessing",
            "capabilities": ["analyze", "detect_anomalies", "recommend_preprocessing"],
            "requires": [],
        },
        "coder": {
            "name": "Code Generator Agent",
            "description": "AI-powered code generation and review",
            "capabilities": ["generate", "review", "refactor", "test"],
            "requires": ["ollama"],
        },
        "ml": {
            "name": "ML Engineer Agent",
            "description": "Machine learning pipelines and optimization",
            "capabilities": ["train", "optimize", "evaluate", "deploy"],
            "requires": [],
        },
    }

    def __init__(self, model: str = "qwen3.5:27b", headless: bool = True):
        """Initialize agent executor.

        Args:
            model: Ollama model for AI-powered agents
            headless: Run browser in headless mode
        """
        self.model = model
        self.headless = headless
        self._initialized_agents: dict[str, Any] = {}

    @classmethod
    def list_agents(cls) -> list[dict[str, Any]]:
        """List all available agents."""
        return [
            {"name": name, **info}
            for name, info in cls.AGENTS.items()
        ]

    @classmethod
    def get_agent_info(cls, agent_name: str) -> dict[str, Any] | None:
        """Get information about a specific agent."""
        if agent_name in cls.AGENTS:
            return {"name": agent_name, **cls.AGENTS[agent_name]}
        return None

    async def _get_browser_agent(self):
        """Get or create browser agent."""
        if "browser" not in self._initialized_agents:
            try:
                from src.infrastructure.agents.browser_agent_service import BrowserAgentService
                from src.infrastructure.ml.ollama import OllamaAdapter

                ollama = OllamaAdapter()
                self._initialized_agents["browser"] = BrowserAgentService(
                    ollama_adapter=ollama,
                    default_model=self.model,
                    headless=self.headless,
                )
                logger.info("Browser agent initialized")
            except ImportError as e:
                logger.error(f"Failed to import browser agent: {e}")
                raise RuntimeError(f"Browser agent dependencies not available: {e}")

        return self._initialized_agents["browser"]

    async def _get_analyst_agent(self):
        """Get or create analyst agent."""
        if "analyst" not in self._initialized_agents:
            try:
                from src.infrastructure.agents.advanced.data_analyst_agent import DataAnalystAgent
                self._initialized_agents["analyst"] = DataAnalystAgent()
                logger.info("Analyst agent initialized")
            except ImportError as e:
                logger.error(f"Failed to import analyst agent: {e}")
                raise RuntimeError(f"Analyst agent dependencies not available: {e}")

        return self._initialized_agents["analyst"]

    async def _get_coder_agent(self):
        """Get or create coder agent."""
        if "coder" not in self._initialized_agents:
            try:
                from src.infrastructure.agents.advanced.code_generator_agent import (
                    CodeGeneratorAgent,
                )
                agent = CodeGeneratorAgent()
                await agent.initialize()
                self._initialized_agents["coder"] = agent
                logger.info("Coder agent initialized")
            except ImportError as e:
                logger.error(f"Failed to import coder agent: {e}")
                raise RuntimeError(f"Coder agent dependencies not available: {e}")

        return self._initialized_agents["coder"]

    async def _get_ml_agent(self):
        """Get or create ML agent."""
        if "ml" not in self._initialized_agents:
            try:
                from src.infrastructure.agents.advanced.ml_engineer_agent import MLEngineerAgent
                self._initialized_agents["ml"] = MLEngineerAgent()
                logger.info("ML agent initialized")
            except ImportError as e:
                logger.error(f"Failed to import ML agent: {e}")
                raise RuntimeError(f"ML agent dependencies not available: {e}")

        return self._initialized_agents["ml"]

    async def run(
        self,
        agent_name: str,
        task: str,
        data: str | None = None,
        **kwargs
    ) -> AgentResult:
        """Execute an agent with the given task.

        Args:
            agent_name: Name of agent (browser, analyst, coder, ml)
            task: Natural language task description
            data: Optional data file path
            **kwargs: Additional agent-specific arguments

        Returns:
            AgentResult with execution details
        """
        if agent_name not in self.AGENTS:
            return AgentResult(
                agent=agent_name,
                task=task,
                status="error",
                error=f"Unknown agent: {agent_name}. Available: {list(self.AGENTS.keys())}"
            )

        start_time = datetime.now()
        logs = []

        try:
            logs.append(f"Starting {agent_name} agent...")

            if agent_name == "browser":
                result = await self._run_browser(task, **kwargs)
            elif agent_name == "analyst":
                result = await self._run_analyst(task, data, **kwargs)
            elif agent_name == "coder":
                result = await self._run_coder(task, **kwargs)
            elif agent_name == "ml":
                result = await self._run_ml(task, data, **kwargs)
            else:
                raise ValueError(f"Agent {agent_name} not implemented")

            duration = (datetime.now() - start_time).total_seconds()
            logs.append(f"Completed in {duration:.2f}s")

            return AgentResult(
                agent=agent_name,
                task=task,
                status="success",
                result=result,
                duration_seconds=duration,
                logs=logs,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logs.append(f"Error: {str(e)}")
            logger.exception(f"Agent {agent_name} failed")

            return AgentResult(
                agent=agent_name,
                task=task,
                status="error",
                error=str(e),
                duration_seconds=duration,
                logs=logs,
            )

    async def _run_browser(self, task: str, url: str | None = None, **kwargs) -> dict[str, Any]:
        """Run browser automation task."""
        agent = await self._get_browser_agent()

        task_config = {
            "description": task,
            "max_actions": kwargs.get("max_actions", 50),
            "timeout": kwargs.get("timeout", 300),
        }

        if url:
            task_config["url"] = url

        result = await agent.execute_task(task_config)
        return result

    async def _run_analyst(
        self,
        task: str,
        data: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Run data analysis task."""
        agent = await self._get_analyst_agent()

        if not data:
            return {
                "error": "Data file required for analyst agent",
                "usage": "tawiza run analyst -t 'analyze' -d data.csv"
            }

        data_path = Path(data)
        if not data_path.exists():
            return {"error": f"Data file not found: {data}"}

        # Run analysis
        report = await agent.analyze_dataset(str(data_path))

        # Convert dataclass to dict
        from dataclasses import asdict
        return {
            "report": asdict(report),
            "summary": {
                "rows": report.rows,
                "columns": report.columns,
                "quality_score": report.quality_score,
                "anomalies_count": len(report.anomalies_detected),
                "recommendations_count": len(report.recommendations),
            }
        }

    async def _run_coder(self, task: str, **kwargs) -> dict[str, Any]:
        """Run code generation task."""
        agent = await self._get_coder_agent()

        # Parse task to determine language and requirements
        language = kwargs.get("language", "python")
        framework = kwargs.get("framework")

        import uuid

        from src.infrastructure.agents.advanced.code_generator_agent import CodeGenerationRequest

        request = CodeGenerationRequest(
            request_id=str(uuid.uuid4())[:8],
            language=language,
            framework=framework,
            description=task,
            requirements=kwargs.get("requirements", []),
        )

        # Generate code
        generated = await agent.generate_code(request)

        from dataclasses import asdict
        return asdict(generated)

    async def _run_ml(
        self,
        task: str,
        data: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Run ML pipeline task."""
        agent = await self._get_ml_agent()

        if not data:
            return {
                "error": "Data file required for ML agent",
                "usage": "tawiza run ml -t 'train classification model' -d data.csv"
            }

        data_path = Path(data)
        if not data_path.exists():
            return {"error": f"Data file not found: {data}"}

        import uuid

        from src.infrastructure.agents.advanced.ml_engineer_agent import MLTrainingConfig

        # Infer problem type from task
        problem_type = "classification"
        if any(word in task.lower() for word in ["regress", "predict value", "forecast"]):
            problem_type = "regression"

        config = MLTrainingConfig(
            task_id=str(uuid.uuid4())[:8],
            dataset_path=str(data_path),
            target_column=kwargs.get("target", "target"),
            problem_type=problem_type,
            model_type=kwargs.get("model_type", "random_forest"),
            optimization_method=kwargs.get("optimization", "random_search"),
            max_trials=kwargs.get("max_trials", 20),
            gpu_acceleration=kwargs.get("gpu", True),
        )

        result = await agent.create_ml_pipeline(config)

        from dataclasses import asdict
        return asdict(result)

    async def stream_progress(
        self,
        agent_name: str,
        task_id: str
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream progress updates for a running task.

        Only supported by browser agent currently.
        """
        if agent_name == "browser":
            agent = await self._get_browser_agent()
            async for update in agent.stream_progress(task_id):
                yield update
        else:
            yield {"error": f"Streaming not supported for {agent_name} agent"}
