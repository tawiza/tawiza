"""Sparkline Widget - Mini inline charts for metrics."""


from textual.reactive import reactive
from textual.widget import Widget


class Sparkline(Widget):
    """A compact inline chart for displaying metric trends.

    Uses Unicode block characters to draw a mini bar chart.
    """

    DEFAULT_CSS = """
    Sparkline {
        height: 1;
        width: 100%;
        padding: 0;
        background: transparent;
    }

    Sparkline.with-border {
        border: round $surface-lighter;
        padding: 0 1;
    }
    """

    # Unicode block characters for different heights (0-8)
    BLOCKS = " ▁▂▃▄▅▆▇█"

    data = reactive(list)
    min_val = reactive(0.0)
    max_val = reactive(100.0)
    color = reactive("primary")

    def __init__(
        self,
        data: list[float] | None = None,
        min_val: float = 0.0,
        max_val: float = 100.0,
        width: int = 20,
        color: str = "primary",
        show_value: bool = True,
        label: str = "",
        **kwargs
    ):
        super().__init__(**kwargs)
        self._data = data or []
        self.min_val = min_val
        self.max_val = max_val
        self._width = width
        self.color = color
        self._show_value = show_value
        self._label = label

    def render(self) -> str:
        """Render the sparkline."""
        if not self._data:
            return f"[dim]{self._label}: No data[/]" if self._label else "[dim]No data[/]"

        # Normalize data to 0-8 range for block selection
        range_val = self.max_val - self.min_val
        if range_val == 0:
            range_val = 1

        # Take last N values based on width
        display_data = self._data[-self._width:]

        # Build sparkline string
        bars = []
        for val in display_data:
            # Clamp value to range
            clamped = max(self.min_val, min(self.max_val, val))
            # Normalize to 0-8
            normalized = int((clamped - self.min_val) / range_val * 8)
            bars.append(self.BLOCKS[normalized])

        sparkline = "".join(bars)

        # Get color based on current value
        current_val = self._data[-1] if self._data else 0
        val_color = self._get_value_color(current_val)

        # Format output
        parts = []

        if self._label:
            parts.append(f"[bold]{self._label}[/]")

        parts.append(f"[{self.color}]{sparkline}[/]")

        if self._show_value:
            parts.append(f"[{val_color}]{current_val:.1f}[/]")

        return " ".join(parts)

    def _get_value_color(self, value: float) -> str:
        """Get color based on value threshold."""
        pct = (value - self.min_val) / (self.max_val - self.min_val) * 100

        if pct < 50:
            return "green"
        elif pct < 80:
            return "yellow"
        else:
            return "red"

    def push(self, value: float) -> None:
        """Add a new value to the sparkline."""
        self._data.append(value)
        # Keep only last 100 values
        if len(self._data) > 100:
            self._data = self._data[-100:]
        self.refresh()

    def set_data(self, data: list[float]) -> None:
        """Set the full data list."""
        self._data = data[-100:]  # Keep last 100
        self.refresh()

    def clear(self) -> None:
        """Clear all data."""
        self._data = []
        self.refresh()


class MultiSparkline(Widget):
    """Multiple sparklines stacked vertically."""

    DEFAULT_CSS = """
    MultiSparkline {
        height: auto;
        width: 100%;
        padding: 1;
        border: round $surface-lighter;
        background: $surface;
    }

    MultiSparkline .sparkline-row {
        height: 1;
    }
    """

    def __init__(
        self,
        metrics: list[tuple[str, str, float, float]] | None = None,
        width: int = 30,
        **kwargs
    ):
        """Initialize with list of (label, color, min, max) tuples."""
        super().__init__(**kwargs)
        self._metrics = metrics or []
        self._data: dict = {m[0]: [] for m in self._metrics}
        self._width = width

    def render(self) -> str:
        """Render all sparklines."""
        lines = []

        for label, color, min_val, max_val in self._metrics:
            data = self._data.get(label, [])

            if not data:
                lines.append(f"[bold]{label:10}[/] [dim]No data[/]")
                continue

            # Build sparkline
            range_val = max_val - min_val if max_val != min_val else 1
            display_data = data[-self._width:]

            bars = []
            for val in display_data:
                clamped = max(min_val, min(max_val, val))
                normalized = int((clamped - min_val) / range_val * 8)
                bars.append(Sparkline.BLOCKS[normalized])

            sparkline = "".join(bars)
            current = data[-1]

            # Color based on threshold
            pct = (current - min_val) / range_val * 100
            val_color = "green" if pct < 50 else "yellow" if pct < 80 else "red"

            lines.append(
                f"[bold]{label:10}[/] [{color}]{sparkline}[/] [{val_color}]{current:6.1f}[/]"
            )

        return "\n".join(lines)

    def update_metric(self, label: str, value: float) -> None:
        """Update a specific metric with a new value."""
        if label in self._data:
            self._data[label].append(value)
            # Keep last 100 values
            if len(self._data[label]) > 100:
                self._data[label] = self._data[label][-100:]
            self.refresh()

    def set_metric_data(self, label: str, data: list[float]) -> None:
        """Set the full data for a metric."""
        if label in self._data:
            self._data[label] = data[-100:]
            self.refresh()


class MetricCard(Widget):
    """A card showing a metric with sparkline and current value."""

    DEFAULT_CSS = """
    MetricCard {
        height: 5;
        width: 100%;
        padding: 1;
        border: round $surface-lighter;
        background: $surface;
    }

    MetricCard.highlight {
        border: round $primary;
    }

    MetricCard .title {
        text-style: bold;
        color: $accent;
    }

    MetricCard .value {
        text-style: bold;
        text-align: right;
    }

    MetricCard .value.good {
        color: $success;
    }

    MetricCard .value.warning {
        color: $warning;
    }

    MetricCard .value.critical {
        color: $error;
    }
    """

    value = reactive(0.0)

    def __init__(
        self,
        title: str,
        unit: str = "%",
        min_val: float = 0.0,
        max_val: float = 100.0,
        color: str = "primary",
        icon: str = "",
        **kwargs
    ):
        super().__init__(**kwargs)
        self._title = title
        self._unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self._color = color
        self._icon = icon
        self._history: list[float] = []

    def render(self) -> str:
        """Render the metric card."""
        # Calculate percentage for color
        range_val = self.max_val - self.min_val
        pct = (self.value - self.min_val) / range_val * 100 if range_val > 0 else 0

        # Choose color
        if pct < 50:
            val_color = "green"
        elif pct < 80:
            val_color = "yellow"
        else:
            val_color = "red"

        # Build sparkline
        display_data = self._history[-20:]
        if display_data:
            bars = []
            for val in display_data:
                clamped = max(self.min_val, min(self.max_val, val))
                normalized = int((clamped - self.min_val) / range_val * 8) if range_val > 0 else 0
                bars.append(Sparkline.BLOCKS[normalized])
            sparkline = "".join(bars)
        else:
            sparkline = "─" * 20

        # Format output
        icon_str = f"{self._icon} " if self._icon else ""
        return f"""[bold cyan]{icon_str}{self._title}[/]
[{self._color}]{sparkline}[/]
[{val_color} bold]{self.value:.1f}{self._unit}[/]"""

    def update(self, value: float) -> None:
        """Update the metric value."""
        self.value = value
        self._history.append(value)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        self.refresh()

    def set_history(self, data: list[float]) -> None:
        """Set the history data."""
        self._history = data[-100:]
        if self._history:
            self.value = self._history[-1]
        self.refresh()
