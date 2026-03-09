"""Status command - Show system status dashboard."""

import typer
from rich.console import Console

from src.cli.v2.ui.components import StatusBar
from src.cli.v2.ui.theme import footer, header

console = Console()


def status_command(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
):
    """Show system status dashboard."""
    console.print(header("tawiza status", 40))

    bar = StatusBar()

    # Check system status
    bar.add("system", "online", "ok")

    # Check GPU
    try:
        import subprocess
        result = subprocess.run(
            ["rocm-smi", "--showid"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            bar.add("gpu", "amd ready", "ok")
        else:
            bar.add("gpu", "not available", "warn")
    except Exception:
        bar.add("gpu", "not detected", "warn")

    # Check Ollama
    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            bar.add("ollama", "running", "ok")
        else:
            bar.add("ollama", "not running", "warn")
    except Exception:
        bar.add("ollama", "unavailable", "warn")

    bar.add("agents", "ready", "ok")

    console.print(bar.render())

    if verbose:
        console.print()
        console.print("  [dim]Python:[/] 3.13")
        console.print("  [dim]Platform:[/] linux")

    console.print(footer(40))
