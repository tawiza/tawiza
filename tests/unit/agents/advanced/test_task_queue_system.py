#!/usr/bin/env python3
"""
Tests unitaires pour le Task Queue System
Couvre: SharedTaskQueue, LoadBalancer, WorkerPool, TaskQueueSystem
"""

import asyncio
import time

import pytest

from src.infrastructure.agents.advanced.task_queue_system import (
    LoadBalancer,
    SharedTaskQueue,
    Task,
    TaskPriority,
    TaskQueueSystem,
    TaskStatus,
    WorkerPool,
    WorkerStats,
)


class TestTask:
    """Tests pour la classe Task"""

    def test_task_creation(self):
        """Test création d'une tâche basique"""

        async def dummy_func():
            return "test"

        task = Task(
            task_id="test-123",
            task_type="analyze",
            agent_type="data_analyst",
            func=dummy_func,
            priority=TaskPriority.NORMAL,
        )

        assert task.task_id == "test-123"
        assert task.task_type == "analyze"
        assert task.agent_type == "data_analyst"
        assert task.priority == TaskPriority.NORMAL
        assert task.status == TaskStatus.PENDING

    def test_task_priority_comparison(self):
        """Test que les priorités sont correctement comparées"""

        async def dummy_func():
            pass

        task_low = Task("1", "test", "agent", dummy_func, priority=TaskPriority.LOW)
        task_high = Task("2", "test", "agent", dummy_func, priority=TaskPriority.HIGH)
        task_critical = Task("3", "test", "agent", dummy_func, priority=TaskPriority.CRITICAL)

        # Plus haute priorité = plus petit dans la comparaison (pour heap)
        assert task_critical < task_high
        assert task_high < task_low


class TestSharedTaskQueue:
    """Tests pour SharedTaskQueue"""

    @pytest.mark.asyncio
    async def test_queue_put_get(self):
        """Test ajout et récupération de tâches"""
        queue = SharedTaskQueue(max_size=10)

        async def dummy_func():
            return "test"

        task = Task("test-1", "analyze", "data_analyst", dummy_func)

        # Put task
        await queue.put(task)
        assert await queue.size() == 1
        assert task.status == TaskStatus.QUEUED

        # Get task
        retrieved_task = await queue.get()
        assert retrieved_task.task_id == "test-1"
        assert retrieved_task.status == TaskStatus.RUNNING
        assert await queue.size() == 0

    @pytest.mark.asyncio
    async def test_queue_priority_order(self):
        """Test que les tâches sont récupérées par priorité"""
        queue = SharedTaskQueue(max_size=10)

        async def dummy_func():
            pass

        # Ajouter tâches dans ordre mixte
        task_normal = Task("1", "test", "agent", dummy_func, priority=TaskPriority.NORMAL)
        task_high = Task("2", "test", "agent", dummy_func, priority=TaskPriority.HIGH)
        task_low = Task("3", "test", "agent", dummy_func, priority=TaskPriority.LOW)
        task_critical = Task("4", "test", "agent", dummy_func, priority=TaskPriority.CRITICAL)

        await queue.put(task_normal)
        await queue.put(task_high)
        await queue.put(task_low)
        await queue.put(task_critical)

        # Récupérer dans l'ordre de priorité
        first = await queue.get()
        assert first.priority == TaskPriority.CRITICAL

        second = await queue.get()
        assert second.priority == TaskPriority.HIGH

        third = await queue.get()
        assert third.priority == TaskPriority.NORMAL

        fourth = await queue.get()
        assert fourth.priority == TaskPriority.LOW

    @pytest.mark.asyncio
    async def test_queue_max_size(self):
        """Test que la queue respecte max_size"""
        queue = SharedTaskQueue(max_size=2)

        async def dummy_func():
            pass

        task1 = Task("1", "test", "agent", dummy_func)
        task2 = Task("2", "test", "agent", dummy_func)
        task3 = Task("3", "test", "agent", dummy_func)

        await queue.put(task1)
        await queue.put(task2)

        # La 3ème devrait échouer
        with pytest.raises(ValueError, match="Queue pleine"):
            await queue.put(task3)

    @pytest.mark.asyncio
    async def test_queue_get_task_by_id(self):
        """Test récupération d'une tâche par ID"""
        queue = SharedTaskQueue()

        async def dummy_func():
            pass

        task = Task("test-id", "test", "agent", dummy_func)
        await queue.put(task)

        retrieved = await queue.get_task("test-id")
        assert retrieved is not None
        assert retrieved.task_id == "test-id"

    @pytest.mark.asyncio
    async def test_queue_empty_returns_none(self):
        """Test que get() retourne None si queue vide"""
        queue = SharedTaskQueue()

        result = await queue.get()
        assert result is None


class TestLoadBalancer:
    """Tests pour LoadBalancer"""

    @pytest.mark.asyncio
    async def test_register_worker(self):
        """Test enregistrement d'un worker"""
        balancer = LoadBalancer()

        await balancer.register_worker(worker_id="worker-1", agent_type="data_analyst", max_load=5)

        assert "worker-1" in balancer.workers
        assert balancer.workers["worker-1"].max_load == 5

    @pytest.mark.asyncio
    async def test_get_best_worker(self):
        """Test sélection du meilleur worker"""
        balancer = LoadBalancer()

        await balancer.register_worker("worker-1", "data_analyst", max_load=5)
        await balancer.register_worker("worker-2", "data_analyst", max_load=5)

        # Worker 1 a moins de charge
        balancer.workers["worker-1"].current_load = 1
        balancer.workers["worker-2"].current_load = 3

        best = await balancer.get_best_worker("data_analyst")
        assert best == "worker-1"

    @pytest.mark.asyncio
    async def test_update_worker_load(self):
        """Test mise à jour de la charge d'un worker"""
        balancer = LoadBalancer()

        await balancer.register_worker("worker-1", "data_analyst", max_load=5)

        await balancer.update_worker_load("worker-1", 2)
        assert balancer.workers["worker-1"].current_load == 2
        assert balancer.workers["worker-1"].is_busy is True

        await balancer.update_worker_load("worker-1", -2)
        assert balancer.workers["worker-1"].current_load == 0
        assert balancer.workers["worker-1"].is_busy is False

    @pytest.mark.asyncio
    async def test_record_task_completion(self):
        """Test enregistrement de complétion de tâche"""
        balancer = LoadBalancer()

        await balancer.register_worker("worker-1", "data_analyst", max_load=5)

        # Task succeeded
        await balancer.record_task_completion("worker-1", True, 1.5)
        assert balancer.workers["worker-1"].tasks_completed == 1
        assert balancer.workers["worker-1"].total_execution_time == 1.5

        # Task failed
        await balancer.record_task_completion("worker-1", False, 0.5)
        assert balancer.workers["worker-1"].tasks_failed == 1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test récupération des statistiques"""
        balancer = LoadBalancer()

        await balancer.register_worker("worker-1", "data_analyst", max_load=5)
        await balancer.record_task_completion("worker-1", True, 2.0)

        stats = await balancer.get_stats()

        assert "worker-1" in stats
        assert stats["worker-1"]["tasks_completed"] == 1
        assert stats["worker-1"]["avg_execution_time"] == 2.0
        assert stats["worker-1"]["utilization"] == 0.0


class TestWorkerPool:
    """Tests pour WorkerPool"""

    @pytest.mark.asyncio
    async def test_worker_pool_start_stop(self):
        """Test démarrage et arrêt du worker pool"""
        queue = SharedTaskQueue()
        balancer = LoadBalancer()
        pool = WorkerPool(queue, balancer, num_workers=2)

        await pool.start()
        assert pool.is_running is True
        assert len(pool.workers) == 2

        await pool.stop()
        assert pool.is_running is False
        assert len(pool.workers) == 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_worker_executes_task(self):
        """Test qu'un worker exécute une tâche"""
        queue = SharedTaskQueue()
        balancer = LoadBalancer()

        # Register a worker for the agent type
        await balancer.register_worker("worker-0", "test_agent", max_load=5)

        pool = WorkerPool(queue, balancer, num_workers=1)
        await pool.start()

        # Create and submit task
        executed = False

        async def test_func():
            nonlocal executed
            executed = True
            return "done"

        task = Task("test-1", "test", "test_agent", test_func)
        await queue.put(task)

        # Wait for execution
        await asyncio.sleep(0.5)

        assert executed is True
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "done"

        await pool.stop()


class TestTaskQueueSystem:
    """Tests d'intégration pour TaskQueueSystem"""

    @pytest.mark.asyncio
    async def test_system_initialization(self):
        """Test initialisation du système complet"""
        system = TaskQueueSystem(num_workers=2, max_queue_size=100)

        await system.start()
        assert system.worker_pool.is_running is True

        await system.stop()
        assert system.worker_pool.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_submit_and_execute_task(self):
        """Test soumission et exécution d'une tâche complète"""
        system = TaskQueueSystem(num_workers=2)

        # Register worker
        await system.load_balancer.register_worker("worker-0", "data_analyst", max_load=5)

        await system.start()

        # Create and submit task
        async def analysis_task(data):
            await asyncio.sleep(0.1)
            return f"analyzed: {data}"

        task = Task(
            task_id="analysis-1",
            task_type="analyze",
            agent_type="data_analyst",
            func=analysis_task,
            args=("test_data",),
        )

        task_id = await system.submit_task(task)
        assert task_id == "analysis-1"

        # Wait for completion
        await asyncio.sleep(0.5)

        # Check status
        status = await system.get_task_status(task_id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["task_id"] == "analysis-1"

        await system.stop()

    @pytest.mark.asyncio
    async def test_get_system_stats(self):
        """Test récupération des statistiques système"""
        system = TaskQueueSystem(num_workers=2)
        await system.start()

        stats = await system.get_system_stats()

        assert "queue_size" in stats
        assert "num_workers" in stats
        assert "workers" in stats
        assert "total_tasks_completed" in stats
        assert "total_tasks_failed" in stats
        assert "avg_utilization" in stats

        await system.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_task_timeout(self):
        """Test qu'une tâche timeout correctement"""
        system = TaskQueueSystem(num_workers=1)
        await system.load_balancer.register_worker("worker-0", "test", max_load=5)
        await system.start()

        async def slow_task():
            await asyncio.sleep(10)  # Très long
            return "done"

        task = Task(
            task_id="slow-1",
            task_type="process",
            agent_type="test",
            func=slow_task,
            timeout=0.2,  # Timeout court
        )

        await system.submit_task(task)
        await asyncio.sleep(0.5)

        status = await system.get_task_status("slow-1")
        assert status["status"] == "failed"

        await system.stop()


# Performance benchmarks
@pytest.mark.slow
class TestPerformance:
    """Tests de performance"""

    @pytest.mark.asyncio
    async def test_high_throughput(self):
        """Test throughput avec beaucoup de tâches"""
        system = TaskQueueSystem(num_workers=4)

        # Register workers
        for i in range(4):
            await system.load_balancer.register_worker(f"worker-{i}", "test_agent", max_load=10)

        await system.start()

        async def quick_task(n):
            await asyncio.sleep(0.01)
            return n * 2

        # Submit 50 tasks
        start_time = time.time()
        task_ids = []

        for i in range(50):
            task = Task(
                task_id=f"task-{i}",
                task_type="compute",
                agent_type="test_agent",
                func=quick_task,
                args=(i,),
            )
            task_id = await system.submit_task(task)
            task_ids.append(task_id)

        # Wait for all to complete
        await asyncio.sleep(2)

        duration = time.time() - start_time

        # Check stats
        stats = await system.get_system_stats()
        completed = stats["total_tasks_completed"]

        assert completed >= 40, f"Expected at least 40 completed tasks, got {completed}"

        # Throughput should be > 20 tasks/s with 4 workers
        throughput = completed / duration
        assert throughput > 15, f"Throughput too low: {throughput:.1f} tasks/s"

        await system.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
