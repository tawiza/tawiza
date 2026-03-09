"""Tool Router - Intelligent tool selection for tasks."""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolCapability:
    """Describes a tool's capabilities.

    Attributes:
        name: Tool identifier
        strengths: List of things this tool does well
        weaknesses: List of limitations
        use_when: Human-readable description of when to use
        cost: Resource cost level (low/medium/high)
    """

    name: str
    strengths: list[str]
    weaknesses: list[str]
    use_when: str
    cost: str = "low"  # low, medium, high (tokens/time)


@dataclass
class TaskAnalysis:
    """Analysis result for a task.

    Captures what the task requires to help with tool selection.
    """

    task_type: str = "unknown"
    complexity: str = "medium"  # low, medium, high
    requires_vision: bool = False
    requires_js: bool = False
    requires_reasoning: bool = False
    requires_code: bool = False
    requires_annotation: bool = False
    steps: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    """Single step in execution plan.

    Attributes:
        tool: Name of tool to use
        action: Action description
        config: Tool-specific configuration
        depends_on: Index of step this depends on
        fallback_tool: Backup tool if primary fails
    """

    tool: str
    action: str
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: int | None = None  # Index of step this depends on
    fallback_tool: str | None = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task.

    Contains all steps needed to complete a task,
    with tool assignments and dependencies.
    """

    task: str
    analysis: TaskAnalysis
    steps: list[PlanStep]
    is_chain: bool = False
    is_parallel: bool = False
    estimated_duration: str = "unknown"


class ToolRouter:
    """Routes tasks to appropriate tools based on analysis.

    Uses LLM for task understanding and rule-based matching
    for tool selection. Each tool has defined strengths and
    weaknesses that influence selection.

    Example:
        router = ToolRouter()
        plan = await router.plan("Scrape prices from amazon.com")
        print(f"Using: {plan.steps[0].tool}")
    """

    # Tool capability definitions
    TOOLS: dict[str, ToolCapability] = {
        "browser_use": ToolCapability(
            name="browser_use",
            strengths=["navigation", "complex_spa", "ai_reasoning", "dynamic_content"],
            weaknesses=["slow", "high_token_cost"],
            use_when="Task requires reasoning, adaptation, or complex navigation",
            cost="high",
        ),
        "skyvern": ToolCapability(
            name="skyvern",
            strengths=["vision", "captcha", "anti_bot", "visual_extraction"],
            weaknesses=["setup_complex", "slower"],
            use_when="Visual extraction or sites with anti-bot measures",
            cost="medium",
        ),
        "openmanus": ToolCapability(
            name="openmanus",
            strengths=["fast", "bulk_scraping", "scriptable", "low_resource"],
            weaknesses=["fragile_to_dom_changes", "no_vision"],
            use_when="Simple, repetitive scraping tasks",
            cost="low",
        ),
        "open_interpreter": ToolCapability(
            name="open_interpreter",
            strengths=["code_execution", "data_processing", "api_calls", "file_ops"],
            weaknesses=["security_risk", "needs_sandbox"],
            use_when="Data transformation, API calls, or code execution needed",
            cost="medium",
        ),
        "label_studio": ToolCapability(
            name="label_studio",
            strengths=["annotation", "human_qa", "labeling_workflows"],
            weaknesses=["human_latency", "async"],
            use_when="Data needs human validation or labeling",
            cost="low",
        ),
    }

    def __init__(
        self,
        llm_client: Any | None = None,
        enabled_tools: list[str] | None = None,
    ):
        """Initialize tool router.

        Args:
            llm_client: LLM client for task analysis
            enabled_tools: List of enabled tool names, all if None
        """
        self.llm_client = llm_client
        self.enabled_tools = enabled_tools or list(self.TOOLS.keys())

        logger.info(f"ToolRouter initialized with tools: {self.enabled_tools}")

    def get_capabilities(self, tool_name: str) -> ToolCapability:
        """Get capabilities for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool capability description

        Raises:
            ValueError: If tool is not recognized
        """
        if tool_name not in self.TOOLS:
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.TOOLS[tool_name]

    async def _analyze_with_llm(self, task: str) -> dict[str, Any]:
        """Analyze task using LLM.

        Args:
            task: Task description

        Returns:
            Analysis result dictionary
        """
        if self.llm_client is None:
            # Fallback to rule-based analysis
            return self._analyze_with_rules(task)

        prompt = f"""Analyze this task and return JSON:
Task: {task}

Return:
{{
    "task_type": "scraping|navigation|extraction|code|annotation|pipeline",
    "complexity": "low|medium|high",
    "requires_vision": true/false,
    "requires_js": true/false,
    "requires_reasoning": true/false,
    "requires_code": true/false,
    "requires_annotation": true/false,
    "steps": ["step1", "step2", ...]
}}"""

        try:
            response = await self.llm_client.generate(prompt)
            import json
            return json.loads(response)
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}, falling back to rules")
            return self._analyze_with_rules(task)

    def _analyze_with_rules(self, task: str) -> dict[str, Any]:
        """Rule-based task analysis fallback.

        Simple keyword matching when LLM is not available.
        """
        task_lower = task.lower()

        result = {
            "task_type": "unknown",
            "complexity": "medium",
            "requires_vision": False,
            "requires_js": False,
            "requires_reasoning": False,
            "requires_code": False,
            "requires_annotation": False,
            "steps": [],
        }

        # Detect task type
        if any(w in task_lower for w in ["scrape", "collect", "extract", "crawl"]):
            result["task_type"] = "scraping"
        elif any(w in task_lower for w in ["navigate", "login", "click", "fill"]):
            result["task_type"] = "navigation"
            result["requires_js"] = True
        elif any(w in task_lower for w in ["analyze", "process", "transform", "calculate"]):
            result["task_type"] = "code"
            result["requires_code"] = True
        elif any(w in task_lower for w in ["annotate", "label", "review", "validate"]):
            result["task_type"] = "annotation"
            result["requires_annotation"] = True

        # Detect complexity
        if any(w in task_lower for w in ["simple", "basic", "just", "only"]):
            result["complexity"] = "low"
        elif any(w in task_lower for w in ["complex", "multiple", "advanced", "then"]):
            result["complexity"] = "high"

        # Detect special requirements
        if any(w in task_lower for w in ["captcha", "screenshot", "visual", "image"]):
            result["requires_vision"] = True
        if any(w in task_lower for w in ["think", "decide", "figure out", "understand"]):
            result["requires_reasoning"] = True

        return result

    async def analyze(self, task: str, context: dict | None = None) -> TaskAnalysis:
        """Analyze a task to understand requirements.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Task analysis result
        """
        result = await self._analyze_with_llm(task)

        return TaskAnalysis(
            task_type=result.get("task_type", "unknown"),
            complexity=result.get("complexity", "medium"),
            requires_vision=result.get("requires_vision", False),
            requires_js=result.get("requires_js", False),
            requires_reasoning=result.get("requires_reasoning", False),
            requires_code=result.get("requires_code", False),
            requires_annotation=result.get("requires_annotation", False),
            steps=result.get("steps", []),
            context=context or {},
        )

    async def select_tools(self, analysis: TaskAnalysis) -> list[str]:
        """Select best tools for the analyzed task.

        Uses a scoring system based on task requirements
        and tool capabilities.

        Args:
            analysis: Task analysis result

        Returns:
            List of tool names in priority order
        """
        scores: dict[str, float] = {}

        for tool_name in self.enabled_tools:
            cap = self.TOOLS[tool_name]
            score = 0.0

            # Score based on task type match
            if analysis.task_type == "scraping":
                if tool_name == "openmanus":
                    score += 0.8 if analysis.complexity == "low" else 0.4
                elif tool_name == "browser_use":
                    score += 0.6 if analysis.complexity == "high" else 0.3
                elif tool_name == "skyvern":
                    score += 0.5

            elif analysis.task_type == "navigation":
                if tool_name == "browser_use":
                    score += 0.9
                elif tool_name == "skyvern":
                    score += 0.6
                elif tool_name == "openmanus":
                    score += 0.3

            elif analysis.task_type == "code":
                if tool_name == "open_interpreter":
                    score += 1.0

            elif analysis.task_type == "annotation" and tool_name == "label_studio":
                score += 1.0

            # Bonus for special requirements
            if analysis.requires_vision and "vision" in cap.strengths:
                score += 0.3
            if analysis.requires_reasoning and "ai_reasoning" in cap.strengths:
                score += 0.3
            if analysis.requires_code and "code_execution" in cap.strengths:
                score += 0.3

            # Penalty for cost on simple tasks
            if analysis.complexity == "low" and cap.cost == "high":
                score -= 0.2

            scores[tool_name] = score

        # Sort by score and return tools above threshold
        sorted_tools = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [t for t, s in sorted_tools if s > 0.2]

        logger.debug(f"Tool scores: {scores}, selected: {selected}")
        return selected if selected else [sorted_tools[0][0]]

    async def plan(self, task: str, context: dict | None = None) -> ExecutionPlan:
        """Create execution plan for a task.

        Analyzes the task, selects tools, and creates
        a step-by-step execution plan.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Complete execution plan
        """
        analysis = await self.analyze(task, context)
        tools = await self.select_tools(analysis)

        steps = []
        is_chain = len(analysis.steps) > 1 or len(tools) > 1

        if analysis.steps:
            # Multi-step task
            for i, step_desc in enumerate(analysis.steps):
                step_analysis = await self.analyze(step_desc)
                step_tools = await self.select_tools(step_analysis)

                steps.append(PlanStep(
                    tool=step_tools[0] if step_tools else tools[0],
                    action=step_desc,
                    depends_on=i - 1 if i > 0 else None,
                    fallback_tool=step_tools[1] if len(step_tools) > 1 else None,
                ))
        else:
            # Single-step task
            steps.append(PlanStep(
                tool=tools[0],
                action=task,
                fallback_tool=tools[1] if len(tools) > 1 else None,
            ))

        return ExecutionPlan(
            task=task,
            analysis=analysis,
            steps=steps,
            is_chain=is_chain,
        )
