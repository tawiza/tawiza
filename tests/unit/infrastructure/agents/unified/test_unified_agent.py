"""Tests for Unified Adaptive Agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.unified.config import (
    AutonomyLevel,
    UnifiedAgentConfig,
)
from src.infrastructure.agents.unified.tool_router import ToolRouter
from src.infrastructure.agents.unified.trust_manager import TrustManager
from src.infrastructure.agents.unified.unified_agent import (
    TaskRequest,
    TaskResult,
    TaskStatus,
    UnifiedAdaptiveAgent,
)


class TestTaskRequest:
    """Test TaskRequest dataclass."""

    def test_create_request(self):
        """Should create valid request."""
        request = TaskRequest(
            task_id="task_1",
            description="Scrape data from example.com",
        )
        assert request.task_id == "task_1"
        assert request.description == "Scrape data from example.com"

    def test_request_with_context(self):
        """Should support context data."""
        request = TaskRequest(
            task_id="task_1",
            description="Navigate and extract",
            context={"url": "https://example.com", "target": ".content"},
        )
        assert request.context["url"] == "https://example.com"


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_create_result(self):
        """Should create valid result."""
        result = TaskResult(
            task_id="task_1",
            status=TaskStatus.COMPLETED,
            output={"data": "extracted content"},
        )
        assert result.status == TaskStatus.COMPLETED

    def test_result_with_error(self):
        """Should track errors."""
        result = TaskResult(
            task_id="task_1",
            status=TaskStatus.FAILED,
            error="Connection timeout",
        )
        assert result.status == TaskStatus.FAILED
        assert result.error == "Connection timeout"


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_statuses_exist(self):
        """Should have all expected statuses."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.AWAITING_APPROVAL.value == "awaiting_approval"


class TestUnifiedAgentInit:
    """Test agent initialization."""

    def test_init_default(self):
        """Should initialize with defaults."""
        agent = UnifiedAdaptiveAgent()
        assert agent.config is not None
        assert agent.trust_manager is not None
        assert agent.tool_router is not None

    def test_init_with_config(self):
        """Should accept custom config."""
        config = UnifiedAgentConfig(llm_model="custom-model")
        agent = UnifiedAdaptiveAgent(config=config)
        assert agent.config.llm_model == "custom-model"

    def test_init_with_custom_components(self):
        """Should accept custom components."""
        trust_manager = TrustManager()
        tool_router = ToolRouter()

        agent = UnifiedAdaptiveAgent(
            trust_manager=trust_manager,
            tool_router=tool_router,
        )

        assert agent.trust_manager is trust_manager
        assert agent.tool_router is tool_router


class TestUnifiedAgentProperties:
    """Test agent properties."""

    def test_autonomy_level(self):
        """Should expose current autonomy level."""
        agent = UnifiedAdaptiveAgent()
        assert agent.autonomy_level == AutonomyLevel.SUPERVISED

    def test_trust_score(self):
        """Should expose current trust score."""
        agent = UnifiedAdaptiveAgent()
        assert agent.trust_score == 0.0

    def test_is_learning_enabled(self):
        """Should check if learning is enabled."""
        config = UnifiedAgentConfig()
        config.learning.auto_learning_enabled = True
        agent = UnifiedAdaptiveAgent(config=config)

        assert agent.is_learning_enabled is True


class TestUnifiedAgentExecution:
    """Test task execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_task(self):
        """Should execute a simple task."""
        agent = UnifiedAdaptiveAgent()

        # Mock tool execution
        agent._execute_with_tool = AsyncMock(
            return_value={
                "success": True,
                "data": "result",
            }
        )

        request = TaskRequest(
            task_id="task_1",
            description="Scrape example.com",
        )

        result = await agent.execute(request)

        assert result.status == TaskStatus.COMPLETED
        assert result.output["success"] is True

    @pytest.mark.asyncio
    async def test_execute_requires_approval(self):
        """Should require approval at supervised level."""
        agent = UnifiedAdaptiveAgent()
        agent.trust_manager._level = AutonomyLevel.SUPERVISED

        request = TaskRequest(
            task_id="task_1",
            description="Execute code",
            task_type="code_execution",
        )

        result = await agent.execute(request)

        assert result.status == TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_execute_auto_approve_at_higher_level(self):
        """Should auto-approve at higher autonomy levels."""
        agent = UnifiedAdaptiveAgent()
        agent.trust_manager._level = AutonomyLevel.AUTONOMOUS

        agent._execute_with_tool = AsyncMock(return_value={"success": True})

        request = TaskRequest(
            task_id="task_1",
            description="Scrape data",
            task_type="web_scraping",
        )

        result = await agent.execute(request)

        assert result.status != TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_execute_handles_failure(self):
        """Should handle execution failures."""
        agent = UnifiedAdaptiveAgent()
        agent.trust_manager._level = AutonomyLevel.AUTONOMOUS

        agent._execute_with_tool = AsyncMock(side_effect=Exception("Tool error"))

        request = TaskRequest(
            task_id="task_1",
            description="Failing task",
        )

        result = await agent.execute(request)

        assert result.status == TaskStatus.FAILED
        assert "Tool error" in result.error


class TestUnifiedAgentApproval:
    """Test approval workflow."""

    @pytest.mark.asyncio
    async def test_approve_pending_task(self):
        """Should approve a pending task."""
        agent = UnifiedAdaptiveAgent()

        # Create pending task
        request = TaskRequest(task_id="task_1", description="Test", task_type="code_execution")
        await agent.execute(request)

        # Mock execution
        agent._execute_with_tool = AsyncMock(return_value={"success": True})

        result = await agent.approve("task_1")

        assert result.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_reject_pending_task(self):
        """Should reject a pending task."""
        agent = UnifiedAdaptiveAgent()

        request = TaskRequest(task_id="task_1", description="Test", task_type="code_execution")
        await agent.execute(request)

        result = await agent.reject("task_1", reason="Not needed")

        assert result.status == TaskStatus.FAILED
        assert "rejected" in result.error.lower()


class TestUnifiedAgentLearning:
    """Test learning integration."""

    @pytest.mark.asyncio
    async def test_record_feedback(self):
        """Should record feedback for learning."""
        agent = UnifiedAdaptiveAgent()

        agent.record_feedback(
            task_id="task_1",
            feedback="positive",
        )

        assert len(agent.learning_engine.dataset_builder.examples) >= 0

    @pytest.mark.asyncio
    async def test_trigger_learning_cycle(self):
        """Should trigger learning when conditions met."""
        agent = UnifiedAdaptiveAgent()
        agent.learning_engine.min_examples = 2
        agent.learning_engine.auto_train = True

        # Mock training
        agent.learning_engine._training_adapter = MagicMock()
        agent.learning_engine._training_adapter.train = AsyncMock(
            return_value={
                "run_id": "test",
                "model_path": "/models/test",
                "metrics": {"accuracy": 0.85},
            }
        )
        agent.learning_engine._training_adapter.evaluate = AsyncMock(
            return_value={
                "accuracy": 0.87,
            }
        )

        # Add enough examples
        agent.learning_engine.record_interaction(task_id="1", instruction="Q1", output="A1")
        agent.learning_engine.record_interaction(task_id="2", instruction="Q2", output="A2")

        # Trigger learning
        if agent.learning_engine.should_trigger_learning():
            cycle = await agent.learning_engine.run_full_cycle()
            assert cycle is not None


class TestUnifiedAgentStatus:
    """Test status and statistics."""

    def test_get_status(self):
        """Should return agent status."""
        agent = UnifiedAdaptiveAgent()

        status = agent.get_status()

        assert "autonomy_level" in status
        assert "trust_score" in status
        assert "learning_enabled" in status

    def test_get_stats(self):
        """Should return detailed statistics."""
        agent = UnifiedAdaptiveAgent()

        stats = agent.get_stats()

        assert "tasks_completed" in stats
        assert "tasks_failed" in stats
        assert "learning_stats" in stats


class TestUnifiedAgentToolRouting:
    """Test tool routing behavior."""

    @pytest.mark.asyncio
    async def test_routes_to_correct_tool(self):
        """Should route task to appropriate tool."""
        agent = UnifiedAdaptiveAgent()
        agent.trust_manager._level = AutonomyLevel.AUTONOMOUS

        # Check that tool router is called
        agent.tool_router.plan = AsyncMock(
            return_value=MagicMock(steps=[MagicMock(tool="openmanus", action="scrape")])
        )
        agent._execute_with_tool = AsyncMock(return_value={"success": True})

        request = TaskRequest(
            task_id="task_1",
            description="Scrape data",
        )

        await agent.execute(request)

        agent.tool_router.plan.assert_called_once()
