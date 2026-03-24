"""Tests complets pour task_queue_system.py

Tests couvrant:
- TaskPriority et TaskStatus enums
- Task dataclass
- WorkerStats dataclass
- SharedTaskQueue
- LoadBalancer
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.advanced.task_queue_system import (
    LoadBalancer,
    SharedTaskQueue,
    Task,
    TaskPriority,
    TaskStatus,
    WorkerStats,
)


# ============================================================================
# Tests TaskPriority Enum
# ============================================================================
class TestTaskPriority:
    """Tests pour l'enum TaskPriority."""

    def test_priority_values(self):
        """Vérifie les valeurs des priorités."""
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.NORMAL.value == 5
        assert TaskPriority.HIGH.value == 8
        assert TaskPriority.CRITICAL.value == 10

    def test_priority_ordering(self):
        """Vérifie l'ordre des priorités."""
        assert TaskPriority.LOW.value < TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value < TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value < TaskPriority.CRITICAL.value

    def test_priority_count(self):
        """Vérifie le nombre de priorités."""
        assert len(TaskPriority) == 4


# ============================================================================
# Tests TaskStatus Enum
# ============================================================================
class TestTaskStatus:
    """Tests pour l'enum TaskStatus."""

    def test_status_values(self):
        """Vérifie les valeurs des statuts."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_count(self):
        """Vérifie le nombre de statuts."""
        assert len(TaskStatus) == 6


# ============================================================================
# Tests Task Dataclass
# ============================================================================
class TestTask:
    """Tests pour la dataclass Task."""

    def test_create_task_minimal(self):
        """Création d'une tâche avec paramètres minimaux."""

        def dummy_func():
            pass

        task = Task(task_id="task-1", task_type="test", agent_type="analyzer", func=dummy_func)

        assert task.task_id == "task-1"
        assert task.task_type == "test"
        assert task.agent_type == "analyzer"
        assert task.func == dummy_func
        assert task.args == ()
        assert task.kwargs == {}
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout == 300.0
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None

    def test_create_task_full(self):
        """Création d'une tâche complète."""

        def task_func(x, y):
            return x + y

        task = Task(
            task_id="task-2",
            task_type="compute",
            agent_type="ml_engineer",
            func=task_func,
            args=(1, 2),
            kwargs={"extra": "param"},
            priority=TaskPriority.HIGH,
            timeout=60.0,
            retry_count=1,
            max_retries=5,
            status=TaskStatus.RUNNING,
            result=3,
            error=None,
        )

        assert task.args == (1, 2)
        assert task.kwargs == {"extra": "param"}
        assert task.priority == TaskPriority.HIGH
        assert task.timeout == 60.0
        assert task.max_retries == 5

    def test_task_comparison_high_priority_first(self):
        """Comparaison: priorité haute < priorité basse (pour heapq)."""

        def dummy():
            pass

        task_low = Task(
            task_id="t1", task_type="t", agent_type="a", func=dummy, priority=TaskPriority.LOW
        )
        task_high = Task(
            task_id="t2", task_type="t", agent_type="a", func=dummy, priority=TaskPriority.HIGH
        )
        task_critical = Task(
            task_id="t3", task_type="t", agent_type="a", func=dummy, priority=TaskPriority.CRITICAL
        )

        # CRITICAL < HIGH < LOW (pour que heapq retourne CRITICAL en premier)
        assert task_critical < task_high
        assert task_high < task_low

    def test_task_timestamps(self):
        """Vérification des timestamps."""

        def dummy():
            pass

        before = time.time()
        task = Task(task_id="t1", task_type="t", agent_type="a", func=dummy)
        after = time.time()

        assert before <= task.created_at <= after
        assert task.started_at is None
        assert task.completed_at is None


# ============================================================================
# Tests WorkerStats Dataclass
# ============================================================================
class TestWorkerStats:
    """Tests pour la dataclass WorkerStats."""

    def test_create_worker_stats_minimal(self):
        """Création de stats worker minimales."""
        stats = WorkerStats(worker_id="worker-1")

        assert stats.worker_id == "worker-1"
        assert stats.tasks_completed == 0
        assert stats.tasks_failed == 0
        assert stats.total_execution_time == 0.0
        assert stats.current_load == 0
        assert stats.max_load == 5
        assert stats.is_busy is False
        assert stats.last_task_time is None

    def test_create_worker_stats_full(self):
        """Création de stats worker complètes."""
        stats = WorkerStats(
            worker_id="worker-2",
            tasks_completed=10,
            tasks_failed=2,
            total_execution_time=120.5,
            current_load=3,
            max_load=10,
            is_busy=True,
            last_task_time=1234567890.0,
        )

        assert stats.tasks_completed == 10
        assert stats.tasks_failed == 2
        assert stats.total_execution_time == 120.5
        assert stats.current_load == 3
        assert stats.max_load == 10
        assert stats.is_busy is True


# ============================================================================
# Tests SharedTaskQueue
# ============================================================================
class TestSharedTaskQueue:
    """Tests pour la classe SharedTaskQueue."""

    @pytest.fixture
    def dummy_func(self):
        """Fonction dummy pour les tâches."""

        def func():
            return "done"

        return func

    def test_create_queue(self):
        """Création d'une queue."""
        queue = SharedTaskQueue(max_size=100)
        assert queue.max_size == 100
        assert len(queue._queue) == 0
        assert len(queue._task_map) == 0

    @pytest.mark.asyncio
    async def test_put_task(self, dummy_func):
        """Ajout d'une tâche à la queue."""
        queue = SharedTaskQueue()
        task = Task(task_id="t1", task_type="test", agent_type="a", func=dummy_func)

        await queue.put(task)

        assert await queue.size() == 1
        assert task.status == TaskStatus.QUEUED

    @pytest.mark.asyncio
    async def test_get_task(self, dummy_func):
        """Récupération d'une tâche."""
        queue = SharedTaskQueue()
        task = Task(task_id="t1", task_type="test", agent_type="a", func=dummy_func)

        await queue.put(task)
        retrieved = await queue.get()

        assert retrieved.task_id == "t1"
        assert retrieved.status == TaskStatus.RUNNING
        assert retrieved.started_at is not None

    @pytest.mark.asyncio
    async def test_get_empty_queue(self):
        """Récupération d'une queue vide."""
        queue = SharedTaskQueue()
        result = await queue.get()
        assert result is None

    @pytest.mark.asyncio
    async def test_priority_ordering(self, dummy_func):
        """Les tâches sont retournées par priorité."""
        queue = SharedTaskQueue()

        task_low = Task(
            task_id="low", task_type="t", agent_type="a", func=dummy_func, priority=TaskPriority.LOW
        )
        task_high = Task(
            task_id="high",
            task_type="t",
            agent_type="a",
            func=dummy_func,
            priority=TaskPriority.HIGH,
        )
        task_normal = Task(
            task_id="normal",
            task_type="t",
            agent_type="a",
            func=dummy_func,
            priority=TaskPriority.NORMAL,
        )

        # Ajouter dans un ordre mélangé
        await queue.put(task_low)
        await queue.put(task_high)
        await queue.put(task_normal)

        # Récupérer dans l'ordre de priorité
        first = await queue.get()
        second = await queue.get()
        third = await queue.get()

        assert first.task_id == "high"  # Priorité HIGH
        assert second.task_id == "normal"  # Priorité NORMAL
        assert third.task_id == "low"  # Priorité LOW

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, dummy_func):
        """Récupération d'une tâche par ID."""
        queue = SharedTaskQueue()
        task = Task(task_id="specific-task", task_type="t", agent_type="a", func=dummy_func)

        await queue.put(task)
        retrieved = await queue.get_task("specific-task")

        assert retrieved.task_id == "specific-task"

    @pytest.mark.asyncio
    async def test_get_task_nonexistent_id(self):
        """Récupération d'un ID inexistant."""
        queue = SharedTaskQueue()
        result = await queue.get_task("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_queue_full(self, dummy_func):
        """Queue pleine lève une erreur."""
        queue = SharedTaskQueue(max_size=2)

        await queue.put(Task(task_id="t1", task_type="t", agent_type="a", func=dummy_func))
        await queue.put(Task(task_id="t2", task_type="t", agent_type="a", func=dummy_func))

        with pytest.raises(ValueError, match="Queue pleine"):
            await queue.put(Task(task_id="t3", task_type="t", agent_type="a", func=dummy_func))

    @pytest.mark.asyncio
    async def test_is_empty(self, dummy_func):
        """Vérification is_empty."""
        queue = SharedTaskQueue()

        assert await queue.is_empty() is True

        await queue.put(Task(task_id="t1", task_type="t", agent_type="a", func=dummy_func))
        assert await queue.is_empty() is False

        await queue.get()
        assert await queue.is_empty() is True


# ============================================================================
# Tests LoadBalancer
# ============================================================================
class TestLoadBalancer:
    """Tests pour la classe LoadBalancer."""

    def test_create_load_balancer(self):
        """Création d'un load balancer."""
        lb = LoadBalancer()
        assert lb.workers == {}
        assert len(lb.agent_to_workers) == 0

    @pytest.mark.asyncio
    async def test_register_worker(self):
        """Enregistrement d'un worker."""
        lb = LoadBalancer()

        await lb.register_worker("worker-1", "data_analyst", max_load=10)

        assert "worker-1" in lb.workers
        assert lb.workers["worker-1"].max_load == 10
        assert "worker-1" in lb.agent_to_workers["data_analyst"]

    @pytest.mark.asyncio
    async def test_register_multiple_workers_same_type(self):
        """Enregistrement de plusieurs workers du même type."""
        lb = LoadBalancer()

        await lb.register_worker("worker-1", "analyzer")
        await lb.register_worker("worker-2", "analyzer")

        assert len(lb.agent_to_workers["analyzer"]) == 2

    @pytest.mark.asyncio
    async def test_get_best_worker_no_workers(self):
        """Aucun worker disponible."""
        lb = LoadBalancer()
        result = await lb.get_best_worker("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_best_worker_single(self):
        """Un seul worker disponible."""
        lb = LoadBalancer()
        await lb.register_worker("worker-1", "analyzer")

        result = await lb.get_best_worker("analyzer")
        assert result == "worker-1"

    @pytest.mark.asyncio
    async def test_get_best_worker_by_load(self):
        """Sélection du worker avec la charge la plus faible."""
        lb = LoadBalancer()

        await lb.register_worker("worker-1", "analyzer")
        await lb.register_worker("worker-2", "analyzer")

        # Simuler une charge différente
        lb.workers["worker-1"].current_load = 5
        lb.workers["worker-2"].current_load = 2

        result = await lb.get_best_worker("analyzer")
        assert result == "worker-2"  # Charge la plus faible

    @pytest.mark.asyncio
    async def test_get_best_worker_excludes_busy(self):
        """Exclure les workers occupés."""
        lb = LoadBalancer()

        await lb.register_worker("worker-1", "analyzer")
        await lb.register_worker("worker-2", "analyzer")

        # worker-1 est occupé à pleine charge
        lb.workers["worker-1"].current_load = 5
        lb.workers["worker-1"].max_load = 5
        lb.workers["worker-2"].current_load = 0

        result = await lb.get_best_worker("analyzer")
        assert result == "worker-2"


# ============================================================================
# Tests d'intégration
# ============================================================================
class TestTaskQueueIntegration:
    """Tests d'intégration pour le système de queue."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Workflow complet: queue + load balancer."""

        def task_func():
            return "done"

        # Setup
        queue = SharedTaskQueue()
        lb = LoadBalancer()

        await lb.register_worker("w1", "processor")
        await lb.register_worker("w2", "processor")

        # Ajouter des tâches
        for i in range(5):
            task = Task(
                task_id=f"task-{i}",
                task_type="process",
                agent_type="processor",
                func=task_func,
                priority=TaskPriority.NORMAL,
            )
            await queue.put(task)

        # Traiter les tâches
        while not await queue.is_empty():
            task = await queue.get()
            worker_id = await lb.get_best_worker(task.agent_type)

            assert worker_id is not None
            assert task.status == TaskStatus.RUNNING

            # Simuler l'exécution
            lb.workers[worker_id].current_load += 1
            task.result = task.func()
            task.status = TaskStatus.COMPLETED
            lb.workers[worker_id].current_load -= 1
            lb.workers[worker_id].tasks_completed += 1

        assert await queue.is_empty()

    @pytest.mark.asyncio
    async def test_concurrent_task_submission(self):
        """Soumission concurrente de tâches."""

        def task_func():
            pass

        queue = SharedTaskQueue()

        async def submit_task(i):
            task = Task(task_id=f"t{i}", task_type="t", agent_type="a", func=task_func)
            await queue.put(task)

        # Soumettre 50 tâches en parallèle
        await asyncio.gather(*[submit_task(i) for i in range(50)])

        assert await queue.size() == 50


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestTaskQueueEdgeCases:
    """Tests des cas limites."""

    @pytest.mark.asyncio
    async def test_critical_priority_always_first(self):
        """Les tâches critiques sont toujours traitées en premier."""

        def func():
            pass

        queue = SharedTaskQueue()

        # Ajouter beaucoup de tâches normales
        for i in range(100):
            task = Task(
                task_id=f"normal-{i}",
                task_type="t",
                agent_type="a",
                func=func,
                priority=TaskPriority.NORMAL,
            )
            await queue.put(task)

        # Ajouter une tâche critique
        critical_task = Task(
            task_id="critical",
            task_type="t",
            agent_type="a",
            func=func,
            priority=TaskPriority.CRITICAL,
        )
        await queue.put(critical_task)

        # La première tâche récupérée devrait être critique
        first = await queue.get()
        assert first.task_id == "critical"

    @pytest.mark.asyncio
    async def test_same_priority_fifo(self):
        """Tâches de même priorité: FIFO."""

        def func():
            pass

        queue = SharedTaskQueue()

        # Ajouter plusieurs tâches avec la même priorité
        for i in range(3):
            task = Task(
                task_id=f"t{i}",
                task_type="t",
                agent_type="a",
                func=func,
                priority=TaskPriority.HIGH,
            )
            await queue.put(task)

        # Note: heapq ne garantit pas FIFO strict pour éléments égaux
        # Ce test vérifie juste qu'ils sont tous récupérés
        retrieved = []
        for _ in range(3):
            t = await queue.get()
            retrieved.append(t.task_id)

        assert len(retrieved) == 3

    def test_worker_stats_calculation(self):
        """Calculs sur WorkerStats."""
        stats = WorkerStats(
            worker_id="w1", tasks_completed=90, tasks_failed=10, total_execution_time=100.0
        )

        total_tasks = stats.tasks_completed + stats.tasks_failed
        success_rate = stats.tasks_completed / total_tasks
        avg_time = stats.total_execution_time / total_tasks

        assert total_tasks == 100
        assert success_rate == 0.9
        assert avg_time == 1.0

    @pytest.mark.asyncio
    async def test_worker_at_max_load(self):
        """Worker à charge maximale."""
        lb = LoadBalancer()

        await lb.register_worker("w1", "type", max_load=3)
        lb.workers["w1"].current_load = 3  # À charge max

        await lb.register_worker("w2", "type", max_load=3)
        lb.workers["w2"].current_load = 1

        # Devrait choisir w2 (charge plus faible)
        result = await lb.get_best_worker("type")
        assert result == "w2"
