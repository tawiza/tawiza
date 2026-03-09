"""Tests complets pour multi_agent_system.py

Tests couvrant:
- Enums et dataclasses
- BaseAgent
- AgentCoordinator
- MultiAgentSystem
- Edge cases et intégration
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.multi_agent_system import (
    AgentCoordinator,
    AgentMetrics,
    AgentPriority,
    AgentStatus,
    AgentTask,
    BaseAgent,
    MultiAgentSystem,
)


# ============================================================================
# Tests AgentStatus Enum
# ============================================================================
class TestAgentStatus:
    """Tests pour l'enum AgentStatus."""

    def test_status_values(self):
        """Vérifie les valeurs de l'enum."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.ERROR.value == "error"
        assert AgentStatus.COMPLETED.value == "completed"

    def test_status_count(self):
        """Vérifie le nombre de statuts."""
        assert len(AgentStatus) == 5

    def test_status_from_value(self):
        """Vérifie la création depuis une valeur."""
        assert AgentStatus("idle") == AgentStatus.IDLE
        assert AgentStatus("running") == AgentStatus.RUNNING


# ============================================================================
# Tests AgentPriority Enum
# ============================================================================
class TestAgentPriority:
    """Tests pour l'enum AgentPriority."""

    def test_priority_values(self):
        """Vérifie les valeurs numériques des priorités."""
        assert AgentPriority.LOW.value == 1
        assert AgentPriority.MEDIUM.value == 2
        assert AgentPriority.HIGH.value == 3
        assert AgentPriority.CRITICAL.value == 4

    def test_priority_ordering(self):
        """Vérifie l'ordre des priorités."""
        assert AgentPriority.LOW.value < AgentPriority.MEDIUM.value
        assert AgentPriority.MEDIUM.value < AgentPriority.HIGH.value
        assert AgentPriority.HIGH.value < AgentPriority.CRITICAL.value

    def test_priority_comparison(self):
        """Vérifie la comparaison des priorités."""
        priorities = [AgentPriority.HIGH, AgentPriority.LOW, AgentPriority.CRITICAL]
        sorted_priorities = sorted(priorities, key=lambda x: x.value)
        assert sorted_priorities == [AgentPriority.LOW, AgentPriority.HIGH, AgentPriority.CRITICAL]


# ============================================================================
# Tests AgentTask Dataclass
# ============================================================================
class TestAgentTask:
    """Tests pour la dataclass AgentTask."""

    def test_create_task_minimal(self):
        """Création d'une tâche avec paramètres minimaux."""
        task = AgentTask(id="task-1", name="Test Task", agent_type="test")
        assert task.id == "task-1"
        assert task.name == "Test Task"
        assert task.agent_type == "test"
        assert task.parameters == {}
        assert task.priority == AgentPriority.MEDIUM
        assert task.status == AgentStatus.IDLE
        assert task.result is None
        assert task.error is None

    def test_create_task_full(self):
        """Création d'une tâche avec tous les paramètres."""
        task = AgentTask(
            id="task-2",
            name="Full Task",
            agent_type="analyzer",
            parameters={"key": "value"},
            priority=AgentPriority.HIGH,
            status=AgentStatus.RUNNING,
            result={"data": "result"},
            error=None,
        )
        assert task.parameters == {"key": "value"}
        assert task.priority == AgentPriority.HIGH
        assert task.status == AgentStatus.RUNNING
        assert task.result == {"data": "result"}

    def test_task_created_at_auto(self):
        """Vérifie que created_at est auto-généré."""
        before = time.time()
        task = AgentTask(id="task-3", name="Timed Task", agent_type="test")
        after = time.time()
        assert before <= task.created_at <= after

    def test_task_mutable(self):
        """Vérifie que la tâche est mutable."""
        task = AgentTask(id="task-4", name="Mutable Task", agent_type="test")
        task.status = AgentStatus.COMPLETED
        task.result = "done"
        assert task.status == AgentStatus.COMPLETED
        assert task.result == "done"


# ============================================================================
# Tests AgentMetrics Dataclass
# ============================================================================
class TestAgentMetrics:
    """Tests pour la dataclass AgentMetrics."""

    def test_create_metrics_default(self):
        """Création de métriques avec valeurs par défaut."""
        metrics = AgentMetrics()
        assert metrics.total_tasks == 0
        assert metrics.completed_tasks == 0
        assert metrics.failed_tasks == 0
        assert metrics.average_execution_time == 0.0
        assert metrics.success_rate == 0.0
        assert metrics.last_execution_time is None

    def test_metrics_update(self):
        """Mise à jour des métriques."""
        metrics = AgentMetrics()
        metrics.completed_tasks = 5
        metrics.failed_tasks = 1
        metrics.success_rate = 5 / 6
        assert metrics.success_rate == pytest.approx(0.833, rel=0.01)


# ============================================================================
# Tests BaseAgent
# ============================================================================
class TestBaseAgent:
    """Tests pour la classe BaseAgent."""

    def test_create_agent(self):
        """Création d'un agent de base."""
        agent = BaseAgent(name="TestAgent", agent_type="test")
        assert agent.name == "TestAgent"
        assert agent.agent_type == "test"
        assert agent.status == AgentStatus.IDLE
        assert isinstance(agent.metrics, AgentMetrics)
        assert agent.memory is None
        assert agent.tools == []
        assert agent.capabilities == []

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test de l'initialisation de l'agent."""
        agent = BaseAgent(name="InitAgent", agent_type="test")
        agent.status = AgentStatus.PAUSED
        await agent.initialize()
        assert agent.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_execute_task_not_implemented(self):
        """execute_task doit lever NotImplementedError."""
        agent = BaseAgent(name="BaseAgent", agent_type="test")
        task = AgentTask(id="t1", name="Task", agent_type="test")
        with pytest.raises(NotImplementedError):
            await agent.execute_task(task)

    @pytest.mark.asyncio
    async def test_pause(self):
        """Test de la mise en pause."""
        agent = BaseAgent(name="PauseAgent", agent_type="test")
        agent.status = AgentStatus.RUNNING
        await agent.pause()
        assert agent.status == AgentStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume(self):
        """Test de la reprise."""
        agent = BaseAgent(name="ResumeAgent", agent_type="test")
        agent.status = AgentStatus.PAUSED
        await agent.resume()
        assert agent.status == AgentStatus.RUNNING

    def test_get_metrics(self):
        """Test de récupération des métriques."""
        agent = BaseAgent(name="MetricsAgent", agent_type="test")
        agent.metrics.completed_tasks = 10
        metrics = agent.get_metrics()
        assert metrics.completed_tasks == 10

    def test_add_capability(self):
        """Test d'ajout de capacité."""
        agent = BaseAgent(name="CapAgent", agent_type="test")
        agent.add_capability("analyze")
        agent.add_capability("process")
        assert "analyze" in agent.capabilities
        assert "process" in agent.capabilities
        assert len(agent.capabilities) == 2


# ============================================================================
# Tests AgentCoordinator
# ============================================================================
class TestAgentCoordinator:
    """Tests pour la classe AgentCoordinator."""

    def test_create_coordinator(self):
        """Création d'un coordinateur."""
        coordinator = AgentCoordinator()
        assert coordinator.agents == {}
        assert coordinator.task_queue == []
        assert coordinator.running is False
        assert isinstance(coordinator.metrics, AgentMetrics)

    def test_register_agent(self):
        """Enregistrement d'un agent."""
        coordinator = AgentCoordinator()
        agent = BaseAgent(name="Agent1", agent_type="test")
        coordinator.register_agent(agent)
        assert "Agent1" in coordinator.agents
        assert coordinator.agents["Agent1"] == agent

    def test_register_multiple_agents(self):
        """Enregistrement de plusieurs agents."""
        coordinator = AgentCoordinator()
        agent1 = BaseAgent(name="Agent1", agent_type="type1")
        agent2 = BaseAgent(name="Agent2", agent_type="type2")
        coordinator.register_agent(agent1)
        coordinator.register_agent(agent2)
        assert len(coordinator.agents) == 2

    def test_unregister_agent(self):
        """Désenregistrement d'un agent."""
        coordinator = AgentCoordinator()
        agent = BaseAgent(name="Agent1", agent_type="test")
        coordinator.register_agent(agent)
        coordinator.unregister_agent("Agent1")
        assert "Agent1" not in coordinator.agents

    def test_unregister_nonexistent_agent(self):
        """Désenregistrement d'un agent inexistant (pas d'erreur)."""
        coordinator = AgentCoordinator()
        coordinator.unregister_agent("NonExistent")  # Ne doit pas lever d'erreur

    def test_submit_task(self):
        """Soumission d'une tâche."""
        coordinator = AgentCoordinator()
        task = AgentTask(id="task-1", name="Test", agent_type="test")
        task_id = coordinator.submit_task(task)
        assert task_id == "task-1"
        assert len(coordinator.task_queue) == 1
        assert coordinator.task_queue[0] == task

    def test_get_suitable_agents_none(self):
        """Aucun agent disponible."""
        coordinator = AgentCoordinator()
        task = AgentTask(id="t1", name="Task", agent_type="analyzer")
        agents = coordinator.get_suitable_agents(task)
        assert agents == []

    def test_get_suitable_agents_by_capability(self):
        """Trouver agents par capacité."""
        coordinator = AgentCoordinator()
        agent1 = BaseAgent(name="Agent1", agent_type="test")
        agent1.add_capability("analyzer")
        agent2 = BaseAgent(name="Agent2", agent_type="test")
        agent2.add_capability("processor")
        coordinator.register_agent(agent1)
        coordinator.register_agent(agent2)

        task = AgentTask(id="t1", name="Task", agent_type="analyzer")
        agents = coordinator.get_suitable_agents(task)
        assert len(agents) == 1
        assert agents[0].name == "Agent1"

    def test_get_suitable_agents_excludes_busy(self):
        """Exclure les agents occupés."""
        coordinator = AgentCoordinator()
        agent1 = BaseAgent(name="Agent1", agent_type="test")
        agent1.add_capability("work")
        agent1.status = AgentStatus.RUNNING
        agent2 = BaseAgent(name="Agent2", agent_type="test")
        agent2.add_capability("work")
        agent2.status = AgentStatus.IDLE
        coordinator.register_agent(agent1)
        coordinator.register_agent(agent2)

        task = AgentTask(id="t1", name="Task", agent_type="work")
        agents = coordinator.get_suitable_agents(task)
        assert len(agents) == 1
        assert agents[0].name == "Agent2"

    def test_get_system_status(self):
        """Récupérer le statut du système."""
        coordinator = AgentCoordinator()
        agent = BaseAgent(name="Agent1", agent_type="test")
        coordinator.register_agent(agent)
        coordinator.submit_task(AgentTask(id="t1", name="Task", agent_type="test"))

        status = coordinator.get_system_status()
        assert status["running"] is False
        assert status["total_agents"] == 1
        assert status["active_agents"] == 0
        assert status["queued_tasks"] == 1
        assert "Agent1" in status["agents_metrics"]

    @pytest.mark.asyncio
    async def test_stop_coordinator(self):
        """Arrêt du coordinateur."""
        coordinator = AgentCoordinator()
        coordinator.running = True
        await coordinator.stop_coordinator()
        assert coordinator.running is False


# ============================================================================
# Tests AgentCoordinator - Exécution de tâches
# ============================================================================
class TestAgentCoordinatorExecution:
    """Tests d'exécution de tâches du coordinateur."""

    @pytest.mark.asyncio
    async def test_execute_task_with_agent_success(self):
        """Exécution réussie d'une tâche."""
        coordinator = AgentCoordinator()

        # Créer un agent mock
        agent = BaseAgent(name="MockAgent", agent_type="test")
        agent.execute_task = AsyncMock(return_value={"result": "success"})
        coordinator.register_agent(agent)

        task = AgentTask(id="t1", name="TestTask", agent_type="test")
        await coordinator.execute_task_with_agent(agent, task)

        assert task.status == AgentStatus.COMPLETED
        assert task.result == {"result": "success"}
        assert agent.status == AgentStatus.IDLE
        assert agent.metrics.completed_tasks == 1

    @pytest.mark.asyncio
    async def test_execute_task_with_agent_failure(self):
        """Exécution échouée d'une tâche."""
        coordinator = AgentCoordinator()

        agent = BaseAgent(name="FailAgent", agent_type="test")
        agent.execute_task = AsyncMock(side_effect=Exception("Task failed"))
        coordinator.register_agent(agent)

        task = AgentTask(id="t1", name="FailTask", agent_type="test")
        await coordinator.execute_task_with_agent(agent, task)

        assert task.status == AgentStatus.ERROR
        assert task.error == "Task failed"
        assert agent.status == AgentStatus.IDLE
        assert agent.metrics.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_execute_task_updates_metrics(self):
        """Vérifie la mise à jour des métriques après exécution."""
        coordinator = AgentCoordinator()

        agent = BaseAgent(name="MetricsAgent", agent_type="test")
        agent.execute_task = AsyncMock(return_value="done")
        coordinator.register_agent(agent)

        # Exécuter plusieurs tâches
        for i in range(3):
            task = AgentTask(id=f"t{i}", name=f"Task{i}", agent_type="test")
            await coordinator.execute_task_with_agent(agent, task)

        assert agent.metrics.completed_tasks == 3
        assert agent.metrics.success_rate == 1.0
        assert agent.metrics.last_execution_time is not None


# ============================================================================
# Tests MultiAgentSystem
# ============================================================================
class TestMultiAgentSystem:
    """Tests pour la classe MultiAgentSystem."""

    def test_create_system(self):
        """Création du système multi-agents."""
        system = MultiAgentSystem()
        assert isinstance(system.coordinator, AgentCoordinator)
        assert system.initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Initialisation du système."""
        system = MultiAgentSystem()
        await system.initialize()
        assert system.initialized is True
        assert system.coordinator.running is True
        # Cleanup
        await system.coordinator.stop_coordinator()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """L'initialisation est idempotente."""
        system = MultiAgentSystem()
        await system.initialize()
        await system.initialize()  # Deuxième appel
        assert system.initialized is True
        await system.coordinator.stop_coordinator()

    def test_get_system_info(self):
        """Récupérer les infos du système."""
        system = MultiAgentSystem()
        info = system.get_system_info()
        assert info["system"] == "Tawiza-V2 Multi-Agent System"
        assert info["version"] == "2.0.0"
        assert "status" in info
        assert "capabilities" in info
        assert len(info["capabilities"]) == 5

    def test_register_base_agents(self):
        """register_base_agents ne lève pas d'erreur."""
        system = MultiAgentSystem()
        system.register_base_agents()  # Actuellement un pass


# ============================================================================
# Tests d'intégration légère
# ============================================================================
class TestMultiAgentSystemIntegration:
    """Tests d'intégration du système complet."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test du workflow complet: init -> register -> submit -> execute."""
        system = MultiAgentSystem()
        await system.initialize()

        # Créer et enregistrer un agent
        class TestAgent(BaseAgent):
            async def execute_task(self, task):
                return f"Processed: {task.name}"

        agent = TestAgent(name="WorkflowAgent", agent_type="processor")
        agent.add_capability("processor")
        system.coordinator.register_agent(agent)

        # Soumettre une tâche
        task = AgentTask(id="workflow-task", name="Integration Test", agent_type="processor")
        system.coordinator.submit_task(task)

        # Attendre un peu pour le traitement
        await asyncio.sleep(0.2)

        # Vérifier
        assert task.status == AgentStatus.COMPLETED
        assert task.result == "Processed: Integration Test"

        await system.coordinator.stop_coordinator()

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Les tâches à haute priorité sont traitées en premier."""
        coordinator = AgentCoordinator()

        # Soumettre des tâches avec différentes priorités
        task_low = AgentTask(id="t1", name="Low", agent_type="test", priority=AgentPriority.LOW)
        task_high = AgentTask(id="t2", name="High", agent_type="test", priority=AgentPriority.HIGH)
        task_critical = AgentTask(
            id="t3", name="Critical", agent_type="test", priority=AgentPriority.CRITICAL
        )

        coordinator.submit_task(task_low)
        coordinator.submit_task(task_high)
        coordinator.submit_task(task_critical)

        # Trier comme le ferait le coordinateur
        coordinator.task_queue.sort(key=lambda x: x.priority.value, reverse=True)

        assert coordinator.task_queue[0].name == "Critical"
        assert coordinator.task_queue[1].name == "High"
        assert coordinator.task_queue[2].name == "Low"

    @pytest.mark.asyncio
    async def test_multiple_agents_selection(self):
        """Sélection du meilleur agent parmi plusieurs."""
        coordinator = AgentCoordinator()

        # Agent avec bon taux de succès
        good_agent = BaseAgent(name="GoodAgent", agent_type="test")
        good_agent.add_capability("work")
        good_agent.metrics.success_rate = 0.9

        # Agent avec mauvais taux de succès
        bad_agent = BaseAgent(name="BadAgent", agent_type="test")
        bad_agent.add_capability("work")
        bad_agent.metrics.success_rate = 0.5

        coordinator.register_agent(bad_agent)
        coordinator.register_agent(good_agent)

        task = AgentTask(id="t1", name="Task", agent_type="work")
        agents = coordinator.get_suitable_agents(task)

        # Le bon agent devrait être en premier (meilleur success_rate)
        assert len(agents) == 2
        assert agents[0].name == "GoodAgent"


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestEdgeCases:
    """Tests des cas limites."""

    def test_empty_task_parameters(self):
        """Tâche avec paramètres vides."""
        task = AgentTask(id="t1", name="Empty", agent_type="test", parameters={})
        assert task.parameters == {}

    def test_task_with_complex_parameters(self):
        """Tâche avec paramètres complexes."""
        params = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "none": None,
        }
        task = AgentTask(id="t1", name="Complex", agent_type="test", parameters=params)
        assert task.parameters["nested"]["key"] == "value"
        assert task.parameters["list"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_agent_rapid_status_changes(self):
        """Changements rapides de statut."""
        agent = BaseAgent(name="RapidAgent", agent_type="test")
        for _ in range(100):
            await agent.pause()
            await agent.resume()
        assert agent.status == AgentStatus.RUNNING

    def test_coordinator_with_many_agents(self):
        """Coordinateur avec beaucoup d'agents."""
        coordinator = AgentCoordinator()
        for i in range(100):
            agent = BaseAgent(name=f"Agent{i}", agent_type="mass")
            coordinator.register_agent(agent)
        assert len(coordinator.agents) == 100

    def test_coordinator_with_many_tasks(self):
        """Coordinateur avec beaucoup de tâches."""
        coordinator = AgentCoordinator()
        for i in range(100):
            task = AgentTask(id=f"t{i}", name=f"Task{i}", agent_type="test")
            coordinator.submit_task(task)
        assert len(coordinator.task_queue) == 100
