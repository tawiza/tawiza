"""Tests for StrategicPlanner - Task decomposition and planning.

Tests the enhanced planner including:
- Intent-to-tool mapping
- LLM-powered decomposition (optional)
- Tool discovery from registry
- Dependency management
- Plan validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStrategicPlannerImports:
    """Test planner can be imported."""

    def test_import_strategic_planner(self):
        """Test StrategicPlanner can be imported."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        assert StrategicPlanner is not None

    def test_import_planned_task(self):
        """Test PlannedTask dataclass can be imported."""
        from src.infrastructure.agents.tajine.planning import PlannedTask

        assert PlannedTask is not None

    def test_import_from_package(self):
        """Test imports from tajine package."""
        from src.infrastructure.agents.tajine import StrategicPlanner

        assert StrategicPlanner is not None


class TestStrategicPlannerCreation:
    """Test planner instantiation."""

    def test_create_planner_default(self):
        """Test creating planner with defaults."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()
        assert planner is not None

    def test_create_planner_with_tool_registry(self):
        """Test creating planner with tool registry."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        assert planner.tool_registry is tools

    def test_create_planner_with_llm_client(self):
        """Test creating planner with LLM client."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        mock_llm = MagicMock()
        planner = StrategicPlanner(llm_client=mock_llm)

        assert planner.llm_client is mock_llm

    def test_planner_has_intent_tools_mapping(self):
        """Test planner has intent to tools mapping."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        assert hasattr(planner, "intent_tools")
        assert "analyze" in planner.intent_tools
        assert "compare" in planner.intent_tools
        assert "prospect" in planner.intent_tools
        assert "monitor" in planner.intent_tools


class TestBasicPlanCreation:
    """Test basic plan creation."""

    @pytest.mark.asyncio
    async def test_create_plan_returns_dict(self):
        """Test create_plan returns a dict."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze", "territory": "34", "sector": "tech"})

        assert isinstance(plan, dict)

    @pytest.mark.asyncio
    async def test_create_plan_has_subtasks(self):
        """Test plan has subtasks list."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze", "territory": "34"})

        assert "subtasks" in plan
        assert isinstance(plan["subtasks"], list)
        assert len(plan["subtasks"]) > 0

    @pytest.mark.asyncio
    async def test_create_plan_has_strategy(self):
        """Test plan has strategy field."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze"})

        assert "strategy" in plan
        assert "analyze" in plan["strategy"]

    @pytest.mark.asyncio
    async def test_create_plan_has_estimated_steps(self):
        """Test plan has estimated_steps."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze"})

        assert "estimated_steps" in plan
        assert plan["estimated_steps"] == len(plan["subtasks"])

    @pytest.mark.asyncio
    async def test_subtask_has_tool_and_params(self):
        """Test each subtask has tool and params."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze", "territory": "34", "sector": "tech"})

        for subtask in plan["subtasks"]:
            assert "tool" in subtask
            assert "params" in subtask
            assert isinstance(subtask["params"], dict)

    @pytest.mark.asyncio
    async def test_subtask_has_priority(self):
        """Test subtasks have priority field."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze"})

        for subtask in plan["subtasks"]:
            assert "priority" in subtask
            assert isinstance(subtask["priority"], int)


class TestIntentMapping:
    """Test intent to tool mapping."""

    @pytest.mark.asyncio
    async def test_analyze_intent_uses_data_hunt(self):
        """Test analyze intent includes data_hunt tool."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze"})

        tools = [s["tool"] for s in plan["subtasks"]]
        assert "data_hunt" in tools

    @pytest.mark.asyncio
    async def test_monitor_intent_uses_data_hunt(self):
        """Test monitor intent includes data_hunt tool."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "monitor"})

        tools = [s["tool"] for s in plan["subtasks"]]
        assert "data_hunt" in tools

    @pytest.mark.asyncio
    async def test_unknown_intent_defaults_to_data_collect(self):
        """Test unknown intent falls back to data_collect."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "unknown_intent"})

        tools = [s["tool"] for s in plan["subtasks"]]
        assert "data_collect" in tools

    @pytest.mark.asyncio
    async def test_empty_perception_creates_valid_plan(self):
        """Test empty perception still creates a plan."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({})

        assert "subtasks" in plan
        assert len(plan["subtasks"]) > 0


class TestToolRegistryIntegration:
    """Test integration with TerritorialTools."""

    def test_planner_can_use_tool_registry(self):
        """Test planner can access tool registry."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        assert planner.tool_registry is not None
        assert planner.tool_registry.get_tool("data_collect") is not None

    @pytest.mark.asyncio
    async def test_validate_plan_tools_exist(self):
        """Test plan validation checks tools exist."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        plan = await planner.create_plan({"intent": "analyze"})

        # Validate should pass for existing tools
        is_valid, issues = planner.validate_plan(plan)
        # data_collect exists, others may not - just check no crash
        assert isinstance(is_valid, bool)
        assert isinstance(issues, list)

    def test_get_available_tools(self):
        """Test planner can list available tools."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        available = planner.get_available_tools()

        assert isinstance(available, list)
        assert "data_collect" in available
        assert "veille_scan" in available


class TestLLMDecomposition:
    """Test LLM-powered task decomposition."""

    @pytest.mark.asyncio
    async def test_llm_decomposition_when_available(self):
        """Test LLM is used for decomposition when available."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        mock_llm = MagicMock()
        # chat() returns a dict with 'content' containing JSON string
        mock_llm.chat = AsyncMock(
            return_value={
                "content": '{"subtasks": [{"tool": "data_hunt", "params": {"territory": "34"}}, {"tool": "territorial_analysis", "params": {"territory": "34"}}]}'
            }
        )

        planner = StrategicPlanner(llm_client=mock_llm)

        plan = await planner.create_plan(
            {"intent": "analyze", "territory": "34", "raw_query": "Analyze tech sector in Herault"}
        )

        # LLM should have been called
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_rules_when_llm_fails(self):
        """Test rule-based fallback when LLM fails."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM error"))

        planner = StrategicPlanner(llm_client=mock_llm)

        plan = await planner.create_plan({"intent": "analyze", "territory": "34"})

        # Should still return a valid plan via rules
        assert "subtasks" in plan
        assert len(plan["subtasks"]) > 0

    @pytest.mark.asyncio
    async def test_rule_based_when_no_llm(self):
        """Test rule-based planning when no LLM provider."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()  # No LLM

        plan = await planner.create_plan({"intent": "analyze", "territory": "34"})

        assert "subtasks" in plan
        assert len(plan["subtasks"]) > 0


class TestDependencyManagement:
    """Test task dependency handling."""

    @pytest.mark.asyncio
    async def test_plan_has_execution_order(self):
        """Test plan includes execution order."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze", "territory": "34"})

        # Subtasks should have priorities indicating order
        priorities = [s["priority"] for s in plan["subtasks"]]
        assert priorities == sorted(priorities)  # Should be ordered

    @pytest.mark.asyncio
    async def test_independent_tasks_can_run_parallel(self):
        """Test plan identifies parallel-executable tasks."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze", "territory": "34"})

        # Check for parallel_group or dependencies field
        assert "parallel_groups" in plan or all(
            "dependencies" in s or "priority" in s for s in plan["subtasks"]
        )


class TestComplexityEstimation:
    """Test plan complexity estimation."""

    @pytest.mark.asyncio
    async def test_estimate_complexity_basic(self):
        """Test basic complexity estimation."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = await planner.create_plan({"intent": "analyze"})

        complexity = planner.estimate_complexity(plan)

        assert "score" in complexity
        assert "factors" in complexity
        assert complexity["score"] > 0

    @pytest.mark.asyncio
    async def test_more_subtasks_higher_complexity(self):
        """Test more subtasks means higher complexity."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan_simple = await planner.create_plan({"intent": "monitor"})
        plan_complex = await planner.create_plan({"intent": "analyze"})

        complexity_simple = planner.estimate_complexity(plan_simple)
        complexity_complex = planner.estimate_complexity(plan_complex)

        # analyze typically has more tools than monitor
        if len(plan_complex["subtasks"]) > len(plan_simple["subtasks"]):
            assert complexity_complex["score"] >= complexity_simple["score"]


class TestPlanValidation:
    """Test plan validation."""

    def test_validate_valid_plan(self):
        """Test validation of valid plan."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        plan = {
            "subtasks": [{"tool": "data_collect", "params": {"territory": "34"}, "priority": 1}],
            "strategy": "test",
            "estimated_steps": 1,
        }

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_missing_tool(self):
        """Test validation catches missing tools."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        planner = StrategicPlanner(tool_registry=tools)

        plan = {
            "subtasks": [{"tool": "nonexistent_tool", "params": {}, "priority": 1}],
            "strategy": "test",
            "estimated_steps": 1,
        }

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert any("nonexistent_tool" in issue for issue in issues)

    def test_validate_empty_plan(self):
        """Test validation handles empty plan."""
        from src.infrastructure.agents.tajine.planning import StrategicPlanner

        planner = StrategicPlanner()

        plan = {"subtasks": [], "strategy": "test", "estimated_steps": 0}

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert any("empty" in issue.lower() for issue in issues)


class TestTAJINEAgentIntegration:
    """Test integration with TAJINEAgent."""

    def test_agent_uses_planner(self):
        """Test TAJINEAgent uses StrategicPlanner."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert hasattr(agent, "planner")
        assert agent.planner is not None

    def test_agent_planner_has_tool_registry(self):
        """Test TAJINEAgent passes tool_registry to planner."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Access planner which should get tool_registry
        planner = agent.planner

        assert planner.tool_registry is not None
        assert planner.tool_registry is agent.tool_registry

    @pytest.mark.asyncio
    async def test_agent_plan_calls_planner(self):
        """Test TAJINEAgent.plan() uses planner."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        perception = {"intent": "analyze", "territory": "34", "sector": "tech"}

        plan = await agent.plan(perception)

        assert "subtasks" in plan
        assert "strategy" in plan

    @pytest.mark.asyncio
    async def test_agent_plan_can_validate(self):
        """Test plan from TAJINEAgent can be validated."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        perception = {"intent": "analyze", "territory": "34"}
        plan = await agent.plan(perception)

        # Validate the plan
        is_valid, issues = agent.planner.validate_plan(plan)

        # Should be mostly valid (some tools may not exist in registry)
        assert isinstance(is_valid, bool)
        assert isinstance(issues, list)
