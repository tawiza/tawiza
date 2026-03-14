"""Metrics schema definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MetricCategory(StrEnum):
    """Categories of metrics."""

    GPU = "gpu"
    SYSTEM = "system"
    OLLAMA = "ollama"
    AGENTS = "agents"
    TRAINING = "training"
    SERVICES = "services"


METRICS_SCHEMA = {
    MetricCategory.GPU: {
        "utilization": {"type": float, "unit": "%", "range": (0, 100)},
        "memory_used": {"type": int, "unit": "bytes"},
        "memory_total": {"type": int, "unit": "bytes"},
        "memory_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "temperature": {"type": float, "unit": "°C"},
        "power_draw": {"type": float, "unit": "W"},
        "fan_speed": {"type": int, "unit": "RPM"},
        "clock_speed": {"type": int, "unit": "MHz"},
    },
    MetricCategory.SYSTEM: {
        "cpu_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "cpu_per_core": {"type": list, "unit": "%"},
        "memory_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "memory_used_gb": {"type": float, "unit": "GB"},
        "memory_total_gb": {"type": float, "unit": "GB"},
        "swap_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "disk_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "disk_read_bytes": {"type": int, "unit": "bytes/s"},
        "disk_write_bytes": {"type": int, "unit": "bytes/s"},
        "network_sent_bytes": {"type": int, "unit": "bytes/s"},
        "network_recv_bytes": {"type": int, "unit": "bytes/s"},
        "load_average_1m": {"type": float, "unit": ""},
        "load_average_5m": {"type": float, "unit": ""},
        "load_average_15m": {"type": float, "unit": ""},
        "uptime_seconds": {"type": int, "unit": "s"},
    },
    MetricCategory.OLLAMA: {
        "status": {"type": str, "values": ["running", "stopped", "error"]},
        "models_count": {"type": int, "unit": ""},
        "vram_used": {"type": int, "unit": "bytes"},
        "active_requests": {"type": int, "unit": ""},
        "total_requests": {"type": int, "unit": ""},
        "avg_tokens_per_second": {"type": float, "unit": "tok/s"},
        "model_load_time": {"type": float, "unit": "s"},
    },
    MetricCategory.AGENTS: {
        "total_tasks": {"type": int, "unit": ""},
        "active_tasks": {"type": int, "unit": ""},
        "completed_tasks": {"type": int, "unit": ""},
        "failed_tasks": {"type": int, "unit": ""},
        "success_rate": {"type": float, "unit": "%", "range": (0, 100)},
        "avg_duration_seconds": {"type": float, "unit": "s"},
        "avg_iterations": {"type": float, "unit": ""},
    },
    MetricCategory.TRAINING: {
        "active_jobs": {"type": int, "unit": ""},
        "queued_jobs": {"type": int, "unit": ""},
        "completed_jobs": {"type": int, "unit": ""},
        "current_epoch": {"type": int, "unit": ""},
        "current_loss": {"type": float, "unit": ""},
        "current_learning_rate": {"type": float, "unit": ""},
        "progress_percent": {"type": float, "unit": "%", "range": (0, 100)},
        "eta_seconds": {"type": int, "unit": "s"},
    },
    MetricCategory.SERVICES: {
        "ollama_status": {"type": str, "values": ["ok", "down", "error"]},
        "ollama_latency_ms": {"type": float, "unit": "ms"},
        "label_studio_status": {"type": str, "values": ["ok", "down", "error"]},
        "label_studio_latency_ms": {"type": float, "unit": "ms"},
        "llama_factory_status": {"type": str, "values": ["ok", "down", "error"]},
        "llama_factory_latency_ms": {"type": float, "unit": "ms"},
        "tawiza_api_status": {"type": str, "values": ["ok", "down", "error"]},
        "tawiza_api_latency_ms": {"type": float, "unit": "ms"},
        "vm_sandbox_status": {"type": str, "values": ["ok", "down", "error"]},
        "vm_sandbox_latency_ms": {"type": float, "unit": "ms"},
    },
}


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: datetime
    category: MetricCategory
    name: str
    value: float
    unit: str = ""
    tags: dict = field(default_factory=dict)


@dataclass
class MetricsSummary:
    """Summary statistics for a metric over a time period."""

    name: str
    category: MetricCategory
    min_value: float
    max_value: float
    avg_value: float
    count: int
    start_time: datetime
    end_time: datetime
