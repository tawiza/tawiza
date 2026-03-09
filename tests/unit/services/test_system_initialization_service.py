"""Unit tests for SystemInitializationService.

Tests the SystemInitializationService orchestration with mocked dependencies.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.system_initialization_service import SystemInitializationService
from src.core.constants import APP_VERSION
from src.core.exceptions import (
    SystemAlreadyInitializedError,
    SystemInitializationError,
    SystemNotInitializedError,
)
from src.core.system_state import (
    InitializationConfig,
    SystemState,
    SystemStateManager,
)


@pytest.fixture
def mock_verification_service():
    """Create mock verification service."""
    service = AsyncMock()
    service.verify_all = AsyncMock(
        return_value={
            "python": True,
            "docker": True,
            "gpu": True,
        }
    )
    return service


@pytest.fixture
def mock_directory_manager():
    """Create mock directory manager."""
    manager = MagicMock()
    manager.create_required_directories = MagicMock()
    return manager


@pytest.fixture
def mock_state_manager():
    """Create mock state manager."""
    manager = MagicMock()
    manager.is_initialized = MagicMock(return_value=False)
    manager.update_state = MagicMock()
    manager.clear_state = MagicMock()
    manager.get_state_or_raise = MagicMock()
    return manager


@pytest.fixture
def initialization_service(mock_verification_service, mock_directory_manager, mock_state_manager):
    """Create SystemInitializationService with mocked dependencies."""
    return SystemInitializationService(
        verification_service=mock_verification_service,
        directory_manager=mock_directory_manager,
        state_manager=mock_state_manager,
    )


@pytest.fixture
def sample_config():
    """Create sample initialization configuration."""
    return InitializationConfig(
        gpu_enabled=True,
        monitoring_enabled=True,
        max_concurrent_tasks=5,
        auto_scale=True,
        retry_failed_tasks=3,
        verbose=False,
    )


class TestInitialization:
    """Tests for system initialization."""

    @pytest.mark.asyncio
    async def test_initialize_system_success(
        self,
        initialization_service,
        sample_config,
        mock_state_manager,
        mock_verification_service,
        mock_directory_manager,
    ):
        """Test successful system initialization."""
        # Execute initialization
        state = await initialization_service.initialize_system(sample_config)

        # Verify steps were executed
        mock_verification_service.verify_all.assert_called_once()
        mock_directory_manager.create_required_directories.assert_called_once()
        mock_state_manager.update_state.assert_called_once()

        # Verify returned state
        assert isinstance(state, SystemState)
        assert state.config == sample_config
        assert state.version == APP_VERSION
        assert isinstance(state.initialized_at, datetime)

    @pytest.mark.asyncio
    async def test_initialize_system_already_initialized_no_force(
        self, initialization_service, sample_config, mock_state_manager
    ):
        """Test initialization fails when already initialized without force."""
        # Mock already initialized
        mock_state_manager.is_initialized.return_value = True

        # Should raise error
        with pytest.raises(SystemAlreadyInitializedError):
            await initialization_service.initialize_system(sample_config, force=False)

    @pytest.mark.asyncio
    async def test_initialize_system_already_initialized_with_force(
        self, initialization_service, sample_config, mock_state_manager
    ):
        """Test re-initialization succeeds with force=True."""
        # Mock already initialized
        mock_state_manager.is_initialized.return_value = True

        # Should succeed with force=True
        state = await initialization_service.initialize_system(sample_config, force=True)

        assert isinstance(state, SystemState)
        mock_state_manager.update_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_system_verification_failure(
        self, initialization_service, sample_config, mock_verification_service
    ):
        """Test initialization handles verification failure."""
        # Mock verification failure
        mock_verification_service.verify_all.side_effect = Exception("Verification failed")

        # Should raise SystemInitializationError
        with pytest.raises(SystemInitializationError) as exc_info:
            await initialization_service.initialize_system(sample_config)

        assert "Verification failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initialize_system_directory_creation_failure(
        self, initialization_service, sample_config, mock_directory_manager
    ):
        """Test initialization handles directory creation failure."""
        # Mock directory creation failure
        mock_directory_manager.create_required_directories.side_effect = OSError(
            "Permission denied"
        )

        # Should raise SystemInitializationError
        with pytest.raises(SystemInitializationError) as exc_info:
            await initialization_service.initialize_system(sample_config)

        assert "Permission denied" in str(exc_info.value)


class TestConfigurationAdjustment:
    """Tests for configuration adjustment based on verification."""

    @pytest.mark.asyncio
    async def test_adjust_config_gpu_not_available(
        self, initialization_service, sample_config, mock_verification_service
    ):
        """Test config adjustment when GPU verification fails."""
        # Mock GPU verification failure
        mock_verification_service.verify_all.return_value = {
            "python": True,
            "docker": True,
            "gpu": False,  # GPU not available
        }

        # Initialize
        state = await initialization_service.initialize_system(sample_config)

        # GPU should be disabled in final config
        assert state.config.gpu_enabled is False

    @pytest.mark.asyncio
    async def test_adjust_config_gpu_already_disabled(
        self, initialization_service, mock_verification_service
    ):
        """Test config adjustment when GPU already disabled."""
        # Create config with GPU disabled
        config = InitializationConfig(
            gpu_enabled=False,
            monitoring_enabled=True,
            max_concurrent_tasks=5,
            auto_scale=True,
            retry_failed_tasks=3,
            verbose=False,
        )

        # Mock verification (GPU won't be checked)
        mock_verification_service.verify_all.return_value = {
            "python": True,
            "docker": True,
        }

        # Initialize
        state = await initialization_service.initialize_system(config)

        # GPU should remain disabled
        assert state.config.gpu_enabled is False


class TestShutdown:
    """Tests for system shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_system_success(self, initialization_service, mock_state_manager):
        """Test successful system shutdown."""
        # Mock initialized state
        mock_state = MagicMock()
        mock_state.monitoring = None
        mock_state.agents = None
        mock_state_manager.get_state_or_raise.return_value = mock_state

        # Execute shutdown
        await initialization_service.shutdown_system()

        # Verify state was cleared
        mock_state_manager.clear_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_system_not_initialized(
        self, initialization_service, mock_state_manager
    ):
        """Test shutdown fails when system not initialized."""
        # Mock not initialized
        mock_state_manager.get_state_or_raise.side_effect = SystemNotInitializedError()

        # Should raise error
        with pytest.raises(SystemNotInitializedError):
            await initialization_service.shutdown_system()

    @pytest.mark.asyncio
    async def test_shutdown_system_with_monitoring(
        self, initialization_service, mock_state_manager
    ):
        """Test shutdown with monitoring active."""
        # Mock state with monitoring
        mock_state = MagicMock()
        mock_monitoring = MagicMock()
        mock_state.monitoring = mock_monitoring
        mock_state.agents = None
        mock_state_manager.get_state_or_raise.return_value = mock_state

        # Execute shutdown
        await initialization_service.shutdown_system()

        # Verify shutdown was called
        mock_state_manager.clear_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_system_with_agents(self, initialization_service, mock_state_manager):
        """Test shutdown with agents active."""
        # Mock state with agents
        mock_state = MagicMock()
        mock_agents = MagicMock()
        mock_state.monitoring = None
        mock_state.agents = mock_agents
        mock_state_manager.get_state_or_raise.return_value = mock_state

        # Execute shutdown
        await initialization_service.shutdown_system()

        # Verify shutdown was called
        mock_state_manager.clear_state.assert_called_once()


class TestRestart:
    """Tests for system restart."""

    @pytest.mark.asyncio
    async def test_restart_system_with_config(
        self, initialization_service, sample_config, mock_state_manager
    ):
        """Test system restart with provided config."""
        # Mock initialized state
        mock_state = MagicMock()
        mock_state.monitoring = None
        mock_state.agents = None
        mock_state_manager.get_state_or_raise.return_value = mock_state

        # Execute restart
        new_state = await initialization_service.restart_system(sample_config)

        # Verify shutdown and re-initialization
        mock_state_manager.clear_state.assert_called_once()
        mock_state_manager.update_state.assert_called_once()
        assert isinstance(new_state, SystemState)

    @pytest.mark.asyncio
    async def test_restart_system_without_config(
        self, initialization_service, sample_config, mock_state_manager
    ):
        """Test system restart using existing config."""
        # Mock current state with config
        mock_current_state = MagicMock()
        mock_current_state.config = sample_config
        mock_state_manager.state = mock_current_state

        # Mock get_state_or_raise for shutdown
        mock_state = MagicMock()
        mock_state.monitoring = None
        mock_state.agents = None
        mock_state_manager.get_state_or_raise.return_value = mock_state

        # Execute restart without config (should use existing)
        new_state = await initialization_service.restart_system(None)

        # Verify restart succeeded
        assert isinstance(new_state, SystemState)
        assert new_state.config == sample_config

    @pytest.mark.asyncio
    async def test_restart_system_not_initialized(
        self, initialization_service, sample_config, mock_state_manager
    ):
        """Test restart when system not initialized."""
        # Mock not initialized
        mock_state_manager.get_state_or_raise.side_effect = SystemNotInitializedError()
        mock_state_manager.state = None

        # Should proceed with initialization
        new_state = await initialization_service.restart_system(sample_config)

        # Verify initialization succeeded
        assert isinstance(new_state, SystemState)

    @pytest.mark.asyncio
    async def test_restart_system_no_config_available(
        self, initialization_service, mock_state_manager
    ):
        """Test restart fails when no config available."""
        # Mock no config available
        mock_state_manager.state = None
        mock_state_manager.get_state_or_raise.side_effect = SystemNotInitializedError()

        # Should raise error
        with pytest.raises(SystemInitializationError) as exc_info:
            await initialization_service.restart_system(None)

        assert "No configuration available" in str(exc_info.value)


class TestPrivateHelpers:
    """Tests for private helper methods."""

    @pytest.mark.asyncio
    async def test_verify_requirements(
        self, initialization_service, sample_config, mock_verification_service
    ):
        """Test _verify_requirements helper."""
        # Call private method
        results = await initialization_service._verify_requirements(sample_config)

        # Verify service was called
        mock_verification_service.verify_all.assert_called_once_with(sample_config)
        assert isinstance(results, dict)

    def test_adjust_config_from_verification_gpu_failed(
        self, initialization_service, sample_config
    ):
        """Test _adjust_config_from_verification with GPU failure."""
        verification_results = {
            "python": True,
            "docker": True,
            "gpu": False,
        }

        # Adjust config
        adjusted_config = initialization_service._adjust_config_from_verification(
            sample_config, verification_results
        )

        assert adjusted_config.gpu_enabled is False

    def test_adjust_config_from_verification_all_passed(
        self, initialization_service, sample_config
    ):
        """Test _adjust_config_from_verification with all checks passing."""
        verification_results = {
            "python": True,
            "docker": True,
            "gpu": True,
        }

        # Adjust config
        adjusted_config = initialization_service._adjust_config_from_verification(
            sample_config, verification_results
        )

        assert adjusted_config.gpu_enabled is True

    def test_setup_directories(self, initialization_service, mock_directory_manager):
        """Test _setup_directories helper."""
        # Call private method
        initialization_service._setup_directories()

        # Verify directory manager was called
        mock_directory_manager.create_required_directories.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_agents(self, initialization_service, sample_config):
        """Test _initialize_agents helper."""
        # Call private method
        result = await initialization_service._initialize_agents(sample_config)

        # Currently returns None (not yet implemented)
        assert result is None

    @pytest.mark.asyncio
    async def test_setup_monitoring_enabled(self, initialization_service, sample_config):
        """Test _setup_monitoring with monitoring enabled."""
        # Call private method
        result = await initialization_service._setup_monitoring(sample_config)

        # Currently returns None (not yet implemented)
        assert result is None

    @pytest.mark.asyncio
    async def test_setup_monitoring_disabled(self, initialization_service):
        """Test _setup_monitoring with monitoring disabled."""
        config = InitializationConfig(
            gpu_enabled=True,
            monitoring_enabled=False,  # Disabled
            max_concurrent_tasks=5,
            auto_scale=True,
            retry_failed_tasks=3,
            verbose=False,
        )

        # Call private method
        result = await initialization_service._setup_monitoring(config)

        # Should return None (monitoring disabled)
        assert result is None

    @pytest.mark.asyncio
    async def test_save_configuration(self, initialization_service, sample_config, tmp_path):
        """Test _save_configuration helper."""
        # Mock SYSTEM_CONFIG_FILE to use temp directory
        with patch(
            "src.application.services.system_initialization_service.SYSTEM_CONFIG_FILE",
            str(tmp_path / "config.json"),
        ):
            # Call private method
            await initialization_service._save_configuration(sample_config)

            # Verify file was created
            config_file = tmp_path / "config.json"
            assert config_file.exists()

            # Verify contents
            import json

            with open(config_file) as f:
                saved_config = json.load(f)

            assert saved_config["version"] == APP_VERSION
            assert saved_config["gpu_enabled"] == sample_config.gpu_enabled
            assert saved_config["monitoring_enabled"] == sample_config.monitoring_enabled


class TestErrorScenarios:
    """Tests for various error scenarios."""

    @pytest.mark.asyncio
    async def test_initialization_partial_failure(
        self, initialization_service, sample_config, mock_verification_service
    ):
        """Test initialization continues despite non-critical failures."""
        # Mock verification with some failures
        mock_verification_service.verify_all.return_value = {
            "python": True,
            "docker": False,  # Docker failed (non-critical)
            "gpu": False,  # GPU failed (non-critical)
        }

        # Should still succeed
        state = await initialization_service.initialize_system(sample_config)

        assert isinstance(state, SystemState)
        # GPU should be disabled
        assert state.config.gpu_enabled is False

    @pytest.mark.asyncio
    async def test_initialization_save_config_failure(self, initialization_service, sample_config):
        """Test initialization handles config save failure."""

        # Mock save_configuration to fail
        async def mock_save_fail(config):
            raise OSError("Disk full")

        with patch.object(
            initialization_service, "_save_configuration", side_effect=mock_save_fail
        ):
            # Should raise SystemInitializationError
            with pytest.raises(SystemInitializationError) as exc_info:
                await initialization_service.initialize_system(sample_config)

            assert "Disk full" in str(exc_info.value)


class TestIntegration:
    """Integration-style tests with minimal mocking."""

    @pytest.mark.asyncio
    async def test_full_initialization_lifecycle(
        self, mock_verification_service, mock_directory_manager, sample_config, tmp_path
    ):
        """Test complete initialization lifecycle."""
        # Create real state manager
        state_manager = SystemStateManager()
        state_manager._state = None  # Reset

        # Create service with real state manager
        service = SystemInitializationService(
            verification_service=mock_verification_service,
            directory_manager=mock_directory_manager,
            state_manager=state_manager,
        )

        # Mock config file location
        with patch(
            "src.application.services.system_initialization_service.SYSTEM_CONFIG_FILE",
            str(tmp_path / "config.json"),
        ):
            # Initialize
            state = await service.initialize_system(sample_config)

            # Verify state manager was updated
            assert state_manager.is_initialized()
            assert state_manager.state.config == sample_config

            # Shutdown
            await service.shutdown_system()

            # Verify state was cleared
            assert not state_manager.is_initialized()
