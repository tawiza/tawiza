"""Composite dashboards combining multiple charts and metrics."""

import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..ui import ColorGradient, Icons, icon
from .charts import (
    DatasetChart,
    ModelComparisonChart,
    ProgressChart,
    RichChartWrapper,
    SystemMetricsChart,
    TrainingMetricsChart,
)

console = Console()


class TrainingDashboard:
    """Dashboard for monitoring training progress."""

    def __init__(self):
        """Initialize training dashboard."""
        self.metrics_chart = TrainingMetricsChart(width=70, height=15)
        self.progress_chart = ProgressChart()

    def create_layout(
        self,
        job_id: str,
        epochs: list[int],
        train_loss: list[float],
        val_loss: list[float] | None = None,
        train_acc: list[float] | None = None,
        val_acc: list[float] | None = None,
        current_epoch: int = 0,
        total_epochs: int = 10,
        current_lr: float = 0.001,
        status: str = "running",
    ) -> Layout:
        """
        Create complete training dashboard layout.

        Args:
            job_id: Training job ID
            epochs: Epoch numbers
            train_loss: Training loss values
            val_loss: Validation loss values
            train_acc: Training accuracy values
            val_acc: Validation accuracy values
            current_epoch: Current epoch number
            total_epochs: Total number of epochs
            current_lr: Current learning rate
            status: Job status

        Returns:
            Rich Layout with dashboard
        """
        layout = Layout()

        # Main layout split
        layout.split_column(
            Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3)
        )

        # Header
        header_text = Text()
        header_text.append(f"{icon(Icons.BRAIN, 'Training Job')} ", style="cyan")
        header_text.append(job_id, style="bold white")
        header_text.append(" • Status: ", style="dim")
        status_color = "green" if status == "running" else "yellow"
        header_text.append(status.upper(), style=f"bold {status_color}")

        layout["header"].update(Panel(header_text, border_style="cyan"))

        # Body split into charts
        layout["body"].split_row(Layout(name="loss"), Layout(name="accuracy"))

        # Loss chart
        loss_chart = self.metrics_chart.plot_loss_curve(
            epochs, train_loss, val_loss, title="Loss Curve"
        )
        layout["body"]["loss"].update(
            RichChartWrapper.wrap_chart(loss_chart, "Training Loss", "red")
        )

        # Accuracy chart (if available)
        if train_acc:
            acc_chart = self.metrics_chart.plot_accuracy_curve(
                epochs, train_acc, val_acc, title="Accuracy Curve"
            )
            layout["body"]["accuracy"].update(
                RichChartWrapper.wrap_chart(acc_chart, "Training Accuracy", "green")
            )
        else:
            # Show metrics table instead
            metrics_table = Table(show_header=False, box=None)
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="bold white")

            metrics_table.add_row("Current Epoch", f"{current_epoch}/{total_epochs}")
            metrics_table.add_row("Learning Rate", f"{current_lr:.6f}")
            metrics_table.add_row("Train Loss", f"{train_loss[-1]:.4f}" if train_loss else "N/A")
            if val_loss:
                metrics_table.add_row("Val Loss", f"{val_loss[-1]:.4f}")

            layout["body"]["accuracy"].update(
                Panel(metrics_table, title="Current Metrics", border_style="green")
            )

        # Footer with progress
        progress_text = self.progress_chart.create_progress_bar_text(
            current_epoch, total_epochs, width=60, label="Epoch Progress"
        )
        layout["footer"].update(Panel(progress_text, border_style="yellow"))

        return layout

    def display_live(self, update_func, refresh_rate: float = 2.0):
        """
        Display dashboard with live updates.

        Args:
            update_func: Function that returns updated layout
            refresh_rate: Update frequency in seconds
        """
        with Live(update_func(), refresh_per_second=1 / refresh_rate, console=console) as live:
            while True:
                time.sleep(refresh_rate)
                live.update(update_func())


class SystemDashboard:
    """Dashboard for system resource monitoring."""

    def __init__(self):
        """Initialize system dashboard."""
        self.system_chart = SystemMetricsChart(width=60, height=12)

    def create_layout(
        self,
        gpu_usage: list[float],
        gpu_memory: list[float],
        cpu_usage: list[float],
        ram_usage_gb: float,
        ram_total_gb: float,
        gpu_temp: float | None = None,
        services_status: dict[str, bool] | None = None,
    ) -> Layout:
        """
        Create system monitoring dashboard.

        Args:
            gpu_usage: GPU utilization history (last N points)
            gpu_memory: GPU memory usage history
            cpu_usage: CPU usage history
            ram_usage_gb: Current RAM usage in GB
            ram_total_gb: Total RAM in GB
            gpu_temp: GPU temperature (optional)
            services_status: Dictionary of service statuses (optional)

        Returns:
            Rich Layout with dashboard
        """
        layout = Layout()

        # Main split
        layout.split_column(
            Layout(name="header", size=5), Layout(name="charts"), Layout(name="services", size=8)
        )

        # Header with current stats
        stats_table = Table(show_header=False, box=None, expand=True)
        stats_table.add_column(style="cyan", width=20)
        stats_table.add_column(style="bold white", width=15)
        stats_table.add_column(style="cyan", width=20)
        stats_table.add_column(style="bold white", width=15)

        stats_table.add_row(
            icon(Icons.GPU, "GPU Usage"),
            f"{gpu_usage[-1]:.1f}%" if gpu_usage else "N/A",
            icon(Icons.MEMORY, "RAM Usage"),
            f"{ram_usage_gb:.1f}/{ram_total_gb:.1f} GB",
        )
        stats_table.add_row(
            icon(Icons.SYSTEM, "CPU Usage"),
            f"{cpu_usage[-1]:.1f}%" if cpu_usage else "N/A",
            icon(Icons.FIRE, "GPU Temp"),
            f"{gpu_temp:.1f}°C" if gpu_temp else "N/A",
        )

        layout["header"].update(Panel(stats_table, title="System Status", border_style="cyan"))

        # Charts split
        layout["charts"].split_row(Layout(name="gpu"), Layout(name="cpu"))

        # GPU chart
        timestamps = [str(i) for i in range(len(gpu_usage))]
        gpu_chart = self.system_chart.plot_gpu_usage(
            timestamps, gpu_usage, title="GPU Utilization (Last 60s)"
        )
        layout["charts"]["gpu"].update(RichChartWrapper.wrap_chart(gpu_chart, "GPU", "yellow"))

        # CPU chart
        cpu_chart = self.system_chart.plot_cpu_usage(
            timestamps, cpu_usage, title="CPU Usage (Last 60s)"
        )
        layout["charts"]["cpu"].update(RichChartWrapper.wrap_chart(cpu_chart, "CPU", "blue"))

        # Services status
        if services_status:
            services_table = Table(show_header=False, box=None)
            services_table.add_column("Service", style="white")
            services_table.add_column("Status", justify="right")

            for service, is_running in services_status.items():
                status_icon = Icons.SUCCESS if is_running else Icons.ERROR
                status_text = "Running" if is_running else "Stopped"
                status_style = "green" if is_running else "red"

                services_table.add_row(
                    service, Text(f"{icon(status_icon, status_text)}", style=status_style)
                )

            layout["services"].update(Panel(services_table, title="Services", border_style="cyan"))
        else:
            layout["services"].update(Panel("No service data", border_style="dim"))

        return layout


class ModelComparisonDashboard:
    """Dashboard for comparing multiple models."""

    def __init__(self):
        """Initialize model comparison dashboard."""
        self.comparison_chart = ModelComparisonChart(width=70, height=15)

    def create_layout(
        self,
        model_names: list[str],
        performance_metrics: dict[str, list[float]],
        training_times: list[float],
        model_sizes: list[float],
        metadata: dict[str, list[str]] | None = None,
    ) -> Layout:
        """
        Create model comparison dashboard.

        Args:
            model_names: List of model names
            performance_metrics: Dict of {metric_name: [values]}
            training_times: Training time for each model (hours)
            model_sizes: Model sizes (GB)
            metadata: Optional metadata for each model

        Returns:
            Rich Layout with dashboard
        """
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3), Layout(name="performance"), Layout(name="resources")
        )

        # Header
        header = ColorGradient.create_gradient(
            f"Comparing {len(model_names)} Models", "#FF6B6B", "#4ECDC4"
        )
        layout["header"].update(Panel(header, border_style="cyan"))

        # Performance metrics chart
        perf_chart = self.comparison_chart.plot_performance_comparison(
            model_names, performance_metrics, title="Performance Metrics"
        )
        layout["performance"].update(
            RichChartWrapper.wrap_chart(perf_chart, "Performance", "green")
        )

        # Resource usage
        layout["resources"].split_row(Layout(name="time"), Layout(name="size"))

        # Training time
        time_chart = self.comparison_chart.plot_training_time_comparison(
            model_names, training_times, title="Training Time"
        )
        layout["resources"]["time"].update(
            RichChartWrapper.wrap_chart(time_chart, "Training Time", "yellow")
        )

        # Model size
        size_chart = self.comparison_chart.plot_model_size_comparison(
            model_names, model_sizes, title="Model Size"
        )
        layout["resources"]["size"].update(
            RichChartWrapper.wrap_chart(size_chart, "Model Size", "blue")
        )

        return layout


class DatasetDashboard:
    """Dashboard for dataset visualization and analysis."""

    def __init__(self):
        """Initialize dataset dashboard."""
        self.dataset_chart = DatasetChart(width=60, height=12)

    def create_layout(
        self,
        dataset_name: str,
        class_distribution: dict[str, int],
        split_sizes: dict[str, int],
        total_samples: int,
        features: list[str] | None = None,
    ) -> Layout:
        """
        Create dataset analysis dashboard.

        Args:
            dataset_name: Name of the dataset
            class_distribution: Dict of {class_name: count}
            split_sizes: Dict of {split_name: count}
            total_samples: Total number of samples
            features: List of feature names (optional)

        Returns:
            Rich Layout with dashboard
        """
        layout = Layout()

        layout.split_column(Layout(name="header", size=5), Layout(name="charts"))

        # Header with dataset info
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="bold white")

        info_table.add_row("Dataset", dataset_name)
        info_table.add_row("Total Samples", f"{total_samples:,}")
        info_table.add_row("Classes", str(len(class_distribution)))
        if features:
            info_table.add_row("Features", str(len(features)))

        layout["header"].update(Panel(info_table, title="Dataset Info", border_style="cyan"))

        # Charts
        layout["charts"].split_row(Layout(name="classes"), Layout(name="splits"))

        # Class distribution
        class_chart = self.dataset_chart.plot_class_distribution(
            list(class_distribution.keys()),
            list(class_distribution.values()),
            title="Class Distribution",
        )
        layout["charts"]["classes"].update(
            RichChartWrapper.wrap_chart(class_chart, "Classes", "blue")
        )

        # Data split
        split_chart = self.dataset_chart.plot_data_split(
            list(split_sizes.keys()), list(split_sizes.values()), title="Data Split"
        )
        layout["charts"]["splits"].update(
            RichChartWrapper.wrap_chart(split_chart, "Splits", "green")
        )

        return layout


class CompactDashboard:
    """Compact single-panel dashboard for quick views."""

    @staticmethod
    def create_metrics_panel(
        title: str, metrics: dict[str, any], border_style: str = "cyan"
    ) -> Panel:
        """
        Create compact metrics panel.

        Args:
            title: Panel title
            metrics: Dictionary of metric names and values
            border_style: Border color

        Returns:
            Rich Panel with metrics
        """
        table = Table(show_header=False, box=None, expand=True)
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="bold white")

        for key, value in metrics.items():
            # Format value based on type
            if isinstance(value, float):
                formatted_value = f"{value:.4f}"
            elif isinstance(value, int):
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)

            table.add_row(key, formatted_value)

        return Panel(table, title=title, border_style=border_style)

    @staticmethod
    def create_status_grid(items: dict[str, tuple[str, str]], title: str = "Status") -> Panel:
        """
        Create compact status grid.

        Args:
            items: Dict of {name: (status, color)}
            title: Panel title

        Returns:
            Rich Panel with status grid
        """
        table = Table(show_header=False, box=None, expand=True)
        table.add_column("Item", style="white", width=25)
        table.add_column("Status", justify="right")

        for name, (status, color) in items.items():
            status_text = Text(status, style=f"bold {color}")
            table.add_row(name, status_text)

        return Panel(table, title=title, border_style="cyan")
