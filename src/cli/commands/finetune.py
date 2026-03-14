"""Fine-tuning CLI commands with live progress display."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from src.cli.config.defaults import API_BASE_URL
from src.cli.ui import ColorGradient, Icons, TextStyling, icon
from src.cli.ui.theme import get_sunset_banner, get_sunset_table

app = typer.Typer(
    name="finetune",
    help="🎯 Fine-tuning management with live progress",
)

console = Console()


def get_api_url(endpoint: str) -> str:
    """Get full API URL."""
    return f"{API_BASE_URL}{endpoint}"


@app.command()
def start(
    project_id: str = typer.Option(..., "--project", "-p", help="Label Studio project ID"),
    base_model: str = typer.Option("qwen3-coder:30b", "--model", "-m", help="Base model"),
    model_name: str | None = typer.Option(None, "--name", "-n", help="Fine-tuned model name"),
    task_type: str = typer.Option("classification", "--task", "-t", help="Task type"),
    annotations_file: Path | None = typer.Option(
        None, "--annotations", "-a", help="JSON file with annotations"
    ),
):
    """
    🚀 Start a fine-tuning job with live progress tracking.

    Example:
        tawiza finetune start --project 1 --model qwen3-coder:30b --name my-model
        tawiza finetune start -p 1 -m qwen3.5:27b -n custom-classifier -a data.json
    """
    console.print(
        Panel.fit("[bold cyan]🎯 Fine-Tuning Job Launcher[/bold cyan]", border_style="cyan")
    )

    # Load annotations if provided
    annotations = []
    if annotations_file:
        console.print(f"[cyan]Loading annotations from {annotations_file}...[/cyan]")
        try:
            with open(annotations_file) as f:
                annotations = json.load(f)
            console.print(f"[green]✅ Loaded {len(annotations)} annotations[/green]")
        except Exception as e:
            console.print(f"[red]❌ Error loading annotations: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Fetch from Label Studio API
        console.print(f"[cyan]Fetching annotations from project {project_id}...[/cyan]")
        try:
            response = httpx.get(
                get_api_url(f"/annotations/projects/{project_id}/export"), timeout=30.0
            )
            response.raise_for_status()
            annotations = response.json()
            console.print(f"[green]✅ Fetched {len(annotations)} annotations[/green]")
        except Exception as e:
            console.print(f"[red]❌ Error fetching annotations: {e}[/red]")
            raise typer.Exit(1)

    if not annotations:
        console.print(get_sunset_banner("[yellow]⚠️  No annotations found![/yellow]"))
        raise typer.Exit(1)

    # Prepare request
    request_data = {
        "project_id": project_id,
        "base_model": base_model,
        "task_type": task_type,
        "annotations": annotations,
    }
    if model_name:
        request_data["model_name"] = model_name

    # Start job
    console.print(get_sunset_banner("\n[cyan]Starting fine-tuning job...[/cyan]"))
    try:
        response = httpx.post(get_api_url("/fine-tuning/start"), json=request_data, timeout=60.0)
        response.raise_for_status()
        job_data = response.json()

        # Display job info
        table = get_sunset_table("Fine-Tuning Job Created")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Job ID", job_data["job_id"])
        table.add_row("Project ID", job_data["project_id"])
        table.add_row("Base Model", job_data["base_model"])
        table.add_row("Model Name", job_data["model_name"])
        table.add_row("Status", job_data["status"])
        table.add_row("Training Examples", str(job_data["training_examples"]))
        table.add_row("Created At", job_data["created_at"])

        console.print(table)

        # Ask if user wants to watch progress
        watch_progress = typer.confirm("\n🔍 Watch progress in real-time?", default=True)
        if watch_progress:
            console.print(get_sunset_banner(""))
            asyncio.run(watch_job(job_data["job_id"]))
        else:
            console.print(
                f"\n[cyan]💡 Use [bold]tawiza finetune watch {job_data['job_id']}[/bold] to monitor progress[/cyan]"
            )

    except httpx.HTTPStatusError as e:
        console.print(f"[red]❌ API Error: {e.response.status_code}[/red]")
        console.print(f"[red]{e.response.text}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """
    📊 Get status of a fine-tuning job.

    Example:
        tawiza finetune status abc-123
    """
    console.print(f"[cyan]Fetching status for job {job_id}...[/cyan]\n")

    try:
        response = httpx.get(get_api_url(f"/fine-tuning/jobs/{job_id}"), timeout=10.0)
        response.raise_for_status()
        job = response.json()

        # Display status
        table = Table(title=f"Job Status: {job_id}", border_style="cyan")
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        # Status with color
        status_color = {
            "pending": "yellow",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }.get(job["status"], "white")

        table.add_row("Status", f"[{status_color}]{job['status'].upper()}[/{status_color}]")
        table.add_row("Project ID", job["project_id"])
        table.add_row("Base Model", job["base_model"])
        table.add_row("Model Name", job["model_name"])
        table.add_row("Training Examples", str(job["training_examples"]))
        table.add_row("Created At", job["created_at"])

        if job.get("started_at"):
            table.add_row("Started At", job["started_at"])
        if job.get("completed_at"):
            table.add_row("Completed At", job["completed_at"])
        if job.get("failed_at"):
            table.add_row("Failed At", job["failed_at"])
        if job.get("error"):
            table.add_row("Error", f"[red]{job['error']}[/red]")

        console.print(table)

        # Test results if available
        if job.get("test_result"):
            console.print(get_sunset_banner("\n[bold]Test Results:[/bold]"))
            results_table = Table(border_style="green")
            results_table.add_column("Metric", style="cyan")
            results_table.add_column("Value", style="green")

            for key, value in job["test_result"].items():
                results_table.add_row(key, str(value))

            console.print(results_table)

    except httpx.HTTPStatusError:
        console.print(f"[red]❌ Job not found: {job_id}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of jobs to show"),
    status_filter: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """
    📋 List all fine-tuning jobs.

    Example:
        tawiza finetune list
        tawiza finetune list --limit 20 --status running
    """
    console.print(get_sunset_banner("[cyan]Fetching fine-tuning jobs...[/cyan]\n"))

    try:
        params = {"limit": limit}
        if status_filter:
            params["status"] = status_filter

        response = httpx.get(get_api_url("/fine-tuning/jobs"), params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        # Handle different API response formats
        # Note: Using __builtins__ because function name 'list' shadows built-in
        list_type = type([])
        dict_type = type({})

        if isinstance(data, dict_type):
            jobs = data.get("jobs", data.get("items", []))
        elif isinstance(data, list_type):
            jobs = data
        else:
            jobs = []

        if not jobs or not isinstance(jobs, list_type):
            console.print(get_sunset_banner("[yellow]No jobs found[/yellow]"))
            return

        # Header with gradient
        header = ColorGradient.create_gradient(
            f"Fine-Tuning Jobs ({len(jobs)})", "#E74C3C", "#F39C12"
        )
        console.print()
        console.print(header, justify="center")
        console.print(get_sunset_banner("=" * 80))
        console.print()

        # Display jobs table with icons
        table = Table(show_header=True, header_style="bold yellow", border_style="cyan")
        table.add_column(icon(Icons.TASK, "Job ID"), style="cyan")
        table.add_column(icon(Icons.PROJECT, "Project"), style="white")
        table.add_column(icon(Icons.BRAIN, "Base Model"), style="white")
        table.add_column(icon(Icons.MODEL, "Model Name"), style="green")
        table.add_column(icon(Icons.RUNNING, "Status"), style="bold")
        table.add_column(icon(Icons.DATASET, "Examples"), justify="right")
        table.add_column("Created", style="dim")

        for job in jobs:
            # Skip invalid job entries
            if not isinstance(job, dict_type):
                continue

            # Status color
            status_color = {
                "pending": "yellow",
                "running": "blue",
                "completed": "green",
                "failed": "red",
            }.get(job.get("status", ""), "white")

            # Format created time
            try:
                created_at = job.get("created_at", "")
                if created_at:
                    created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                    created_str = created.strftime("%Y-%m-%d %H:%M")
                else:
                    created_str = "N/A"
            except (ValueError, KeyError, AttributeError):
                created_str = str(job.get("created_at", "N/A"))[:16]

            # Support both API formats (job_id vs id, etc.)
            job_id = job.get("job_id", job.get("id", "N/A"))
            project_id = job.get("project_id", job.get("output_name", "N/A"))
            base_model = job.get("base_model", "N/A")
            model_name = job.get("model_name", job.get("output_name", "N/A"))
            status = job.get("status", "unknown")
            examples = job.get("training_examples", job.get("progress", "N/A"))

            table.add_row(
                str(job_id)[:8] + "..." if len(str(job_id)) > 8 else str(job_id),
                str(project_id)[:20],
                str(base_model)[:25],
                str(model_name)[:20],
                f"[{status_color}]{status}[/{status_color}]",
                str(examples),
                created_str,
            )

        console.print(table)
        console.print()

        # Footer badge
        badge = TextStyling.create_badge(f"{len(jobs)} training jobs", color="yellow", symbol="🏋️")
        console.print(badge, justify="center")
        console.print()

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def watch(
    job_id: str = typer.Argument(..., help="Job ID to watch"),
    interval: int = typer.Option(2, "--interval", "-i", help="Refresh interval in seconds"),
):
    """
    🔴 Watch fine-tuning job progress in real-time.

    Example:
        tawiza finetune watch abc-123
        tawiza finetune watch abc-123 --interval 5
    """
    asyncio.run(watch_job(job_id, interval))


async def watch_job(job_id: str, interval: int = 2):
    """Watch job progress with live updates."""

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    )

    async with httpx.AsyncClient() as client:
        with Live(console=console, refresh_per_second=4) as live:
            task_id = progress.add_task(f"[cyan]Watching job {job_id[:8]}...", total=100)

            while True:
                try:
                    # Fetch job status
                    response = await client.get(
                        get_api_url(f"/fine-tuning/jobs/{job_id}"), timeout=10.0
                    )
                    response.raise_for_status()
                    job = response.json()

                    # Create status panel
                    status_color = {
                        "pending": "yellow",
                        "running": "blue",
                        "completed": "green",
                        "failed": "red",
                    }.get(job["status"], "white")

                    status_text = Text()
                    status_text.append("Status: ", style="bold")
                    status_text.append(f"{job['status'].upper()}", style=f"bold {status_color}")
                    status_text.append(f"\nModel: {job['model_name']}\n", style="cyan")
                    status_text.append(f"Examples: {job['training_examples']}\n", style="white")

                    if job.get("started_at"):
                        status_text.append(f"Started: {job['started_at']}\n", style="dim")

                    if job.get("error"):
                        status_text.append(f"\n❌ Error: {job['error']}", style="red")

                    # Update progress
                    if job["status"] == "running":
                        progress.update(task_id, completed=50)
                    elif job["status"] == "completed":
                        progress.update(task_id, completed=100)
                        status_text.append(
                            f"\n✅ Completed at: {job['completed_at']}", style="green"
                        )
                    elif job["status"] == "failed":
                        progress.update(task_id, completed=0)

                    # Build display
                    display = Panel(
                        status_text,
                        title=f"[bold]Job {job_id[:12]}...[/bold]",
                        border_style=status_color,
                    )

                    live.update(display)

                    # Exit conditions
                    if job["status"] in ["completed", "failed"]:
                        break

                    await asyncio.sleep(interval)

                except httpx.HTTPStatusError:
                    console.print(f"[red]❌ Job not found: {job_id}[/red]")
                    break
                except Exception as e:
                    console.print(f"[red]❌ Error: {e}[/red]")
                    break

    # Final status
    if job["status"] == "completed":
        console.print(get_sunset_banner("\n[green]✅ Fine-tuning completed successfully![/green]"))
    elif job["status"] == "failed":
        console.print(f"\n[red]❌ Fine-tuning failed: {job.get('error', 'Unknown error')}[/red]")


@app.command()
def models(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of models to show"),
):
    """
    🤖 List fine-tuned models.

    Example:
        tawiza finetune models
        tawiza finetune models --limit 50
    """
    console.print(get_sunset_banner("[cyan]Fetching fine-tuned models...[/cyan]\n"))

    try:
        response = httpx.get(
            get_api_url("/fine-tuning/models"), params={"limit": limit}, timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        models = data.get("models", [])

        if not models:
            console.print(get_sunset_banner("[yellow]No fine-tuned models found[/yellow]"))
            return

        # Display models table
        table = Table(title=f"Fine-Tuned Models ({data['total']})", border_style="cyan")
        table.add_column("Model Name", style="green bold")
        table.add_column("Base Model", style="cyan")
        table.add_column("Version", style="white")
        table.add_column("Size", justify="right")
        table.add_column("Created", style="dim")

        for model in models:
            # Format size
            size = model.get("size", 0)
            if size > 1e9:
                size_str = f"{size / 1e9:.1f} GB"
            elif size > 1e6:
                size_str = f"{size / 1e6:.1f} MB"
            else:
                size_str = f"{size / 1e3:.1f} KB"

            # Format created time
            try:
                created = datetime.fromisoformat(model["created_at"].replace("Z", "+00:00"))
                created_str = created.strftime("%Y-%m-%d %H:%M")
            except (ValueError, KeyError, AttributeError):
                created_str = model.get("created_at", "N/A")

            table.add_row(
                model["name"],
                model.get("base_model", "N/A"),
                model.get("version", "1.0"),
                size_str,
                created_str,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
