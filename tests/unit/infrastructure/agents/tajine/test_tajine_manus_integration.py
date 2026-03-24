"""Tests for TAJINE-Manus integration.

Tests the connection between TAJINEAgent and ManusAgent including:
- ManusAgent creation and lazy loading
- Delegation with proper result handling
- Fallback behavior when ManusAgent unavailable
- Error handling during delegation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestManusAgentCreation:
    """Test ManusAgent creation from TAJINEAgent."""

    @pytest.mark.asyncio
    async def test_create_manus_agent_success(self):
        """Test successful ManusAgent creation."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Mock successful ManusAgent creation
        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={"status": "completed", "result": {"data": "test"}}
        )

        with patch(
            "src.infrastructure.agents.manus.create_manus_agent",
            new_callable=AsyncMock,
            return_value=mock_manus,
        ):
            manus = await agent._create_manus_agent()
            assert manus is not None

    @pytest.mark.asyncio
    async def test_create_manus_agent_import_error(self):
        """Test graceful handling when ManusAgent import fails."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        with patch("src.infrastructure.agents.tajine.tajine_agent.logger") as mock_logger:
            # Simulate import error by making the import fail
            with patch.dict("sys.modules", {"src.infrastructure.agents.manus": None}):
                manus = await agent._create_manus_agent()

            assert manus is None

    @pytest.mark.asyncio
    async def test_create_manus_agent_handles_connection_error(self):
        """Test that ManusAgent creation handles errors gracefully."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Mock OllamaClient at import location to raise connection error
        with patch(
            "src.infrastructure.llm.ollama_client.OllamaClient",
            side_effect=Exception("Connection refused"),
        ):
            manus = await agent._create_manus_agent()
            # Should return None on error
            assert manus is None


class TestDelegationWithManus:
    """Test delegation to ManusAgent."""

    @pytest.mark.asyncio
    async def test_delegate_with_manus_success(self):
        """Test successful delegation to ManusAgent."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Create mock ManusAgent
        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={"status": "completed", "result": {"companies": 847, "iterations": 3}}
        )

        # Pre-set the manus agent
        agent._manus_agent = mock_manus

        result = await agent.delegate(
            {
                "tool": "data_collect",
                "params": {"territory": "34", "sector": "tech"},
                "timeout": 120,
            }
        )

        assert result["status"] == "completed"
        assert result["success"] is True
        assert result["tool"] == "data_collect"
        assert result["metadata"]["agent"] == "manus"

    @pytest.mark.asyncio
    async def test_delegate_with_manus_failure(self):
        """Test delegation when ManusAgent returns failure."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={"status": "failed", "error": "Tool not found"}
        )

        agent._manus_agent = mock_manus

        result = await agent.delegate({"tool": "unknown_tool", "params": {}})

        assert result["status"] == "failed"
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delegate_manus_raises_exception_triggers_fallback(self):
        """Test delegation falls back to tool_registry when ManusAgent raises exception."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(side_effect=Exception("Network timeout"))

        agent._manus_agent = mock_manus

        # When Manus fails, delegate() falls back to _fallback_delegate
        # which executes via tool_registry or simulation
        result = await agent.delegate({"tool": "data_collect", "params": {"territory": "34"}})

        # Fallback should succeed (via tool_registry or simulation)
        assert result["status"] == "completed"
        assert result["success"] is True
        assert result["metadata"]["agent"] in ("tool_registry", "simulation")

    @pytest.mark.asyncio
    async def test_delegate_lazy_loads_manus(self):
        """Test that delegate() lazy-loads ManusAgent if not available."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()
        assert agent._manus_agent is None

        # Mock _create_manus_agent to track if called
        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(return_value={"status": "completed", "result": {}})

        with patch.object(
            agent, "_create_manus_agent", new_callable=AsyncMock, return_value=mock_manus
        ) as mock_create:
            await agent.delegate({"tool": "test", "params": {}})
            mock_create.assert_called_once()


class TestFallbackBehavior:
    """Test fallback when ManusAgent unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_when_manus_unavailable(self):
        """Test fallback delegate is used when ManusAgent cannot be created."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Mock _create_manus_agent to return None (unavailable)
        with patch.object(agent, "_create_manus_agent", new_callable=AsyncMock, return_value=None):
            # data_collect is a registered tool, so it uses tool_registry
            result = await agent.delegate({"tool": "data_collect", "params": {"territory": "34"}})

            assert result["status"] == "completed"
            assert result["success"] is True
            # Uses tool_registry for registered tools, simulation for unknown
            assert result["metadata"]["agent"] in ("tool_registry", "simulation")

    @pytest.mark.asyncio
    async def test_fallback_delegate_returns_stub(self):
        """Test _fallback_delegate returns proper simulation for unknown tools."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Use an unknown tool to get the simulation response
        result = await agent._fallback_delegate(
            {"tool": "unknown_tool_xyz", "params": {"key": "value"}}
        )

        assert result["status"] == "completed"
        assert result["tool"] == "unknown_tool_xyz"
        assert result["success"] is True
        assert "unknown_tool_xyz" in result["result"]["message"]
        assert result["result"]["params_received"] == {"key": "value"}
        assert result["metadata"]["agent"] == "simulation"

    @pytest.mark.asyncio
    async def test_fallback_handles_missing_params(self):
        """Test fallback handles subtask with missing params."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        result = await agent._fallback_delegate({"tool": "test_tool"})

        assert result["status"] == "completed"
        assert result["result"]["params_received"] == {}


class TestDelegationResultNormalization:
    """Test that delegation results are properly normalized."""

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self):
        """Test delegation result always has required fields."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={"status": "completed", "result": {"data": "test"}}
        )

        agent._manus_agent = mock_manus

        result = await agent.delegate({"tool": "test_tool", "params": {}})

        # Check all required fields present
        assert "status" in result
        assert "tool" in result
        assert "result" in result
        assert "success" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_metadata_includes_iterations(self):
        """Test metadata includes iteration count from ManusAgent."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={"status": "completed", "result": {"iterations": 5, "data": "test"}}
        )

        agent._manus_agent = mock_manus

        result = await agent.delegate({"tool": "test_tool", "params": {}})

        assert result["metadata"]["iterations"] == 5

    @pytest.mark.asyncio
    async def test_tool_name_preserved_in_result(self):
        """Test tool name is preserved in result."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(return_value={"status": "completed", "result": {}})

        agent._manus_agent = mock_manus

        result = await agent.delegate({"tool": "my_custom_tool", "params": {"key": "value"}})

        assert result["tool"] == "my_custom_tool"


class TestSubtaskPromptFormatting:
    """Test subtask prompt formatting for ManusAgent."""

    def test_format_subtask_prompt_basic(self):
        """Test basic subtask prompt formatting."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        prompt = agent._format_subtask_prompt(
            {"tool": "data_collect", "params": {"territory": "34", "sector": "tech"}}
        )

        assert "data_collect" in prompt
        assert "territory=34" in prompt
        assert "sector=tech" in prompt

    def test_format_subtask_prompt_empty_params(self):
        """Test prompt formatting with no params."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        prompt = agent._format_subtask_prompt({"tool": "health_check", "params": {}})

        assert "health_check" in prompt
        assert "Execute" in prompt


class TestEndToEndDelegation:
    """End-to-end tests for the delegation flow."""

    @pytest.mark.asyncio
    async def test_full_delegation_cycle(self):
        """Test complete delegation from subtask to result."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()
        await agent.initialize()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(
            return_value={
                "status": "completed",
                "result": {"companies": 847, "sectors": ["tech", "biotech"], "iterations": 2},
            }
        )

        with patch.object(
            agent, "_create_manus_agent", new_callable=AsyncMock, return_value=mock_manus
        ):
            result = await agent.delegate(
                {
                    "tool": "territorial_analysis",
                    "params": {"territory": "34", "sectors": ["tech"], "depth": "detailed"},
                    "timeout": 180,
                }
            )

            assert result["status"] == "completed"
            assert result["success"] is True
            assert result["tool"] == "territorial_analysis"
            assert result["result"]["companies"] == 847
            assert result["metadata"]["agent"] == "manus"
            assert result["metadata"]["iterations"] == 2

        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_delegations_reuse_manus(self):
        """Test multiple delegations reuse the same ManusAgent."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        mock_manus = MagicMock()
        mock_manus.execute_task = AsyncMock(return_value={"status": "completed", "result": {}})

        with patch.object(
            agent, "_create_manus_agent", new_callable=AsyncMock, return_value=mock_manus
        ) as mock_create:
            # First delegation
            await agent.delegate({"tool": "tool1", "params": {}})
            # Second delegation
            await agent.delegate({"tool": "tool2", "params": {}})
            # Third delegation
            await agent.delegate({"tool": "tool3", "params": {}})

            # _create_manus_agent should only be called once
            assert mock_create.call_count == 1
            # execute_task should be called 3 times
            assert mock_manus.execute_task.call_count == 3
