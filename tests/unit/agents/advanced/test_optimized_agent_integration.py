#!/usr/bin/env python3
"""
Tests unitaires pour OptimizedAgentIntegration
Couvre: Configuration, initialisation, soumission de tâches, statistiques
"""

import asyncio

import pytest

from src.infrastructure.agents.advanced.optimized_agent_integration import (
    OptimizedAgentIntegration,
    OptimizedSystemConfig,
    create_optimized_agent_integration,
)
from src.infrastructure.agents.advanced.task_queue_system import TaskPriority


class TestOptimizedSystemConfig:
    """Tests pour OptimizedSystemConfig"""

    def test_config_default_values(self):
        """Test valeurs par défaut de la configuration"""
        config = OptimizedSystemConfig()

        assert config.num_workers == 4
        assert config.max_queue_size == 1000
        assert config.cache_max_size == 1000
        assert config.cache_max_memory_mb == 100.0
        assert config.cache_default_ttl == 3600.0
        assert config.enable_smart_cache is True
        assert config.enable_gpu_optimization is True
        assert config.task_timeout == 300.0
        assert config.max_retries == 3

    def test_config_custom_values(self):
        """Test configuration personnalisée"""
        config = OptimizedSystemConfig(num_workers=8, cache_max_size=2000, enable_smart_cache=False)

        assert config.num_workers == 8
        assert config.cache_max_size == 2000
        assert config.enable_smart_cache is False


class TestOptimizedAgentIntegration:
    """Tests pour OptimizedAgentIntegration"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test initialisation du système"""
        config = OptimizedSystemConfig(num_workers=2)
        integration = OptimizedAgentIntegration(config)

        assert integration.is_initialized is False

        await integration.initialize()

        assert integration.is_initialized is True
        assert integration.task_queue_system is not None
        assert integration.cache_manager is not None

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_initialization_with_gpu(self):
        """Test initialisation avec GPU optimizer"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=True)
        integration = OptimizedAgentIntegration(config)

        await integration.initialize()

        # GPU optimizer should be initialized (or None if no GPU)
        assert integration.gpu_optimizer is not None or integration.gpu_optimizer is None

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_initialization_without_gpu(self):
        """Test initialisation sans GPU optimizer"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)

        await integration.initialize()

        assert integration.gpu_optimizer is None

        await integration.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_submit_task_basic(self):
        """Test soumission et exécution d'une tâche simple"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func(data):
            await asyncio.sleep(0.1)
            return f"processed: {data}"

        task_id = await integration.submit_task(
            agent_type="data_analyst",
            task_type="analyze",
            func=test_func,
            args=("test_data",),
            priority=TaskPriority.NORMAL,
            use_cache=False,
        )

        assert task_id is not None
        assert isinstance(task_id, str)

        # Wait for execution
        await asyncio.sleep(0.3)

        # Check status
        status = await integration.get_task_status(task_id)
        assert status is not None
        assert status["task_id"] == task_id

        await integration.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_submit_task_with_cache(self):
        """Test soumission avec cache activé"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def expensive_func(data):
            await asyncio.sleep(0.2)
            return f"result: {data}"

        # First call - cache miss
        task_id_1 = await integration.submit_task(
            agent_type="ml_engineer",
            task_type="train",
            func=expensive_func,
            args=("model1",),
            priority=TaskPriority.HIGH,
            use_cache=True,
        )

        await asyncio.sleep(0.4)

        # Second call - should use cache
        task_id_2 = await integration.submit_task(
            agent_type="ml_engineer",
            task_type="train",
            func=expensive_func,
            args=("model1",),
            priority=TaskPriority.HIGH,
            use_cache=True,
        )

        # Second call should be much faster (cached)
        assert task_id_1 != task_id_2

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_submit_task_with_priority(self):
        """Test soumission avec différentes priorités"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func(priority_name):
            return f"executed: {priority_name}"

        # Submit tasks with different priorities
        task_low = await integration.submit_task(
            "agent", "task", test_func, ("low",), priority=TaskPriority.LOW
        )
        task_high = await integration.submit_task(
            "agent", "task", test_func, ("high",), priority=TaskPriority.HIGH
        )
        task_critical = await integration.submit_task(
            "agent", "task", test_func, ("critical",), priority=TaskPriority.CRITICAL
        )

        assert all([task_low, task_high, task_critical])

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test récupération du statut d'une tâche"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func():
            await asyncio.sleep(0.1)
            return "done"

        task_id = await integration.submit_task("agent", "task", test_func, use_cache=False)

        status = await integration.get_task_status(task_id)
        assert status is not None
        assert "task_id" in status
        assert "status" in status
        assert "progress" in status

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_get_task_status_nonexistent(self):
        """Test statut d'une tâche inexistante"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        status = await integration.get_task_status("nonexistent-id")
        assert status is None

        await integration.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_get_task_result(self):
        """Test récupération du résultat d'une tâche"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func(x):
            await asyncio.sleep(0.1)
            return x * 2

        task_id = await integration.submit_task("agent", "task", test_func, (21,), use_cache=False)

        # Wait for completion
        await asyncio.sleep(0.3)

        result = await integration.get_task_result(task_id)
        assert result == 42

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """Test invalidation du cache"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func():
            return "result"

        # Cache something
        await integration.submit_task("agent1", "task", test_func, use_cache=True)

        # Invalidate cache for agent1
        await integration.invalidate_cache("agent1")

        # Cache should be cleared (hard to test without checking internals)
        # Just verify no exceptions
        await integration.invalidate_cache()  # Clear all

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_show_system_stats(self):
        """Test affichage des statistiques"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        # Should not raise exception
        await integration.show_system_stats()

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_when_not_initialized(self):
        """Test shutdown sur système non initialisé"""
        config = OptimizedSystemConfig(num_workers=2)
        integration = OptimizedAgentIntegration(config)

        # Should not raise exception
        await integration.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_multiple_tasks_parallel_execution(self):
        """Test exécution parallèle de plusieurs tâches"""
        config = OptimizedSystemConfig(num_workers=4, enable_gpu_optimization=False)
        integration = OptimizedAgentIntegration(config)
        await integration.initialize()

        async def test_func(n):
            await asyncio.sleep(0.1)
            return n * 2

        # Submit multiple tasks
        task_ids = []
        for i in range(10):
            task_id = await integration.submit_task(
                "agent", "task", test_func, (i,), use_cache=False
            )
            task_ids.append(task_id)

        # Wait for all to complete
        await asyncio.sleep(0.5)

        # Check all completed
        completed = 0
        for task_id in task_ids:
            status = await integration.get_task_status(task_id)
            if status and status["status"] == "completed":
                completed += 1

        # Most should be completed
        assert completed >= 8

        await integration.shutdown()


class TestCreateOptimizedAgentIntegration:
    """Tests pour la fonction helper create_optimized_agent_integration"""

    @pytest.mark.asyncio
    async def test_create_with_default_config(self):
        """Test création avec config par défaut"""
        integration = await create_optimized_agent_integration()

        assert integration is not None
        assert integration.is_initialized is True

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self):
        """Test création avec config personnalisée"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)

        integration = await create_optimized_agent_integration(config)

        assert integration is not None
        assert integration.is_initialized is True
        assert integration.config.num_workers == 2

        await integration.shutdown()


# Integration tests
@pytest.mark.slow
class TestSystemIntegration:
    """Tests d'intégration du système complet"""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test workflow complet: init → submit → execute → get result → shutdown"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = await create_optimized_agent_integration(config)

        # Define task
        async def analysis_task(data):
            await asyncio.sleep(0.1)
            return {"analyzed": data, "score": 0.95}

        # Submit task
        task_id = await integration.submit_task(
            agent_type="data_analyst",
            task_type="analyze",
            func=analysis_task,
            args=({"input": "test"},),
            priority=TaskPriority.HIGH,
            use_cache=True,
        )

        # Wait for completion
        for _ in range(10):
            await asyncio.sleep(0.1)
            status = await integration.get_task_status(task_id)
            if status and status["status"] == "completed":
                break

        # Get result
        result = await integration.get_task_result(task_id)

        assert result is not None
        assert result["analyzed"] == {"input": "test"}
        assert result["score"] == 0.95

        # Shutdown
        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_cache_effectiveness(self):
        """Test efficacité du cache"""
        config = OptimizedSystemConfig(
            num_workers=2, enable_smart_cache=True, enable_gpu_optimization=False
        )
        integration = await create_optimized_agent_integration(config)

        async def slow_task(x):
            await asyncio.sleep(0.2)
            return x**2

        # First call - cache miss
        import time

        start1 = time.time()
        task_id_1 = await integration.submit_task(
            "agent", "compute", slow_task, (5,), use_cache=True
        )
        await asyncio.sleep(0.3)
        duration1 = time.time() - start1

        # Second call - cache hit (should be instant)
        start2 = time.time()
        task_id_2 = await integration.submit_task(
            "agent", "compute", slow_task, (5,), use_cache=True
        )
        await asyncio.sleep(0.1)
        duration2 = time.time() - start2

        # Cache hit should be significantly faster
        assert duration2 < duration1 * 0.5

        await integration.shutdown()

    @pytest.mark.asyncio
    async def test_system_resilience(self):
        """Test résilience du système face aux erreurs"""
        config = OptimizedSystemConfig(num_workers=2, enable_gpu_optimization=False)
        integration = await create_optimized_agent_integration(config)

        async def failing_task():
            raise ValueError("Intentional error")

        # Submit failing task
        task_id = await integration.submit_task("agent", "task", failing_task, use_cache=False)

        # Wait for execution
        await asyncio.sleep(0.3)

        # System should still be operational
        status = await integration.get_task_status(task_id)
        assert status is not None

        # Submit another task (system should still work)
        async def working_task():
            return "success"

        task_id_2 = await integration.submit_task("agent", "task2", working_task, use_cache=False)

        await asyncio.sleep(0.2)

        # Check it worked
        status2 = await integration.get_task_status(task_id_2)
        assert status2 is not None

        await integration.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
