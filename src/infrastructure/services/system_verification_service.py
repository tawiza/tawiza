"""System verification service implementation.

This service is responsible for verifying system requirements like Python version,
Docker availability, GPU detection, etc.

Follows Single Responsibility Principle: Only handles verification logic.
"""
import asyncio
import sys
from typing import Any

from loguru import logger

from src.core.constants import (
    COMMAND_TIMEOUT_SHORT,
    MIN_PYTHON_VERSION,
)
from src.core.exceptions import (
    DockerNotAvailableError,
    GPUNotAvailableError,
    PythonVersionError,
    ROCmNotInstalledError,
)
from src.core.system_state import InitializationConfig


class SystemVerificationService:
    """Concrete implementation of system verification.

    This service checks system requirements without any side effects.
    Pure verification logic - no initialization or state changes.
    """

    async def verify_python_version(self) -> bool:
        """Verify Python version meets minimum requirements.

        Returns:
            True if Python version is adequate

        Raises:
            PythonVersionError: If Python version is too old
        """
        current_version = sys.version_info[:2]

        if current_version < MIN_PYTHON_VERSION:
            raise PythonVersionError(
                current_version=current_version,
                required_version=MIN_PYTHON_VERSION
            )

        logger.info(
            f"Python version verified: {current_version[0]}.{current_version[1]}"
        )
        return True

    async def verify_docker(self) -> bool:
        """Verify Docker is installed and running.

        Returns:
            True if Docker is available

        Raises:
            DockerNotAvailableError: If Docker is not available
        """
        try:
            # Use async subprocess
            proc = await asyncio.create_subprocess_exec(
                "docker", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SHORT
            )

            if proc.returncode != 0:
                raise DockerNotAvailableError(
                    f"Docker command failed: {stderr.decode()}"
                )

            version = stdout.decode().strip()
            logger.info(f"Docker verified: {version}")
            return True

        except FileNotFoundError:
            raise DockerNotAvailableError("Docker not installed")

        except TimeoutError:
            raise DockerNotAvailableError("Docker command timed out")

        except Exception as e:
            raise DockerNotAvailableError(f"Unexpected error: {e}")

    async def verify_gpu(self) -> bool:
        """Verify AMD GPU with ROCm is available.

        Returns:
            True if GPU is available and configured

        Raises:
            GPUNotAvailableError: If GPU is not available
            ROCmNotInstalledError: If ROCm is not installed
        """
        try:
            # Check ROCm installation
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showid",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SHORT
            )

            if proc.returncode != 0:
                raise GPUNotAvailableError(
                    f"ROCm command failed: {stderr.decode()}"
                )

            gpu_info = stdout.decode().strip()
            logger.info(f"GPU verified: {gpu_info}")
            return True

        except FileNotFoundError:
            raise ROCmNotInstalledError()

        except TimeoutError:
            raise GPUNotAvailableError("GPU detection timed out")

        except Exception as e:
            raise GPUNotAvailableError(f"Unexpected error: {e}")

    async def verify_all(
        self,
        config: InitializationConfig
    ) -> dict[str, bool]:
        """Verify all system requirements based on configuration.

        Args:
            config: Initialization configuration

        Returns:
            Dictionary with verification results:
            {
                "python": True/False,
                "docker": True/False,
                "gpu": True/False
            }
        """
        results = {}

        # Python is always required
        try:
            results["python"] = await self.verify_python_version()
        except PythonVersionError as e:
            logger.error(f"Python verification failed: {e}")
            results["python"] = False
            # Python failure is critical, re-raise
            raise

        # Docker is optional but recommended
        try:
            results["docker"] = await self.verify_docker()
        except DockerNotAvailableError as e:
            logger.warning(f"Docker verification failed: {e}")
            results["docker"] = False
            # Don't fail initialization if Docker is missing

        # GPU only if enabled in config
        if config.gpu_enabled:
            try:
                results["gpu"] = await self.verify_gpu()
            except (GPUNotAvailableError, ROCmNotInstalledError) as e:
                logger.warning(f"GPU verification failed: {e}")
                results["gpu"] = False
                # GPU failure is not critical, just disable GPU features
        else:
            results["gpu"] = False
            logger.info("GPU verification skipped (not enabled in config)")

        return results


class GPUDetectionService:
    """Service for detailed GPU detection and information."""

    async def detect_amd_gpu(self) -> bool:
        """Detect if AMD GPU with ROCm is available.

        Returns:
            True if AMD GPU detected
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showid",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SHORT
            )

            return proc.returncode == 0

        except (TimeoutError, FileNotFoundError):
            return False

    async def get_gpu_info(self) -> dict[str, Any]:
        """Get detailed GPU information.

        Returns:
            Dictionary with GPU details (model, memory, etc.)
        """
        if not await self.detect_amd_gpu():
            return {
                "available": False,
                "reason": "No AMD GPU detected or ROCm not installed"
            }

        try:
            # Get GPU info
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showproductname",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SHORT
            )

            gpu_name = stdout.decode().strip()

            # Get memory info
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi", "--showmeminfo", "vram",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=COMMAND_TIMEOUT_SHORT
            )

            memory_info = stdout.decode().strip()

            return {
                "available": True,
                "model": gpu_name,
                "memory": memory_info,
                "driver": "ROCm"
            }

        except Exception as e:
            logger.error(f"Failed to get GPU info: {e}")
            return {
                "available": True,
                "model": "Unknown AMD GPU",
                "error": str(e)
            }

    async def test_gpu_functionality(self) -> bool:
        """Test if GPU is functional (can run computations).

        Returns:
            True if GPU is functional
        """
        # This would require PyTorch/ROCm to be installed
        # For now, just check if GPU is detected
        return await self.detect_amd_gpu()
