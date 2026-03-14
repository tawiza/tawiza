# src/cli/ui/gpu_monitor.py
"""Moniteur GPU hybride - supporte host (ROCm) et VM (SSH)."""

import os
import re
import subprocess
from dataclasses import dataclass
from enum import StrEnum


class GPULocation(StrEnum):
    HOST = "host"
    VM = "vm"
    NONE = "none"


@dataclass
class GPUStatus:
    """État actuel du GPU."""

    available: bool = False
    location: GPULocation = GPULocation.NONE
    name: str = "Unknown"
    memory_used: int = 0  # MB
    memory_total: int = 0  # MB
    utilization: float = 0.0  # %
    temperature: int = 0  # °C

    @property
    def memory_percent(self) -> float:
        if self.memory_total == 0:
            return 0.0
        return (self.memory_used / self.memory_total) * 100


class GPUMonitor:
    """Moniteur GPU qui détecte automatiquement host ou VM."""

    def __init__(self, vm_host: str = os.getenv("GPU_VM_HOST", "localhost"), vm_user: str = "root"):
        self.vm_host = vm_host
        self.vm_user = vm_user
        self._cached_status: GPUStatus | None = None

    def check_host_gpu(self) -> GPUStatus | None:
        """Vérifie si le GPU est disponible sur l'host via ROCm."""
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--showtemp", "--showuse"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "GPU" in result.stdout:
                return self._parse_rocm_output(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def check_vm_gpu(self) -> GPUStatus | None:
        """Vérifie le GPU dans VM 400 via SSH."""
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=3",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{self.vm_user}@{self.vm_host}",
                    "rocm-smi",
                    "--showmeminfo",
                    "vram",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                status = self._parse_rocm_output(result.stdout)
                if status:
                    status.location = GPULocation.VM
                return status
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def get_status(self) -> GPUStatus:
        """Retourne le statut GPU (essaie host puis VM)."""
        # Essayer d'abord l'host
        status = self.check_host_gpu()
        if status:
            status.location = GPULocation.HOST
            self._cached_status = status
            return status

        # Sinon essayer la VM
        status = self.check_vm_gpu()
        if status:
            self._cached_status = status
            return status

        # Pas de GPU disponible
        return GPUStatus(available=False, location=GPULocation.NONE)

    def _parse_rocm_output(self, output: str) -> GPUStatus | None:
        """Parse la sortie de rocm-smi."""
        try:
            status = GPUStatus(available=True, name="AMD RX 7900 XTX")

            # Memory parsing
            mem_match = re.search(r"(\d+)\s*/\s*(\d+)\s*MB", output)
            if mem_match:
                status.memory_used = int(mem_match.group(1))
                status.memory_total = int(mem_match.group(2))

            # Temperature
            temp_match = re.search(r"(\d+)\.?\d*\s*c", output, re.IGNORECASE)
            if temp_match:
                status.temperature = int(temp_match.group(1))

            # Utilization
            use_match = re.search(r"(\d+)\.?\d*\s*%", output)
            if use_match:
                status.utilization = float(use_match.group(1))

            return status
        except Exception:
            return None


def get_gpu_status() -> GPUStatus:
    """Fonction helper pour obtenir le statut GPU."""
    return GPUMonitor().get_status()
