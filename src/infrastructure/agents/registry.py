"""Agent Registry - Centralized agent management.

Provides a singleton registry for managing all agents in the system,
enabling discovery, lifecycle management, and health monitoring.
"""

from typing import Any, Optional

from loguru import logger

from src.application.ports.agent_ports import IAgent


class AgentRegistry:
    """Centralized registry for agent management.

    Provides:
    - Agent registration and discovery
    - Lifecycle management (initialize, shutdown)
    - Health monitoring for all registered agents
    - Agent lookup by name or type

    Example:
        >>> registry = AgentRegistry()
        >>> registry.register(my_agent)
        >>> agent = registry.get("my_agent")
        >>> await registry.initialize_all()
    """

    _instance: Optional["AgentRegistry"] = None

    def __new__(cls) -> "AgentRegistry":
        """Singleton pattern for global registry access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: dict[str, IAgent] = {}
            cls._instance._initialized = False
        return cls._instance

    @property
    def agents(self) -> dict[str, IAgent]:
        """Get all registered agents."""
        return self._agents.copy()

    def register(self, agent: IAgent) -> None:
        """Register an agent.

        Args:
            agent: Agent implementing IAgent interface.

        Raises:
            ValueError: If agent with same name already registered.
        """
        if agent.name in self._agents:
            raise ValueError(
                f"Agent '{agent.name}' already registered. "
                "Use unregister() first to replace."
            )
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} (type: {agent.agent_type})")

    def unregister(self, name: str) -> IAgent | None:
        """Unregister an agent by name.

        Args:
            name: Agent name.

        Returns:
            The unregistered agent, or None if not found.
        """
        agent = self._agents.pop(name, None)
        if agent:
            logger.info(f"Unregistered agent: {name}")
        return agent

    def get(self, name: str) -> IAgent | None:
        """Get an agent by name.

        Args:
            name: Agent name.

        Returns:
            Agent instance or None if not found.
        """
        return self._agents.get(name)

    def get_by_type(self, agent_type: str) -> list[IAgent]:
        """Get all agents of a specific type.

        Args:
            agent_type: Type of agents to find.

        Returns:
            List of matching agents.
        """
        return [
            agent for agent in self._agents.values()
            if agent.agent_type == agent_type
        ]

    def list_names(self) -> list[str]:
        """List all registered agent names.

        Returns:
            List of agent names.
        """
        return list(self._agents.keys())

    def list_types(self) -> list[str]:
        """List all unique agent types.

        Returns:
            List of unique agent types.
        """
        return list({agent.agent_type for agent in self._agents.values()})

    async def initialize_all(self) -> dict[str, bool]:
        """Initialize all registered agents.

        Returns:
            Dict mapping agent name to initialization success.
        """
        results = {}
        for name, agent in self._agents.items():
            try:
                await agent.initialize()
                results[name] = True
                logger.info(f"Initialized agent: {name}")
            except Exception as e:
                results[name] = False
                logger.error(f"Failed to initialize agent {name}: {e}")
        self._initialized = True
        return results

    async def shutdown_all(self) -> dict[str, bool]:
        """Shutdown all registered agents.

        Returns:
            Dict mapping agent name to shutdown success.
        """
        results = {}
        for name, agent in self._agents.items():
            try:
                await agent.shutdown()
                results[name] = True
                logger.info(f"Shutdown agent: {name}")
            except Exception as e:
                results[name] = False
                logger.warning(f"Error shutting down agent {name}: {e}")
        self._initialized = False
        return results

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all registered agents.

        Returns:
            Dict mapping agent name to health status.
        """
        results = {}
        for name, agent in self._agents.items():
            try:
                results[name] = await agent.health_check()
            except Exception as e:
                results[name] = False
                logger.warning(f"Health check failed for {name}: {e}")
        return results

    async def get_status(self) -> dict[str, Any]:
        """Get overall registry status.

        Returns:
            Status dict with agent counts and health info.
        """
        health = await self.health_check_all()
        healthy_count = sum(1 for h in health.values() if h)

        return {
            "total_agents": len(self._agents),
            "healthy_agents": healthy_count,
            "unhealthy_agents": len(self._agents) - healthy_count,
            "initialized": self._initialized,
            "agents": {
                name: {
                    "type": agent.agent_type,
                    "healthy": health.get(name, False),
                }
                for name, agent in self._agents.items()
            },
        }

    def clear(self) -> None:
        """Clear all registered agents.

        Warning: Does not call shutdown. Use shutdown_all() first.
        """
        self._agents.clear()
        self._initialized = False
        logger.info("Cleared all agents from registry")


# Global registry instance
_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry.

    Returns:
        Global AgentRegistry singleton.
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
