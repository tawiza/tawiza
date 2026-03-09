#!/usr/bin/env python3
"""
Live Dashboard pour CLI Tawiza-V2
Dashboards temps réel avec auto-refresh et multi-panels
"""

import contextlib
import time
from dataclasses import dataclass
from datetime import datetime

import psutil
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()


# ===== DATA PROVIDERS =====

@dataclass
class SystemMetrics:
    """Métriques système"""
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float

    @staticmethod
    def collect() -> 'SystemMetrics':
        """Collecter les métriques système"""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return SystemMetrics(
            cpu_percent=cpu,
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024**3),
            disk_total_gb=disk.total / (1024**3)
        )


@dataclass
class PerformanceMetrics:
    """Métriques de performance"""
    throughput: float  # tasks/s
    latency: float  # ms
    success_rate: float  # %
    cache_hit_rate: float  # %
    active_tasks: int
    completed_tasks: int
    failed_tasks: int


@dataclass
class AgentStatus:
    """Status d'un agent"""
    name: str
    status: str  # running, idle, error
    tasks_completed: int
    success_rate: float


# ===== DASHBOARD COMPONENTS =====

class DashboardComponents:
    """Composants réutilisables pour dashboards"""

    @staticmethod
    def create_header(title: str, subtitle: str | None = None) -> Panel:
        """Créer un header de dashboard"""
        content = f"[bold cyan]{title}[/]"
        if subtitle:
            content += f"\n[dim]{subtitle}[/]"

        return Panel(
            Align.center(content),
            border_style="cyan",
            box=box.HEAVY
        )

    @staticmethod
    def create_metric_bar(
        label: str,
        value: float,
        max_value: float = 100.0,
        unit: str = "%",
        color: str = "cyan"
    ) -> str:
        """Créer une barre de métrique"""
        percentage = (value / max_value) * 100 if max_value > 0 else 0
        bar_length = 30
        filled = int(bar_length * percentage / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Color based on percentage
        if percentage >= 90:
            bar_color = "red"
        elif percentage >= 75:
            bar_color = "yellow"
        else:
            bar_color = "green"

        return f"[cyan]{label:15}[/] [{bar_color}]{bar}[/] [bold]{value:.1f}{unit}[/]"

    @staticmethod
    def create_status_indicator(status: str) -> str:
        """Créer un indicateur de status"""
        indicators = {
            "running": "[green]● Running[/]",
            "idle": "[yellow]○ Idle[/]",
            "error": "[red]✗ Error[/]",
            "stopped": "[dim]◌ Stopped[/]",
            "starting": "[cyan]◐ Starting[/]",
        }
        return indicators.get(status.lower(), f"[white]? {status}[/]")


# ===== SYSTEM DASHBOARD =====

class SystemDashboard:
    """Dashboard système temps réel"""

    @staticmethod
    def generate(iteration: int = 0) -> Layout:
        """Générer le dashboard système"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        # Header
        timestamp = datetime.now().strftime("%H:%M:%S")
        layout["header"].update(
            DashboardComponents.create_header(
                "System Monitor",
                f"Updated: {timestamp} | Refresh: 1s"
            )
        )

        # Main - split en 2 colonnes
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        # Left: System metrics
        metrics = SystemMetrics.collect()

        left_content = (
            f"{DashboardComponents.create_metric_bar('CPU', metrics.cpu_percent)}\n"
            f"{DashboardComponents.create_metric_bar('Memory', metrics.memory_percent)}\n"
            f"{DashboardComponents.create_metric_bar('Disk', metrics.disk_percent)}\n\n"
            f"[cyan]Memory:[/] {metrics.memory_used_gb:.2f}GB / {metrics.memory_total_gb:.2f}GB\n"
            f"[cyan]Disk:[/] {metrics.disk_used_gb:.1f}GB / {metrics.disk_total_gb:.1f}GB"
        )

        layout["left"].update(Panel(
            left_content,
            title="[bold cyan]System Resources[/]",
            border_style="cyan"
        ))

        # Right: Process info
        process_count = len(psutil.pids())
        cpu_count = psutil.cpu_count()
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        right_content = (
            f"[cyan]CPU Cores:[/] {cpu_count}\n"
            f"[cyan]Processes:[/] {process_count}\n"
            f"[cyan]Boot Time:[/] {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[cyan]Uptime:[/] {uptime.days}d {uptime.seconds//3600}h\n\n"
            f"[bold green]System Status: Healthy ✓[/]"
        )

        layout["right"].update(Panel(
            right_content,
            title="[bold cyan]System Info[/]",
            border_style="cyan"
        ))

        # Footer
        layout["footer"].update(Panel(
            Align.center("[dim]Press Ctrl+C to exit[/]"),
            border_style="dim"
        ))

        return layout

    @staticmethod
    def run(duration: int = 60, refresh_rate: int = 1):
        """Lancer le dashboard en temps réel"""
        console.clear()

        with Live(
            SystemDashboard.generate(0),
            console=console,
            refresh_per_second=refresh_rate,
            screen=False
        ) as live:
            for i in range(duration * refresh_rate):
                time.sleep(1 / refresh_rate)
                live.update(SystemDashboard.generate(i))


# ===== PERFORMANCE DASHBOARD =====

class PerformanceDashboard:
    """Dashboard de performance temps réel"""

    def __init__(self):
        self.metrics_history: list[PerformanceMetrics] = []
        self.max_history = 30

    def add_metrics(self, metrics: PerformanceMetrics):
        """Ajouter des métriques à l'historique"""
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)

    def generate_sparkline(self, values: list[float]) -> str:
        """Générer une sparkline"""
        if not values:
            return ""

        chars = "▁▂▃▄▅▆▇█"
        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            return chars[0] * len(values)

        normalized = [(v - min_val) / (max_val - min_val) for v in values]
        return "".join(chars[min(int(n * 7), 7)] for n in normalized)

    def generate(self, current_metrics: PerformanceMetrics) -> Layout:
        """Générer le dashboard de performance"""
        self.add_metrics(current_metrics)

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        # Header
        timestamp = datetime.now().strftime("%H:%M:%S")
        layout["header"].update(
            DashboardComponents.create_header(
                "Performance Monitor",
                f"Updated: {timestamp}"
            )
        )

        # Main - 2x2 grid
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        layout["left"].split_column(
            Layout(name="top_left"),
            Layout(name="bottom_left")
        )

        layout["right"].split_column(
            Layout(name="top_right"),
            Layout(name="bottom_right")
        )

        # Top Left: Throughput
        throughput_values = [m.throughput for m in self.metrics_history]
        throughput_spark = self.generate_sparkline(throughput_values)

        layout["top_left"].update(Panel(
            f"[bold cyan]{current_metrics.throughput:.1f}[/] tasks/s\n\n"
            f"[green]{throughput_spark}[/]\n\n"
            f"[dim]History (30s)[/]",
            title="[bold cyan]Throughput[/]",
            border_style="cyan"
        ))

        # Top Right: Latency
        latency_values = [m.latency for m in self.metrics_history]
        latency_spark = self.generate_sparkline(latency_values)

        layout["top_right"].update(Panel(
            f"[bold cyan]{current_metrics.latency:.1f}[/] ms\n\n"
            f"[green]{latency_spark}[/]\n\n"
            f"[dim]History (30s)[/]",
            title="[bold cyan]Latency[/]",
            border_style="cyan"
        ))

        # Bottom Left: Success Rate & Cache
        layout["bottom_left"].update(Panel(
            f"[cyan]Success Rate:[/]\n"
            f"[bold green]{current_metrics.success_rate:.1f}%[/]\n\n"
            f"[cyan]Cache Hit Rate:[/]\n"
            f"[bold green]{current_metrics.cache_hit_rate:.1f}%[/]",
            title="[bold cyan]Quality Metrics[/]",
            border_style="cyan"
        ))

        # Bottom Right: Tasks
        total_tasks = current_metrics.active_tasks + current_metrics.completed_tasks + current_metrics.failed_tasks

        layout["bottom_right"].update(Panel(
            f"[cyan]Active:[/] [bold yellow]{current_metrics.active_tasks}[/]\n"
            f"[cyan]Completed:[/] [bold green]{current_metrics.completed_tasks}[/]\n"
            f"[cyan]Failed:[/] [bold red]{current_metrics.failed_tasks}[/]\n"
            f"[cyan]Total:[/] [bold]{total_tasks}[/]",
            title="[bold cyan]Tasks[/]",
            border_style="cyan"
        ))

        # Footer
        layout["footer"].update(Panel(
            Align.center("[dim]Press Ctrl+C to exit[/]"),
            border_style="dim"
        ))

        return layout


# ===== AGENTS DASHBOARD =====

class AgentsDashboard:
    """Dashboard des agents temps réel"""

    @staticmethod
    def generate(agents: list[AgentStatus]) -> Layout:
        """Générer le dashboard des agents"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        # Header
        timestamp = datetime.now().strftime("%H:%M:%S")
        active_count = sum(1 for a in agents if a.status == "running")

        layout["header"].update(
            DashboardComponents.create_header(
                "Agents Monitor",
                f"Active: {active_count}/{len(agents)} | Updated: {timestamp}"
            )
        )

        # Main: Agents table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="cyan", width=20)
        table.add_column("Status", width=15)
        table.add_column("Tasks", justify="right", width=10)
        table.add_column("Success Rate", justify="right", width=15)

        for agent in agents:
            status_indicator = DashboardComponents.create_status_indicator(agent.status)
            success_color = "green" if agent.success_rate >= 90 else ("yellow" if agent.success_rate >= 75 else "red")

            table.add_row(
                agent.name,
                status_indicator,
                str(agent.tasks_completed),
                f"[{success_color}]{agent.success_rate:.1f}%[/]"
            )

        layout["main"].update(Panel(
            table,
            title="[bold cyan]Agent Status[/]",
            border_style="cyan"
        ))

        # Footer
        layout["footer"].update(Panel(
            Align.center("[dim]Press Ctrl+C to exit[/]"),
            border_style="dim"
        ))

        return layout


# ===== DEMO =====

if __name__ == "__main__":
    import random

    console.clear()
    console.print(Panel(
        "[bold cyan]Live Dashboard Demo[/]\n"
        "[dim]Testing real-time dashboards[/]",
        border_style="cyan"
    ))
    console.print()

    # Demo 1: System Dashboard
    console.print("[bold]1. System Dashboard (10 seconds)[/]")
    time.sleep(2)

    with contextlib.suppress(KeyboardInterrupt):
        SystemDashboard.run(duration=10, refresh_rate=2)

    console.print("\n[green]✓ System dashboard demo complete[/]\n")
    time.sleep(1)

    # Demo 2: Performance Dashboard
    console.print("[bold]2. Performance Dashboard (10 seconds)[/]")
    time.sleep(2)

    perf_dash = PerformanceDashboard()

    try:
        with Live(
            perf_dash.generate(PerformanceMetrics(25, 8, 98.5, 92, 4, 150, 3)),
            console=console,
            refresh_per_second=2
        ) as live:
            for i in range(20):
                # Simulate changing metrics
                metrics = PerformanceMetrics(
                    throughput=random.uniform(20, 30),
                    latency=random.uniform(5, 15),
                    success_rate=random.uniform(95, 99),
                    cache_hit_rate=random.uniform(88, 95),
                    active_tasks=random.randint(2, 6),
                    completed_tasks=150 + i * 5,
                    failed_tasks=3 + random.randint(0, 1)
                )
                live.update(perf_dash.generate(metrics))
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    console.print("\n[green]✓ Performance dashboard demo complete[/]\n")
    time.sleep(1)

    # Demo 3: Agents Dashboard
    console.print("[bold]3. Agents Dashboard (10 seconds)[/]")
    time.sleep(2)

    agents = [
        AgentStatus("ML Engineer", "running", 42, 98.2),
        AgentStatus("Data Analyst", "running", 38, 99.1),
        AgentStatus("Code Reviewer", "idle", 12, 97.5),
        AgentStatus("Optimizer", "running", 15, 96.8),
    ]

    try:
        with Live(
            AgentsDashboard.generate(agents),
            console=console,
            refresh_per_second=2
        ) as live:
            for i in range(20):
                # Simulate changing agent status
                for agent in agents:
                    agent.tasks_completed += random.randint(0, 2)
                    agent.success_rate = random.uniform(95, 100)

                live.update(AgentsDashboard.generate(agents))
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    console.print("\n[green]✓ Agents dashboard demo complete[/]\n")

    console.print(Panel(
        "[bold green]All Dashboards Demo Complete![/]",
        border_style="green"
    ))
