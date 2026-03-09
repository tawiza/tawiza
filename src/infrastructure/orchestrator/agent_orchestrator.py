"""AgentOrchestrator - Central hub for agent management and event coordination.

Provides:
- Agent registry (register, unregister, list agents)
- Event bus with pub/sub pattern
- Agent lifecycle management (start, stop, pause)
- WebSocket-ready event serialization
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.infrastructure.agents.base_agent import BaseAgent


class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class EventType(Enum):
    """Standard orchestrator event types."""
    # Agent lifecycle
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_PAUSED = "agent.paused"
    AGENT_RESUMED = "agent.resumed"
    AGENT_ERROR = "agent.error"

    # Task events
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # TAJINE specific
    TAJINE_PERCEIVE = "tajine.perceive"
    TAJINE_PLAN = "tajine.plan"
    TAJINE_DELEGATE = "tajine.delegate"
    TAJINE_SYNTHESIZE = "tajine.synthesize"
    TAJINE_LEARN = "tajine.learn"
    COGNITIVE_LEVEL = "tajine.cognitive_level"

    # Browser events
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_ACTION = "browser.action"
    BROWSER_CAPTCHA = "browser.captcha"

    # Custom
    CUSTOM = "custom"


@dataclass
class OrchestratorEvent:
    """Event emitted by the orchestrator."""
    type: str
    agent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to WebSocket-ready dict."""
        return {
            "event_id": self.event_id,
            "type": self.type,
            "agent_id": self.agent_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    agent_type: str
    name: str
    state: AgentState = AgentState.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    current_task: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "current_task": self.current_task,
            "metadata": self.metadata,
        }


# Type for event callbacks
EventCallback = Callable[[OrchestratorEvent], None]
AsyncEventCallback = Callable[[OrchestratorEvent], Any]


class AgentOrchestrator:
    """Central hub for agent management and event coordination.

    Singleton pattern - use get_orchestrator() to access.

    Features:
    - Agent registry with lifecycle management
    - Event bus with sync and async subscribers
    - WebSocket-ready event serialization
    - Task tracking across agents
    """

    _instance: Optional["AgentOrchestrator"] = None

    def __new__(cls) -> "AgentOrchestrator":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize orchestrator (only once due to singleton)."""
        if self._initialized:
            return

        # Agent registry
        self._agents: dict[str, BaseAgent] = {}
        self._agent_info: dict[str, AgentInfo] = {}

        # Event bus
        self._subscribers: dict[str, list[EventCallback]] = {}
        self._async_subscribers: dict[str, list[AsyncEventCallback]] = {}
        self._global_subscribers: list[EventCallback] = []
        self._async_global_subscribers: list[AsyncEventCallback] = []

        # Event history for replay
        self._event_history: list[OrchestratorEvent] = []
        self._max_history = 1000

        # Running tasks
        self._tasks: dict[str, asyncio.Task] = {}

        self._initialized = True
        logger.info("AgentOrchestrator initialized")

    # =========================================================================
    # Agent Registry
    # =========================================================================

    def register_agent(
        self,
        agent: "BaseAgent",
        agent_type: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """Register an agent with the orchestrator.

        Args:
            agent: The agent instance
            agent_type: Type identifier (e.g., "tajine", "manus", "browser")
            name: Optional friendly name
            metadata: Optional metadata dict

        Returns:
            Generated agent_id
        """
        agent_id = str(uuid.uuid4())[:12]

        self._agents[agent_id] = agent
        self._agent_info[agent_id] = AgentInfo(
            agent_id=agent_id,
            agent_type=agent_type,
            name=name or f"{agent_type}_{agent_id[:4]}",
            metadata=metadata or {},
        )

        # Emit registration event
        self.emit(OrchestratorEvent(
            type=EventType.AGENT_REGISTERED.value,
            agent_id=agent_id,
            data={"agent_type": agent_type, "name": name}
        ))

        logger.info(f"Agent registered: {agent_id} ({agent_type})")
        return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent.

        Args:
            agent_id: The agent ID to unregister

        Returns:
            True if agent was found and removed
        """
        if agent_id not in self._agents:
            return False

        del self._agents[agent_id]
        info = self._agent_info.pop(agent_id, None)

        self.emit(OrchestratorEvent(
            type=EventType.AGENT_UNREGISTERED.value,
            agent_id=agent_id,
            data={"agent_type": info.agent_type if info else "unknown"}
        ))

        logger.info(f"Agent unregistered: {agent_id}")
        return True

    def get_agent(self, agent_id: str) -> Optional["BaseAgent"]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        """Get agent info by ID."""
        return self._agent_info.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> list[str]:
        """Get all agent IDs of a specific type."""
        return [
            aid for aid, info in self._agent_info.items()
            if info.agent_type == agent_type
        ]

    def list_agents(self) -> list[AgentInfo]:
        """List all registered agents."""
        return list(self._agent_info.values())

    def update_agent_state(self, agent_id: str, state: AgentState) -> None:
        """Update agent state."""
        if agent_id in self._agent_info:
            self._agent_info[agent_id].state = state
            self._agent_info[agent_id].last_activity = datetime.now()

    # =========================================================================
    # Event Bus
    # =========================================================================

    def subscribe(
        self,
        event_type: str,
        callback: EventCallback
    ) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Event type to subscribe to
            callback: Sync callback function
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_async(
        self,
        event_type: str,
        callback: AsyncEventCallback
    ) -> None:
        """Subscribe to a specific event type with async callback.

        Args:
            event_type: Event type to subscribe to
            callback: Async callback function
        """
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """Subscribe to all events."""
        self._global_subscribers.append(callback)

    def subscribe_all_async(self, callback: AsyncEventCallback) -> None:
        """Subscribe to all events with async callback."""
        self._async_global_subscribers.append(callback)

    def unsubscribe(self, event_type: str, callback: EventCallback) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def emit(self, event: OrchestratorEvent) -> None:
        """Emit an event to all subscribers.

        Args:
            event: The event to emit
        """
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify type-specific subscribers
        for callback in self._subscribers.get(event.type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

        # Notify global subscribers
        for callback in self._global_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Global event callback error: {e}")

        # Schedule async callbacks only if event loop is running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._emit_async(event))
        except RuntimeError:
            # No running event loop - skip async callbacks
            pass

    async def _emit_async(self, event: OrchestratorEvent) -> None:
        """Emit event to async subscribers."""
        # Type-specific async subscribers
        for callback in self._async_subscribers.get(event.type, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Async event callback error: {e}")

        # Global async subscribers
        for callback in self._async_global_subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Global async event callback error: {e}")

    def get_event_history(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
        limit: int = 100
    ) -> list[OrchestratorEvent]:
        """Get event history with optional filters.

        Args:
            event_type: Filter by event type
            agent_id: Filter by agent ID
            limit: Maximum events to return

        Returns:
            List of matching events (newest first)
        """
        events = self._event_history.copy()

        if event_type:
            events = [e for e in events if e.type == event_type]

        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]

        return list(reversed(events[-limit:]))

    # =========================================================================
    # Agent Lifecycle
    # =========================================================================

    async def start_agent(self, agent_id: str, task: str | None = None) -> bool:
        """Start an agent.

        Args:
            agent_id: Agent to start
            task: Optional initial task

        Returns:
            True if started successfully
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        self.update_agent_state(agent_id, AgentState.STARTING)

        try:
            # Update info
            info = self._agent_info[agent_id]
            info.state = AgentState.RUNNING
            info.current_task = task
            info.last_activity = datetime.now()

            self.emit(OrchestratorEvent(
                type=EventType.AGENT_STARTED.value,
                agent_id=agent_id,
                data={"task": task}
            ))

            return True

        except Exception as e:
            self.update_agent_state(agent_id, AgentState.ERROR)
            self.emit(OrchestratorEvent(
                type=EventType.AGENT_ERROR.value,
                agent_id=agent_id,
                data={"error": str(e)}
            ))
            return False

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent."""
        if agent_id not in self._agents:
            return False

        self.update_agent_state(agent_id, AgentState.STOPPING)

        # Cancel any running tasks for this agent
        task_key = f"agent_{agent_id}"
        if task_key in self._tasks:
            self._tasks[task_key].cancel()
            del self._tasks[task_key]

        self.update_agent_state(agent_id, AgentState.STOPPED)

        self.emit(OrchestratorEvent(
            type=EventType.AGENT_STOPPED.value,
            agent_id=agent_id
        ))

        return True

    async def pause_agent(self, agent_id: str) -> bool:
        """Pause an agent."""
        if agent_id not in self._agents:
            return False

        self.update_agent_state(agent_id, AgentState.PAUSED)

        self.emit(OrchestratorEvent(
            type=EventType.AGENT_PAUSED.value,
            agent_id=agent_id
        ))

        return True

    async def resume_agent(self, agent_id: str) -> bool:
        """Resume a paused agent."""
        if agent_id not in self._agents:
            return False

        info = self._agent_info.get(agent_id)
        if info and info.state == AgentState.PAUSED:
            self.update_agent_state(agent_id, AgentState.RUNNING)

            self.emit(OrchestratorEvent(
                type=EventType.AGENT_RESUMED.value,
                agent_id=agent_id
            ))

            return True

        return False

    # =========================================================================
    # Task Management
    # =========================================================================

    async def run_tajine_task(
        self,
        agent_id: str,
        prompt: str,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run a TAJINE task with full PPDSL cycle.

        Args:
            agent_id: TAJINE agent ID
            prompt: Task prompt
            context: Optional context dict

        Returns:
            Task result with cognitive analysis
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        info = self._agent_info.get(agent_id)
        if info:
            info.current_task = prompt[:50]
            info.state = AgentState.RUNNING

        self.emit(OrchestratorEvent(
            type=EventType.TASK_STARTED.value,
            agent_id=agent_id,
            data={"prompt": prompt, "context": context}
        ))

        try:
            # Run TAJINE PPDSL cycle
            result = await agent.run(prompt, context=context)

            self.emit(OrchestratorEvent(
                type=EventType.TASK_COMPLETED.value,
                agent_id=agent_id,
                data={"result": result}
            ))

            if info:
                info.state = AgentState.IDLE
                info.current_task = None

            return result

        except Exception as e:
            self.emit(OrchestratorEvent(
                type=EventType.TASK_FAILED.value,
                agent_id=agent_id,
                data={"error": str(e)}
            ))

            if info:
                info.state = AgentState.ERROR

            raise

    # =========================================================================
    # Utility
    # =========================================================================

    def reset(self) -> None:
        """Reset orchestrator state (for testing)."""
        self._agents.clear()
        self._agent_info.clear()
        self._subscribers.clear()
        self._async_subscribers.clear()
        self._global_subscribers.clear()
        self._async_global_subscribers.clear()
        self._event_history.clear()
        self._tasks.clear()
        logger.debug("AgentOrchestrator reset")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        if cls._instance:
            cls._instance.reset()
        cls._instance = None


# Singleton accessor
def get_orchestrator() -> AgentOrchestrator:
    """Get the global AgentOrchestrator instance."""
    return AgentOrchestrator()
