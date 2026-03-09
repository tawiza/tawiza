"""Tests for Agent Chains - Sequential and parallel orchestration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.chains import (
    AgentChain,
    AgentStep,
    ChainResult,
    ChainStatus,
    ChainStep,
    ConditionalStep,
    FunctionStep,
    MapReduceChain,
    ParallelChain,
    create_parallel_analysis,
    create_sequential_chain,
)


class TestChainResult:
    """Tests for ChainResult."""

    def test_duration_seconds(self):
        """Test duration calculation."""
        from datetime import datetime, timedelta

        result = ChainResult(
            status=ChainStatus.COMPLETED,
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            completed_at=datetime(2024, 1, 1, 10, 0, 30),
        )

        assert result.duration_seconds == 30.0

    def test_duration_none_when_incomplete(self):
        """Test duration is None when not completed."""
        result = ChainResult(status=ChainStatus.RUNNING)

        assert result.duration_seconds is None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ChainResult(
            status=ChainStatus.COMPLETED,
            data={"output": "value"},
            steps=[{"step": 1, "name": "test"}],
        )

        d = result.to_dict()

        assert d["status"] == "completed"
        assert d["data"] == {"output": "value"}
        assert len(d["steps"]) == 1


class TestFunctionStep:
    """Tests for FunctionStep."""

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test executing async function."""

        async def process(data):
            return data * 2

        step = FunctionStep("double", process)
        result = await step.execute(5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_sync_function(self):
        """Test executing sync function."""

        def process(data):
            return data.upper()

        step = FunctionStep("upper", process)
        result = await step.execute("hello")

        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        """Test function with kwargs."""

        def add(data, amount=0):
            return data + amount

        step = FunctionStep("add", add, amount=10)
        result = await step.execute(5)

        assert result == 15


class TestAgentStep:
    """Tests for AgentStep."""

    @pytest.mark.asyncio
    async def test_execute_agent(self):
        """Test executing an agent step."""
        mock_agent = MagicMock()
        mock_agent.execute_task = AsyncMock(return_value={"result": "success"})

        step = AgentStep("test_agent", mock_agent, {"base_config": True})
        result = await step.execute({"input": "data"})

        assert result == {"result": "success"}
        mock_agent.execute_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_input_transform(self):
        """Test input transformation."""
        mock_agent = MagicMock()
        mock_agent.execute_task = AsyncMock(return_value="ok")

        step = AgentStep("test", mock_agent, input_transform=lambda x: x["nested"]["value"])

        await step.execute({"nested": {"value": "extracted"}})

        call_args = mock_agent.execute_task.call_args[0][0]
        assert call_args["input"] == "extracted"

    @pytest.mark.asyncio
    async def test_output_transform(self):
        """Test output transformation."""
        mock_agent = MagicMock()
        mock_agent.execute_task = AsyncMock(return_value={"data": 123})

        step = AgentStep("test", mock_agent, output_transform=lambda x: x["data"])

        result = await step.execute({})

        assert result == 123


class TestConditionalStep:
    """Tests for ConditionalStep."""

    @pytest.mark.asyncio
    async def test_true_branch(self):
        """Test taking true branch."""
        true_step = FunctionStep("true", lambda x: "TRUE")
        false_step = FunctionStep("false", lambda x: "FALSE")

        step = ConditionalStep(
            "check",
            condition=lambda x: x > 10,
            if_true=true_step,
            if_false=false_step,
        )

        result = await step.execute(15)

        assert result == "TRUE"

    @pytest.mark.asyncio
    async def test_false_branch(self):
        """Test taking false branch."""
        true_step = FunctionStep("true", lambda x: "TRUE")
        false_step = FunctionStep("false", lambda x: "FALSE")

        step = ConditionalStep(
            "check",
            condition=lambda x: x > 10,
            if_true=true_step,
            if_false=false_step,
        )

        result = await step.execute(5)

        assert result == "FALSE"


class TestAgentChain:
    """Tests for AgentChain."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Test steps execute in sequence."""
        execution_order = []

        async def step1(data):
            execution_order.append(1)
            return data + 1

        async def step2(data):
            execution_order.append(2)
            return data * 2

        chain = AgentChain("test")
        chain.add_function("step1", step1)
        chain.add_function("step2", step2)

        result = await chain.execute(5)

        assert execution_order == [1, 2]
        assert result.data == 12  # (5 + 1) * 2
        assert result.status == ChainStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_chain_fluent_api(self):
        """Test fluent API for adding steps."""
        chain = (
            AgentChain("test").add_function("a", lambda x: x + 1).add_function("b", lambda x: x * 2)
        )

        result = await chain.execute(3)

        assert result.data == 8  # (3 + 1) * 2

    @pytest.mark.asyncio
    async def test_error_stops_chain(self):
        """Test error stops chain execution."""

        def fails(_):
            raise ValueError("Step failed")

        chain = AgentChain("test")
        chain.add_function("ok", lambda x: x)
        chain.add_function("fails", fails)
        chain.add_function("never_reached", lambda x: x)

        result = await chain.execute("data")

        assert result.status == ChainStatus.FAILED
        assert "Step failed" in result.error
        assert len(result.steps) == 2

    @pytest.mark.asyncio
    async def test_continue_on_error(self):
        """Test chain can continue on error."""
        chain = AgentChain("test")
        chain.add_function("ok", lambda x: x + 1)
        chain.add_function("fails", lambda x: 1 / 0)
        chain.add_function("also_ok", lambda x: x * 2)

        result = await chain.execute(5, stop_on_error=False)

        assert result.status == ChainStatus.COMPLETED
        # Result is None because fails step didn't return value

    @pytest.mark.asyncio
    async def test_cancel_chain(self):
        """Test cancelling a chain."""
        execution_count = 0

        async def slow_step(data):
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.1)
            return data

        chain = AgentChain("test")
        for i in range(5):
            chain.add_function(f"step_{i}", slow_step)

        async def cancel_soon():
            await asyncio.sleep(0.05)
            chain.cancel()

        asyncio.create_task(cancel_soon())
        result = await chain.execute("data")

        assert result.status == ChainStatus.CANCELLED
        assert execution_count < 5

    @pytest.mark.asyncio
    async def test_steps_record_timing(self):
        """Test step timing is recorded."""
        chain = AgentChain("test")
        chain.add_function("step", lambda x: x)

        result = await chain.execute("data")

        assert len(result.steps) == 1
        assert "started_at" in result.steps[0]
        assert "completed_at" in result.steps[0]

    @pytest.mark.asyncio
    async def test_add_agent_convenience(self):
        """Test add_agent convenience method."""
        mock_agent = MagicMock()
        mock_agent.execute_task = AsyncMock(return_value={"ok": True})

        chain = AgentChain("test")
        chain.add_agent("agent", mock_agent, {"config": "value"})

        result = await chain.execute({})

        assert result.status == ChainStatus.COMPLETED


class TestParallelChain:
    """Tests for ParallelChain."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test branches execute in parallel."""
        start_times = {}

        async def track_start(key):
            async def func(data):
                import time

                start_times[key] = time.time()
                await asyncio.sleep(0.1)
                return f"{key}_result"

            return func

        parallel = ParallelChain("test")
        parallel.add("a", FunctionStep("a", await track_start("a")))
        parallel.add("b", FunctionStep("b", await track_start("b")))
        parallel.add("c", FunctionStep("c", await track_start("c")))

        result = await parallel.execute("input")

        # All should have started within a small window
        times = list(start_times.values())
        max_diff = max(times) - min(times)
        assert max_diff < 0.05  # Started nearly simultaneously

        assert "a" in result
        assert "b" in result
        assert "c" in result

    @pytest.mark.asyncio
    async def test_branch_error_captured(self):
        """Test errors in branches are captured."""

        async def fails(data):
            raise ValueError("branch error")

        parallel = ParallelChain("test")
        parallel.add("ok", FunctionStep("ok", lambda x: "ok"))
        parallel.add("fails", FunctionStep("fails", fails))

        result = await parallel.execute("input")

        assert result["ok"] == "ok"
        assert "error" in result["fails"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test parallel execution with timeout."""

        async def slow(data):
            await asyncio.sleep(10)
            return "done"

        parallel = ParallelChain("test")
        parallel.add("slow", FunctionStep("slow", slow))

        with pytest.raises(asyncio.TimeoutError):
            await parallel.execute("input", timeout=0.1)

    @pytest.mark.asyncio
    async def test_with_agent_chain(self):
        """Test parallel with AgentChain branch."""
        chain = AgentChain("sub")
        chain.add_function("double", lambda x: x * 2)

        parallel = ParallelChain("test")
        parallel.add("chain", chain)
        parallel.add("direct", FunctionStep("direct", lambda x: x))

        result = await parallel.execute(5)

        assert result["chain"] == 10
        assert result["direct"] == 5


class TestMapReduceChain:
    """Tests for MapReduceChain."""

    @pytest.mark.asyncio
    async def test_map_reduce(self):
        """Test basic map-reduce operation."""
        chain = MapReduceChain(
            "sum_squares",
            splitter=lambda x: x,
            processor=FunctionStep("square", lambda x: x * x),
            combiner=lambda results: sum(results),
        )

        result = await chain.execute([1, 2, 3, 4, 5])

        assert result == 55  # 1 + 4 + 9 + 16 + 25

    @pytest.mark.asyncio
    async def test_respects_max_parallel(self):
        """Test max_parallel is respected."""
        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrent(data):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return data

        chain = MapReduceChain(
            "test",
            splitter=lambda x: x,
            processor=FunctionStep("track", track_concurrent),
            combiner=lambda results: results,
            max_parallel=2,
        )

        await chain.execute(list(range(10)))

        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_handles_processor_errors(self):
        """Test graceful handling of processor errors."""
        call_count = 0

        async def sometimes_fails(data):
            nonlocal call_count
            call_count += 1
            if data == 3:
                raise ValueError("fails on 3")
            return data * 2

        chain = MapReduceChain(
            "test",
            splitter=lambda x: x,
            processor=FunctionStep("process", sometimes_fails),
            combiner=lambda results: sum(results),
        )

        result = await chain.execute([1, 2, 3, 4, 5])

        # Should process 1, 2, 4, 5 (skip 3)
        assert result == 24  # 2 + 4 + 8 + 10

    @pytest.mark.asyncio
    async def test_with_agent_chain_processor(self):
        """Test map-reduce with AgentChain processor."""
        processor = AgentChain("process")
        processor.add_function("triple", lambda x: x * 3)

        chain = MapReduceChain(
            "test",
            splitter=lambda x: x,
            processor=processor,
            combiner=lambda results: results,
        )

        result = await chain.execute([1, 2, 3])

        assert result == [3, 6, 9]


class TestUtilityFunctions:
    """Tests for utility functions."""

    @pytest.mark.asyncio
    async def test_create_sequential_chain(self):
        """Test create_sequential_chain utility."""
        mock_agent1 = MagicMock()
        mock_agent1.execute_task = AsyncMock(return_value={"step": 1})

        mock_agent2 = MagicMock()
        mock_agent2.execute_task = AsyncMock(return_value={"step": 2})

        chain = create_sequential_chain(
            "test",
            [
                ("first", mock_agent1, {}),
                ("second", mock_agent2, {}),
            ],
        )

        result = await chain.execute({})

        assert result.status == ChainStatus.COMPLETED
        assert mock_agent1.execute_task.called
        assert mock_agent2.execute_task.called

    @pytest.mark.asyncio
    async def test_create_parallel_analysis(self):
        """Test create_parallel_analysis utility."""
        mock_agent1 = MagicMock()
        mock_agent1.execute_task = AsyncMock(return_value={"analysis": "a"})

        mock_agent2 = MagicMock()
        mock_agent2.execute_task = AsyncMock(return_value={"analysis": "b"})

        parallel = create_parallel_analysis(
            "test",
            {
                "analyzer1": mock_agent1,
                "analyzer2": mock_agent2,
            },
        )

        result = await parallel.execute({"data": "test"})

        assert "analyzer1" in result
        assert "analyzer2" in result


class TestChainStatus:
    """Tests for ChainStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert ChainStatus.PENDING.value == "pending"
        assert ChainStatus.RUNNING.value == "running"
        assert ChainStatus.COMPLETED.value == "completed"
        assert ChainStatus.FAILED.value == "failed"
        assert ChainStatus.CANCELLED.value == "cancelled"
