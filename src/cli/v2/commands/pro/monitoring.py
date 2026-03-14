"""Monitoring commands for Tawiza CLI v2 pro."""

import time
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.spinners import WaveSpinner
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()


def register(app: typer.Typer) -> None:
    """Register monitoring commands."""

    @app.command("gpu-monitor")
    def gpu_monitor(
        interval: int = typer.Option(2, "--interval", "-i", help="Update interval (seconds)"),
        duration: int = typer.Option(60, "--duration", "-d", help="Duration (seconds)"),
    ):
        """Real-time GPU monitoring."""
        console.print(header("gpu monitor", 40))

        spinner = WaveSpinner()
        start_time = time.time()

        try:
            while time.time() - start_time < duration:
                console.clear()
                console.print(header("gpu monitor", 40))
                console.print(f"         {spinner.next()}")
                console.print()

                # Get GPU stats
                try:
                    import subprocess

                    result = subprocess.run(
                        ["rocm-smi", "--showuse", "--showtemp", "--showmeminfo", "vram"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if result.returncode == 0:
                        # Parse output for key metrics
                        lines = result.stdout.strip().split("\n")
                        for line in lines[:15]:  # Limit output
                            console.print(f"  {line}")
                    else:
                        console.print("  [dim]GPU data unavailable[/]")

                except Exception as e:
                    console.print(f"  [dim]Error: {e}[/]")

                elapsed = int(time.time() - start_time)
                remaining = duration - elapsed
                console.print()
                console.print(f"  [dim]Elapsed: {elapsed}s | Remaining: {remaining}s[/]")
                console.print("  [dim]Press Ctrl+C to stop[/]")
                console.print(footer(40))

                time.sleep(interval)

        except KeyboardInterrupt:
            pass

        console.print()
        console.print("  [dim]Monitoring stopped.[/]")
        console.print(footer(40))

    @app.command("logs-show")
    def logs_show(
        lines: int = typer.Option(50, "--lines", "-n", help="Number of lines"),
        follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
        level: str | None = typer.Option(None, "--level", "-l", help="Filter by level"),
    ):
        """Show application logs."""
        console.print(header("logs", 40))

        from src.cli.v2.utils.config import get_logs_dir

        log_file = get_logs_dir() / "tawiza.log"

        if not log_file.exists():
            console.print("  [dim]No logs found.[/]")
            console.print("  [dim]Logs will appear after using the CLI.[/]")
            console.print(footer(40))
            return

        try:
            with open(log_file) as f:
                all_lines = f.readlines()

            # Filter by level if specified
            if level:
                level = level.upper()
                all_lines = [l for l in all_lines if level in l]

            # Get last N lines
            display_lines = all_lines[-lines:]

            for line in display_lines:
                line = line.strip()
                if "ERROR" in line:
                    console.print(f"  [{THEME['error']}]{line}[/]")
                elif "WARNING" in line:
                    console.print(f"  [{THEME['warning']}]{line}[/]")
                elif "INFO" in line:
                    console.print(f"  [{THEME['accent']}]{line}[/]")
                else:
                    console.print(f"  [dim]{line}[/]")

            if follow:
                console.print()
                console.print("  [dim]Following... Press Ctrl+C to stop[/]")
                try:
                    import subprocess

                    subprocess.run(["tail", "-f", str(log_file)])
                except KeyboardInterrupt:
                    pass

        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(40))

    @app.command("logs-clear")
    def logs_clear(
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Clear application logs."""
        console.print(header("logs clear", 40))

        from src.cli.v2.utils.config import get_logs_dir

        log_file = get_logs_dir() / "tawiza.log"

        if not log_file.exists():
            console.print("  [dim]No logs to clear.[/]")
            console.print(footer(40))
            return

        if not force:
            from rich.prompt import Confirm

            if not Confirm.ask("  Clear all logs?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

        log_file.unlink()

        msg = MessageBox()
        console.print(msg.success("Logs cleared"))
        console.print(footer(40))

    @app.command("metrics-export")
    def metrics_export(
        output: Path = typer.Argument(..., help="Output file"),
        format: str = typer.Option("json", "--format", "-f", help="Output format (json, csv)"),
    ):
        """Export system metrics."""
        console.print(header("metrics export", 40))

        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "gpu": {},
        }

        # Collect system metrics
        try:
            import psutil

            metrics["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }
        except ImportError:
            metrics["system"] = {"error": "psutil not available"}

        # Collect GPU metrics
        try:
            import subprocess

            result = subprocess.run(
                ["rocm-smi", "--showuse", "--showtemp", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                import json

                metrics["gpu"] = json.loads(result.stdout)
        except Exception:
            metrics["gpu"] = {"error": "GPU data unavailable"}

        # Export
        try:
            if format == "json":
                import json

                output.write_text(json.dumps(metrics, indent=2))
            elif format == "csv":
                import csv

                with open(output, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["metric", "value"])
                    for category, values in metrics.items():
                        if isinstance(values, dict):
                            for k, v in values.items():
                                writer.writerow([f"{category}.{k}", v])
                        else:
                            writer.writerow([category, values])

            msg = MessageBox()
            console.print(msg.success(f"Metrics exported to {output}"))

        except Exception as e:
            msg = MessageBox()
            console.print(msg.error(str(e)))

        console.print(footer(40))
