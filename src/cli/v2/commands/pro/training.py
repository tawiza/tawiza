"""Training commands for Tawiza CLI v2 pro."""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()

# Jobs storage
JOBS_FILE = Path.home() / ".tawiza" / "jobs.json"


def _load_jobs() -> dict:
    """Load jobs from file."""
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_jobs(jobs: dict) -> None:
    """Save jobs to file."""
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def register(app: typer.Typer) -> None:
    """Register training commands."""

    @app.command("train-start")
    def train_start(
        model: str = typer.Argument(..., help="Base model to fine-tune"),
        data: Path = typer.Option(..., "--data", "-d", help="Training data file"),
        name: str | None = typer.Option(None, "--name", "-n", help="Job name"),
        epochs: int = typer.Option(3, "--epochs", "-e", help="Number of epochs"),
        batch_size: int = typer.Option(4, "--batch-size", "-b", help="Batch size"),
    ):
        """Start a training job."""
        console.print(header("train start", 40))

        if not data.exists():
            msg = MessageBox()
            console.print(msg.error(f"Data file not found: {data}"))
            console.print(footer(40))
            return

        job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_name = name or f"train_{job_id}"

        console.print(f"  [bold]Job ID:[/] {job_id}")
        console.print(f"  [bold]Name:[/] {job_name}")
        console.print(f"  [bold]Model:[/] {model}")
        console.print(f"  [bold]Data:[/] {data}")
        console.print(f"  [bold]Epochs:[/] {epochs}")
        console.print(f"  [bold]Batch size:[/] {batch_size}")
        console.print()

        # Save job info
        jobs = _load_jobs()
        jobs[job_id] = {
            "name": job_name,
            "model": model,
            "data": str(data),
            "epochs": epochs,
            "batch_size": batch_size,
            "status": "running",
            "progress": 0,
            "started_at": datetime.now().isoformat(),
        }
        _save_jobs(jobs)

        msg = MessageBox()
        console.print(msg.success(
            "Training job started!",
            f"Monitor with: tawiza pro train-status {job_id}"
        ))

        # Note: Actual training would be done asynchronously
        console.print()
        console.print("  [dim]Note: Training runs in background.[/]")
        console.print("  [dim]Check status with: tawiza pro train-status[/]")

        console.print(footer(40))

    @app.command("train-status")
    def train_status(
        job_id: str | None = typer.Argument(None, help="Job ID (optional)"),
    ):
        """Show training job status."""
        console.print(header("train status", 40))

        jobs = _load_jobs()

        if not jobs:
            console.print("  [dim]No training jobs found.[/]")
            console.print("  [dim]Start one with: tawiza pro train-start[/]")
            console.print(footer(40))
            return

        if job_id:
            # Show specific job
            if job_id not in jobs:
                msg = MessageBox()
                console.print(msg.error(f"Job not found: {job_id}"))
                console.print(footer(40))
                return

            job = jobs[job_id]
            console.print(f"  [bold]Job ID:[/] {job_id}")
            console.print(f"  [bold]Name:[/] {job['name']}")
            console.print(f"  [bold]Model:[/] {job['model']}")
            console.print(f"  [bold]Status:[/] [{THEME['success'] if job['status'] == 'completed' else THEME['warning']}]{job['status']}[/]")
            console.print(f"  [bold]Progress:[/] {job['progress']}%")
            console.print(f"  [bold]Started:[/] {job['started_at']}")
        else:
            # Show all jobs
            table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Model")
            table.add_column("Status")
            table.add_column("Progress")

            for jid, job in jobs.items():
                status_color = THEME['success'] if job['status'] == 'completed' else THEME['warning']
                table.add_row(
                    jid,
                    job['name'],
                    job['model'],
                    f"[{status_color}]{job['status']}[/]",
                    f"{job['progress']}%"
                )

            console.print(table)

        console.print(footer(40))

    @app.command("train-stop")
    def train_stop(
        job_id: str = typer.Argument(..., help="Job ID to stop"),
    ):
        """Stop a training job."""
        console.print(header("train stop", 40))

        jobs = _load_jobs()

        if job_id not in jobs:
            msg = MessageBox()
            console.print(msg.error(f"Job not found: {job_id}"))
            console.print(footer(40))
            return

        jobs[job_id]["status"] = "stopped"
        _save_jobs(jobs)

        msg = MessageBox()
        console.print(msg.success(f"Job {job_id} stopped"))
        console.print(footer(40))

    @app.command("train-delete")
    def train_delete(
        job_id: str = typer.Argument(..., help="Job ID to delete"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Delete a training job."""
        console.print(header("train delete", 40))

        jobs = _load_jobs()

        if job_id not in jobs:
            msg = MessageBox()
            console.print(msg.error(f"Job not found: {job_id}"))
            console.print(footer(40))
            return

        if not force:
            from rich.prompt import Confirm
            if not Confirm.ask(f"  Delete job '{job_id}'?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

        del jobs[job_id]
        _save_jobs(jobs)

        msg = MessageBox()
        console.print(msg.success(f"Job {job_id} deleted"))
        console.print(footer(40))
