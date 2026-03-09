"""Metric Gauge widget with sparkline history."""


from textual.reactive import reactive
from textual.widgets import Static
from textual_plotext import PlotextPlot


class MetricGauge(Static):
    """Compact metric gauge with sparkline visualization."""

    DEFAULT_CSS = """
    MetricGauge {
        height: 5;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
    }
    """

    value = reactive(0.0)
    label = reactive("")
    max_value = reactive(100.0)

    def __init__(
        self,
        label: str,
        value: float = 0.0,
        unit: str = "%",
        max_value: float = 100.0,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.label = label
        self.value = value
        self.unit = unit
        self.max_value = max_value
        self._history: list[float] = []

    def render(self) -> str:
        """Render the metric gauge."""
        # Color based on value
        percent = (self.value / self.max_value) * 100
        if percent < 50:
            color = "green"
        elif percent < 80:
            color = "yellow"
        else:
            color = "red"

        # Build progress bar
        filled = int((self.value / self.max_value) * 10)
        empty = 10 - filled

        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

        # Sparkline from history
        sparkline = self._render_sparkline()

        return (
            f"[bold]{self.label}[/]\n"
            f"{bar} [{color}]{self.value:.1f}{self.unit}[/]\n"
            f"[dim]{sparkline}[/]"
        )

    def _render_sparkline(self) -> str:
        """Render a simple text sparkline from history."""
        if len(self._history) < 2:
            return "─" * 10

        # Normalize history to 0-7 range for braille blocks
        chars = "▁▂▃▄▅▆▇█"
        min_val = min(self._history[-10:]) if self._history else 0
        max_val = max(self._history[-10:]) if self._history else 100
        range_val = max_val - min_val if max_val != min_val else 1

        result = ""
        for val in self._history[-10:]:
            normalized = int(((val - min_val) / range_val) * 7)
            normalized = max(0, min(7, normalized))
            result += chars[normalized]

        return result.ljust(10, "─")

    def update_value(self, value: float) -> None:
        """Update the gauge value and history."""
        self.value = value
        self._history.append(value)
        # Keep last 60 data points (1 minute at 1s interval)
        if len(self._history) > 60:
            self._history.pop(0)
        self.refresh()

    def get_history(self) -> list[float]:
        """Get the value history."""
        return self._history.copy()


class MetricGaugePlotex(PlotextPlot):
    """Metric gauge using plotext for advanced visualization."""

    DEFAULT_CSS = """
    MetricGaugePlotex {
        height: 8;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str = "Metric", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._history: list[float] = []

    def on_mount(self) -> None:
        """Initialize the plot."""
        self._update_plot()

    def update_value(self, value: float) -> None:
        """Add a value and update the plot."""
        self._history.append(value)
        if len(self._history) > 60:
            self._history.pop(0)
        self._update_plot()

    def _update_plot(self) -> None:
        """Update the plotext visualization."""
        plt = self.plt
        plt.clear_figure()

        if self._history:
            plt.plot(self._history, marker="braille")
            plt.title(self._title)
            plt.plotsize(self.size.width - 4, self.size.height - 2)
            plt.theme("textual-dark")

            # Set y-axis range
            plt.ylim(0, 100)

        self.refresh()
