"""Agent Chains - Sequential and parallel agent orchestration.

Provides patterns for chaining agents together to create complex workflows:
- Sequential chains: A → B → C
- Parallel execution: A, B, C simultaneously
- Conditional branching: if condition then A else B
- Map-reduce patterns: split → process → combine
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger


class ChainStatus(StrEnum):
    """Status of a chain execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChainResult:
    """Result of a chain execution."""

    status: ChainStatus
    data: Any = None
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "steps": self.steps,
            "duration_seconds": self.duration_seconds,
        }


class ChainStep(ABC):
    """Base class for chain steps."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, input_data: Any) -> Any:
        """Execute this step.

        Args:
            input_data: Input from previous step

        Returns:
            Output to pass to next step
        """
        pass


class AgentStep(ChainStep):
    """Step that invokes an agent.

    Example:
        >>> step = AgentStep("data_agent", agent, {"action": "analyze"})
        >>> result = await step.execute({"query": "market analysis"})
    """

    def __init__(
        self,
        name: str,
        agent: Any,  # IAgent or any agent-like object
        config: dict[str, Any] | None = None,
        input_transform: Callable[[Any], Any] | None = None,
        output_transform: Callable[[Any], Any] | None = None,
    ):
        """Initialize agent step.

        Args:
            name: Step name
            agent: Agent instance to invoke
            config: Base configuration for the agent
            input_transform: Transform input before passing to agent
            output_transform: Transform output before passing to next step
        """
        super().__init__(name)
        self.agent = agent
        self.config = config or {}
        self.input_transform = input_transform
        self.output_transform = output_transform

    async def execute(self, input_data: Any) -> Any:
        """Execute agent with input data."""
        # Transform input if needed
        if self.input_transform:
            input_data = self.input_transform(input_data)

        # Merge input with config
        task_config = {**self.config}
        if isinstance(input_data, dict):
            task_config.update(input_data)
        else:
            task_config["input"] = input_data

        # Execute agent
        logger.debug(f"Executing agent step: {self.name}")
        result = await self.agent.execute_task(task_config)

        # Transform output if needed
        if self.output_transform:
            result = self.output_transform(result)

        return result


class FunctionStep(ChainStep):
    """Step that executes a function.

    Example:
        >>> async def process(data):
        ...     return {"processed": data}
        >>> step = FunctionStep("process", process)
    """

    def __init__(self, name: str, func: Callable, **kwargs):
        super().__init__(name)
        self.func = func
        self.kwargs = kwargs

    async def execute(self, input_data: Any) -> Any:
        """Execute function with input data."""
        logger.debug(f"Executing function step: {self.name}")

        if asyncio.iscoroutinefunction(self.func):
            return await self.func(input_data, **self.kwargs)
        else:
            return self.func(input_data, **self.kwargs)


class ConditionalStep(ChainStep):
    """Step with conditional branching.

    Example:
        >>> step = ConditionalStep(
        ...     "check_size",
        ...     condition=lambda x: len(x) > 100,
        ...     if_true=large_processor,
        ...     if_false=small_processor
        ... )
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[Any], bool],
        if_true: ChainStep,
        if_false: ChainStep,
    ):
        super().__init__(name)
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false

    async def execute(self, input_data: Any) -> Any:
        """Execute based on condition."""
        if self.condition(input_data):
            logger.debug(f"Condition true, executing: {self.if_true.name}")
            return await self.if_true.execute(input_data)
        else:
            logger.debug(f"Condition false, executing: {self.if_false.name}")
            return await self.if_false.execute(input_data)


class AgentChain:
    """Chain of steps executed sequentially.

    Example:
        >>> chain = AgentChain("market_analysis")
        >>> chain.add_step(AgentStep("collect", data_agent))
        >>> chain.add_step(AgentStep("analyze", analyst_agent))
        >>> chain.add_step(FunctionStep("format", format_report))
        >>> result = await chain.execute({"sector": "tech", "region": "Lyon"})
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: list[ChainStep] = []
        self._cancelled = False

    def add_step(self, step: ChainStep) -> "AgentChain":
        """Add a step to the chain.

        Args:
            step: Step to add

        Returns:
            Self for chaining
        """
        self.steps.append(step)
        return self

    def add_agent(
        self, name: str, agent: Any, config: dict[str, Any] | None = None, **kwargs
    ) -> "AgentChain":
        """Convenience method to add an agent step.

        Args:
            name: Step name
            agent: Agent instance
            config: Agent configuration
            **kwargs: Additional AgentStep parameters

        Returns:
            Self for chaining
        """
        step = AgentStep(name, agent, config, **kwargs)
        return self.add_step(step)

    def add_function(self, name: str, func: Callable, **kwargs) -> "AgentChain":
        """Convenience method to add a function step.

        Args:
            name: Step name
            func: Function to execute
            **kwargs: Additional function parameters

        Returns:
            Self for chaining
        """
        step = FunctionStep(name, func, **kwargs)
        return self.add_step(step)

    async def execute(self, input_data: Any = None, stop_on_error: bool = True) -> ChainResult:
        """Execute the chain.

        Args:
            input_data: Initial input data
            stop_on_error: Stop chain on first error

        Returns:
            ChainResult with final output and step details
        """
        result = ChainResult(
            status=ChainStatus.RUNNING,
            started_at=datetime.utcnow(),
            data=input_data,
        )

        self._cancelled = False
        current_data = input_data

        logger.info(f"Starting chain: {self.name} with {len(self.steps)} steps")

        for i, step in enumerate(self.steps):
            if self._cancelled:
                result.status = ChainStatus.CANCELLED
                result.error = "Chain was cancelled"
                break

            step_result = {
                "step": i + 1,
                "name": step.name,
                "started_at": datetime.utcnow().isoformat(),
            }

            try:
                logger.debug(f"Executing step {i + 1}/{len(self.steps)}: {step.name}")
                current_data = await step.execute(current_data)
                step_result["status"] = "completed"
                step_result["output_preview"] = str(current_data)[:200]

            except Exception as e:
                logger.error(f"Step {step.name} failed: {e}")
                step_result["status"] = "failed"
                step_result["error"] = str(e)

                if stop_on_error:
                    result.status = ChainStatus.FAILED
                    result.error = f"Step '{step.name}' failed: {e}"
                    result.steps.append(step_result)
                    break

            step_result["completed_at"] = datetime.utcnow().isoformat()
            result.steps.append(step_result)

        if result.status == ChainStatus.RUNNING:
            result.status = ChainStatus.COMPLETED

        result.data = current_data
        result.completed_at = datetime.utcnow()

        logger.info(
            f"Chain {self.name} completed: {result.status.value} in {result.duration_seconds:.2f}s"
        )

        return result

    def cancel(self) -> None:
        """Cancel the chain execution."""
        self._cancelled = True
        logger.info(f"Chain {self.name} cancelled")


class ParallelChain:
    """Execute multiple chains/steps in parallel.

    Example:
        >>> parallel = ParallelChain("gather_data")
        >>> parallel.add("web", AgentStep("web", web_agent))
        >>> parallel.add("api", AgentStep("api", api_agent))
        >>> results = await parallel.execute({"query": "market"})
        >>> # results = {"web": {...}, "api": {...}}
    """

    def __init__(self, name: str, combine_results: bool = True):
        """Initialize parallel chain.

        Args:
            name: Chain name
            combine_results: If True, combine results into dict
        """
        self.name = name
        self.combine_results = combine_results
        self.branches: dict[str, ChainStep | AgentChain] = {}

    def add(self, key: str, branch: ChainStep | AgentChain) -> "ParallelChain":
        """Add a parallel branch.

        Args:
            key: Unique key for this branch
            branch: Step or chain to execute

        Returns:
            Self for chaining
        """
        self.branches[key] = branch
        return self

    async def execute(self, input_data: Any = None, timeout: float | None = None) -> dict[str, Any]:
        """Execute all branches in parallel.

        Args:
            input_data: Input passed to all branches
            timeout: Maximum execution time

        Returns:
            Dict mapping branch keys to their results
        """
        logger.info(f"Starting parallel chain: {self.name} with {len(self.branches)} branches")

        async def execute_branch(key: str, branch) -> tuple:
            try:
                if isinstance(branch, AgentChain):
                    result = await branch.execute(input_data)
                    return key, result.data
                else:
                    result = await branch.execute(input_data)
                    return key, result
            except Exception as e:
                logger.error(f"Branch {key} failed: {e}")
                return key, {"error": str(e)}

        # Create tasks
        tasks = [execute_branch(key, branch) for key, branch in self.branches.items()]

        # Execute with optional timeout
        if timeout:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )
        else:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        output = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Parallel branch error: {result}")
            else:
                key, data = result
                output[key] = data

        logger.info(f"Parallel chain {self.name} completed")
        return output


class MapReduceChain:
    """Map-reduce pattern for parallel processing.

    Splits input, processes in parallel, then combines results.

    Example:
        >>> chain = MapReduceChain(
        ...     "process_regions",
        ...     splitter=lambda x: x["regions"],
        ...     processor=region_analyzer,
        ...     combiner=lambda results: {"summary": merge(results)}
        ... )
        >>> result = await chain.execute({"regions": ["Lyon", "Paris", "Marseille"]})
    """

    def __init__(
        self,
        name: str,
        splitter: Callable[[Any], list[Any]],
        processor: ChainStep | AgentChain,
        combiner: Callable[[list[Any]], Any],
        max_parallel: int = 10,
    ):
        """Initialize map-reduce chain.

        Args:
            name: Chain name
            splitter: Function to split input into parts
            processor: Step/chain to process each part
            combiner: Function to combine results
            max_parallel: Maximum concurrent executions
        """
        self.name = name
        self.splitter = splitter
        self.processor = processor
        self.combiner = combiner
        self.max_parallel = max_parallel

    async def execute(self, input_data: Any) -> Any:
        """Execute map-reduce operation.

        Args:
            input_data: Input to split and process

        Returns:
            Combined result
        """
        logger.info(f"Starting map-reduce: {self.name}")

        # Split
        parts = self.splitter(input_data)
        logger.debug(f"Split into {len(parts)} parts")

        # Map (process in parallel with semaphore)
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def process_part(part):
            async with semaphore:
                if isinstance(self.processor, AgentChain):
                    result = await self.processor.execute(part)
                    return result.data
                else:
                    return await self.processor.execute(part)

        results = await asyncio.gather(
            *[process_part(part) for part in parts], return_exceptions=True
        )

        # Filter out exceptions
        valid_results = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]

        if errors:
            logger.warning(f"MapReduce had {len(errors)} failed parts")

        # Reduce
        combined = self.combiner(valid_results)
        logger.info(f"Map-reduce {self.name} completed")

        return combined


# Utility functions for common patterns


def create_sequential_chain(
    name: str,
    agents: list[tuple],  # List of (name, agent, config)
) -> AgentChain:
    """Create a sequential chain from a list of agents.

    Args:
        name: Chain name
        agents: List of (step_name, agent, config) tuples

    Returns:
        Configured AgentChain
    """
    chain = AgentChain(name)
    for step_name, agent, config in agents:
        chain.add_agent(step_name, agent, config)
    return chain


def create_parallel_analysis(
    name: str,
    analyzers: dict[str, Any],  # {name: agent}
    input_key: str = "data",
) -> ParallelChain:
    """Create a parallel analysis chain.

    Args:
        name: Chain name
        analyzers: Dict of analyzer name to agent
        input_key: Key in input containing data to analyze

    Returns:
        Configured ParallelChain
    """
    parallel = ParallelChain(name)

    for analyzer_name, agent in analyzers.items():
        step = AgentStep(
            analyzer_name,
            agent,
            input_transform=lambda x: x.get(input_key) if isinstance(x, dict) else x,
        )
        parallel.add(analyzer_name, step)

    return parallel
