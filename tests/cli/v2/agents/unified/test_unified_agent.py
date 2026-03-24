"""Tests for the unified agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.v2.agents.unified.models import AgentResult
from src.cli.v2.agents.unified.unified_agent import UnifiedAgent


class TestUnifiedAgent:
    @pytest.fixture
    def mock_planner(self):
        from src.cli.v2.agents.unified.models import ToolCall
        from src.cli.v2.agents.unified.planner import PlanResult

        mock = AsyncMock()
        # Immediately finish
        mock.plan_next_action = AsyncMock(
            side_effect=[
                PlanResult(
                    thought="I'll finish",
                    tool_call=ToolCall(name="finish", params={"answer": "Done!"}),
                )
            ]
        )
        return mock

    @pytest.fixture
    def mock_registry(self):
        mock = MagicMock()
        mock.get_tools_description.return_value = "- finish(answer): Complete task"
        mock.execute = AsyncMock(return_value={"status": "ok"})
        return mock

    @pytest.mark.asyncio
    async def test_run_simple_task(self, mock_planner, mock_registry):
        agent = UnifiedAgent(planner=mock_planner, tools=mock_registry, max_steps=5)

        result = await agent.run("Say hello")

        assert result.success is True
        assert result.answer == "Done!"
        assert len(result.steps) == 1

    @pytest.mark.asyncio
    async def test_run_reaches_max_steps(self, mock_registry):
        from src.cli.v2.agents.unified.models import ToolCall
        from src.cli.v2.agents.unified.planner import PlanResult

        # Planner that never finishes
        mock_planner = AsyncMock()
        mock_planner.plan_next_action = AsyncMock(
            return_value=PlanResult(
                thought="Still working", tool_call=ToolCall(name="test.loop", params={})
            )
        )

        agent = UnifiedAgent(planner=mock_planner, tools=mock_registry, max_steps=3)

        result = await agent.run("Infinite task")

        assert result.success is False
        assert "max steps" in result.error.lower()
        assert len(result.steps) == 3

    @pytest.mark.asyncio
    async def test_run_with_data_context(self, mock_planner, mock_registry):
        agent = UnifiedAgent(planner=mock_planner, tools=mock_registry)

        result = await agent.run("Analyze data", data="test.csv")

        # Verify planner was called with data in context
        call_kwargs = mock_planner.plan_next_action.call_args[1]
        assert "data" in call_kwargs["context"]
        assert call_kwargs["context"]["data"] == "test.csv"

    @pytest.mark.asyncio
    async def test_run_tool_execution_error(self, mock_planner, mock_registry):
        from src.cli.v2.agents.unified.models import ToolCall
        from src.cli.v2.agents.unified.planner import PlanResult

        # First call uses a tool, second call finishes
        mock_planner.plan_next_action = AsyncMock(
            side_effect=[
                PlanResult(thought="Use tool", tool_call=ToolCall(name="test.fail", params={})),
                PlanResult(
                    thought="Finish anyway",
                    tool_call=ToolCall(name="finish", params={"answer": "OK"}),
                ),
            ]
        )

        # Tool that throws
        mock_registry.execute = AsyncMock(side_effect=Exception("Tool failed"))

        agent = UnifiedAgent(planner=mock_planner, tools=mock_registry, max_steps=5)
        result = await agent.run("Test error handling")

        # Agent should continue after tool error and eventually finish
        assert result.success is True
        # First step should have error in observation
        assert result.steps[0].observation.success is False
        assert "Tool failed" in result.steps[0].observation.error
