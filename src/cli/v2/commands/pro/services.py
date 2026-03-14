"""Services dashboard commands for Tawiza CLI v2 pro.

Provides a unified dashboard with links to all Tawiza services including:
- Monitoring (GPU, system, agents)
- Fine-tuning (LLaMA-Factory, training jobs)
- Annotations (Label Studio, projects)
- API services (OpenAI-compatible, Agents API)
- Infrastructure (Ollama, VM sandbox)
"""

import os
import time

import httpx
import typer
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()

# Service definitions with URLs and health check endpoints
SERVICES = {
    "api": {
        "name": "Tawiza API",
        "description": "OpenAI-compatible API + Agents",
        "url": "http://localhost:8002",
        "health_endpoint": "/health",
        "docs_url": "http://localhost:8002/docs",
        "category": "core",
    },
    "ollama": {
        "name": "Ollama",
        "description": "Local LLM inference server",
        "url": "http://localhost:11434",
        "health_endpoint": "/api/tags",
        "docs_url": None,
        "category": "core",
    },
    "label-studio": {
        "name": "Label Studio",
        "description": "Data annotation platform",
        "url": "http://localhost:8082",
        "health_endpoint": "/api/health",
        "docs_url": "http://localhost:8082",
        "category": "ml",
    },
    "llama-factory": {
        "name": "LLaMA-Factory",
        "description": "Model fine-tuning WebUI",
        "url": "http://localhost:7860",
        "health_endpoint": "/",
        "docs_url": "http://localhost:7860",
        "category": "ml",
    },
    "vm-sandbox": {
        "name": "Sandbox",
        "description": "Isolated execution environment",
        "url": f"http://{os.getenv('VM_SANDBOX_HOST', 'localhost')}:22",  # SSH check
        "health_endpoint": None,
        "ssh_check": True,
        "category": "infra",
    },
}

# Quick links organized by category
QUICK_LINKS = {
    "ML Platform": [
        ("Fine-tune model", "tawiza pro train-start <model> -d <data>"),
        ("Training status", "tawiza pro train-status"),
        ("List models", "tawiza pro model-list"),
        ("Pull model", "tawiza pro model-pull <model>"),
    ],
    "Annotations": [
        ("Create project", "tawiza annotate create -n <name>"),
        ("List projects", "tawiza annotate list"),
        ("Export annotations", "tawiza annotate export <id>"),
        ("Upload tasks", "tawiza annotate upload <id> -f <file>"),
    ],
    "Agents": [
        ("List agents", "tawiza pro agents"),
        ("Run Manus agent", "tawiza pro agent-run manus -t <task>"),
        ("Run S3 agent", "tawiza pro agent-run s3 -t <task>"),
        ("Debug agent", "tawiza pro agent-debug"),
    ],
    "Monitoring": [
        ("GPU monitor", "tawiza pro gpu-monitor"),
        ("System dashboard", "tawiza pro dashboard"),
        ("View logs", "tawiza pro logs-show"),
        ("Export metrics", "tawiza pro metrics-export <file>"),
    ],
}


def check_service_health(service_id: str) -> tuple[bool, str]:
    """Check if a service is healthy.

    Returns (is_healthy, status_message).
    """
    service = SERVICES.get(service_id)
    if not service:
        return False, "unknown"

    if service.get("ssh_check"):
        # Check SSH connectivity
        import subprocess

        try:
            host = service["url"].replace("http://", "").split(":")[0]
            result = subprocess.run(
                ["nc", "-z", "-w", "2", host, "22"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return True, "reachable"
            return False, "unreachable"
        except Exception:
            return False, "error"

    if not service.get("health_endpoint"):
        return False, "no health check"

    try:
        url = f"{service['url']}{service['health_endpoint']}"
        response = httpx.get(url, timeout=5)
        if response.status_code < 400:
            return True, "healthy"
        return False, f"error ({response.status_code})"
    except httpx.ConnectError:
        return False, "offline"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception:
        return False, "error"


def register(app: typer.Typer) -> None:
    """Register services commands."""

    @app.command("services")
    def list_services(
        category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
        check_health: bool = typer.Option(True, "--check/--no-check", help="Check service health"),
    ):
        """Show all Tawiza services with status and links."""
        console.print(header("services", 60))

        # Group services by category
        categories = {"core": "Core Services", "ml": "ML Platform", "infra": "Infrastructure"}

        for cat_id, cat_name in categories.items():
            if category and category != cat_id:
                continue

            services_in_cat = [
                (sid, s) for sid, s in SERVICES.items() if s.get("category") == cat_id
            ]

            if not services_in_cat:
                continue

            console.print(f"\n  [bold {THEME['accent']}]{cat_name}[/]")
            console.print()

            table = Table(
                show_header=True,
                header_style=f"bold {THEME['accent']}",
                expand=True,
                box=None,
            )
            table.add_column("Service", style="cyan", width=18)
            table.add_column("Status", width=12)
            table.add_column("URL", style="dim")
            table.add_column("Description")

            for service_id, service in services_in_cat:
                if check_health:
                    is_healthy, status = check_service_health(service_id)
                    status_color = THEME["success"] if is_healthy else THEME["error"]
                    status_text = f"[{status_color}]{status}[/]"
                else:
                    status_text = "[dim]--[/]"

                table.add_row(
                    service["name"],
                    status_text,
                    service.get("docs_url") or service["url"],
                    service["description"],
                )

            console.print(table)

        console.print()
        console.print("  [dim]Open service:[/] Click URL or copy to browser")
        console.print("  [dim]Check health:[/] tawiza pro services --check")
        console.print(footer(60))

    @app.command("dashboard")
    def unified_dashboard(
        refresh: int = typer.Option(5, "--refresh", "-r", help="Refresh interval (seconds)"),
        duration: int = typer.Option(60, "--duration", "-d", help="Duration (seconds)"),
    ):
        """Show unified dashboard with all services and metrics."""

        def build_dashboard() -> Layout:
            """Build the dashboard layout."""
            layout = Layout()

            layout.split_column(
                Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=5)
            )

            # Header
            header_text = Text()
            header_text.append("Tawiza Dashboard", style="bold cyan")
            header_text.append(f"  |  {time.strftime('%H:%M:%S')}", style="dim")
            layout["header"].update(Panel(header_text, border_style="cyan"))

            # Body split into services and metrics
            layout["body"].split_row(
                Layout(name="services", ratio=1), Layout(name="metrics", ratio=1)
            )

            # Services panel
            services_table = Table(
                show_header=True,
                header_style="bold yellow",
                expand=True,
                box=None,
            )
            services_table.add_column("Service", style="cyan")
            services_table.add_column("Status", justify="center")

            for service_id, service in SERVICES.items():
                is_healthy, status = check_service_health(service_id)
                status_color = "green" if is_healthy else "red"
                services_table.add_row(service["name"], Text(status, style=f"bold {status_color}"))

            layout["body"]["services"].update(
                Panel(services_table, title="Services", border_style="blue")
            )

            # Metrics panel
            metrics_table = Table(
                show_header=False,
                expand=True,
                box=None,
            )
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="bold white")

            # System metrics
            try:
                import psutil

                metrics_table.add_row("CPU", f"{psutil.cpu_percent():.1f}%")
                metrics_table.add_row("RAM", f"{psutil.virtual_memory().percent:.1f}%")
                metrics_table.add_row("Disk", f"{psutil.disk_usage('/').percent:.1f}%")
            except ImportError:
                metrics_table.add_row("System", "psutil not available")

            # GPU metrics
            try:
                import subprocess

                result = subprocess.run(
                    ["rocm-smi", "--showuse"], capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0:
                    # Parse GPU usage from output
                    for line in result.stdout.split("\n"):
                        if "%" in line and "GPU" in line:
                            metrics_table.add_row("GPU", line.strip()[:30])
                            break
                    else:
                        metrics_table.add_row("GPU", "Available")
            except Exception:
                metrics_table.add_row("GPU", "N/A")

            layout["body"]["metrics"].update(
                Panel(metrics_table, title="System", border_style="green")
            )

            # Footer with quick commands
            footer_text = Text()
            footer_text.append("Quick Commands: ", style="bold")
            footer_text.append("agents ", style="cyan")
            footer_text.append("| ")
            footer_text.append("train-start ", style="cyan")
            footer_text.append("| ")
            footer_text.append("gpu-monitor ", style="cyan")
            footer_text.append("| ")
            footer_text.append("logs-show", style="cyan")
            footer_text.append("\n")
            footer_text.append("Press Ctrl+C to exit", style="dim")

            layout["footer"].update(Panel(footer_text, border_style="dim"))

            return layout

        console.print("[cyan]Starting dashboard...[/]")

        try:
            start_time = time.time()
            with Live(build_dashboard(), refresh_per_second=1, console=console) as live:
                while time.time() - start_time < duration:
                    time.sleep(refresh)
                    live.update(build_dashboard())
        except KeyboardInterrupt:
            pass

        console.print("\n[dim]Dashboard stopped.[/]")

    @app.command("links")
    def show_links(
        category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
    ):
        """Show quick command links for common tasks."""
        console.print(header("quick links", 60))

        for cat_name, links in QUICK_LINKS.items():
            if category and category.lower() not in cat_name.lower():
                continue

            console.print(f"\n  [bold {THEME['accent']}]{cat_name}[/]")
            console.print()

            for desc, cmd in links:
                console.print(f"    [cyan]{desc:.<25}[/] [dim]{cmd}[/]")

        console.print()
        console.print(footer(60))

    @app.command("open")
    def open_service(
        service_name: str = typer.Argument(..., help="Service to open"),
    ):
        """Open a service URL in the browser or show connection info."""
        console.print(header(f"open: {service_name}", 50))

        # Find service
        service = None
        for sid, s in SERVICES.items():
            if sid == service_name or s["name"].lower() == service_name.lower():
                service = s
                break

        if not service:
            msg = MessageBox()
            console.print(
                msg.error(
                    f"Service not found: {service_name}",
                    [f"Available: {', '.join(SERVICES.keys())}"],
                )
            )
            console.print(footer(50))
            return

        # Check health
        service_id = [k for k, v in SERVICES.items() if v == service][0]
        is_healthy, status = check_service_health(service_id)

        console.print(f"  [bold]Service:[/] {service['name']}")
        console.print(f"  [bold]Description:[/] {service['description']}")
        console.print()

        if is_healthy:
            status_color = THEME["success"]
            console.print(f"  [bold]Status:[/] [{status_color}]{status}[/]")
            console.print()

            url = service.get("docs_url") or service["url"]
            console.print(f"  [bold]URL:[/] [link={url}]{url}[/]")

            # Try to open in browser
            try:
                import webbrowser

                console.print()
                console.print("  [dim]Opening in browser...[/]")
                webbrowser.open(url)
            except Exception:
                console.print()
                console.print("  [dim]Copy the URL above to your browser.[/]")
        else:
            status_color = THEME["error"]
            console.print(f"  [bold]Status:[/] [{status_color}]{status}[/]")
            console.print()

            msg = MessageBox()
            console.print(msg.warning("Service is not available", "Try starting it first"))

            # Show start command if available
            if service_id == "ollama":
                console.print("  [dim]Start with:[/] tawiza pro ollama-start")
            elif service_id == "api":
                console.print("  [dim]Start with:[/] tawiza system start")

        console.print(footer(50))
