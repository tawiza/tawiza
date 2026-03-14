"""System initialization service.

This service orchestrates the complete system initialization process by
coordinating multiple smaller services.

Follows:
- Single Responsibility Principle: Only handles orchestration
- Dependency Inversion Principle: Depends on interfaces, not concrete classes
- Open/Closed Principle: Extensible without modification
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.application.services.interfaces import (
    IDirectoryManagerService,
    ISystemVerificationService,
)
from src.core.constants import (
    APP_VERSION,
    DIRS_TO_CREATE,
    SYSTEM_CONFIG_FILE,
)
from src.core.exceptions import (
    SystemAlreadyInitializedError,
    SystemInitializationError,
    SystemNotInitializedError,
)
from src.core.system_state import (
    InitializationConfig,
    SystemState,
    SystemStateManager,
    get_system_state_manager,
)


class SystemInitializationService:
    """Orchestrates system initialization.

    This service coordinates multiple services to initialize the system:
    1. Verify system requirements
    2. Create directories
    3. Initialize agents
    4. Setup monitoring
    5. Save configuration

    All dependencies are injected, following Dependency Inversion Principle.
    """

    def __init__(
        self,
        verification_service: ISystemVerificationService,
        directory_manager: IDirectoryManagerService,
        state_manager: SystemStateManager | None = None,
    ):
        """Initialize with injected dependencies.

        Args:
            verification_service: Service for system verification
            directory_manager: Service for directory management
            state_manager: System state manager (optional, uses singleton if not provided)
        """
        self._verification_service = verification_service
        self._directory_manager = directory_manager
        self._state_manager = state_manager or get_system_state_manager()

        logger.info("SystemInitializationService created")

    async def initialize_system(
        self, config: InitializationConfig, force: bool = False
    ) -> SystemState:
        """Initialize the complete system.

        Args:
            config: Initialization configuration
            force: Force re-initialization if already initialized

        Returns:
            New system state

        Raises:
            SystemAlreadyInitializedError: If already initialized and force=False
            SystemInitializationError: If initialization fails
        """
        logger.info("Starting system initialization...")

        # Check if already initialized
        if self._state_manager.is_initialized() and not force:
            raise SystemAlreadyInitializedError()

        try:
            # Step 1: Verify system requirements
            logger.info("Step 1/5: Verifying system requirements...")
            verification_results = await self._verify_requirements(config)

            # Adjust config based on verification results
            config = self._adjust_config_from_verification(config, verification_results)

            # Step 2: Setup directory structure
            logger.info("Step 2/5: Creating directory structure...")
            self._setup_directories()

            # Step 3: Initialize agents (if available)
            logger.info("Step 3/5: Initializing agents...")
            agents = await self._initialize_agents(config)

            # Step 4: Setup monitoring (if enabled)
            logger.info("Step 4/5: Setting up monitoring...")
            monitoring = await self._setup_monitoring(config)

            # Step 5: Save configuration
            logger.info("Step 5/5: Saving configuration...")
            await self._save_configuration(config)

            # Create new system state
            state = SystemState(
                agents=agents,
                monitoring=monitoring,
                config=config,
                initialized_at=datetime.utcnow(),
                version=APP_VERSION,
            )

            # Update state manager
            self._state_manager.update_state(state)

            logger.info("System initialization complete!")
            return state

        except Exception as e:
            logger.error(f"System initialization failed: {e}", exc_info=True)
            raise SystemInitializationError(f"Initialization failed: {e}") from e

    async def shutdown_system(self) -> None:
        """Shutdown the system gracefully.

        Raises:
            SystemNotInitializedError: If system not initialized
        """
        state = self._state_manager.get_state_or_raise()

        logger.info("Shutting down system...")

        try:
            # Shutdown monitoring if active
            if state.monitoring is not None:
                logger.info("Stopping monitoring...")
                # Monitoring shutdown logic would go here
                # await state.monitoring.stop()

            # Shutdown agents if active
            if state.agents is not None:
                logger.info("Stopping agents...")
                # Agent shutdown logic would go here
                # await state.agents.shutdown()

            # Clear state
            self._state_manager.clear_state()

            logger.info("System shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            raise

    async def restart_system(self, config: InitializationConfig | None = None) -> SystemState:
        """Restart the system.

        Args:
            config: Optional new configuration (uses existing if not provided)

        Returns:
            New system state after restart
        """
        logger.info("Restarting system...")

        # Get current config if not provided
        if config is None:
            current_state = self._state_manager.state
            if current_state and current_state.config:
                config = current_state.config
            else:
                raise SystemInitializationError("No configuration available for restart")

        # Shutdown current system
        try:
            await self.shutdown_system()
        except SystemNotInitializedError:
            # System not initialized, just initialize
            pass

        # Re-initialize
        return await self.initialize_system(config, force=True)

    # ========================================================================
    # Private helper methods (each follows SRP)
    # ========================================================================

    async def _verify_requirements(self, config: InitializationConfig) -> dict[str, bool]:
        """Verify all system requirements.

        Args:
            config: Initialization configuration

        Returns:
            Dictionary with verification results
        """
        return await self._verification_service.verify_all(config)

    def _adjust_config_from_verification(
        self, config: InitializationConfig, verification_results: dict[str, bool]
    ) -> InitializationConfig:
        """Adjust configuration based on verification results.

        Args:
            config: Original configuration
            verification_results: Results from verification

        Returns:
            Adjusted configuration
        """
        # If GPU verification failed, disable GPU in config
        if not verification_results.get("gpu", False):
            logger.warning("GPU not available, disabling GPU features")
            # Create new config with GPU disabled
            from dataclasses import replace

            config = replace(config, gpu_enabled=False)

        return config

    def _setup_directories(self) -> None:
        """Setup directory structure.

        Raises:
            OSError: If directory creation fails
        """
        self._directory_manager.create_required_directories(DIRS_TO_CREATE)
        logger.info(f"Created {len(DIRS_TO_CREATE)} directories")

    async def _initialize_agents(self, config: InitializationConfig) -> Any | None:
        """Initialize agent system.

        Args:
            config: Initialization configuration

        Returns:
            Agent integration instance or None
        """
        try:
            # This would use an AgentFactory or AgentManagementService
            # For now, return None (Phase 3 will implement this)
            logger.info("Agent initialization skipped (not yet implemented)")
            return None

        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            # Don't fail entire initialization if agents fail
            return None

    async def _setup_monitoring(self, config: InitializationConfig) -> Any | None:
        """Setup monitoring system.

        Args:
            config: Initialization configuration

        Returns:
            Monitoring system instance or None
        """
        if not config.monitoring_enabled:
            logger.info("Monitoring disabled in configuration")
            return None

        try:
            # This would use a MonitoringService
            # For now, return None (Phase 3 will implement this)
            logger.info("Monitoring setup skipped (not yet implemented)")
            return None

        except Exception as e:
            logger.error(f"Failed to setup monitoring: {e}")
            # Don't fail entire initialization if monitoring fails
            return None

    async def _save_configuration(self, config: InitializationConfig) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save

        Raises:
            OSError: If save fails
        """
        config_path = Path(SYSTEM_CONFIG_FILE)

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            "version": APP_VERSION,
            "initialized_at": datetime.utcnow().isoformat(),
            "gpu_enabled": config.gpu_enabled,
            "monitoring_enabled": config.monitoring_enabled,
            "config": {
                "max_concurrent_tasks": config.max_concurrent_tasks,
                "auto_scale": config.auto_scale,
                "retry_failed_tasks": config.retry_failed_tasks,
            },
        }

        try:
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

            logger.info(f"Configuration saved to {config_path}")

        except OSError as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
