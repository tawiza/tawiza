"""Accessibility features for CLI graphs and dashboards."""


from rich.console import Console
from rich.table import Table


class AccessibilityHelper:
    """Provides text alternatives and accessible descriptions for graphs."""

    @staticmethod
    def describe_line_graph(
        x_data: list[float],
        y_data: list[float],
        title: str = "Line Graph",
        xlabel: str = "X",
        ylabel: str = "Y"
    ) -> str:
        """
        Generate text description of line graph for screen readers.

        Args:
            x_data: X-axis data
            y_data: Y-axis data
            title: Graph title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Text description
        """
        if not y_data:
            return f"{title}: No data available"

        min_val = min(y_data)
        max_val = max(y_data)
        avg_val = sum(y_data) / len(y_data)

        # Detect trend
        if y_data[-1] > y_data[0]:
            trend = "increasing"
        elif y_data[-1] < y_data[0]:
            trend = "decreasing"
        else:
            trend = "stable"

        description = f"""
{title}
Data points: {len(y_data)}
{xlabel} range: {x_data[0]} to {x_data[-1]}
{ylabel} range: {min_val:.2f} to {max_val:.2f}
Average: {avg_val:.2f}
Trend: {trend}
Starting value: {y_data[0]:.2f}
Ending value: {y_data[-1]:.2f}
"""
        return description.strip()

    @staticmethod
    def describe_bar_graph(
        labels: list[str],
        values: list[float],
        title: str = "Bar Graph"
    ) -> str:
        """
        Generate text description of bar graph.

        Args:
            labels: Bar labels
            values: Bar values
            title: Graph title

        Returns:
            Text description
        """
        if not values:
            return f"{title}: No data available"

        # Find highest and lowest
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))

        description = f"""
{title}
Number of bars: {len(values)}
Highest: {labels[max_idx]} ({values[max_idx]:.2f})
Lowest: {labels[min_idx]} ({values[min_idx]:.2f})
Average: {sum(values) / len(values):.2f}

Values:
"""
        for label, value in zip(labels, values, strict=False):
            description += f"  - {label}: {value:.2f}\n"

        return description.strip()

    @staticmethod
    def describe_training_metrics(
        epochs: list[int],
        train_loss: list[float],
        val_loss: list[float] | None = None,
        train_acc: list[float] | None = None,
        val_acc: list[float] | None = None
    ) -> str:
        """
        Generate accessible description of training metrics.

        Args:
            epochs: Epoch numbers
            train_loss: Training loss values
            val_loss: Validation loss values (optional)
            train_acc: Training accuracy values (optional)
            val_acc: Validation accuracy values (optional)

        Returns:
            Comprehensive text description
        """
        description = "Training Metrics Summary\n\n"

        # Loss analysis
        if train_loss:
            loss_improvement = ((train_loss[0] - train_loss[-1]) / train_loss[0]) * 100
            description += "Training Loss:\n"
            description += f"  Initial: {train_loss[0]:.4f}\n"
            description += f"  Final: {train_loss[-1]:.4f}\n"
            description += f"  Improvement: {loss_improvement:.1f}%\n"

            if val_loss:
                val_improvement = ((val_loss[0] - val_loss[-1]) / val_loss[0]) * 100
                gap = abs(train_loss[-1] - val_loss[-1])
                description += "\nValidation Loss:\n"
                description += f"  Initial: {val_loss[0]:.4f}\n"
                description += f"  Final: {val_loss[-1]:.4f}\n"
                description += f"  Improvement: {val_improvement:.1f}%\n"
                description += f"  Train-Val Gap: {gap:.4f}\n"

                if gap > 0.5:
                    description += "  Warning: Large gap suggests overfitting\n"

        # Accuracy analysis
        if train_acc:
            acc_improvement = train_acc[-1] - train_acc[0]
            description += "\nTraining Accuracy:\n"
            description += f"  Initial: {train_acc[0]:.1f}%\n"
            description += f"  Final: {train_acc[-1]:.1f}%\n"
            description += f"  Improvement: +{acc_improvement:.1f} percentage points\n"

            if val_acc:
                val_acc_improvement = val_acc[-1] - val_acc[0]
                gap = abs(train_acc[-1] - val_acc[-1])
                description += "\nValidation Accuracy:\n"
                description += f"  Initial: {val_acc[0]:.1f}%\n"
                description += f"  Final: {val_acc[-1]:.1f}%\n"
                description += f"  Improvement: +{val_acc_improvement:.1f} percentage points\n"
                description += f"  Train-Val Gap: {gap:.1f}%\n"

        return description

    @staticmethod
    def create_text_table(
        data: dict[str, float],
        title: str = "Data Table"
    ) -> str:
        """
        Create accessible text table.

        Args:
            data: Dictionary of {label: value}
            title: Table title

        Returns:
            Formatted text table
        """
        console = Console()
        table = Table(title=title, show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white", justify="right")

        for key, value in data.items():
            if isinstance(value, float):
                formatted_value = f"{value:.2f}"
            elif isinstance(value, int):
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)

            table.add_row(key, formatted_value)

        # Capture table as string
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = output = StringIO()

        try:
            console.print(table)
            result = output.getvalue()
        finally:
            sys.stdout = old_stdout

        return result

    @staticmethod
    def announce_metric(
        metric_name: str,
        value: float,
        threshold: float | None = None,
        higher_is_better: bool = True
    ) -> str:
        """
        Generate announcement text for metric updates.

        Args:
            metric_name: Name of metric
            value: Current value
            threshold: Threshold for comparison
            higher_is_better: Whether higher values are better

        Returns:
            Announcement text
        """
        announcement = f"{metric_name}: {value:.2f}"

        if threshold:
            if higher_is_better:
                if value >= threshold:
                    announcement += " (Target reached)"
                else:
                    announcement += f" (Target: {threshold:.2f})"
            else:
                if value <= threshold:
                    announcement += " (Target reached)"
                else:
                    announcement += f" (Target: {threshold:.2f})"

        return announcement


class ColorBlindMode:
    """Color-blind friendly palettes and indicators."""

    @staticmethod
    def get_colorblind_palette():
        """Return color-blind safe palette."""
        return {
            "primary": "blue",      # Distinguishable for all types
            "secondary": "orange",  # Safe alternative
            "success": "green",     # OK for most, use with patterns
            "warning": "yellow",    # Use with black text
            "error": "magenta",     # Distinguishable alternative to red
            "info": "cyan",         # Clear blue variant
        }

    @staticmethod
    def add_pattern_indicators(value: float, threshold: float = 0) -> str:
        """
        Add text-based indicators in addition to color.

        Args:
            value: Numeric value
            threshold: Threshold for comparison

        Returns:
            Indicator symbol
        """
        if value > threshold:
            return "↑"  # Up arrow
        elif value < threshold:
            return "↓"  # Down arrow
        else:
            return "→"  # Right arrow

    @staticmethod
    def format_status_with_symbol(status: str) -> str:
        """
        Add symbols to status for non-color identification.

        Args:
            status: Status string

        Returns:
            Status with symbol
        """
        symbols = {
            "running": "▶",
            "completed": "✓",
            "failed": "✗",
            "pending": "○",
            "stopped": "■"
        }

        symbol = symbols.get(status.lower(), "•")
        return f"{symbol} {status.upper()}"


class TerminalAccessibility:
    """Terminal-specific accessibility features."""

    @staticmethod
    def supports_unicode() -> bool:
        """Check if terminal supports Unicode."""
        import locale

        encoding = locale.getpreferredencoding()
        return 'utf' in encoding.lower()

    @staticmethod
    def get_safe_characters() -> dict[str, str]:
        """
        Get character set safe for current terminal.

        Returns:
            Dictionary of character mappings
        """
        if TerminalAccessibility.supports_unicode():
            return {
                "bar_full": "█",
                "bar_empty": "░",
                "bullet": "●",
                "arrow_up": "↑",
                "arrow_down": "↓",
                "check": "✓",
                "cross": "✗",
            }
        else:
            # ASCII fallback
            return {
                "bar_full": "#",
                "bar_empty": "-",
                "bullet": "*",
                "arrow_up": "^",
                "arrow_down": "v",
                "check": "+",
                "cross": "x",
            }

    @staticmethod
    def is_screen_reader_active() -> bool:
        """
        Detect if a screen reader might be active.

        Returns:
            True if screen reader detected
        """
        import os

        # Check for common screen reader environment variables
        screen_reader_vars = [
            'SCREEN_READER',
            'BRLTTY_PID',
            'ORCA_ENABLED'
        ]

        return any(os.environ.get(var) for var in screen_reader_vars)

    @staticmethod
    def should_use_text_mode() -> bool:
        """
        Determine if text-only mode should be used.

        Returns:
            True if text mode should be preferred
        """
        import os

        # Check for accessibility flags
        if os.environ.get('TAWIZA_TEXT_MODE') == '1':
            return True

        if os.environ.get('NO_COLOR') == '1':
            return True

        return bool(TerminalAccessibility.is_screen_reader_active())


# Global configuration
ACCESSIBILITY_CONFIG = {
    "enable_descriptions": True,
    "enable_announcements": True,
    "use_colorblind_palette": False,
    "text_mode": TerminalAccessibility.should_use_text_mode(),
    "verbose_output": False,
}


def set_accessibility_mode(
    text_mode: bool = False,
    colorblind_mode: bool = False,
    verbose: bool = False
):
    """
    Configure accessibility settings.

    Args:
        text_mode: Use text descriptions instead of graphs
        colorblind_mode: Use color-blind safe palette
        verbose: Provide detailed descriptions
    """
    ACCESSIBILITY_CONFIG["text_mode"] = text_mode
    ACCESSIBILITY_CONFIG["use_colorblind_palette"] = colorblind_mode
    ACCESSIBILITY_CONFIG["verbose_output"] = verbose
