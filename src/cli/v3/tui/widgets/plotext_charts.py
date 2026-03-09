"""Plotext-based chart widgets for metrics visualization."""

from datetime import datetime

from textual_plotext import PlotextPlot


class GPUChart(PlotextPlot):
    """GPU utilization chart using plotext."""

    DEFAULT_CSS = """
    GPUChart {
        height: 12;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str = "GPU Utilization", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._history: list[float] = []
        self._timestamps: list[str] = []
        self._max_points = 60

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def add_value(self, value: float, timestamp: datetime | None = None) -> None:
        """Add a new value to the chart."""
        self._history.append(value)
        ts = timestamp or datetime.now()
        self._timestamps.append(ts.strftime("%H:%M"))

        # Keep limited history
        if len(self._history) > self._max_points:
            self._history.pop(0)
            self._timestamps.pop(0)

        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        if len(self._history) >= 2:
            plt.plot(self._history, marker="braille", color="cyan")
            plt.title(self._title)
            plt.ylabel("%")
            plt.ylim(0, 100)
            plt.theme("textual-dark")

            # Add reference lines
            plt.hline(50, color="yellow")
            plt.hline(80, color="red")

        self.refresh()

    def clear(self) -> None:
        """Clear the chart data."""
        self._history.clear()
        self._timestamps.clear()
        self._update_chart()


class CPUMemoryChart(PlotextPlot):
    """CPU and Memory dual-line chart."""

    DEFAULT_CSS = """
    CPUMemoryChart {
        height: 10;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cpu_history: list[float] = []
        self._memory_history: list[float] = []
        self._max_points = 60

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def add_values(self, cpu: float, memory: float) -> None:
        """Add new CPU and memory values."""
        self._cpu_history.append(cpu)
        self._memory_history.append(memory)

        if len(self._cpu_history) > self._max_points:
            self._cpu_history.pop(0)
            self._memory_history.pop(0)

        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        if len(self._cpu_history) >= 2:
            plt.plot(self._cpu_history, label="CPU", color="cyan", marker="braille")
            plt.plot(self._memory_history, label="RAM", color="magenta", marker="braille")
            plt.title("CPU & Memory")
            plt.ylabel("%")
            plt.ylim(0, 100)
            plt.theme("textual-dark")

        self.refresh()

    def clear(self) -> None:
        """Clear chart data."""
        self._cpu_history.clear()
        self._memory_history.clear()
        self._update_chart()


class PerformanceChart(PlotextPlot):
    """Performance metrics bar chart."""

    DEFAULT_CSS = """
    PerformanceChart {
        height: 10;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._metrics: dict = {
            "tokens_per_sec": 0,
            "avg_duration": 0,
            "success_rate": 0,
        }

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def update_metrics(
        self,
        tokens_per_sec: float = 0,
        avg_duration: float = 0,
        success_rate: float = 0
    ) -> None:
        """Update performance metrics."""
        self._metrics["tokens_per_sec"] = min(tokens_per_sec, 200)  # Cap at 200
        self._metrics["avg_duration"] = min(avg_duration / 10, 100)  # Scale to 0-100
        self._metrics["success_rate"] = success_rate
        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        labels = ["Tokens/s", "Duration", "Success %"]
        values = [
            self._metrics["tokens_per_sec"] / 2,  # Scale to 0-100
            self._metrics["avg_duration"],
            self._metrics["success_rate"],
        ]
        colors = ["cyan", "yellow", "green"]

        plt.bar(labels, values, color=colors)
        plt.title("Agent Performance")
        plt.ylim(0, 100)
        plt.theme("textual-dark")

        self.refresh()


class ActivityChart(PlotextPlot):
    """Activity over time chart (tasks completed per hour)."""

    DEFAULT_CSS = """
    ActivityChart {
        height: 8;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hourly_data: list[int] = [0] * 24
        self._current_hour = datetime.now().hour

    def on_mount(self) -> None:
        """Initialize the chart."""
        self._update_chart()

    def increment_current_hour(self, count: int = 1) -> None:
        """Increment task count for current hour."""
        hour = datetime.now().hour
        if hour != self._current_hour:
            # Reset if hour changed
            self._current_hour = hour
        self._hourly_data[hour] += count
        self._update_chart()

    def set_hourly_data(self, data: list[int]) -> None:
        """Set all hourly data."""
        self._hourly_data = data[:24] + [0] * (24 - len(data))
        self._update_chart()

    def _update_chart(self) -> None:
        """Update the plotext chart."""
        plt = self.plt
        plt.clear_figure()

        # Show last 12 hours
        current = datetime.now().hour
        hours = [(current - 11 + i) % 24 for i in range(12)]
        values = [self._hourly_data[h] for h in hours]
        labels = [f"{h:02d}h" for h in hours]

        plt.bar(labels, values, color="cyan")
        plt.title("Tasks per Hour")
        plt.theme("textual-dark")

        self.refresh()

    def clear(self) -> None:
        """Clear activity data."""
        self._hourly_data = [0] * 24
        self._update_chart()
