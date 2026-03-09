"""Metrics collection from various system sources."""

import json
import os
import subprocess
import time
from datetime import datetime

from src.cli.v3.metrics.schema import MetricCategory
from src.cli.v3.metrics.storage import MetricsStorage


class MetricsCollector:
    """Collects metrics from GPU, system, Ollama, agents, and services."""

    def __init__(self, storage: MetricsStorage | None = None):
        """Initialize collector.

        Args:
            storage: MetricsStorage instance for persisting metrics
        """
        self.storage = storage or MetricsStorage()

    def collect_all(self) -> dict:
        """Collect all metrics and optionally store them.

        Returns:
            Dict with all collected metrics
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "gpu": self.collect_gpu(),
            "system": self.collect_system(),
            "ollama": self.collect_ollama(),
            "agents": self.collect_agents(),
            "services": self.collect_services(),
        }

        # Store to database
        for category, values in metrics.items():
            if category != "timestamp" and isinstance(values, dict):
                self.storage.record_batch({category: values})

        return metrics

    def collect_gpu(self) -> dict:
        """Collect GPU metrics using rocm-smi."""
        metrics = {
            "available": False,
            "utilization": 0.0,
            "memory_percent": 0.0,
            "temperature": 0.0,
        }

        try:
            result = subprocess.run(
                ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--showtemp", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                metrics["available"] = True

                for _card_id, card_data in data.items():
                    if isinstance(card_data, dict):
                        if "GPU use (%)" in card_data:
                            val = card_data["GPU use (%)"]
                            metrics["utilization"] = float(str(val).rstrip("%"))
                        if "GPU memory use (%)" in card_data:
                            val = card_data["GPU memory use (%)"]
                            metrics["memory_percent"] = float(str(val).rstrip("%"))
                        if "Temperature (Sensor edge) (C)" in card_data:
                            metrics["temperature"] = float(card_data["Temperature (Sensor edge) (C)"])
                        break

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception:
            pass

        return metrics

    def collect_system(self) -> dict:
        """Collect system metrics using psutil."""
        metrics = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_used_gb": 0.0,
            "memory_total_gb": 0.0,
            "disk_percent": 0.0,
            "load_average_1m": 0.0,
            "uptime_seconds": 0,
        }

        try:
            import psutil

            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)

            mem = psutil.virtual_memory()
            metrics["memory_percent"] = mem.percent
            metrics["memory_used_gb"] = mem.used / (1024**3)
            metrics["memory_total_gb"] = mem.total / (1024**3)

            disk = psutil.disk_usage("/")
            metrics["disk_percent"] = disk.percent

            load = psutil.getloadavg()
            metrics["load_average_1m"] = load[0]
            metrics["load_average_5m"] = load[1]
            metrics["load_average_15m"] = load[2]

            boot_time = psutil.boot_time()
            metrics["uptime_seconds"] = int(time.time() - boot_time)

        except ImportError:
            pass

        return metrics

    def collect_ollama(self) -> dict:
        """Collect Ollama metrics."""
        metrics = {
            "status": "unknown",
            "models_count": 0,
            "active_requests": 0,
        }

        try:
            import httpx

            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                metrics["status"] = "running"
                metrics["models_count"] = len(data.get("models", []))
            else:
                metrics["status"] = "error"

        except Exception:
            metrics["status"] = "stopped"

        return metrics

    def collect_agents(self) -> dict:
        """Collect agent task metrics."""
        from pathlib import Path

        metrics = {
            "total_tasks": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "success_rate": 0.0,
            "avg_duration_seconds": 0.0,
        }

        tasks_file = Path.home() / ".tawiza" / "agent_tasks.json"
        if tasks_file.exists():
            try:
                tasks = json.loads(tasks_file.read_text())
                metrics["total_tasks"] = len(tasks)

                completed = [t for t in tasks.values() if t.get("status") == "completed"]
                failed = [t for t in tasks.values() if t.get("status") == "failed"]
                active = [t for t in tasks.values() if t.get("status") in ("running", "pending")]

                metrics["completed_tasks"] = len(completed)
                metrics["failed_tasks"] = len(failed)
                metrics["active_tasks"] = len(active)

                if metrics["total_tasks"] > 0:
                    metrics["success_rate"] = (len(completed) / metrics["total_tasks"]) * 100

                durations = [t.get("duration", 0) for t in tasks.values() if t.get("duration")]
                if durations:
                    metrics["avg_duration_seconds"] = sum(durations) / len(durations)

            except Exception:
                pass

        return metrics

    def collect_services(self) -> dict:
        """Collect service health status."""
        import httpx

        services = {
            "ollama": ("http://localhost:11434/api/tags", "ok"),
            "label_studio": ("http://localhost:8082/api/health", "ok"),
            "llama_factory": ("http://localhost:7860/", "ok"),
            "tawiza_api": ("http://localhost:8002/health", "ok"),
        }

        metrics = {}

        for name, (url, _) in services.items():
            status = "down"
            latency_ms = 0.0

            try:
                start = time.time()
                response = httpx.get(url, timeout=5)
                latency_ms = (time.time() - start) * 1000

                status = "ok" if response.status_code < 400 else "error"

            except Exception:
                status = "down"

            metrics[f"{name}_status"] = status
            metrics[f"{name}_latency_ms"] = latency_ms

        # VM sandbox SSH check
        try:
            result = subprocess.run(
                ["nc", "-z", "-w", "2", os.getenv("VM_SANDBOX_HOST", "localhost"), "22"],
                capture_output=True,
                timeout=5,
            )
            metrics["vm_sandbox_status"] = "ok" if result.returncode == 0 else "down"
        except Exception:
            metrics["vm_sandbox_status"] = "down"

        metrics["vm_sandbox_latency_ms"] = 0.0

        return metrics

    def start_background_collection(
        self,
        interval_seconds: int = 60,
        categories: list[MetricCategory] | None = None,
    ) -> None:
        """Start background metrics collection.

        Args:
            interval_seconds: Collection interval
            categories: Categories to collect (None = all)
        """
        import threading

        def collect_loop():
            while True:
                try:
                    if categories:
                        for cat in categories:
                            method = getattr(self, f"collect_{cat.value}", None)
                            if method:
                                data = method()
                                self.storage.record_batch({cat.value: data})
                    else:
                        self.collect_all()
                except Exception:
                    pass

                time.sleep(interval_seconds)

        thread = threading.Thread(target=collect_loop, daemon=True)
        thread.start()
