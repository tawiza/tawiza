#!/usr/bin/env python3
"""
Système Multi-Agents Avancé pour Tawiza-V2
Architecture unifiée pour agents IA intelligents et coordonnés
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger
from rich.console import Console

console = Console()


class AgentStatus(Enum):
    """Statut des agents"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


class AgentPriority(Enum):
    """Priorité des agents"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    """Tâche pour un agent"""

    id: str
    name: str
    agent_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: AgentPriority = AgentPriority.MEDIUM
    created_at: float = field(default_factory=time.time)
    status: AgentStatus = AgentStatus.IDLE
    result: Any | None = None
    error: str | None = None


@dataclass
class AgentMetrics:
    """Métriques de performance des agents"""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    last_execution_time: float | None = None


class BaseAgent:
    """Agent de base avec fonctionnalités avancées"""

    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics()
        self.memory = None  # Sera initialisé plus tard
        self.tools = []
        self.capabilities = []

    async def initialize(self):
        """Initialisation de l'agent"""
        logger.info(f"🚀 Initialisation de {self.name} ({self.agent_type})")
        self.status = AgentStatus.IDLE

    async def execute_task(self, task: AgentTask) -> Any:
        """Exécuter une tâche spécifique"""
        raise NotImplementedError("Chaque agent doit implémenter execute_task")

    async def pause(self):
        """Mettre l'agent en pause"""
        self.status = AgentStatus.PAUSED
        logger.info(f"⏸️ {self.name} mis en pause")

    async def resume(self):
        """Reprendre l'exécution"""
        self.status = AgentStatus.RUNNING
        logger.info(f"▶️ {self.name} repris")

    def get_metrics(self) -> AgentMetrics:
        """Obtenir les métriques de l'agent"""
        return self.metrics

    def add_capability(self, capability: str):
        """Ajouter une capacité à l'agent"""
        self.capabilities.append(capability)
        logger.info(f"✅ Capacité ajoutée à {self.name}: {capability}")


class AgentCoordinator:
    """Coordinateur central pour tous les agents"""

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.task_queue: list[AgentTask] = []
        self.running = False
        self.metrics = AgentMetrics()

    def register_agent(self, agent: BaseAgent):
        """Enregistrer un agent dans le système"""
        self.agents[agent.name] = agent
        logger.info(f"📋 Agent enregistré: {agent.name} ({agent.agent_type})")

    def unregister_agent(self, agent_name: str):
        """Désenregistrer un agent"""
        if agent_name in self.agents:
            del self.agents[agent_name]
            logger.info(f"🗑️ Agent désenregistré: {agent_name}")

    def submit_task(self, task: AgentTask) -> str:
        """Soumettre une tâche à exécuter"""
        self.task_queue.append(task)
        logger.info(f"📨 Tâche soumise: {task.name} (priorité: {task.priority.name})")
        return task.id

    def get_suitable_agents(self, task: AgentTask) -> list[BaseAgent]:
        """Trouver les agents appropriés pour une tâche"""
        suitable_agents = []

        for agent in self.agents.values():
            if agent.status == AgentStatus.IDLE and task.agent_type in agent.capabilities:
                suitable_agents.append(agent)

        # Trier par priorité et disponibilité
        suitable_agents.sort(
            key=lambda x: (x.status == AgentStatus.IDLE, x.metrics.success_rate), reverse=True
        )

        return suitable_agents

    async def start_coordinator(self):
        """Démarrer le coordinateur"""
        self.running = True
        logger.info("🎯 Coordinateur multi-agents démarré")

        while self.running:
            if self.task_queue:
                # Trier par priorité
                self.task_queue.sort(key=lambda x: x.priority.value, reverse=True)
                task = self.task_queue.pop(0)

                # Trouver l'agent approprié
                suitable_agents = self.get_suitable_agents(task)

                if suitable_agents:
                    agent = suitable_agents[0]
                    await self.execute_task_with_agent(agent, task)
                else:
                    logger.warning(f"⚠️ Aucun agent disponible pour {task.name}")
                    task.status = AgentStatus.ERROR
                    task.error = "Aucun agent disponible"

            await asyncio.sleep(0.1)  # Éviter la boucle CPU intensive

    async def execute_task_with_agent(self, agent: BaseAgent, task: AgentTask):
        """Exécuter une tâche avec un agent spécifique"""
        try:
            logger.info(f"🚀 Exécution de {task.name} avec {agent.name}")
            task.status = AgentStatus.RUNNING
            agent.status = AgentStatus.RUNNING

            start_time = time.time()
            result = await agent.execute_task(task)
            execution_time = time.time() - start_time

            # Mise à jour des métriques
            task.result = result
            task.status = AgentStatus.COMPLETED
            agent.status = AgentStatus.IDLE

            agent.metrics.completed_tasks += 1
            agent.metrics.last_execution_time = execution_time

            # Calcul du taux de réussite
            total = agent.metrics.completed_tasks + agent.metrics.failed_tasks
            if total > 0:
                agent.metrics.success_rate = agent.metrics.completed_tasks / total

            logger.info(f"✅ Tâche complétée: {task.name} en {execution_time:.2f}s")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution de {task.name}: {str(e)}")
            task.status = AgentStatus.ERROR
            task.error = str(e)
            agent.status = AgentStatus.IDLE
            agent.metrics.failed_tasks += 1

    async def stop_coordinator(self):
        """Arrêter le coordinateur"""
        self.running = False
        logger.info("🛑 Coordinateur arrêté")

    def get_system_status(self) -> dict[str, Any]:
        """Obtenir le statut global du système"""
        return {
            "running": self.running,
            "total_agents": len(self.agents),
            "active_agents": len(
                [a for a in self.agents.values() if a.status == AgentStatus.RUNNING]
            ),
            "queued_tasks": len(self.task_queue),
            "agents_metrics": {name: agent.get_metrics() for name, agent in self.agents.items()},
        }


# Classe principale du système multi-agents
class MultiAgentSystem:
    """Système multi-agents principal de Tawiza-V2"""

    def __init__(self):
        self.coordinator = AgentCoordinator()
        self.initialized = False

    async def initialize(self):
        """Initialiser le système complet"""
        if self.initialized:
            return

        logger.info("🌅 Initialisation du Système Multi-Agents Avancé Tawiza-V2")

        # Démarrer le coordinateur en arrière-plan (sans bloquer)
        self.coordinator.running = True
        asyncio.create_task(self.coordinator.start_coordinator())

        # Enregistrer les agents de base (sera fait plus tard)
        # self.register_base_agents()

        self.initialized = True
        logger.info("✅ Système Multi-Agents initialisé avec succès")

    def register_base_agents(self):
        """Enregistrer les agents de base du système"""
        # Cette méthode sera implémentée après la création des agents spécialisés
        pass

    def get_system_info(self) -> dict[str, Any]:
        """Obtenir des informations sur le système"""
        return {
            "system": "Tawiza-V2 Multi-Agent System",
            "version": "2.0.0",
            "status": self.coordinator.get_system_status(),
            "capabilities": [
                "Multi-agent coordination",
                "Intelligent task distribution",
                "Advanced memory management",
                "Real-time monitoring",
                "GPU acceleration support",
            ],
        }


# Export des classes principales
__all__ = [
    "BaseAgent",
    "AgentCoordinator",
    "MultiAgentSystem",
    "AgentTask",
    "AgentStatus",
    "AgentPriority",
    "AgentMetrics",
]
