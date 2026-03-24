"""Enhanced metrics commands for Tawiza CLI v2 pro.

Provides comprehensive metrics collection and visualization including:
- GPU metrics (utilization, memory, temperature)
- System metrics (CPU, RAM, disk)
- Agent metrics (tasks, success rate, avg duration)
- Model metrics (inference time, token throughput)
"""

import json
import time
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.spinners import ProgressBar
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()

# Metrics storage file
METRICS_FILE = Path.home() / ".tawiza" / "metrics_history.json"


def collect_gpu_metrics() -> dict:
    """Collect GPU metrics using rocm-smi."""
    metrics = {
        "available": False,
        "utilization": 0,
        "memory_used": 0,
        "memory_total": 0,
        "temperature": 0,
    }

    try:
        import subprocess

        result = subprocess.run(
            ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--showtemp", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            metrics["available"] = True

            # Extract metrics from JSON (format varies by rocm-smi version)
            for _card_id, card_data in data.items():
                if isinstance(card_data, dict):
                    if "GPU use (%)" in card_data:
                        metrics["utilization"] = float(card_data["GPU use (%)"].rstrip("%"))
                    if "GPU memory use (%)" in card_data:
                        metrics["memory_percent"] = float(
                            card_data["GPU memory use (%)"].rstrip("%")
                        )
                    if "Temperature (Sensor edge) (C)" in card_data:
                        metrics["temperature"] = float(card_data["Temperature (Sensor edge) (C)"])
                    break  # Only first GPU for now

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    except Exception:
        pass

    return metrics


def collect_system_metrics() -> dict:
    """Collect system metrics using psutil."""
    metrics = {
        "cpu_percent": 0,
        "memory_percent": 0,
        "memory_used_gb": 0,
        "memory_total_gb": 0,
        "disk_percent": 0,
        "disk_used_gb": 0,
        "disk_total_gb": 0,
    }

    try:
        import psutil

        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)

        mem = psutil.virtual_memory()
        metrics["memory_percent"] = mem.percent
        metrics["memory_used_gb"] = mem.used / (1024**3)
        metrics["memory_total_gb"] = mem.total / (1024**3)

        disk = psutil.disk_usage("/")
        metrics["disk_percent"] = disk.percent
        metrics["disk_used_gb"] = disk.used / (1024**3)
        metrics["disk_total_gb"] = disk.total / (1024**3)

    except ImportError:
        pass

    return metrics


def collect_agent_metrics() -> dict:
    """Collect agent execution metrics from task history."""
    metrics = {
        "total_tasks": 0,
        "completed_tasks": 0,
        "failed_tasks": 0,
        "success_rate": 0,
        "avg_duration_seconds": 0,
        "avg_iterations": 0,
    }

    tasks_file = Path.home() / ".tawiza" / "agent_tasks.json"
    if tasks_file.exists():
        try:
            tasks = json.loads(tasks_file.read_text())
            metrics["total_tasks"] = len(tasks)

            completed = [t for t in tasks.values() if t.get("status") == "completed"]
            failed = [t for t in tasks.values() if t.get("status") == "failed"]

            metrics["completed_tasks"] = len(completed)
            metrics["failed_tasks"] = len(failed)

            if metrics["total_tasks"] > 0:
                metrics["success_rate"] = (len(completed) / metrics["total_tasks"]) * 100

            # Calculate average duration
            durations = []
            iterations = []
            for task in tasks.values():
                if task.get("duration"):
                    durations.append(task["duration"])
                if task.get("iterations"):
                    iterations.append(task["iterations"])

            if durations:
                metrics["avg_duration_seconds"] = sum(durations) / len(durations)
            if iterations:
                metrics["avg_iterations"] = sum(iterations) / len(iterations)

        except Exception:
            pass

    return metrics


def collect_model_metrics() -> dict:
    """Collect model inference metrics."""
    metrics = {
        "models_loaded": 0,
        "total_inferences": 0,
        "avg_tokens_per_second": 0,
    }

    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            metrics["models_loaded"] = len(data.get("models", []))
    except Exception:
        pass

    return metrics


def register(app: typer.Typer) -> None:
    """Register metrics commands."""

    @app.command("metrics")
    def show_metrics(
        category: str | None = typer.Option(
            None, "--category", "-c", help="Filter: gpu, system, agent, model"
        ),
        json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    ):
        """Show comprehensive system and agent metrics."""
        console.print(header("metrics", 60))

        all_metrics = {
            "timestamp": datetime.now().isoformat(),
            "gpu": collect_gpu_metrics(),
            "system": collect_system_metrics(),
            "agent": collect_agent_metrics(),
            "model": collect_model_metrics(),
        }

        if json_output:
            console.print(json.dumps(all_metrics, indent=2))
            console.print(footer(60))
            return

        # GPU Metrics
        if not category or category == "gpu":
            console.print(f"\n  [bold {THEME['accent']}]GPU Metrics[/]")
            console.print()

            gpu = all_metrics["gpu"]
            if gpu["available"]:
                bar = ProgressBar(width=20)

                console.print(
                    f"    Utilization   {bar.render(gpu.get('utilization', 0) / 100)}  {gpu.get('utilization', 0):.1f}%"
                )
                if "memory_percent" in gpu:
                    console.print(
                        f"    Memory        {bar.render(gpu.get('memory_percent', 0) / 100)}  {gpu.get('memory_percent', 0):.1f}%"
                    )
                if gpu.get("temperature"):
                    temp_color = (
                        "green"
                        if gpu["temperature"] < 70
                        else "yellow"
                        if gpu["temperature"] < 85
                        else "red"
                    )
                    console.print(f"    Temperature   [{temp_color}]{gpu['temperature']:.0f}°C[/]")
            else:
                console.print("    [dim]GPU not available[/]")

        # System Metrics
        if not category or category == "system":
            console.print(f"\n  [bold {THEME['accent']}]System Metrics[/]")
            console.print()

            sys = all_metrics["system"]
            bar = ProgressBar(width=20)

            console.print(
                f"    CPU           {bar.render(sys['cpu_percent'] / 100)}  {sys['cpu_percent']:.1f}%"
            )
            console.print(
                f"    Memory        {bar.render(sys['memory_percent'] / 100)}  {sys['memory_used_gb']:.1f}/{sys['memory_total_gb']:.1f} GB"
            )
            console.print(
                f"    Disk          {bar.render(sys['disk_percent'] / 100)}  {sys['disk_used_gb']:.0f}/{sys['disk_total_gb']:.0f} GB"
            )

        # Agent Metrics
        if not category or category == "agent":
            console.print(f"\n  [bold {THEME['accent']}]Agent Metrics[/]")
            console.print()

            agent = all_metrics["agent"]
            console.print(f"    Total Tasks       {agent['total_tasks']}")
            console.print(f"    Completed         {agent['completed_tasks']}")
            console.print(f"    Failed            {agent['failed_tasks']}")

            if agent["total_tasks"] > 0:
                success_color = (
                    "green"
                    if agent["success_rate"] > 80
                    else "yellow"
                    if agent["success_rate"] > 50
                    else "red"
                )
                console.print(
                    f"    Success Rate      [{success_color}]{agent['success_rate']:.1f}%[/]"
                )

            if agent["avg_duration_seconds"] > 0:
                console.print(f"    Avg Duration      {agent['avg_duration_seconds']:.1f}s")
            if agent["avg_iterations"] > 0:
                console.print(f"    Avg Iterations    {agent['avg_iterations']:.1f}")

        # Model Metrics
        if not category or category == "model":
            console.print(f"\n  [bold {THEME['accent']}]Model Metrics[/]")
            console.print()

            model = all_metrics["model"]
            console.print(f"    Models Loaded     {model['models_loaded']}")

        console.print()
        console.print(footer(60))

    @app.command("metrics-live")
    def live_metrics(
        interval: int = typer.Option(2, "--interval", "-i", help="Refresh interval (seconds)"),
        duration: int = typer.Option(120, "--duration", "-d", help="Duration (seconds)"),
    ):
        """Live updating metrics dashboard."""

        def build_metrics_layout() -> Layout:
            """Build the metrics dashboard layout."""
            layout = Layout()

            layout.split_column(
                Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3)
            )

            # Header
            header_text = Text()
            header_text.append("Live Metrics", style="bold cyan")
            header_text.append(f"  |  {time.strftime('%H:%M:%S')}", style="dim")
            layout["header"].update(Panel(header_text, border_style="cyan"))

            # Body with GPU and System metrics
            layout["body"].split_row(
                Layout(name="gpu"), Layout(name="system"), Layout(name="agents")
            )

            # GPU Panel
            gpu = collect_gpu_metrics()
            gpu_table = Table(show_header=False, box=None, expand=True)
            gpu_table.add_column("Metric", style="cyan")
            gpu_table.add_column("Value", justify="right")

            if gpu["available"]:
                gpu_table.add_row("Utilization", f"{gpu.get('utilization', 0):.1f}%")
                gpu_table.add_row("Memory", f"{gpu.get('memory_percent', 0):.1f}%")
                if gpu.get("temperature"):
                    gpu_table.add_row("Temp", f"{gpu['temperature']:.0f}°C")
            else:
                gpu_table.add_row("Status", "N/A")

            layout["body"]["gpu"].update(Panel(gpu_table, title="GPU", border_style="yellow"))

            # System Panel
            sys = collect_system_metrics()
            sys_table = Table(show_header=False, box=None, expand=True)
            sys_table.add_column("Metric", style="cyan")
            sys_table.add_column("Value", justify="right")

            sys_table.add_row("CPU", f"{sys['cpu_percent']:.1f}%")
            sys_table.add_row("RAM", f"{sys['memory_percent']:.1f}%")
            sys_table.add_row("Disk", f"{sys['disk_percent']:.1f}%")

            layout["body"]["system"].update(Panel(sys_table, title="System", border_style="blue"))

            # Agents Panel
            agent = collect_agent_metrics()
            agent_table = Table(show_header=False, box=None, expand=True)
            agent_table.add_column("Metric", style="cyan")
            agent_table.add_column("Value", justify="right")

            agent_table.add_row("Tasks", str(agent["total_tasks"]))
            agent_table.add_row("Success", f"{agent['success_rate']:.0f}%")
            agent_table.add_row("Avg Time", f"{agent['avg_duration_seconds']:.1f}s")

            layout["body"]["agents"].update(
                Panel(agent_table, title="Agents", border_style="green")
            )

            # Footer
            footer_text = Text()
            footer_text.append("Press Ctrl+C to exit", style="dim")
            layout["footer"].update(Panel(footer_text, border_style="dim"))

            return layout

        console.print("[cyan]Starting live metrics...[/]")

        try:
            start_time = time.time()
            with Live(build_metrics_layout(), refresh_per_second=1, console=console) as live:
                while time.time() - start_time < duration:
                    time.sleep(interval)
                    live.update(build_metrics_layout())
        except KeyboardInterrupt:
            pass

        console.print("\n[dim]Metrics stopped.[/]")

    @app.command("metrics-history")
    def metrics_history(
        limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show"),
        export_file: Path | None = typer.Option(None, "--export", "-e", help="Export to file"),
    ):
        """Show metrics history over time."""
        console.print(header("metrics history", 60))

        if not METRICS_FILE.exists():
            console.print("  [dim]No metrics history found.[/]")
            console.print("  [dim]History is recorded during live monitoring.[/]")
            console.print(footer(60))
            return

        try:
            history = json.loads(METRICS_FILE.read_text())
            entries = history.get("entries", [])

            if not entries:
                console.print("  [dim]No entries recorded yet.[/]")
                console.print(footer(60))
                return

            # Show recent entries
            recent = entries[-limit:]

            table = Table(
                show_header=True,
                header_style=f"bold {THEME['accent']}",
            )
            table.add_column("Time", style="dim")
            table.add_column("CPU", justify="right")
            table.add_column("RAM", justify="right")
            table.add_column("GPU", justify="right")
            table.add_column("Tasks", justify="right")

            for entry in recent:
                table.add_row(
                    entry.get("timestamp", "")[:19],
                    f"{entry.get('system', {}).get('cpu_percent', 0):.1f}%",
                    f"{entry.get('system', {}).get('memory_percent', 0):.1f}%",
                    f"{entry.get('gpu', {}).get('utilization', 0):.1f}%",
                    str(entry.get("agent", {}).get("total_tasks", 0)),
                )

            console.print(table)

            if export_file:
                export_file.parent.mkdir(parents=True, exist_ok=True)
                export_file.write_text(json.dumps(entries, indent=2))
                console.print(f"\n  [green]Exported to {export_file}[/]")

        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(60))

    @app.command("metrics-record")
    def record_metrics(
        interval: int = typer.Option(60, "--interval", "-i", help="Recording interval (seconds)"),
        duration: int = typer.Option(3600, "--duration", "-d", help="Recording duration (seconds)"),
    ):
        """Record metrics to history file for later analysis."""
        console.print(header("record metrics", 50))
        console.print(f"  Recording every {interval}s for {duration // 60} minutes")
        console.print("  Press Ctrl+C to stop\n")

        # Load or create history
        history = json.loads(METRICS_FILE.read_text()) if METRICS_FILE.exists() else {"entries": []}

        try:
            start_time = time.time()
            records = 0

            while time.time() - start_time < duration:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "gpu": collect_gpu_metrics(),
                    "system": collect_system_metrics(),
                    "agent": collect_agent_metrics(),
                }

                history["entries"].append(entry)
                records += 1

                # Keep last 1000 entries
                if len(history["entries"]) > 1000:
                    history["entries"] = history["entries"][-1000:]

                METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
                METRICS_FILE.write_text(json.dumps(history))

                console.print(f"  [{time.strftime('%H:%M:%S')}] Recorded #{records}", style="dim")
                time.sleep(interval)

        except KeyboardInterrupt:
            pass

        msg = MessageBox()
        console.print(msg.success(f"Recorded {records} entries"))
        console.print(footer(50))
