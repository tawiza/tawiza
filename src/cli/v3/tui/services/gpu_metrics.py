"""GPU Metrics - Async GPU metrics collection using ROCm."""

import asyncio
import functools
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from loguru import logger

# Shared thread pool for GPU commands (limit to 2 threads to avoid overloading)
_gpu_thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gpu_metrics")


@dataclass
class GPUInfo:
    """GPU metrics snapshot."""

    utilization: float = 0.0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 24.0
    temperature: int = 0
    fan_speed: int = 0
    power_usage: float = 0.0


# Track if rocm-smi is available to avoid repeated error logs
_rocm_available: bool | None = None


def _run_rocm_sync(*args: str, timeout: float = 2.0) -> dict | None:
    """
    Run rocm-smi command synchronously and return parsed JSON.
    This function runs in a thread pool to avoid blocking the event loop.
    """
    global _rocm_available

    # Skip if we already know rocm-smi is not available
    if _rocm_available is False:
        return None

    try:
        result = subprocess.run(
            ["rocm-smi", *args, "--json"], capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            _rocm_available = True
            return data
        # rocm-smi returned but no valid output (no GPU)
        _rocm_available = False
        return None
    except subprocess.TimeoutExpired:
        logger.debug("rocm-smi command timed out")
    except FileNotFoundError:
        _rocm_available = False  # rocm-smi not installed
    except json.JSONDecodeError:
        # Empty or invalid JSON - GPU not available
        _rocm_available = False
    except Exception:
        _rocm_available = False
    return None


async def _run_rocm_async(*args: str, timeout: float = 2.0) -> dict | None:
    """
    Run rocm-smi command asynchronously using thread pool.
    This wraps the blocking subprocess call to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    func = functools.partial(_run_rocm_sync, *args, timeout=timeout)
    return await loop.run_in_executor(_gpu_thread_pool, func)


async def get_gpu_utilization() -> float:
    """Get GPU utilization percentage asynchronously."""
    data = await _run_rocm_async("--showuse")
    if data and "card0" in data:
        return float(data["card0"].get("GPU use (%)", 0))
    return 0.0


async def get_gpu_metrics() -> GPUInfo:
    """
    Collect all GPU metrics asynchronously.

    Runs multiple rocm-smi commands concurrently for better performance.
    Each command runs in a thread pool to avoid blocking.
    """
    metrics = GPUInfo()

    # Run all commands concurrently in thread pool
    results = await asyncio.gather(
        _run_rocm_async("--showuse"),
        _run_rocm_async("--showmeminfo", "vram"),
        _run_rocm_async("--showtemp", "--showfan"),
        _run_rocm_async("--showpower"),
        return_exceptions=True,
    )

    use_data, mem_data, temp_data, power_data = results

    # Parse utilization
    if isinstance(use_data, dict) and "card0" in use_data:
        metrics.utilization = float(use_data["card0"].get("GPU use (%)", 0))

    # Parse memory
    if isinstance(mem_data, dict) and "card0" in mem_data:
        vram_used = float(mem_data["card0"].get("VRAM Total Used Memory (B)", 0))
        vram_total = float(mem_data["card0"].get("VRAM Total Memory (B)", 24 * 1024**3))
        metrics.vram_used_gb = vram_used / (1024**3)
        metrics.vram_total_gb = vram_total / (1024**3)

    # Parse temperature and fan
    if isinstance(temp_data, dict) and "card0" in temp_data:
        metrics.temperature = int(temp_data["card0"].get("Temperature (Sensor edge) (C)", 0))
        metrics.fan_speed = int(temp_data["card0"].get("Fan Speed (%)", 0))

    # Parse power
    if isinstance(power_data, dict) and "card0" in power_data:
        metrics.power_usage = float(
            power_data["card0"].get("Average Graphics Package Power (W)", 0)
        )

    return metrics


def shutdown_thread_pool():
    """Shutdown the GPU thread pool gracefully."""
    _gpu_thread_pool.shutdown(wait=False)
