"""Tests complets pour optimized_agent_integration.py

Tests couvrant:
- OptimizedSystemConfig dataclass
- OptimizedAgentIntegration
- Tests d'intégration avec mocks
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.optimized_agent_integration import (
    OptimizedAgentIntegration,
    OptimizedSystemConfig,
)


# ============================================================================
# Tests OptimizedSystemConfig Dataclass
# ============================================================================
class TestOptimizedSystemConfig:
    """Tests pour la dataclass OptimizedSystemConfig."""

    def test_create_config_default(self):
        """Configuration par défaut."""
        config = OptimizedSystemConfig()

        # Task Queue
        assert config.num_workers == 4
        assert config.max_queue_size == 1000

        # Cache
        assert config.cache_max_size == 1000
        assert config.cache_max_memory_mb == 100.0
        assert config.cache_default_ttl == 3600.0
        assert config.enable_smart_cache is True

        # GPU
        assert config.enable_gpu_optimization is True

        # Performance
        assert config.enable_performance_monitoring is True
        assert config.task_timeout == 300.0
        assert config.max_retries == 3

    def test_create_config_custom(self):
        """Configuration personnalisée."""
        config = OptimizedSystemConfig(
            num_workers=8,
            max_queue_size=5000,
            cache_max_size=5000,
            cache_max_memory_mb=500.0,
            cache_default_ttl=7200.0,
            enable_smart_cache=False,
            enable_gpu_optimization=False,
            enable_performance_monitoring=False,
            task_timeout=600.0,
            max_retries=5,
        )

        assert config.num_workers == 8
        assert config.max_queue_size == 5000
        assert config.cache_max_size == 5000
        assert config.cache_max_memory_mb == 500.0
        assert config.enable_smart_cache is False
        assert config.enable_gpu_optimization is False
        assert config.max_retries == 5


# ============================================================================
# Tests OptimizedAgentIntegration - Création
# ============================================================================
class TestOptimizedAgentIntegrationBasic:
    """Tests basiques pour OptimizedAgentIntegration."""

    def test_create_integration_default(self):
        """Création avec configuration par défaut."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration()

            assert integration.config.num_workers == 4
            assert integration.is_initialized is False
            assert integration.gpu_optimizer is None
            assert integration.performance_metrics == {}

    def test_create_integration_custom(self):
        """Création avec configuration personnalisée."""
        config = OptimizedSystemConfig(num_workers=10, max_queue_size=2000)

        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration(config=config)

            assert integration.config.num_workers == 10
            assert integration.config.max_queue_size == 2000


# ============================================================================
# Tests OptimizedAgentIntegration - Initialisation mockée
# ============================================================================
class TestOptimizedAgentIntegrationInitialization:
    """Tests d'initialisation avec mocks."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Initialisation réussie."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.create_gpu_optimizer"
            ) as mock_gpu,
        ):
            # Setup mocks
            mock_task_queue = MagicMock()
            mock_task_queue.start = AsyncMock()
            mock_task_queue.load_balancer = MagicMock()
            mock_task_queue.load_balancer.register_worker = AsyncMock()
            mock_tqs.return_value = mock_task_queue

            mock_cache = MagicMock()
            mock_cm.return_value = mock_cache

            mock_optimizer = MagicMock()
            mock_optimizer.initialize = AsyncMock()
            mock_gpu.return_value = mock_optimizer

            integration = OptimizedAgentIntegration()
            integration.show_system_stats = AsyncMock()

            await integration.initialize()

            assert integration.is_initialized is True
            mock_task_queue.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_gpu(self):
        """Initialisation sans GPU."""
        config = OptimizedSystemConfig(enable_gpu_optimization=False)

        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_task_queue = MagicMock()
            mock_task_queue.start = AsyncMock()
            mock_task_queue.load_balancer = MagicMock()
            mock_task_queue.load_balancer.register_worker = AsyncMock()
            mock_tqs.return_value = mock_task_queue

            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration(config=config)
            integration.show_system_stats = AsyncMock()

            await integration.initialize()

            assert integration.is_initialized is True
            assert integration.gpu_optimizer is None


# ============================================================================
# Tests OptimizedAgentIntegration - Workers
# ============================================================================
class TestOptimizedAgentIntegrationWorkers:
    """Tests de gestion des workers."""

    @pytest.mark.asyncio
    async def test_register_workers(self):
        """Enregistrement des workers."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_task_queue = MagicMock()
            mock_task_queue.start = AsyncMock()
            mock_load_balancer = MagicMock()
            mock_load_balancer.register_worker = AsyncMock()
            mock_task_queue.load_balancer = mock_load_balancer
            mock_tqs.return_value = mock_task_queue

            mock_cm.return_value = MagicMock()

            config = OptimizedSystemConfig(enable_gpu_optimization=False)
            integration = OptimizedAgentIntegration(config=config)
            integration.show_system_stats = AsyncMock()

            await integration.initialize()

            # Vérifier que les workers ont été enregistrés pour chaque type d'agent
            # 4 types: data_analyst, ml_engineer, browser_automation, code_generator
            assert mock_load_balancer.register_worker.call_count == 4


# ============================================================================
# Tests OptimizedAgentIntegration - Cache
# ============================================================================
class TestOptimizedAgentIntegrationCache:
    """Tests du système de cache."""

    def test_cache_config(self):
        """Configuration du cache."""
        config = OptimizedSystemConfig(
            cache_max_size=2000, cache_max_memory_mb=200.0, cache_default_ttl=1800.0
        )

        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration(config=config)

            assert integration.config.cache_max_size == 2000
            assert integration.config.cache_max_memory_mb == 200.0
            assert integration.config.cache_default_ttl == 1800.0

    @pytest.mark.asyncio
    async def test_cache_warmup(self):
        """Warmup du cache."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_task_queue = MagicMock()
            mock_task_queue.start = AsyncMock()
            mock_task_queue.load_balancer = MagicMock()
            mock_task_queue.load_balancer.register_worker = AsyncMock()
            mock_tqs.return_value = mock_task_queue

            mock_cm.return_value = MagicMock()

            config = OptimizedSystemConfig(enable_gpu_optimization=False)
            integration = OptimizedAgentIntegration(config=config)
            integration.show_system_stats = AsyncMock()

            # _warmup_cache est appelé pendant initialize
            await integration.initialize()

            assert integration.is_initialized is True


# ============================================================================
# Tests OptimizedAgentIntegration - Performance Metrics
# ============================================================================
class TestOptimizedAgentIntegrationMetrics:
    """Tests des métriques de performance."""

    def test_empty_metrics(self):
        """Métriques vides au départ."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration()

            assert integration.performance_metrics == {}

    def test_store_metrics(self):
        """Stockage des métriques."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            integration = OptimizedAgentIntegration()

            integration.performance_metrics["task_latency_ms"] = 150.0
            integration.performance_metrics["cache_hit_rate"] = 0.85
            integration.performance_metrics["queue_size"] = 10

            assert integration.performance_metrics["task_latency_ms"] == 150.0
            assert integration.performance_metrics["cache_hit_rate"] == 0.85


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestOptimizedAgentIntegrationEdgeCases:
    """Tests des cas limites."""

    def test_config_min_values(self):
        """Configuration avec valeurs minimales."""
        config = OptimizedSystemConfig(
            num_workers=1,
            max_queue_size=1,
            cache_max_size=1,
            cache_max_memory_mb=1.0,
            task_timeout=1.0,
            max_retries=0,
        )

        assert config.num_workers == 1
        assert config.max_queue_size == 1
        assert config.max_retries == 0

    def test_config_high_values(self):
        """Configuration avec valeurs élevées."""
        config = OptimizedSystemConfig(
            num_workers=100,
            max_queue_size=100000,
            cache_max_size=100000,
            cache_max_memory_mb=10000.0,
            task_timeout=3600.0,
            max_retries=10,
        )

        assert config.num_workers == 100
        assert config.max_queue_size == 100000
        assert config.max_retries == 10

    def test_multiple_instances(self):
        """Plusieurs instances indépendantes."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_tqs.return_value = MagicMock()
            mock_cm.return_value = MagicMock()

            config1 = OptimizedSystemConfig(num_workers=2)
            config2 = OptimizedSystemConfig(num_workers=8)

            int1 = OptimizedAgentIntegration(config=config1)
            int2 = OptimizedAgentIntegration(config=config2)

            assert int1.config.num_workers != int2.config.num_workers

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Échec de l'initialisation."""
        with (
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.TaskQueueSystem"
            ) as mock_tqs,
            patch(
                "src.infrastructure.agents.advanced.optimized_agent_integration.CacheManager"
            ) as mock_cm,
        ):
            mock_task_queue = MagicMock()
            mock_task_queue.start = AsyncMock(side_effect=Exception("Start failed"))
            mock_task_queue.load_balancer = MagicMock()
            mock_task_queue.load_balancer.register_worker = AsyncMock()
            mock_tqs.return_value = mock_task_queue

            mock_cm.return_value = MagicMock()

            config = OptimizedSystemConfig(enable_gpu_optimization=False)
            integration = OptimizedAgentIntegration(config=config)

            with pytest.raises(Exception):
                await integration.initialize()

            assert integration.is_initialized is False
