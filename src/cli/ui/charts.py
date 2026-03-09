"""Specialized chart types for ML metrics and system monitoring."""


import plotext as plt
from rich.panel import Panel
from rich.table import Table

from .graphs import BarGraph, LineGraph


class TrainingMetricsChart:
    """Charts specifically for training metrics visualization."""

    def __init__(self, width: int = 80, height: int = 20):
        """Initialize training metrics chart."""
        self.width = width
        self.height = height

    def plot_loss_curve(
        self,
        epochs: list[int],
        train_loss: list[float],
        val_loss: list[float] | None = None,
        title: str = "Training Loss"
    ) -> str:
        """
        Plot training and validation loss curves.

        Args:
            epochs: Epoch numbers
            train_loss: Training loss values
            val_loss: Validation loss values (optional)
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        if val_loss:
            data = {
                "Train Loss": (epochs, train_loss),
                "Val Loss": (epochs, val_loss)
            }
            return graph.plot_multiple(
                data,
                title=title,
                xlabel="Epoch",
                ylabel="Loss"
            )
        else:
            return graph.plot(
                epochs,
                train_loss,
                title=title,
                xlabel="Epoch",
                ylabel="Loss",
                color="error"
            )

    def plot_accuracy_curve(
        self,
        epochs: list[int],
        train_acc: list[float],
        val_acc: list[float] | None = None,
        title: str = "Training Accuracy"
    ) -> str:
        """
        Plot training and validation accuracy curves.

        Args:
            epochs: Epoch numbers
            train_acc: Training accuracy values
            val_acc: Validation accuracy values (optional)
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        if val_acc:
            data = {
                "Train Acc": (epochs, train_acc),
                "Val Acc": (epochs, val_acc)
            }
            return graph.plot_multiple(
                data,
                title=title,
                xlabel="Epoch",
                ylabel="Accuracy (%)"
            )
        else:
            return graph.plot(
                epochs,
                train_acc,
                title=title,
                xlabel="Epoch",
                ylabel="Accuracy (%)",
                color="success"
            )

    def plot_learning_rate(
        self,
        steps: list[int],
        learning_rates: list[float],
        title: str = "Learning Rate Schedule"
    ) -> str:
        """
        Plot learning rate schedule.

        Args:
            steps: Training steps
            learning_rates: Learning rate values
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)
        return graph.plot(
            steps,
            learning_rates,
            title=title,
            xlabel="Step",
            ylabel="Learning Rate",
            color="warning"
        )

    def plot_metrics_comparison(
        self,
        metrics: dict[str, float],
        title: str = "Model Metrics"
    ) -> str:
        """
        Plot multiple metrics as bar chart.

        Args:
            metrics: Dictionary of metric names and values
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)
        labels = list(metrics.keys())
        values = list(metrics.values())

        return graph.plot(
            labels,
            values,
            title=title,
            ylabel="Score",
            color="primary",
            horizontal=True
        )


class SystemMetricsChart:
    """Charts for system resource monitoring."""

    def __init__(self, width: int = 60, height: int = 15):
        """Initialize system metrics chart."""
        self.width = width
        self.height = height

    def plot_gpu_usage(
        self,
        timestamps: list[str],
        usage_percent: list[float],
        title: str = "GPU Utilization"
    ) -> str:
        """
        Plot GPU usage over time.

        Args:
            timestamps: Time points
            usage_percent: GPU usage percentages
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        # Convert timestamps to indices for plotting
        x_data = list(range(len(timestamps)))

        return graph.plot(
            x_data,
            usage_percent,
            title=title,
            xlabel="Time",
            ylabel="Usage (%)",
            color="accent"
        )

    def plot_memory_usage(
        self,
        timestamps: list[str],
        memory_gb: list[float],
        total_gb: float,
        title: str = "Memory Usage"
    ) -> str:
        """
        Plot memory usage over time.

        Args:
            timestamps: Time points
            memory_gb: Memory usage in GB
            total_gb: Total memory capacity
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        x_data = list(range(len(timestamps)))

        # Add threshold line for total memory
        plt.hline(total_gb, color="red")

        return graph.plot(
            x_data,
            memory_gb,
            title=f"{title} (Total: {total_gb:.1f} GB)",
            xlabel="Time",
            ylabel="Memory (GB)",
            color="warning"
        )

    def plot_cpu_usage(
        self,
        timestamps: list[str],
        cpu_percent: list[float],
        title: str = "CPU Usage"
    ) -> str:
        """
        Plot CPU usage over time.

        Args:
            timestamps: Time points
            cpu_percent: CPU usage percentages
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        x_data = list(range(len(timestamps)))

        return graph.plot(
            x_data,
            cpu_percent,
            title=title,
            xlabel="Time",
            ylabel="Usage (%)",
            color="info"
        )

    def plot_multi_gpu(
        self,
        timestamps: list[str],
        gpu_data: dict[str, list[float]],
        title: str = "Multi-GPU Utilization"
    ) -> str:
        """
        Plot multiple GPU usage curves.

        Args:
            timestamps: Time points
            gpu_data: Dictionary of {gpu_name: usage_values}
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = LineGraph(self.width, self.height)

        x_data = list(range(len(timestamps)))

        # Convert to format expected by plot_multiple
        data = {}
        for gpu_name, usage in gpu_data.items():
            data[gpu_name] = (x_data, usage)

        return graph.plot_multiple(
            data,
            title=title,
            xlabel="Time",
            ylabel="Usage (%)"
        )


class ModelComparisonChart:
    """Charts for comparing multiple models."""

    def __init__(self, width: int = 80, height: int = 20):
        """Initialize model comparison chart."""
        self.width = width
        self.height = height

    def plot_performance_comparison(
        self,
        model_names: list[str],
        metrics: dict[str, list[float]],
        title: str = "Model Performance Comparison"
    ) -> str:
        """
        Plot grouped bar chart comparing models across metrics.

        Args:
            model_names: List of model names
            metrics: Dictionary of {metric_name: [values for each model]}
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        return graph.plot_grouped(
            model_names,
            metrics,
            title=title,
            xlabel="Model",
            ylabel="Score"
        )

    def plot_training_time_comparison(
        self,
        model_names: list[str],
        training_hours: list[float],
        title: str = "Training Time Comparison"
    ) -> str:
        """
        Plot training time comparison.

        Args:
            model_names: List of model names
            training_hours: Training time in hours for each model
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        return graph.plot(
            model_names,
            training_hours,
            title=title,
            ylabel="Hours",
            color="warning",
            horizontal=True
        )

    def plot_model_size_comparison(
        self,
        model_names: list[str],
        sizes_gb: list[float],
        title: str = "Model Size Comparison"
    ) -> str:
        """
        Plot model size comparison.

        Args:
            model_names: List of model names
            sizes_gb: Model sizes in GB
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        return graph.plot(
            model_names,
            sizes_gb,
            title=title,
            ylabel="Size (GB)",
            color="info",
            horizontal=False
        )


class DatasetChart:
    """Charts for dataset visualization."""

    def __init__(self, width: int = 60, height: int = 15):
        """Initialize dataset chart."""
        self.width = width
        self.height = height

    def plot_class_distribution(
        self,
        class_names: list[str],
        counts: list[int],
        title: str = "Class Distribution"
    ) -> str:
        """
        Plot class distribution as bar chart.

        Args:
            class_names: List of class names
            counts: Sample counts for each class
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        return graph.plot(
            class_names,
            counts,
            title=title,
            ylabel="Samples",
            color="primary",
            horizontal=True
        )

    def plot_data_split(
        self,
        split_names: list[str],
        sizes: list[int],
        title: str = "Dataset Split"
    ) -> str:
        """
        Plot dataset split (train/val/test).

        Args:
            split_names: Split names (e.g., ["Train", "Val", "Test"])
            sizes: Number of samples in each split
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        return graph.plot(
            split_names,
            sizes,
            title=title,
            ylabel="Samples",
            color="success"
        )


class ProgressChart:
    """Charts for showing progress and status."""

    def __init__(self, width: int = 40, height: int = 10):
        """Initialize progress chart."""
        self.width = width
        self.height = height

    def plot_job_timeline(
        self,
        job_names: list[str],
        start_times: list[int],
        durations: list[int],
        title: str = "Job Timeline"
    ) -> str:
        """
        Plot job timeline (Gantt-style).

        Args:
            job_names: List of job names
            start_times: Start times (relative)
            durations: Duration of each job
            title: Chart title

        Returns:
            Rendered chart
        """
        graph = BarGraph(self.width, self.height)

        # Create horizontal bar chart
        # Each bar starts at start_time and has length duration
        [s + d for s, d in zip(start_times, durations, strict=False)]

        graph.configure_plot(title, xlabel="Time", ylabel="")

        for _i, (name, _start, duration) in enumerate(zip(job_names, start_times, durations, strict=False)):
            plt.bar(
                [name],
                [duration],
                orientation='h',
                color="cyan"
            )

        return graph.render()

    def create_progress_bar_text(
        self,
        current: int,
        total: int,
        width: int = 40,
        label: str = "Progress"
    ) -> str:
        """
        Create text-based progress bar.

        Args:
            current: Current value
            total: Total value
            width: Bar width in characters
            label: Progress label

        Returns:
            Formatted progress bar string
        """
        percentage = (current / total) * 100 if total > 0 else 0
        filled = int((current / total) * width) if total > 0 else 0
        bar = "█" * filled + "░" * (width - filled)

        return f"{label}: [{bar}] {percentage:.1f}% ({current}/{total})"


# Rich integration for better terminal output
class RichChartWrapper:
    """Wrapper to display charts with Rich panels."""

    @staticmethod
    def wrap_chart(chart: str, title: str = "", border_style: str = "cyan") -> Panel:
        """
        Wrap chart in Rich panel.

        Args:
            chart: Chart string
            title: Panel title
            border_style: Border color

        Returns:
            Rich Panel with chart
        """
        return Panel(
            chart,
            title=title,
            border_style=border_style,
            padding=(1, 2)
        )

    @staticmethod
    def create_chart_table(charts: list[tuple[str, str]]) -> Table:
        """
        Create table with multiple charts side by side.

        Args:
            charts: List of (title, chart_string) tuples

        Returns:
            Rich Table with charts
        """
        table = Table(show_header=False, box=None, padding=(0, 1))

        for _ in charts:
            table.add_column()

        # Add charts as row
        table.add_row(*[Panel(chart, title=title, border_style="cyan")
                        for title, chart in charts])

        return table
