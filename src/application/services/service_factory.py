"""Service factory for easy service access in CLI and other layers.

This module provides factory functions for creating service instances with
proper dependencies. It acts as a facade over the DI container.

Usage:
    >>> from src.application.services.service_factory import get_system_initialization_service
    >>> service = get_system_initialization_service()
    >>> await service.initialize_system(config)
"""

from src.application.services.interfaces import (
    IDirectoryManagerService,
    IHealthCheckService,
    ISystemInitializationService,
    ISystemVerificationService,
)
from src.application.services.system_initialization_service import SystemInitializationService
from src.core.system_state import SystemStateManager, get_system_state_manager
from src.infrastructure.services.directory_manager_service import DirectoryManagerService
from src.infrastructure.services.health_check_service import HealthCheckService
from src.infrastructure.services.system_verification_service import SystemVerificationService

# ============================================================================
# Service Factory Functions
# ============================================================================


def get_system_verification_service() -> ISystemVerificationService:
    """Get system verification service instance.

    Returns:
        System verification service

    Example:
        >>> service = get_system_verification_service()
        >>> result = await service.verify_docker()
    """
    return SystemVerificationService()


def get_directory_manager_service() -> IDirectoryManagerService:
    """Get directory manager service instance.

    Returns:
        Directory manager service

    Example:
        >>> service = get_directory_manager_service()
        >>> service.create_required_directories()
    """
    return DirectoryManagerService()


def get_health_check_service() -> IHealthCheckService:
    """Get health check service instance.

    Returns:
        Health check service

    Example:
        >>> service = get_health_check_service()
        >>> result = await service.check_system_health()
    """
    return HealthCheckService()


def get_system_initialization_service(
    state_manager: SystemStateManager | None = None,
) -> ISystemInitializationService:
    """Get system initialization service instance with all dependencies.

    Args:
        state_manager: Optional state manager (uses singleton if not provided)

    Returns:
        System initialization service

    Example:
        >>> service = get_system_initialization_service()
        >>> state = await service.initialize_system(config)
    """
    # Create dependencies
    verification_service = get_system_verification_service()
    directory_manager = get_directory_manager_service()
    state_mgr = state_manager or get_system_state_manager()

    # Create and return initialization service
    return SystemInitializationService(
        verification_service=verification_service,
        directory_manager=directory_manager,
        state_manager=state_mgr,
    )


# ============================================================================
# Convenience Functions
# ============================================================================


async def quick_verify_system() -> dict[str, bool]:
    """Quickly verify system requirements.

    Returns:
        Dictionary with verification results

    Example:
        >>> results = await quick_verify_system()
        >>> if results['docker']:
        ...     print("Docker available")
    """
    service = get_system_verification_service()

    # Verify essential components
    results = {
        "python": await service.verify_python_version(),
        "docker": await service.verify_docker(),
        "gpu": await service.verify_gpu(),
    }

    return results


async def quick_health_check() -> dict:
    """Perform a quick system health check.

    Returns:
        Health check results dictionary

    Example:
        >>> health = await quick_health_check()
        >>> print(f"Health score: {health['overall_health']}")
    """
    service = get_health_check_service()
    return await service.check_system_health()


__all__ = [
    "get_system_verification_service",
    "get_directory_manager_service",
    "get_health_check_service",
    "get_system_initialization_service",
    "quick_verify_system",
    "quick_health_check",
]
