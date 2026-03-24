"""Health check service implementation.

This service performs comprehensive system health checks including CPU, memory,
disk, and external services.

Follows Single Responsibility Principle: Only handles health checking logic.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import psutil

from src.core.constants import (
    COMMAND_TIMEOUT_SHORT,
    CPU_CRITICAL_THRESHOLD,
    CPU_WARNING_THRESHOLD,
    DISK_CRITICAL_THRESHOLD,
    DISK_WARNING_THRESHOLD,
    HEALTH_SCORE_EXCELLENT,
    HEALTH_SCORE_GOOD,
    HEALTH_SCORE_MEDIUM,
    HEALTH_SCORE_PENALTY_CRITICAL,
    HEALTH_SCORE_PENALTY_MINOR,
    MEMORY_CRITICAL_THRESHOLD,
    MEMORY_WARNING_THRESHOLD,
)
from src.core.system_state import get_system_state_manager


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    value: Any
    threshold: Any
    severity: str  # "info", "warning", "critical"
    message: str


class HealthCheckService:
    """Concrete implementation of system health checking.

    Performs various health checks and calculates an overall health score.
    """

    async def check_system_health(self) -> dict[str, Any]:
        """Perform comprehensive system health check.

        Returns:
            Dictionary with health check results including:
            - overall_health: Overall health score (0-100)
            - checks: Individual check results
            - issues: List of detected issues
            - recommendations: List of recommendations
        """
        checks = []

        # Run all health checks
        checks.append(await self.check_cpu_health())
        checks.append(await self.check_memory_health())
        checks.append(await self.check_disk_health())
        checks.extend(await self.check_services_health())

        # Calculate overall score
        score = self.calculate_health_score(checks)

        # Extract issues and recommendations
        issues = [check["message"] for check in checks if not check["passed"]]

        recommendations = self._generate_recommendations(checks)

        return {
            "overall_health": score,
            "status": self._get_status_text(score),
            "checks": checks,
            "issues": issues,
            "recommendations": recommendations,
            "timestamp": psutil.boot_time(),
        }

    async def check_cpu_health(self) -> dict[str, Any]:
        """Check CPU health and usage.

        Returns:
            CPU health check result
        """
        # Get CPU usage over 1 second interval
        cpu_percent = psutil.cpu_percent(interval=1)

        passed = cpu_percent < CPU_WARNING_THRESHOLD
        severity = "info"

        if cpu_percent >= CPU_CRITICAL_THRESHOLD:
            severity = "critical"
            message = f"CPU usage very high: {cpu_percent:.1f}%"
        elif cpu_percent >= CPU_WARNING_THRESHOLD:
            severity = "warning"
            message = f"CPU usage elevated: {cpu_percent:.1f}%"
        else:
            message = f"CPU usage normal: {cpu_percent:.1f}%"

        return {
            "name": "cpu",
            "passed": passed,
            "value": cpu_percent,
            "threshold": CPU_WARNING_THRESHOLD,
            "severity": severity,
            "message": message,
            "details": {
                "cpu_count": psutil.cpu_count(),
                "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            },
        }

    async def check_memory_health(self) -> dict[str, Any]:
        """Check memory health and usage.

        Returns:
            Memory health check result
        """
        memory = psutil.virtual_memory()

        passed = memory.percent < MEMORY_WARNING_THRESHOLD
        severity = "info"

        if memory.percent >= MEMORY_CRITICAL_THRESHOLD:
            severity = "critical"
            message = f"Memory usage very high: {memory.percent:.1f}%"
        elif memory.percent >= MEMORY_WARNING_THRESHOLD:
            severity = "warning"
            message = f"Memory usage elevated: {memory.percent:.1f}%"
        else:
            message = f"Memory usage normal: {memory.percent:.1f}%"

        return {
            "name": "memory",
            "passed": passed,
            "value": memory.percent,
            "threshold": MEMORY_WARNING_THRESHOLD,
            "severity": severity,
            "message": message,
            "details": {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_gb": memory.used / (1024**3),
            },
        }

    async def check_disk_health(self) -> dict[str, Any]:
        """Check disk health and usage.

        Returns:
            Disk health check result
        """
        disk = psutil.disk_usage("/")

        passed = disk.percent < DISK_WARNING_THRESHOLD
        severity = "info"

        if disk.percent >= DISK_CRITICAL_THRESHOLD:
            severity = "critical"
            message = f"Disk usage very high: {disk.percent:.1f}%"
        elif disk.percent >= DISK_WARNING_THRESHOLD:
            severity = "warning"
            message = f"Disk usage elevated: {disk.percent:.1f}%"
        else:
            message = f"Disk usage normal: {disk.percent:.1f}%"

        return {
            "name": "disk",
            "passed": passed,
            "value": disk.percent,
            "threshold": DISK_WARNING_THRESHOLD,
            "severity": severity,
            "message": message,
            "details": {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "used_gb": disk.used / (1024**3),
            },
        }

    async def check_services_health(self) -> list[dict[str, Any]]:
        """Check external services health (Docker, GPU, System State, etc.).

        Returns:
            List of service health check results
        """
        checks = []

        # Check Docker
        docker_check = await self._check_docker()
        checks.append(docker_check)

        # Check GPU (if applicable)
        gpu_check = await self._check_gpu()
        checks.append(gpu_check)

        # Check System State
        state_check = self._check_system_state()
        checks.append(state_check)

        return checks

    async def _check_docker(self) -> dict[str, Any]:
        """Check if Docker is running."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await asyncio.wait_for(proc.communicate(), timeout=COMMAND_TIMEOUT_SHORT)

            passed = proc.returncode == 0

            return {
                "name": "docker",
                "passed": passed,
                "value": "running" if passed else "not running",
                "threshold": "running",
                "severity": "warning" if not passed else "info",
                "message": "Docker is running" if passed else "Docker not available",
            }

        except Exception as e:
            return {
                "name": "docker",
                "passed": False,
                "value": "error",
                "threshold": "running",
                "severity": "warning",
                "message": f"Docker check failed: {e}",
            }

    async def _check_gpu(self) -> dict[str, Any]:
        """Check if GPU is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi",
                "--showid",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await asyncio.wait_for(proc.communicate(), timeout=COMMAND_TIMEOUT_SHORT)

            passed = proc.returncode == 0

            return {
                "name": "gpu",
                "passed": passed,
                "value": "available" if passed else "not available",
                "threshold": "available",
                "severity": "info",  # GPU is optional
                "message": "GPU is available" if passed else "GPU not available",
            }

        except Exception as e:
            return {
                "name": "gpu",
                "passed": False,
                "value": "error",
                "threshold": "available",
                "severity": "info",
                "message": f"GPU check skipped: {e}",
            }

    def _check_system_state(self) -> dict[str, Any]:
        """Check if system is initialized."""
        state_manager = get_system_state_manager()
        initialized = state_manager.is_initialized()

        return {
            "name": "system_state",
            "passed": initialized,
            "value": "initialized" if initialized else "not initialized",
            "threshold": "initialized",
            "severity": "critical" if not initialized else "info",
            "message": "System is initialized" if initialized else "System not initialized",
        }

    def calculate_health_score(self, check_results: list[dict[str, Any]]) -> int:
        """Calculate overall health score from check results.

        Args:
            check_results: List of health check results

        Returns:
            Health score (0-100)
        """
        score = 100

        for check in check_results:
            if not check["passed"]:
                severity = check["severity"]

                if severity == "critical":
                    score -= HEALTH_SCORE_PENALTY_CRITICAL
                elif severity == "warning":
                    score -= HEALTH_SCORE_PENALTY_MINOR
                # "info" severity doesn't reduce score

        # Ensure score stays in valid range
        return max(0, min(100, score))

    def _get_status_text(self, score: int) -> str:
        """Get status text from health score.

        Args:
            score: Health score

        Returns:
            Status text
        """
        if score >= HEALTH_SCORE_EXCELLENT:
            return "Excellent"
        elif score >= HEALTH_SCORE_GOOD:
            return "Good"
        elif score >= HEALTH_SCORE_MEDIUM:
            return "Fair"
        else:
            return "Critical"

    def _generate_recommendations(self, checks: list[dict[str, Any]]) -> list[str]:
        """Generate recommendations based on check results.

        Args:
            checks: List of health check results

        Returns:
            List of recommendation strings
        """
        recommendations = []

        for check in checks:
            if not check["passed"]:
                name = check["name"]
                severity = check["severity"]

                if name == "cpu" and severity == "critical":
                    recommendations.append("Reduce CPU load or scale horizontally")
                elif name == "memory" and severity == "critical":
                    recommendations.append("Free memory or increase available RAM")
                elif name == "disk" and severity == "critical":
                    recommendations.append("Free disk space or add storage capacity")
                elif name == "docker" and severity == "warning":
                    recommendations.append("Install Docker for full functionality")
                elif name == "system_state" and severity == "critical":
                    recommendations.append("Initialize system with 'tawiza system init'")

        if not recommendations:
            recommendations.append("System is healthy - no actions required")

        return recommendations
