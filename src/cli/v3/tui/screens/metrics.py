"""Metrics Screen - Performance graphs and statistics."""

from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Static

from src.cli.v3.tui.services.adaptive_refresh import RefreshPriority, get_refresh_manager
from src.cli.v3.tui.services.gpu_metrics import get_gpu_metrics
from src.cli.v3.tui.widgets.plotext_charts import CPUMemoryChart, GPUChart, PerformanceChart


class PeriodSelector(Static):
    """Period selection widget."""

    DEFAULT_CSS = """
    PeriodSelector {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.period = "1h"

    def render(self) -> str:
        periods = ["1h", "6h", "24h", "7d"]
        parts = []
        for p in periods:
            if p == self.period:
                parts.append(f"[bold cyan][{p}][/]")
            else:
                parts.append(f"[dim]{p}[/]")
        return "Period: " + " | ".join(parts)

    def set_period(self, period: str) -> None:
        self.period = period
        self.refresh()


class StatsPanel(Static):
    """Statistics panel showing session stats."""

    DEFAULT_CSS = """
    StatsPanel {
        height: 6;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_completed = 0
        self.tasks_running = 0
        self.tasks_failed = 0
        self.total_tokens = 0
        self.estimated_cost = 0.0

    def render(self) -> str:
        return (
            "[bold cyan]SESSION STATS[/]\n"
            f"Tasks: [green]{self.tasks_completed} completed[/] | "
            f"[cyan]{self.tasks_running} running[/] | "
            f"[red]{self.tasks_failed} failed[/]\n"
            f"Total tokens: [bold]{self.total_tokens:,}[/] | "
            f"Cost estimate: [bold]${self.estimated_cost:.2f}[/]"
        )

    def update_stats(
        self,
        completed: int = 0,
        running: int = 0,
        failed: int = 0,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        self.tasks_completed = completed
        self.tasks_running = running
        self.tasks_failed = failed
        self.total_tokens = tokens
        self.estimated_cost = cost
        self.refresh()


class GPUInfoPanel(Static):
    """GPU information panel."""

    DEFAULT_CSS = """
    GPUInfoPanel {
        height: 5;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vram_used = 0.0
        self.vram_total = 24.0
        self.temperature = 0
        self.fan_speed = 0

    def render(self) -> str:
        vram_percent = (self.vram_used / self.vram_total) * 100 if self.vram_total > 0 else 0
        vram_color = "green" if vram_percent < 50 else "yellow" if vram_percent < 80 else "red"
        temp_color = (
            "green" if self.temperature < 60 else "yellow" if self.temperature < 80 else "red"
        )

        return (
            f"[bold]VRAM:[/] [{vram_color}]{self.vram_used:.1f} / {self.vram_total:.0f} GB "
            f"({vram_percent:.0f}%)[/]\n"
            f"[bold]Temp:[/] [{temp_color}]{self.temperature}°C[/]  "
            f"[bold]Fan:[/] {self.fan_speed}%"
        )

    def update_info(
        self, vram_used: float = 0, vram_total: float = 24, temperature: int = 0, fan_speed: int = 0
    ) -> None:
        self.vram_used = vram_used
        self.vram_total = vram_total
        self.temperature = temperature
        self.fan_speed = fan_speed
        self.refresh()


class MetricsScreen(Container):
    """Metrics content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("h", "period_hour", "1 Hour", show=True),
        Binding("d", "period_day", "1 Day", show=True),
        Binding("w", "period_week", "1 Week", show=True),
        Binding("e", "export_csv", "Export", show=True),
        Binding("c", "clear_history", "Clear", show=True),
        Binding("escape", "go_back", "Back", show=True),
    ]

    DEFAULT_CSS = """
    MetricsScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #metrics-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
        layout: horizontal;
    }

    #metrics-title {
        width: 1fr;
    }

    #period-selector {
        width: auto;
    }

    #main-charts {
        height: 1fr;
        padding: 1;
        layout: vertical;
    }

    #gpu-chart {
        height: 14;
        margin-bottom: 1;
    }

    #secondary-charts {
        height: 12;
        layout: horizontal;
    }

    #cpu-chart {
        width: 50%;
        margin-right: 1;
    }

    #perf-chart {
        width: 50%;
    }

    #bottom-panels {
        height: 8;
        layout: horizontal;
        padding: 0 1;
    }

    #gpu-info {
        width: 40%;
        margin-right: 1;
    }

    #stats-panel {
        width: 60%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_timer: Timer | None = None
        self._period = "1h"

    def compose(self) -> ComposeResult:
        """Create the metrics screen layout."""
        # Header
        with Horizontal(id="metrics-header"):
            yield Static("[bold cyan]📊 SYSTEM METRICS[/]", id="metrics-title")
            yield PeriodSelector(id="period-selector")

        # Main charts area
        with Vertical(id="main-charts"):
            yield GPUChart(title="GPU Utilization (RX 7900 XTX)", id="gpu-chart")

            with Horizontal(id="secondary-charts"):
                yield CPUMemoryChart(id="cpu-chart")
                yield PerformanceChart(id="perf-chart")

        # Bottom panels
        with Horizontal(id="bottom-panels"):
            yield GPUInfoPanel(id="gpu-info")
            yield StatsPanel(id="stats-panel")

    def on_mount(self) -> None:
        """Initialize on mount with adaptive refresh."""
        # Register with adaptive refresh manager
        refresh_manager = get_refresh_manager()
        if refresh_manager._app:
            refresh_manager.register_timer(
                name="metrics_update",
                callback=self._update_metrics,
                priority=RefreshPriority.HIGH,
                active_interval=2.0,  # 2s when visible
                idle_interval=5.0,  # 5s when idle
                background_interval=30.0,  # 30s when not visible
            )
            refresh_manager.start_timer("metrics_update")
            logger.debug("Metrics using adaptive refresh")
        else:
            # Fallback to fixed timer
            self._refresh_timer = self.set_interval(2.0, self._update_metrics)

        self._init_demo_data()

    def on_unmount(self) -> None:
        """Cleanup on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        # Stop adaptive timer
        refresh_manager = get_refresh_manager()
        refresh_manager.stop_timer("metrics_update")

    def _init_demo_data(self) -> None:
        """Initialize with starting data."""
        # Initialize with real metrics (no random data)
        self.run_worker(self._load_initial_metrics())

    async def _load_initial_metrics(self) -> None:
        """Load initial metrics from real sources."""
        import psutil

        try:
            # Get current system stats
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent

            cpu_chart = self.query_one("#cpu-chart", CPUMemoryChart)
            cpu_chart.add_values(cpu, memory)

            # GPU metrics
            try:
                gpu_metrics = await get_gpu_metrics()

                gpu_chart = self.query_one("#gpu-chart", GPUChart)
                gpu_chart.add_value(gpu_metrics.utilization)

                gpu_info = self.query_one("#gpu-info", GPUInfoPanel)
                gpu_info.update_info(
                    gpu_metrics.vram_used_gb,
                    gpu_metrics.vram_total_gb,
                    gpu_metrics.temperature,
                    gpu_metrics.fan_speed,
                )
            except Exception:
                pass

            # Try to get task stats from Redis
            try:
                await self._load_task_stats()
            except Exception:
                # Use zeros if Redis unavailable
                stats = self.query_one("#stats-panel", StatsPanel)
                stats.update_stats(completed=0, running=0, failed=0, tokens=0, cost=0.0)

            # Performance metrics
            perf_chart = self.query_one("#perf-chart", PerformanceChart)
            perf_chart.update_metrics(tokens_per_sec=0, avg_duration=0, success_rate=0)

        except Exception:
            pass

    async def _load_task_stats(self) -> None:
        """Load task statistics from Redis if available."""
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, socket_timeout=1)

            # Try to get stats from Redis
            completed = int(r.get("tawiza:tasks:completed") or 0)
            running = int(r.get("tawiza:tasks:running") or 0)
            failed = int(r.get("tawiza:tasks:failed") or 0)
            tokens = int(r.get("tawiza:tokens:total") or 0)

            # Estimate cost (assuming Ollama is free, but track for reference)
            cost = tokens * 0.000001  # Placeholder

            stats = self.query_one("#stats-panel", StatsPanel)
            stats.update_stats(
                completed=completed, running=running, failed=failed, tokens=tokens, cost=cost
            )

        except Exception:
            # Redis not available, use session defaults
            stats = self.query_one("#stats-panel", StatsPanel)
            stats.update_stats(completed=0, running=0, failed=0, tokens=0, cost=0.0)

    async def _update_metrics(self) -> None:
        """Update metrics periodically."""
        try:
            import psutil

            # CPU/Memory
            cpu = psutil.cpu_percent(interval=0)
            memory = psutil.virtual_memory().percent

            cpu_chart = self.query_one("#cpu-chart", CPUMemoryChart)
            cpu_chart.add_values(cpu, memory)

            # GPU - async call to avoid blocking event loop
            try:
                gpu_metrics = await get_gpu_metrics()

                gpu_chart = self.query_one("#gpu-chart", GPUChart)
                gpu_chart.add_value(gpu_metrics.utilization)

                # Update GPU info panel
                gpu_info = self.query_one("#gpu-info", GPUInfoPanel)
                gpu_info.update_info(
                    gpu_metrics.vram_used_gb,
                    gpu_metrics.vram_total_gb,
                    gpu_metrics.temperature,
                    gpu_metrics.fan_speed,
                )
            except Exception:
                gpu_chart = self.query_one("#gpu-chart", GPUChart)
                gpu_chart.add_value(0.0)

        except Exception:
            pass

    def action_period_hour(self) -> None:
        """Set period to 1 hour."""
        self._set_period("1h")

    def action_period_day(self) -> None:
        """Set period to 1 day."""
        self._set_period("24h")

    def action_period_week(self) -> None:
        """Set period to 1 week."""
        self._set_period("7d")

    def _set_period(self, period: str) -> None:
        """Set the display period."""
        self._period = period
        selector = self.query_one("#period-selector", PeriodSelector)
        selector.set_period(period)
        self.app.notify(f"Period set to {period}", timeout=1)

    def action_export_csv(self) -> None:
        """Export metrics to CSV."""
        import csv

        try:
            from src.cli.constants import PROJECT_ROOT

            export_path = PROJECT_ROOT / "logs" / "metrics_export.csv"

            gpu_chart = self.query_one("#gpu-chart", GPUChart)
            cpu_chart = self.query_one("#cpu-chart", CPUMemoryChart)

            with open(export_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "gpu_util", "cpu_util", "memory_util"])

                now = datetime.now()
                gpu_values = gpu_chart.values if hasattr(gpu_chart, "values") else []
                cpu_values = cpu_chart.cpu_values if hasattr(cpu_chart, "cpu_values") else []
                mem_values = cpu_chart.mem_values if hasattr(cpu_chart, "mem_values") else []

                max_len = max(len(gpu_values), len(cpu_values), len(mem_values))

                for i in range(max_len):
                    gpu = gpu_values[i] if i < len(gpu_values) else 0
                    cpu = cpu_values[i] if i < len(cpu_values) else 0
                    mem = mem_values[i] if i < len(mem_values) else 0
                    writer.writerow([now.isoformat(), gpu, cpu, mem])

            self.app.notify(f"Exported metrics to {export_path}", timeout=3)

        except Exception as e:
            self.app.notify(f"Export failed: {e}", timeout=3)

    def action_clear_history(self) -> None:
        """Clear metrics history."""
        gpu_chart = self.query_one("#gpu-chart", GPUChart)
        cpu_chart = self.query_one("#cpu-chart", CPUMemoryChart)
        gpu_chart.clear()
        cpu_chart.clear()
        self.app.notify("History cleared", timeout=1)

    def action_go_back(self) -> None:
        """Go back to dashboard."""
        self.app.switch_to_screen("dashboard")
