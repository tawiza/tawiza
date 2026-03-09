"""Tests complets pour gpu_optimizer.py

Tests couvrant:
- GPUMetrics et OptimizationResult dataclasses
- GPUOptimizer initialization et status
- Tests conditionnels pour GPU AMD (auto-détection)
"""

import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.gpu_optimizer import (
    GPUMetrics,
    GPUOptimizer,
    OptimizationResult,
)


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def gpu_available():
    """Détecte si un GPU AMD est disponible."""
    try:
        result = subprocess.run(["rocm-smi", "--showid"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def mock_gpu_metrics():
    """Métriques GPU mockées."""
    return GPUMetrics(
        utilization_percent=75.0,
        memory_used_mb=18432.0,
        memory_total_mb=24576.0,
        temperature_celsius=65.0,
        power_usage_watts=280.0,
        clock_speed_mhz=2400,
        memory_clock_mhz=2500,
        pcie_bandwidth_gb_s=32.0,
    )


# ============================================================================
# Tests GPUMetrics Dataclass
# ============================================================================
class TestGPUMetrics:
    """Tests pour la dataclass GPUMetrics."""

    def test_create_metrics(self, mock_gpu_metrics):
        """Création de métriques GPU."""
        metrics = mock_gpu_metrics
        assert metrics.utilization_percent == 75.0
        assert metrics.memory_used_mb == 18432.0
        assert metrics.memory_total_mb == 24576.0
        assert metrics.temperature_celsius == 65.0
        assert metrics.power_usage_watts == 280.0
        assert metrics.clock_speed_mhz == 2400
        assert metrics.memory_clock_mhz == 2500
        assert metrics.pcie_bandwidth_gb_s == 32.0

    def test_memory_percentage(self, mock_gpu_metrics):
        """Calcul du pourcentage mémoire utilisée."""
        metrics = mock_gpu_metrics
        memory_pct = (metrics.memory_used_mb / metrics.memory_total_mb) * 100
        assert memory_pct == 75.0

    def test_metrics_default_values(self):
        """Valeurs par défaut des métriques."""
        metrics = GPUMetrics(
            utilization_percent=0,
            memory_used_mb=0,
            memory_total_mb=1024,
            temperature_celsius=30,
            power_usage_watts=10,
            clock_speed_mhz=1000,
            memory_clock_mhz=1000,
            pcie_bandwidth_gb_s=8.0,
        )
        assert metrics.utilization_percent == 0


# ============================================================================
# Tests OptimizationResult Dataclass
# ============================================================================
class TestOptimizationResult:
    """Tests pour la dataclass OptimizationResult."""

    def test_create_optimization_result(self, mock_gpu_metrics):
        """Création d'un résultat d'optimisation."""
        result = OptimizationResult(
            original_performance=10.0,
            optimized_performance=50.0,
            improvement_percentage=400.0,
            gpu_metrics_before=mock_gpu_metrics,
            gpu_metrics_after=mock_gpu_metrics,
            optimizations_applied=["memory", "batching", "kernel"],
            timestamp=1234567890.0,
        )
        assert result.original_performance == 10.0
        assert result.optimized_performance == 50.0
        assert result.improvement_percentage == 400.0
        assert len(result.optimizations_applied) == 3

    def test_improvement_calculation(self, mock_gpu_metrics):
        """Vérification du calcul d'amélioration."""
        original = 20.0
        optimized = 50.0
        improvement = ((optimized - original) / original) * 100

        result = OptimizationResult(
            original_performance=original,
            optimized_performance=optimized,
            improvement_percentage=improvement,
            gpu_metrics_before=mock_gpu_metrics,
            gpu_metrics_after=mock_gpu_metrics,
            optimizations_applied=[],
            timestamp=0,
        )
        assert result.improvement_percentage == 150.0


# ============================================================================
# Tests GPUOptimizer - Création et Statut
# ============================================================================
class TestGPUOptimizerBasic:
    """Tests basiques pour GPUOptimizer."""

    def test_create_optimizer(self):
        """Création de l'optimiseur."""
        optimizer = GPUOptimizer()
        assert optimizer.is_initialized is False
        assert optimizer.gpu_info == {}
        assert optimizer.optimization_history == []

    def test_get_gpu_status_not_initialized(self):
        """Statut GPU avant initialisation."""
        optimizer = GPUOptimizer()
        status = optimizer.get_gpu_status()

        assert status["gpu_available"] is False
        assert status["is_initialized"] is False
        assert status["gpu_info"] == {}
        assert status["optimization_count"] == 0
        assert status["last_optimization"] is None

    def test_get_gpu_status_with_history(self, mock_gpu_metrics):
        """Statut GPU avec historique d'optimisations."""
        optimizer = GPUOptimizer()
        optimizer.gpu_info = {"device_id": "test"}

        # Ajouter une optimisation à l'historique
        result = OptimizationResult(
            original_performance=10.0,
            optimized_performance=50.0,
            improvement_percentage=400.0,
            gpu_metrics_before=mock_gpu_metrics,
            gpu_metrics_after=mock_gpu_metrics,
            optimizations_applied=["test"],
            timestamp=1234567890.0,
        )
        optimizer.optimization_history.append(result)

        status = optimizer.get_gpu_status()
        assert status["gpu_available"] is True
        assert status["optimization_count"] == 1
        assert status["last_optimization"] is not None
        assert status["last_optimization"]["improvement_percentage"] == 400.0


# ============================================================================
# Tests GPUOptimizer - Initialisation (avec mocks)
# ============================================================================
class TestGPUOptimizerInitialization:
    """Tests d'initialisation de GPUOptimizer."""

    @pytest.mark.asyncio
    async def test_initialize_success_mocked(self):
        """Initialisation réussie avec GPU mocké."""
        optimizer = GPUOptimizer()

        # Mock les méthodes internes
        optimizer._detect_amd_gpu = AsyncMock(return_value={"device_id": "mock_gpu"})
        optimizer._optimize_system_settings = AsyncMock()
        optimizer._configure_rocm = AsyncMock()

        await optimizer.initialize()

        assert optimizer.is_initialized is True
        assert optimizer.gpu_info["device_id"] == "mock_gpu"
        optimizer._detect_amd_gpu.assert_called_once()
        optimizer._optimize_system_settings.assert_called_once()
        optimizer._configure_rocm.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Initialisation échouée lève une erreur."""
        optimizer = GPUOptimizer()
        optimizer._detect_amd_gpu = AsyncMock(side_effect=Exception("GPU not found"))

        with pytest.raises(Exception, match="GPU not found"):
            await optimizer.initialize()

        assert optimizer.is_initialized is False


# ============================================================================
# Tests conditionnels - GPU réel (si disponible)
# ============================================================================
class TestGPUOptimizerConditional:
    """Tests conditionnels exécutés seulement si GPU disponible."""

    @pytest.mark.asyncio
    async def test_initialize_with_real_gpu(self, gpu_available):
        """Test avec GPU réel si disponible."""
        if not gpu_available:
            pytest.skip("GPU AMD non disponible")

        optimizer = GPUOptimizer()
        await optimizer.initialize()

        assert optimizer.is_initialized is True
        assert "device_id" in optimizer.gpu_info

    @pytest.mark.asyncio
    async def test_real_gpu_status(self, gpu_available):
        """Vérifie le statut avec un vrai GPU."""
        if not gpu_available:
            pytest.skip("GPU AMD non disponible")

        optimizer = GPUOptimizer()
        await optimizer.initialize()

        status = optimizer.get_gpu_status()
        assert status["gpu_available"] is True
        assert status["is_initialized"] is True


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestGPUOptimizerEdgeCases:
    """Tests des cas limites."""

    def test_multiple_optimizations_history(self, mock_gpu_metrics):
        """Historique avec plusieurs optimisations."""
        optimizer = GPUOptimizer()

        for i in range(5):
            result = OptimizationResult(
                original_performance=10.0 + i,
                optimized_performance=50.0 + i,
                improvement_percentage=400.0 - i * 10,
                gpu_metrics_before=mock_gpu_metrics,
                gpu_metrics_after=mock_gpu_metrics,
                optimizations_applied=[f"opt_{i}"],
                timestamp=1234567890.0 + i,
            )
            optimizer.optimization_history.append(result)

        status = optimizer.get_gpu_status()
        assert status["optimization_count"] == 5
        # last_optimization devrait être la dernière
        assert status["last_optimization"]["improvement_percentage"] == 360.0

    def test_empty_gpu_info_is_not_available(self):
        """GPU info vide = pas disponible."""
        optimizer = GPUOptimizer()
        optimizer.gpu_info = {}

        status = optimizer.get_gpu_status()
        assert status["gpu_available"] is False

    def test_partial_gpu_info_is_available(self):
        """GPU info partielle = disponible."""
        optimizer = GPUOptimizer()
        optimizer.gpu_info = {"device_id": "partial"}

        status = optimizer.get_gpu_status()
        assert status["gpu_available"] is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent_after_success(self):
        """Re-initialiser après succès ne pose pas de problème."""
        optimizer = GPUOptimizer()
        optimizer._detect_amd_gpu = AsyncMock(return_value={"device_id": "gpu"})
        optimizer._optimize_system_settings = AsyncMock()
        optimizer._configure_rocm = AsyncMock()

        await optimizer.initialize()
        await optimizer.initialize()  # Second call

        assert optimizer.is_initialized is True
        # _detect_amd_gpu appelé 2 fois
        assert optimizer._detect_amd_gpu.call_count == 2
