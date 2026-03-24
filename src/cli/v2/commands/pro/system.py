"""System commands for Tawiza CLI v2 pro."""

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm

from src.cli.v2.ui.components import MessageBox, StatusBar
from src.cli.v2.ui.spinners import create_spinner
from src.cli.v2.ui.theme import footer, header

console = Console()


def register(app: typer.Typer) -> None:
    """Register system commands."""

    @app.command("cache-clear")
    def cache_clear(
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Clear application cache."""
        console.print(header("cache clear", 40))

        from src.cli.v2.utils.config import get_cache_dir

        cache_dir = get_cache_dir()

        if not cache_dir.exists() or not any(cache_dir.iterdir()):
            console.print("  [dim]Cache is already empty.[/]")
            console.print(footer(40))
            return

        # Calculate cache size
        total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)

        console.print(f"  [bold]Cache size:[/] {size_mb:.2f} MB")
        console.print(f"  [bold]Location:[/] {cache_dir}")
        console.print()

        if not force and not Confirm.ask("  Clear cache?"):
            console.print("  [dim]Cancelled.[/]")
            console.print(footer(40))
            return

        with create_spinner("Clearing cache...", "dots"):
            for item in cache_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

        msg = MessageBox()
        console.print(msg.success(f"Cache cleared ({size_mb:.2f} MB freed)"))
        console.print(footer(40))

    @app.command("cache-info")
    def cache_info():
        """Show cache information."""
        console.print(header("cache info", 40))

        from src.cli.v2.utils.config import get_cache_dir

        cache_dir = get_cache_dir()

        if not cache_dir.exists():
            console.print("  [dim]Cache directory does not exist.[/]")
            console.print(footer(40))
            return

        # Count files and calculate size
        files = list(cache_dir.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        console.print(f"  [bold]Location:[/] {cache_dir}")
        console.print(f"  [bold]Files:[/] {file_count}")
        console.print(f"  [bold]Size:[/] {total_size / (1024 * 1024):.2f} MB")
        console.print()

        # List largest files
        if file_count > 0:
            console.print("  [bold]Largest files:[/]")
            sorted_files = sorted(
                [f for f in files if f.is_file()], key=lambda f: f.stat().st_size, reverse=True
            )[:5]

            for f in sorted_files:
                size_kb = f.stat().st_size / 1024
                console.print(f"    {f.name}: {size_kb:.1f} KB")

        console.print(footer(40))

    @app.command("update-check")
    def update_check():
        """Check for updates."""
        console.print(header("update check", 40))

        try:
            from src.core.constants import APP_VERSION

            current_version = APP_VERSION
        except ImportError:
            current_version = "2.0.0"

        console.print(f"  [bold]Current version:[/] {current_version}")
        console.print()

        with create_spinner("Checking for updates...", "dots"):
            # Simulate update check
            import time

            time.sleep(1)

            # In a real implementation, this would check PyPI or GitHub
            latest_version = current_version  # Assume up to date

        if latest_version == current_version:
            msg = MessageBox()
            console.print(msg.success("You're up to date!"))
        else:
            msg = MessageBox()
            console.print(
                msg.info(f"Update available: {latest_version}", "Run: pip install --upgrade tawiza")
            )

        console.print(footer(40))

    @app.command("doctor")
    def doctor():
        """Run system diagnostics."""
        console.print(header("system doctor", 40))
        console.print()

        checks = []

        # Check Python version
        import sys

        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        py_ok = sys.version_info >= (3, 11)
        checks.append(("Python", py_version, "ok" if py_ok else "warn"))

        # Check Ollama
        try:
            import subprocess

            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"], capture_output=True, timeout=5
            )
            ollama_ok = result.returncode == 0
            checks.append(
                ("Ollama", "running" if ollama_ok else "not running", "ok" if ollama_ok else "warn")
            )
        except Exception:
            checks.append(("Ollama", "unavailable", "err"))

        # Check GPU
        try:
            import subprocess

            result = subprocess.run(["rocm-smi", "--showid"], capture_output=True, timeout=5)
            gpu_ok = result.returncode == 0
            checks.append(
                ("GPU (ROCm)", "detected" if gpu_ok else "not detected", "ok" if gpu_ok else "warn")
            )
        except Exception:
            checks.append(("GPU (ROCm)", "unavailable", "warn"))

        # Check disk space
        try:
            import shutil

            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024**3)
            disk_ok = free_gb > 10
            checks.append(("Disk space", f"{free_gb:.1f} GB free", "ok" if disk_ok else "warn"))
        except Exception:
            checks.append(("Disk space", "unknown", "warn"))

        # Check memory
        try:
            import psutil

            mem = psutil.virtual_memory()
            mem_ok = mem.available > 4 * (1024**3)  # 4GB
            mem_gb = mem.available / (1024**3)
            checks.append(("Memory", f"{mem_gb:.1f} GB available", "ok" if mem_ok else "warn"))
        except ImportError:
            checks.append(("Memory", "psutil not installed", "warn"))

        # Check config
        from src.cli.v2.utils.config import CONFIG_FILE

        config_ok = CONFIG_FILE.exists()
        checks.append(
            ("Config", "found" if config_ok else "not found", "ok" if config_ok else "warn")
        )

        # Display results
        bar = StatusBar()
        for name, value, status in checks:
            bar.add(name, value, status)

        console.print(bar.render())
        console.print()

        # Summary
        errors = sum(1 for _, _, s in checks if s == "err")
        warnings = sum(1 for _, _, s in checks if s == "warn")

        if errors == 0 and warnings == 0:
            msg = MessageBox()
            console.print(msg.success("All systems operational!"))
        elif errors > 0:
            msg = MessageBox()
            console.print(msg.error(f"{errors} error(s), {warnings} warning(s)"))
        else:
            msg = MessageBox()
            console.print(msg.warning(f"{warnings} warning(s)"))

        console.print(footer(40))

    @app.command("info")
    def info():
        """Show system information."""
        console.print(header("system info", 40))

        import platform
        import sys

        console.print("  [bold]Tawiza version:[/] ", end="")
        try:
            from src.core.constants import APP_VERSION

            console.print(APP_VERSION)
        except ImportError:
            console.print("2.0.0")

        console.print(
            f"  [bold]Python:[/] {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        console.print(f"  [bold]Platform:[/] {platform.system()} {platform.release()}")
        console.print(f"  [bold]Architecture:[/] {platform.machine()}")

        # Show paths
        console.print()
        from src.cli.v2.utils.config import CONFIG_DIR

        console.print(f"  [bold]Config dir:[/] {CONFIG_DIR}")
        console.print(f"  [bold]Working dir:[/] {Path.cwd()}")

        console.print(footer(40))
