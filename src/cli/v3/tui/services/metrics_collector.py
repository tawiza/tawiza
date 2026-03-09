"""Metrics Collector - Collects system and agent metrics."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime

import psutil

from src.cli.v3.tui.services.gpu_metrics import get_gpu_metrics


@dataclass
class SystemMetrics:
    """System metrics snapshot."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float


@dataclass
class GPUMetrics:
    """GPU metrics snapshot."""
    timestamp: datetime
    utilization: float
    vram_used_gb: float
    vram_total_gb: float
    temperature: int
    fan_speed: int
    power_usage: float


@dataclass
class AgentMetrics:
    """Agent performance metrics."""
    tokens_per_second: float
    average_task_duration: float
    success_rate: float
    tasks_completed: int
    tasks_failed: int
    total_tokens_used: int


class MetricsCollector:
    """Collector for system and agent metrics."""

    def __init__(self, history_size: int = 3600):
        self._history_size = history_size
        self._system_history: list[SystemMetrics] = []
        self._gpu_history: list[GPUMetrics] = []
        self._agent_metrics = AgentMetrics(
            tokens_per_second=0,
            average_task_duration=0,
            success_rate=100,
            tasks_completed=0,
            tasks_failed=0,
            total_tokens_used=0,
        )

    def collect_system(self) -> SystemMetrics:
        """Collect current system metrics."""
        cpu = psutil.cpu_percent(interval=0)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu,
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024**3),
            disk_total_gb=disk.total / (1024**3),
        )

        self._system_history.append(metrics)
        if len(self._system_history) > self._history_size:
            self._system_history.pop(0)

        return metrics

    def collect_gpu(self) -> GPUMetrics:
        """Collect current GPU metrics (ROCm)."""
        metrics = GPUMetrics(
            timestamp=datetime.now(),
            utilization=0,
            vram_used_gb=0,
            vram_total_gb=24,
            temperature=0,
            fan_speed=0,
            power_usage=0,
        )

        try:
            # Get GPU utilization
            result = subprocess.run(
                ["rocm-smi", "--showuse", "--json"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "card0" in data:
                    metrics.utilization = float(data["card0"].get("GPU use (%)", 0))

            # Get memory info
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "card0" in data:
                    vram_used = float(data["card0"].get("VRAM Total Used Memory (B)", 0))
                    vram_total = float(data["card0"].get("VRAM Total Memory (B)", 24 * 1024**3))
                    metrics.vram_used_gb = vram_used / (1024**3)
                    metrics.vram_total_gb = vram_total / (1024**3)

            # Get temperature and fan
            result = subprocess.run(
                ["rocm-smi", "--showtemp", "--showfan", "--json"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "card0" in data:
                    metrics.temperature = int(data["card0"].get("Temperature (Sensor edge) (C)", 0))
                    metrics.fan_speed = int(data["card0"].get("Fan Speed (%)", 0))

            # Get power
            result = subprocess.run(
                ["rocm-smi", "--showpower", "--json"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "card0" in data:
                    metrics.power_usage = float(data["card0"].get("Average Graphics Package Power (W)", 0))

        except Exception:
            pass

        self._gpu_history.append(metrics)
        if len(self._gpu_history) > self._history_size:
            self._gpu_history.pop(0)

        return metrics

    async def collect_gpu_async(self) -> GPUMetrics:
        """Collect current GPU metrics (ROCm) - async version using thread pool."""
        gpu_info = await get_gpu_metrics()

        metrics = GPUMetrics(
            timestamp=datetime.now(),
            utilization=gpu_info.utilization,
            vram_used_gb=gpu_info.vram_used_gb,
            vram_total_gb=gpu_info.vram_total_gb,
            temperature=gpu_info.temperature,
            fan_speed=gpu_info.fan_speed,
            power_usage=gpu_info.power_usage,
        )

        self._gpu_history.append(metrics)
        if len(self._gpu_history) > self._history_size:
            self._gpu_history.pop(0)

        return metrics

    def get_system_history(self, limit: int | None = None) -> list[SystemMetrics]:
        """Get system metrics history."""
        if limit:
            return self._system_history[-limit:]
        return self._system_history.copy()

    def get_gpu_history(self, limit: int | None = None) -> list[GPUMetrics]:
        """Get GPU metrics history."""
        if limit:
            return self._gpu_history[-limit:]
        return self._gpu_history.copy()

    def get_cpu_values(self, limit: int = 60) -> list[float]:
        """Get CPU percent values for plotting."""
        return [m.cpu_percent for m in self._system_history[-limit:]]

    def get_memory_values(self, limit: int = 60) -> list[float]:
        """Get memory percent values for plotting."""
        return [m.memory_percent for m in self._system_history[-limit:]]

    def get_gpu_values(self, limit: int = 60) -> list[float]:
        """Get GPU utilization values for plotting."""
        return [m.utilization for m in self._gpu_history[-limit:]]

    # Agent metrics

    def update_agent_metrics(
        self,
        tokens_per_second: float | None = None,
        task_duration: float | None = None,
        task_succeeded: bool | None = None,
        tokens_used: int | None = None,
    ) -> None:
        """Update agent performance metrics."""
        if tokens_per_second is not None:
            # Exponential moving average
            self._agent_metrics.tokens_per_second = (
                0.9 * self._agent_metrics.tokens_per_second +
                0.1 * tokens_per_second
            )

        if task_duration is not None:
            # Exponential moving average
            self._agent_metrics.average_task_duration = (
                0.9 * self._agent_metrics.average_task_duration +
                0.1 * task_duration
            )

        if task_succeeded is not None:
            if task_succeeded:
                self._agent_metrics.tasks_completed += 1
            else:
                self._agent_metrics.tasks_failed += 1

            total = self._agent_metrics.tasks_completed + self._agent_metrics.tasks_failed
            if total > 0:
                self._agent_metrics.success_rate = (
                    self._agent_metrics.tasks_completed / total * 100
                )

        if tokens_used is not None:
            self._agent_metrics.total_tokens_used += tokens_used

    def get_agent_metrics(self) -> AgentMetrics:
        """Get current agent metrics."""
        return self._agent_metrics

    def reset_agent_metrics(self) -> None:
        """Reset agent metrics."""
        self._agent_metrics = AgentMetrics(
            tokens_per_second=0,
            average_task_duration=0,
            success_rate=100,
            tasks_completed=0,
            tasks_failed=0,
            total_tokens_used=0,
        )

    def clear_history(self) -> None:
        """Clear all history."""
        self._system_history.clear()
        self._gpu_history.clear()

    def export_to_csv(self, filepath: str) -> None:
        """Export metrics to CSV."""
        import csv

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # System metrics
            writer.writerow(["System Metrics"])
            writer.writerow(["timestamp", "cpu_percent", "memory_percent", "disk_percent"])
            for m in self._system_history:
                writer.writerow([
                    m.timestamp.isoformat(),
                    m.cpu_percent,
                    m.memory_percent,
                    m.disk_percent,
                ])

            writer.writerow([])

            # GPU metrics
            writer.writerow(["GPU Metrics"])
            writer.writerow(["timestamp", "utilization", "vram_used_gb", "temperature"])
            for m in self._gpu_history:
                writer.writerow([
                    m.timestamp.isoformat(),
                    m.utilization,
                    m.vram_used_gb,
                    m.temperature,
                ])


# Singleton instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
