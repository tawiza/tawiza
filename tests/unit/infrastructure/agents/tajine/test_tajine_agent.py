"""Tests for TAJINEAgent - Strategic meta-agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTAJINEAgentImports:
    """Test that TAJINEAgent can be imported."""

    def test_import_tajine_agent(self):
        """Test TAJINEAgent class can be imported."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        assert TAJINEAgent is not None

    def test_import_create_tajine_agent(self):
        """Test factory function can be imported."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        assert create_tajine_agent is not None


class TestTAJINEAgentCreation:
    """Test TAJINEAgent instantiation."""

    def test_agent_has_required_attributes(self):
        """Test agent has cognitive_engine, trust_manager, planner."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert hasattr(agent, "cognitive_engine")
        assert hasattr(agent, "trust_manager")
        assert hasattr(agent, "planner")

    def test_agent_inherits_base_agent(self):
        """Test TAJINEAgent inherits from BaseAgent."""
        from src.infrastructure.agents.base_agent import BaseAgent
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert isinstance(agent, BaseAgent)

    def test_create_tajine_agent_factory(self):
        """Test factory function creates configured agent."""
        from src.infrastructure.agents.tajine import create_tajine_agent

        agent = create_tajine_agent(local_model="qwen3:14b", powerful_model="qwen3-coder:30b")

        assert agent is not None
        assert agent.local_model == "qwen3:14b"
        assert agent.powerful_model == "qwen3-coder:30b"


@pytest.mark.integration
@pytest.mark.ollama
class TestTAJINEAgentCycle:
    """Test the PERCEIVE-PLAN-DELEGATE-SYNTHESIZE-LEARN cycle.

    Note: All methods in this class call real LLM endpoints (perceive, plan,
    synthesize, learn). These are integration tests requiring Ollama.
    Run with: pytest -m integration
    """

    @pytest.mark.asyncio
    async def test_perceive_extracts_intent(self):
        pytest.skip("Integration test: perceive() calls Ollama LLM")

    @pytest.mark.asyncio
    async def test_plan_decomposes_task(self):
        pytest.skip("Integration test: plan() calls Ollama LLM")

    @pytest.mark.asyncio
    async def test_delegate_sends_to_manus(self):
        """Test delegate() sends subtask to ManusAgent."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()
        subtask = {"tool": "data_collect", "params": {"territory": "34", "sector": "tech"}}

        with patch.object(agent, "_manus_agent") as mock_manus:
            mock_manus.execute_task = AsyncMock(
                return_value={"status": "completed", "result": {"companies": 847}}
            )

            result = await agent.delegate(subtask)

            mock_manus.execute_task.assert_called_once()
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_synthesize_aggregates_results(self):
        pytest.skip("Integration test: synthesize() calls Ollama LLM")

    @pytest.mark.asyncio
    async def test_learn_updates_trust(self):
        pytest.skip("Integration test: learn() calls Ollama LLM")


class TestTAJINEAgentExecuteTask:
    """Test main execute_task method."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_execute_task_full_cycle(self):
        """Test execute_task runs full PPDSL cycle.

        Note: This is an integration test - execute_task triggers real LLM
        calls in perceive/plan/synthesize/learn phases even when _manus_agent
        is mocked. Requires running Ollama.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")
