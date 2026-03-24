"""Tests for Tool Router."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.unified.tool_router import (
    ExecutionPlan,
    PlanStep,
    TaskAnalysis,
    ToolCapability,
    ToolRouter,
)


class TestToolCapabilities:
    """Test tool capability definitions."""

    def test_all_tools_defined(self):
        """Should have all 5 tools defined."""
        router = ToolRouter()
        assert len(router.TOOLS) == 5
        assert "browser_use" in router.TOOLS
        assert "skyvern" in router.TOOLS
        assert "openmanus" in router.TOOLS
        assert "open_interpreter" in router.TOOLS
        assert "label_studio" in router.TOOLS

    def test_browser_use_capabilities(self):
        """Browser-Use should have correct capabilities."""
        router = ToolRouter()
        caps = router.get_capabilities("browser_use")

        assert "navigation" in caps.strengths
        assert "complex_spa" in caps.strengths
        assert "ai_reasoning" in caps.strengths
        assert caps.cost == "high"

    def test_openmanus_capabilities(self):
        """OpenManus should be good for bulk scraping."""
        router = ToolRouter()
        caps = router.get_capabilities("openmanus")

        assert "fast" in caps.strengths
        assert "bulk_scraping" in caps.strengths
        assert caps.cost == "low"

    def test_skyvern_capabilities(self):
        """Skyvern should have vision capabilities."""
        router = ToolRouter()
        caps = router.get_capabilities("skyvern")

        assert "vision" in caps.strengths
        assert "captcha" in caps.strengths

    def test_open_interpreter_capabilities(self):
        """Open Interpreter should handle code."""
        router = ToolRouter()
        caps = router.get_capabilities("open_interpreter")

        assert "code_execution" in caps.strengths

    def test_label_studio_capabilities(self):
        """Label Studio should handle annotation."""
        router = ToolRouter()
        caps = router.get_capabilities("label_studio")

        assert "annotation" in caps.strengths

    def test_unknown_tool_raises(self):
        """Should raise for unknown tool."""
        router = ToolRouter()
        with pytest.raises(ValueError, match="Unknown tool"):
            router.get_capabilities("unknown_tool")


class TestTaskAnalysis:
    """Test task analysis."""

    @pytest.mark.asyncio
    async def test_analyze_simple_scraping(self):
        """Should identify simple scraping task."""
        router = ToolRouter(llm_client=MagicMock())
        router._analyze_with_llm = AsyncMock(
            return_value={
                "task_type": "scraping",
                "complexity": "low",
                "requires_vision": False,
                "requires_js": False,
            }
        )

        analysis = await router.analyze("Scrape prices from example.com")

        assert analysis.task_type == "scraping"
        assert analysis.complexity == "low"

    @pytest.mark.asyncio
    async def test_analyze_complex_navigation(self):
        """Should identify complex navigation task."""
        router = ToolRouter(llm_client=MagicMock())
        router._analyze_with_llm = AsyncMock(
            return_value={
                "task_type": "navigation",
                "complexity": "high",
                "requires_vision": False,
                "requires_js": True,
                "requires_reasoning": True,
            }
        )

        analysis = await router.analyze("Login to site, navigate to dashboard, download report")

        assert analysis.complexity == "high"
        assert analysis.requires_reasoning is True

    @pytest.mark.asyncio
    async def test_analyze_with_rules_fallback(self):
        """Should use rule-based analysis when no LLM."""
        router = ToolRouter(llm_client=None)

        analysis = await router.analyze("Scrape product data from amazon.com")

        assert analysis.task_type == "scraping"

    @pytest.mark.asyncio
    async def test_analyze_code_task(self):
        """Should identify code execution task."""
        router = ToolRouter(llm_client=None)

        analysis = await router.analyze("Process and transform the data, calculate totals")

        assert analysis.task_type == "code"
        assert analysis.requires_code is True


class TestToolSelection:
    """Test tool selection logic."""

    @pytest.mark.asyncio
    async def test_select_openmanus_for_simple_scraping(self):
        """Should select OpenManus for simple scraping."""
        router = ToolRouter(llm_client=MagicMock())
        analysis = TaskAnalysis(
            task_type="scraping",
            complexity="low",
            requires_vision=False,
            requires_js=False,
            requires_reasoning=False,
        )

        tools = await router.select_tools(analysis)

        assert "openmanus" in tools
        # OpenManus should be first for simple scraping
        assert tools[0] == "openmanus"

    @pytest.mark.asyncio
    async def test_select_browser_use_for_reasoning(self):
        """Should select Browser-Use when reasoning needed."""
        router = ToolRouter(llm_client=MagicMock())
        analysis = TaskAnalysis(
            task_type="navigation",
            complexity="high",
            requires_vision=False,
            requires_js=True,
            requires_reasoning=True,
        )

        tools = await router.select_tools(analysis)

        assert "browser_use" in tools

    @pytest.mark.asyncio
    async def test_select_skyvern_for_vision(self):
        """Should select Skyvern when vision needed."""
        router = ToolRouter(llm_client=MagicMock())
        analysis = TaskAnalysis(
            task_type="extraction",
            complexity="medium",
            requires_vision=True,
            requires_js=False,
            requires_reasoning=False,
        )

        tools = await router.select_tools(analysis)

        assert "skyvern" in tools

    @pytest.mark.asyncio
    async def test_select_open_interpreter_for_code(self):
        """Should select Open Interpreter for code tasks."""
        router = ToolRouter(llm_client=MagicMock())
        analysis = TaskAnalysis(
            task_type="code",
            complexity="medium",
            requires_code=True,
        )

        tools = await router.select_tools(analysis)

        assert "open_interpreter" in tools

    @pytest.mark.asyncio
    async def test_select_label_studio_for_annotation(self):
        """Should select Label Studio for annotation."""
        router = ToolRouter(llm_client=MagicMock())
        analysis = TaskAnalysis(
            task_type="annotation",
            complexity="low",
            requires_annotation=True,
        )

        tools = await router.select_tools(analysis)

        assert "label_studio" in tools

    @pytest.mark.asyncio
    async def test_respect_enabled_tools(self):
        """Should only select from enabled tools."""
        router = ToolRouter(llm_client=MagicMock(), enabled_tools=["openmanus", "skyvern"])
        analysis = TaskAnalysis(task_type="code", requires_code=True)

        tools = await router.select_tools(analysis)

        # Open Interpreter not in enabled tools
        assert "open_interpreter" not in tools


class TestExecutionPlanning:
    """Test execution plan creation."""

    @pytest.mark.asyncio
    async def test_create_single_tool_plan(self):
        """Should create plan with single tool."""
        router = ToolRouter(llm_client=MagicMock())
        router.analyze = AsyncMock(
            return_value=TaskAnalysis(
                task_type="scraping",
                complexity="low",
            )
        )
        router.select_tools = AsyncMock(return_value=["openmanus"])

        plan = await router.plan("Scrape example.com")

        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "openmanus"
        assert plan.is_chain is False

    @pytest.mark.asyncio
    async def test_create_chain_plan(self):
        """Should create chain plan for multi-step task."""
        router = ToolRouter(llm_client=MagicMock())
        router.analyze = AsyncMock(
            return_value=TaskAnalysis(
                task_type="pipeline",
                complexity="high",
                steps=["scrape", "process", "annotate"],
            )
        )
        router.select_tools = AsyncMock(
            return_value=["openmanus", "open_interpreter", "label_studio"]
        )

        plan = await router.plan("Scrape data, process it, and prepare for annotation")

        assert len(plan.steps) >= 2
        assert plan.is_chain is True

    @pytest.mark.asyncio
    async def test_plan_has_fallback_tools(self):
        """Should include fallback tools when available."""
        router = ToolRouter(llm_client=MagicMock())
        router.analyze = AsyncMock(
            return_value=TaskAnalysis(
                task_type="scraping",
                complexity="medium",
            )
        )
        router.select_tools = AsyncMock(return_value=["openmanus", "skyvern"])

        plan = await router.plan("Scrape data")

        assert plan.steps[0].fallback_tool == "skyvern"


class TestPlanStep:
    """Test PlanStep dataclass."""

    def test_plan_step_defaults(self):
        """Should have correct defaults."""
        step = PlanStep(tool="openmanus", action="scrape")

        assert step.config == {}
        assert step.depends_on is None
        assert step.fallback_tool is None

    def test_plan_step_with_dependency(self):
        """Should support dependency."""
        step = PlanStep(tool="open_interpreter", action="process", depends_on=0)

        assert step.depends_on == 0


class TestTaskAnalysisDataclass:
    """Test TaskAnalysis dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        analysis = TaskAnalysis()

        assert analysis.task_type == "unknown"
        assert analysis.complexity == "medium"
        assert analysis.requires_vision is False
        assert analysis.requires_js is False
        assert analysis.requires_reasoning is False
        assert analysis.requires_code is False
        assert analysis.requires_annotation is False
        assert analysis.steps == []
        assert analysis.context == {}
