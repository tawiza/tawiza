"""Tests complets pour agent_integration.py

Tests couvrant:
- SystemStatus, AgentTask, TaskResult dataclasses
- AdvancedAgentIntegration
- Tests d'intégration avec mocks
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.agent_integration import (
    AdvancedAgentIntegration,
    AgentTask,
    SystemStatus,
    TaskResult,
)


# ============================================================================
# Tests SystemStatus Dataclass
# ============================================================================
class TestSystemStatus:
    """Tests pour la dataclass SystemStatus."""

    def test_create_status(self):
        """Création d'un statut système."""
        status = SystemStatus(
            is_initialized=True,
            active_agents=["data_analyst", "ml_engineer"],
            memory_usage=45.5,
            gpu_utilization=75.0,
            performance_score=0.85,
            last_update="2024-01-01T00:00:00",
        )
        assert status.is_initialized is True
        assert len(status.active_agents) == 2
        assert status.memory_usage == 45.5
        assert status.gpu_utilization == 75.0
        assert status.performance_score == 0.85

    def test_status_default_values(self):
        """Statut avec valeurs minimales."""
        status = SystemStatus(
            is_initialized=False,
            active_agents=[],
            memory_usage=0.0,
            gpu_utilization=0.0,
            performance_score=0.0,
            last_update="",
        )
        assert status.is_initialized is False
        assert status.active_agents == []


# ============================================================================
# Tests AgentTask Dataclass
# ============================================================================
class TestAgentTask:
    """Tests pour la dataclass AgentTask."""

    def test_create_task(self):
        """Création d'une tâche agent."""
        task = AgentTask(
            task_id="task-001",
            task_type="data_analysis",
            parameters={"dataset": "data.csv"},
            priority=5,
            timeout=300.0,
        )
        assert task.task_id == "task-001"
        assert task.task_type == "data_analysis"
        assert task.parameters["dataset"] == "data.csv"
        assert task.priority == 5
        assert task.timeout == 300.0
        assert task.callback is None

    def test_create_task_with_callback(self):
        """Tâche avec callback."""
        task = AgentTask(
            task_id="task-002",
            task_type="ml_training",
            parameters={},
            priority=10,
            timeout=600.0,
            callback="http://callback.url/notify",
        )
        assert task.callback == "http://callback.url/notify"

    def test_task_priority_range(self):
        """Priorités valides (1-10)."""
        for priority in [1, 5, 10]:
            task = AgentTask(
                task_id=f"task-{priority}",
                task_type="test",
                parameters={},
                priority=priority,
                timeout=100.0,
            )
            assert task.priority == priority


# ============================================================================
# Tests TaskResult Dataclass
# ============================================================================
class TestTaskResult:
    """Tests pour la dataclass TaskResult."""

    def test_create_success_result(self):
        """Résultat de tâche réussie."""
        result = TaskResult(
            task_id="task-001", success=True, result={"data": "processed"}, execution_time=1.5
        )
        assert result.task_id == "task-001"
        assert result.success is True
        assert result.result["data"] == "processed"
        assert result.execution_time == 1.5
        assert result.error_message is None

    def test_create_failure_result(self):
        """Résultat de tâche échouée."""
        result = TaskResult(
            task_id="task-002",
            success=False,
            result=None,
            execution_time=0.5,
            error_message="Connection timeout",
        )
        assert result.success is False
        assert result.error_message == "Connection timeout"

    def test_result_with_timestamp(self):
        """Résultat avec timestamp."""
        result = TaskResult(
            task_id="task-003",
            success=True,
            result={},
            execution_time=2.0,
            timestamp="2024-01-01T12:00:00",
        )
        assert result.timestamp == "2024-01-01T12:00:00"


# ============================================================================
# Tests AdvancedAgentIntegration - Création
# ============================================================================
class TestAdvancedAgentIntegrationBasic:
    """Tests basiques pour AdvancedAgentIntegration."""

    def test_create_integration(self):
        """Création de l'intégration."""
        integration = AdvancedAgentIntegration()

        assert integration.is_initialized is False
        assert integration.gpu_optimizer is None
        assert integration.data_analyst is None
        assert integration.ml_engineer is None
        assert integration.browser_automation is None
        assert integration.code_generator is None
        assert integration.task_queue is not None
        assert integration.active_tasks == {}
        assert integration.task_history == []
        assert integration.performance_metrics == {}

    def test_default_config(self):
        """Configuration par défaut."""
        integration = AdvancedAgentIntegration()

        assert integration.config["max_concurrent_tasks"] == 5
        assert integration.config["task_timeout"] == 300.0
        assert integration.config["enable_gpu_optimization"] is True
        assert integration.config["enable_performance_monitoring"] is True
        assert integration.config["auto_scale"] is True
        assert integration.config["retry_failed_tasks"] == 3

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test de get_status()."""
        integration = AdvancedAgentIntegration()
        status = await integration.get_status()

        # get_status returns a dict with status info
        assert "status" in status
        assert status["status"] in ["running", "not_initialized"]


# ============================================================================
# Tests AdvancedAgentIntegration - Initialisation mockée
# ============================================================================
class TestAdvancedAgentIntegrationInitialization:
    """Tests d'initialisation avec mocks."""

    @pytest.mark.asyncio
    async def test_initialize_mocked(self):
        """Initialisation avec composants mockés."""
        integration = AdvancedAgentIntegration()

        # Mock les composants
        with (
            patch.object(
                integration, "_initialize_specialized_agents", new_callable=AsyncMock
            ) as mock_agents,
            patch.object(
                integration, "_optimize_gpu_performance", new_callable=AsyncMock
            ) as mock_gpu,
            patch.object(
                integration, "_setup_multi_agent_system", new_callable=AsyncMock
            ) as mock_setup,
            patch.object(integration, "_start_services", new_callable=AsyncMock) as mock_services,
            patch.object(integration, "show_system_status", new_callable=AsyncMock) as mock_status,
            patch(
                "src.infrastructure.agents.advanced.agent_integration.create_gpu_optimizer"
            ) as mock_optimizer,
        ):
            mock_optimizer_instance = MagicMock()
            mock_optimizer_instance.initialize = AsyncMock()
            mock_optimizer.return_value = mock_optimizer_instance

            await integration.initialize()

            assert integration.is_initialized is True
            mock_agents.assert_called_once()
            mock_setup.assert_called_once()
            mock_services.assert_called_once()


# ============================================================================
# Tests des tâches
# ============================================================================
class TestAdvancedAgentIntegrationTasks:
    """Tests des opérations sur les tâches."""

    def test_task_queue_empty(self):
        """Queue de tâches vide au départ."""
        integration = AdvancedAgentIntegration()
        assert integration.task_queue.empty()

    @pytest.mark.asyncio
    async def test_add_task_to_queue(self):
        """Ajout d'une tâche à la queue."""
        integration = AdvancedAgentIntegration()

        task = AgentTask(
            task_id="task-001", task_type="data_analysis", parameters={}, priority=5, timeout=300.0
        )

        await integration.task_queue.put(task)
        assert not integration.task_queue.empty()

        retrieved = await integration.task_queue.get()
        assert retrieved.task_id == "task-001"

    def test_active_tasks_management(self):
        """Gestion des tâches actives."""
        integration = AdvancedAgentIntegration()

        # Ajouter une tâche active
        integration.active_tasks["task-001"] = {"status": "running"}
        assert "task-001" in integration.active_tasks

        # Supprimer la tâche
        del integration.active_tasks["task-001"]
        assert "task-001" not in integration.active_tasks

    def test_task_history(self):
        """Historique des tâches."""
        integration = AdvancedAgentIntegration()

        result = TaskResult(task_id="task-001", success=True, result={}, execution_time=1.0)
        integration.task_history.append(result)

        assert len(integration.task_history) == 1
        assert integration.task_history[0].task_id == "task-001"


# ============================================================================
# Tests métriques de performance
# ============================================================================
class TestAdvancedAgentIntegrationMetrics:
    """Tests des métriques de performance."""

    def test_performance_metrics_storage(self):
        """Stockage des métriques de performance."""
        integration = AdvancedAgentIntegration()

        integration.performance_metrics["model1"] = {
            "original_performance": 10.0,
            "optimized_performance": 50.0,
            "improvement": 400.0,
        }

        assert "model1" in integration.performance_metrics
        assert integration.performance_metrics["model1"]["improvement"] == 400.0

    def test_multiple_model_metrics(self):
        """Métriques pour plusieurs modèles."""
        integration = AdvancedAgentIntegration()

        models = ["qwen3:14b", "mistral:latest", "llama3:8b"]
        for model in models:
            integration.performance_metrics[model] = {"improvement": 100.0}

        assert len(integration.performance_metrics) == 3


# ============================================================================
# Tests de configuration
# ============================================================================
class TestAdvancedAgentIntegrationConfig:
    """Tests de configuration."""

    def test_config_modification(self):
        """Modification de la configuration."""
        integration = AdvancedAgentIntegration()

        integration.config["max_concurrent_tasks"] = 10
        integration.config["task_timeout"] = 600.0

        assert integration.config["max_concurrent_tasks"] == 10
        assert integration.config["task_timeout"] == 600.0

    def test_disable_gpu_optimization(self):
        """Désactivation de l'optimisation GPU."""
        integration = AdvancedAgentIntegration()
        integration.config["enable_gpu_optimization"] = False

        assert integration.config["enable_gpu_optimization"] is False


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestAdvancedAgentIntegrationEdgeCases:
    """Tests des cas limites."""

    def test_multiple_instances(self):
        """Plusieurs instances indépendantes."""
        int1 = AdvancedAgentIntegration()
        int2 = AdvancedAgentIntegration()

        int1.config["max_concurrent_tasks"] = 10
        int2.config["max_concurrent_tasks"] = 5

        assert int1.config["max_concurrent_tasks"] == 10
        assert int2.config["max_concurrent_tasks"] == 5

    @pytest.mark.asyncio
    async def test_task_queue_multiple_tasks(self):
        """Queue avec plusieurs tâches."""
        integration = AdvancedAgentIntegration()

        for i in range(10):
            task = AgentTask(
                task_id=f"task-{i:03d}",
                task_type="test",
                parameters={"index": i},
                priority=i % 10 + 1,
                timeout=100.0,
            )
            await integration.task_queue.put(task)

        assert integration.task_queue.qsize() == 10

    def test_task_history_growth(self):
        """Croissance de l'historique des tâches."""
        integration = AdvancedAgentIntegration()

        for i in range(100):
            result = TaskResult(task_id=f"task-{i}", success=True, result={}, execution_time=1.0)
            integration.task_history.append(result)

        assert len(integration.task_history) == 100
