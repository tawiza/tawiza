"""Tests for BaseAgent.

Tests the base agent implementation including task management,
progress tracking, and lifecycle operations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.application.ports.agent_ports import (
    AgentType,
    TaskNotCancellableError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskStatus,
)
from src.infrastructure.agents.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing abstract BaseAgent."""

    async def execute_task(self, task_config):
        """Simple execute_task implementation."""
        task_id = self._create_task(task_config)
        self._update_task(task_id, {"status": TaskStatus.RUNNING})
        self._update_progress(task_id, 50, "Processing")
        self._add_log(task_id, "Task executed")
        self._update_task(task_id, {"status": TaskStatus.COMPLETED, "result": {"success": True}})
        return {"task_id": task_id, "status": TaskStatus.COMPLETED}


class TestBaseAgentInit:
    """Tests for BaseAgent initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default config."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        assert agent.agent_type == AgentType.CUSTOM
        assert agent.config == {}
        assert agent.tasks == {}

    def test_init_with_config(self):
        """Should accept custom configuration."""
        config = {"timeout": 30, "retries": 3}
        agent = ConcreteAgent(AgentType.OPENMANUS, config=config)

        assert agent.config == config


class TestTaskManagement:
    """Tests for task lifecycle management."""

    def test_generate_task_id(self):
        """Should generate unique task IDs."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        id1 = agent._generate_task_id()
        id2 = agent._generate_task_id()

        assert id1 != id2
        assert id1.startswith("custom-")
        assert len(id1.split("-")[1]) == 8  # UUID hex

    def test_create_task(self):
        """Should create task with proper structure."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        task_id = agent._create_task({"url": "https://example.com"})

        assert task_id in agent.tasks
        task = agent.tasks[task_id]
        assert task["status"] == TaskStatus.PENDING
        assert task["progress"] == 0
        assert task["config"]["url"] == "https://example.com"
        assert "created_at" in task
        assert "updated_at" in task

    def test_create_task_with_custom_id(self):
        """Should use provided task_id if given."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        task_id = agent._create_task({"task_id": "my-custom-id"})

        assert task_id == "my-custom-id"
        assert "my-custom-id" in agent.tasks

    def test_update_task(self):
        """Should update task fields."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})

        agent._update_task(task_id, {"status": TaskStatus.RUNNING, "progress": 25})

        task = agent.tasks[task_id]
        assert task["status"] == TaskStatus.RUNNING
        assert task["progress"] == 25

    def test_update_task_not_found(self):
        """Should raise error for nonexistent task."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        with pytest.raises(TaskNotFoundError):
            agent._update_task("nonexistent", {"status": TaskStatus.RUNNING})

    def test_update_progress(self):
        """Should update progress and current step."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})

        agent._update_progress(task_id, 75, "Almost done")

        task = agent.tasks[task_id]
        assert task["progress"] == 75
        assert task["current_step"] == "Almost done"

    def test_add_log(self):
        """Should add log entries."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})

        agent._add_log(task_id, "Starting task")
        agent._add_log(task_id, "Error occurred", level="error")

        logs = agent.tasks[task_id]["logs"]
        assert len(logs) == 2
        assert logs[0]["message"] == "Starting task"
        assert logs[0]["level"] == "info"
        assert logs[1]["level"] == "error"

    def test_add_screenshot(self):
        """Should add screenshot entries."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})

        agent._add_screenshot(task_id, "http://example.com/shot1.png", "Step 1")

        screenshots = agent.tasks[task_id]["screenshots"]
        assert len(screenshots) == 1
        assert screenshots[0]["url"] == "http://example.com/shot1.png"
        assert screenshots[0]["label"] == "Step 1"


class TestTaskStatusOperations:
    """Tests for task status operations."""

    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Should return task status info."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(task_id, {"status": TaskStatus.RUNNING})
        agent._update_progress(task_id, 50, "Halfway")

        status = await agent.get_task_status(task_id)

        assert status["task_id"] == task_id
        assert status["status"] == TaskStatus.RUNNING
        assert status["progress"] == 50
        assert status["current_step"] == "Halfway"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self):
        """Should raise error for nonexistent task."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        with pytest.raises(TaskNotFoundError):
            await agent.get_task_status("nonexistent")

    @pytest.mark.asyncio
    async def test_get_task_result_completed(self):
        """Should return result for completed task."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(
            task_id, {"status": TaskStatus.COMPLETED, "result": {"data": "extracted"}}
        )

        result = await agent.get_task_result(task_id)

        assert result["status"] == TaskStatus.COMPLETED
        assert result["result"]["data"] == "extracted"

    @pytest.mark.asyncio
    async def test_get_task_result_not_completed(self):
        """Should raise error if task not completed."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(task_id, {"status": TaskStatus.RUNNING})

        with pytest.raises(TaskNotCompletedError):
            await agent.get_task_result(task_id)


class TestTaskCancellation:
    """Tests for task cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        """Should cancel pending task."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})

        result = await agent.cancel_task(task_id)

        assert result is True
        assert agent.tasks[task_id]["status"] == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        """Should cancel running task."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(task_id, {"status": TaskStatus.RUNNING})

        result = await agent.cancel_task(task_id)

        assert result is True
        assert agent.tasks[task_id]["status"] == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_task_fails(self):
        """Should not cancel completed task."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(task_id, {"status": TaskStatus.COMPLETED})

        with pytest.raises(TaskNotCancellableError):
            await agent.cancel_task(task_id)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """Should raise error for nonexistent task."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        with pytest.raises(TaskNotFoundError):
            await agent.cancel_task("nonexistent")


class TestListTasks:
    """Tests for listing tasks."""

    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        """Should list all tasks."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        agent._create_task({"name": "task1"})
        agent._create_task({"name": "task2"})
        agent._create_task({"name": "task3"})

        tasks = await agent.list_tasks()

        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_filter_by_status(self):
        """Should filter tasks by status."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        id1 = agent._create_task({})
        id2 = agent._create_task({})
        id3 = agent._create_task({})
        agent._update_task(id1, {"status": TaskStatus.COMPLETED})
        agent._update_task(id2, {"status": TaskStatus.COMPLETED})

        pending = await agent.list_tasks(status=TaskStatus.PENDING)
        completed = await agent.list_tasks(status=TaskStatus.COMPLETED)

        assert len(pending) == 1
        assert len(completed) == 2

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self):
        """Should support pagination."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        for i in range(10):
            agent._create_task({"index": i})

        page1 = await agent.list_tasks(limit=3, offset=0)
        page2 = await agent.list_tasks(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3


class TestStreamProgress:
    """Tests for progress streaming."""

    @pytest.mark.asyncio
    async def test_stream_progress(self):
        """Should stream progress updates."""
        agent = ConcreteAgent(AgentType.CUSTOM)
        task_id = agent._create_task({})
        agent._update_task(task_id, {"status": TaskStatus.COMPLETED})

        updates = []
        async for update in agent.stream_progress(task_id):
            updates.append(update)

        assert len(updates) == 1
        assert updates[0]["task_id"] == task_id
        assert updates[0]["status"] == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream_progress_not_found(self):
        """Should raise error for nonexistent task."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        with pytest.raises(TaskNotFoundError):
            async for _ in agent.stream_progress("nonexistent"):
                pass


class TestExecuteTask:
    """Tests for task execution."""

    @pytest.mark.asyncio
    async def test_execute_task(self):
        """Should execute task successfully."""
        agent = ConcreteAgent(AgentType.CUSTOM)

        result = await agent.execute_task({"url": "https://example.com"})

        assert result["status"] == TaskStatus.COMPLETED
        task = agent.tasks[result["task_id"]]
        assert task["result"]["success"] is True
        assert len(task["logs"]) == 1
