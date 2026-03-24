"""Tests complets pour integrated_debug_system.py

Tests couvrant:
- IntegratedDebugSystem
- Tests d'intégration avec mocks
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.agent_integration import (
    AdvancedAgentIntegration,
)
from src.infrastructure.agents.advanced.integrated_debug_system import (
    IntegratedDebugSystem,
)


# ============================================================================
# Tests IntegratedDebugSystem - Création
# ============================================================================
class TestIntegratedDebugSystemBasic:
    """Tests basiques pour IntegratedDebugSystem."""

    def test_create_system(self):
        """Création du système de débogage."""
        mock_integration = MagicMock(spec=AdvancedAgentIntegration)
        system = IntegratedDebugSystem(mock_integration)

        assert system.agent_integration == mock_integration
        assert system.debugger is None
        assert system.agent_debug_integration is None
        assert system.is_debugging_active is False

    def test_default_config(self):
        """Configuration par défaut."""
        mock_integration = MagicMock(spec=AdvancedAgentIntegration)
        system = IntegratedDebugSystem(mock_integration)

        assert system.debug_config["enable_profiling"] is True
        assert system.debug_config["debug_level"] == "INFO"
        assert system.debug_config["max_log_entries"] == 10000
        assert system.debug_config["performance_sampling_interval"] == 1.0
        assert system.debug_config["health_check_interval"] == 30.0
        assert system.debug_config["memory_snapshot_interval"] == 60.0
        assert system.debug_config["enable_real_time_monitoring"] is True
        assert system.debug_config["auto_error_detection"] is True

    def test_anomaly_thresholds(self):
        """Seuils d'anomalies."""
        mock_integration = MagicMock(spec=AdvancedAgentIntegration)
        system = IntegratedDebugSystem(mock_integration)

        thresholds = system.debug_config["anomaly_thresholds"]
        assert thresholds["cpu_usage"] == 85.0
        assert thresholds["memory_usage"] == 85.0
        assert thresholds["gpu_usage"] == 95.0
        assert thresholds["response_time_ms"] == 5000.0
        assert thresholds["error_rate"] == 10.0


# ============================================================================
# Tests IntegratedDebugSystem - Initialisation mockée
# ============================================================================
class TestIntegratedDebugSystemInitialization:
    """Tests d'initialisation avec mocks."""

    @pytest.mark.asyncio
    async def test_initialize_debugging_mocked(self):
        """Initialisation avec tout mocké."""
        mock_integration = MagicMock(spec=AdvancedAgentIntegration)
        system = IntegratedDebugSystem(mock_integration)

        # Mock les composants
        with (
            patch(
                "src.infrastructure.agents.advanced.integrated_debug_system.create_advanced_debugger"
            ) as mock_create_debugger,
            patch(
                "src.infrastructure.agents.advanced.integrated_debug_system.enable_comprehensive_debugging"
            ) as mock_enable_debug,
        ):
            mock_debugger = MagicMock()
            mock_debugger.start_debugging = AsyncMock()
            mock_create_debugger.return_value = mock_debugger

            mock_debug_integration = MagicMock()
            mock_enable_debug.return_value = mock_debug_integration

            # Mock les méthodes internes
            system._integrate_with_multi_agent_system = AsyncMock()
            system._setup_automatic_monitoring = AsyncMock()
            system.show_debug_status = AsyncMock()

            await system.initialize_debugging()

            assert system.is_debugging_active is True
            assert system.debugger == mock_debugger
            mock_debugger.start_debugging.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_debugging_failure(self):
        """Échec de l'initialisation."""
        mock_integration = MagicMock(spec=AdvancedAgentIntegration)
        system = IntegratedDebugSystem(mock_integration)

        with patch(
            "src.infrastructure.agents.advanced.integrated_debug_system.create_advanced_debugger"
        ) as mock_create:
            mock_create.side_effect = Exception("Debugger creation failed")

            with pytest.raises(Exception, match="Debugger creation failed"):
                await system.initialize_debugging()

            assert system.is_debugging_active is False


# ============================================================================
# Tests IntegratedDebugSystem - Configuration
# ============================================================================
class TestIntegratedDebugSystemConfig:
    """Tests de configuration."""

    def test_modify_debug_level(self):
        """Modification du niveau de debug."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        system.debug_config["debug_level"] = "DEBUG"
        assert system.debug_config["debug_level"] == "DEBUG"

    def test_modify_thresholds(self):
        """Modification des seuils."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        system.debug_config["anomaly_thresholds"]["cpu_usage"] = 90.0
        assert system.debug_config["anomaly_thresholds"]["cpu_usage"] == 90.0

    def test_disable_features(self):
        """Désactivation de fonctionnalités."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        system.debug_config["enable_profiling"] = False
        system.debug_config["enable_real_time_monitoring"] = False
        system.debug_config["auto_error_detection"] = False

        assert system.debug_config["enable_profiling"] is False
        assert system.debug_config["enable_real_time_monitoring"] is False
        assert system.debug_config["auto_error_detection"] is False


# ============================================================================
# Tests IntegratedDebugSystem - Wrapping d'agents
# ============================================================================
class TestIntegratedDebugSystemWrapping:
    """Tests du wrapping des agents."""

    def test_wrap_agent_with_debugging_none(self):
        """Wrapping d'un agent None."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        # Ne devrait pas lever d'erreur
        system._wrap_agent_with_debugging(None, "test_agent")

    def test_wrap_agent_with_methods(self):
        """Wrapping d'un agent avec méthodes."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        # Créer un mock d'agent avec des méthodes
        mock_agent = MagicMock()
        mock_agent.process_request = AsyncMock()
        mock_agent.execute_task = AsyncMock()

        # Le wrapping devrait fonctionner sans erreur
        system._wrap_agent_with_debugging(mock_agent, "data_analyst")


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestIntegratedDebugSystemEdgeCases:
    """Tests des cas limites."""

    def test_multiple_system_instances(self):
        """Plusieurs instances indépendantes."""
        mock_int1 = MagicMock()
        mock_int2 = MagicMock()

        system1 = IntegratedDebugSystem(mock_int1)
        system2 = IntegratedDebugSystem(mock_int2)

        system1.debug_config["debug_level"] = "DEBUG"
        system2.debug_config["debug_level"] = "ERROR"

        assert system1.debug_config["debug_level"] == "DEBUG"
        assert system2.debug_config["debug_level"] == "ERROR"

    def test_config_interval_values(self):
        """Valeurs d'intervalles."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        # Vérifier que les intervalles sont raisonnables
        assert system.debug_config["performance_sampling_interval"] > 0
        assert system.debug_config["health_check_interval"] > 0
        assert system.debug_config["memory_snapshot_interval"] > 0

    def test_max_log_entries(self):
        """Limite des entrées de log."""
        mock_integration = MagicMock()
        system = IntegratedDebugSystem(mock_integration)

        assert system.debug_config["max_log_entries"] == 10000

        # Modifier la limite
        system.debug_config["max_log_entries"] = 50000
        assert system.debug_config["max_log_entries"] == 50000
