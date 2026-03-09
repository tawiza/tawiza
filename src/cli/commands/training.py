"""Training and fine-tuning commands for Tawiza CLI."""


import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.cli.ui.theme import get_sunset_banner

from ..utils import api, format_error, format_success, format_table, format_tree

console = Console()
app = typer.Typer(help="Training and fine-tuning")


@app.command()
def list(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json)"),
):
    """List all fine-tuning jobs."""
    try:
        jobs = api.get("/api/v1/fine-tuning/jobs")

        if format_type == "json":
            console.print_json(data=jobs)
            return

        if not jobs:
            console.print(get_sunset_banner("[yellow]No training jobs found[/yellow]"))
            return

        # Create table
        columns = [
            ("job_id", "Job ID", "cyan"),
            ("model_name", "Model", "magenta"),
            ("base_model", "Base Model", "blue"),
            ("status", "Status", "green"),
            ("training_examples", "Examples", "yellow"),
            ("created_at", "Created", "dim"),
        ]

        table = format_table(jobs, columns, title="Fine-tuning Jobs")
        console.print(table)

        console.print(f"\n[dim]Total: {len(jobs)} jobs[/dim]")

    except Exception as e:
        console.print(format_error("Failed to list training jobs", str(e)))
        raise typer.Exit(1)


@app.command()
def status(
    job_id: str = typer.Argument(..., help="Job ID"),
):
    """Get status of a training job."""
    try:
        # Use dedicated endpoint for single job
        job = api.get(f"/api/v1/fine-tuning/jobs/{job_id}")

        # Display job status
        tree = format_tree(job, title=f"Job: {job_id}")
        console.print(tree)

    except Exception as e:
        if "404" in str(e):
            console.print(format_error(f"Job '{job_id}' not found"))
        else:
            console.print(format_error("Failed to get job status", str(e)))
        raise typer.Exit(1)


@app.command()
def start(
    project_id: str = typer.Argument(..., help="Label Studio project ID"),
    model: str = typer.Option("qwen3-coder:30b", "--model", "-m", help="Base model to fine-tune"),
    task_type: str = typer.Option("classification", "--task", "-t", help="Task type"),
    model_name: str | None = typer.Option(None, "--name", "-n", help="Custom model name"),
):
    """Start a new fine-tuning job from Label Studio annotations."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting fine-tuning job...", total=None)

            # Prepare request - using from-label-studio endpoint
            request_data = {
                "project_id": project_id,
                "base_model": model,
                "task_type": task_type,
            }

            if model_name:
                request_data["model_name"] = model_name

            console.print(f"\n[dim]Project ID: {project_id}[/dim]")
            console.print(f"[dim]Base model: {model}[/dim]")
            console.print(f"[dim]Task type: {task_type}[/dim]")
            if model_name:
                console.print(f"[dim]Model name: {model_name}[/dim]")

            # Call API
            result = api.post("/api/v1/fine-tuning/from-label-studio", json=request_data)

            progress.update(task, description="✓ Job started")

        # Show success
        console.print(
            format_success(
                "Fine-tuning job started successfully!",
                {
                    "Job ID": result.get("job_id", "N/A"),
                    "Model": result.get("model_name", "N/A"),
                    "Status": result.get("status", "N/A"),
                    "Training Examples": result.get("training_examples", 0),
                },
            )
        )

        console.print(f"\n[cyan]Track progress with:[/cyan] tawiza train status {result.get('job_id')}")

    except Exception as e:
        console.print(format_error("Failed to start training job", str(e)))
        raise typer.Exit(1)


@app.command()
def logs(
    job_id: str = typer.Argument(..., help="Job ID"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show"),
):
    """View logs for a training job."""
    try:
        # Try to get logs from API
        try:
            logs_data = api.get(f"/api/v1/fine-tuning/jobs/{job_id}/logs", params={"lines": lines})
            console.print(logs_data.get("content", "No logs available"))
        except Exception:
            # Endpoint not implemented yet
            console.print(get_sunset_banner("[yellow]Training job logs endpoint not yet available[/yellow]"))
            console.print(f"[dim]You can check job status with: tawiza train status {job_id}[/dim]")

    except Exception as e:
        console.print(format_error("Failed to get training logs", str(e)))
        raise typer.Exit(1)


@app.command()
def cancel(
    job_id: str = typer.Argument(..., help="Job ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Cancel a running training job."""
    try:
        if not yes:
            confirm = typer.confirm(f"Are you sure you want to cancel job '{job_id}'?", default=False)
            if not confirm:
                console.print(get_sunset_banner("[yellow]Cancellation aborted[/yellow]"))
                return

        console.print(f"[yellow]Cancelling job {job_id}...[/yellow]")

        # Try to cancel via API
        try:
            api.post(f"/api/v1/fine-tuning/jobs/{job_id}/cancel")
            console.print(format_success(f"Job cancelled: {job_id}"))
        except Exception:
            # Endpoint not implemented yet
            console.print(get_sunset_banner("[yellow]Training job cancellation endpoint not yet available[/yellow]"))
            console.print(get_sunset_banner("[dim]Please stop the job manually or wait for completion[/dim]"))

    except Exception as e:
        console.print(format_error("Failed to cancel training job", str(e)))
        raise typer.Exit(1)


@app.command()
def models(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json)"),
):
    """List all fine-tuned models."""
    try:
        response = api.get("/api/v1/fine-tuning/models")
        models_data = response.get("models", [])

        if format_type == "json":
            console.print_json(data=response)
            return

        if not models_data:
            console.print(get_sunset_banner("[yellow]No fine-tuned models found[/yellow]"))
            return

        # Create table
        columns = [
            ("name", "Name", "cyan"),
            ("version", "Version", "magenta"),
            ("base_model", "Base Model", "blue"),
            ("created_at", "Created", "dim"),
        ]

        table = format_table(models_data, columns, title="Fine-tuned Models")
        console.print(table)

        console.print(f"\n[dim]Total: {response.get('total', len(models_data))} models[/dim]")

    except Exception as e:
        console.print(format_error("Failed to list fine-tuned models", str(e)))
        raise typer.Exit(1)


@app.command()
def delete_model(
    model_name: str = typer.Argument(..., help="Model name to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a fine-tuned model."""
    try:
        if not yes:
            confirm = typer.confirm(
                f"Are you sure you want to delete model '{model_name}'?", default=False
            )
            if not confirm:
                console.print(get_sunset_banner("[yellow]Deletion cancelled[/yellow]"))
                return

        # Delete model
        api.delete(f"/api/v1/fine-tuning/models/{model_name}")
        console.print(format_success(f"Model deleted: {model_name}"))

    except Exception as e:
        console.print(format_error("Failed to delete model", str(e)))
        raise typer.Exit(1)


@app.command()
def export(
    model_name: str = typer.Argument(..., help="Model name to export"),
    output_path: str = typer.Option("./", "--output", "-o", help="Output directory"),
):
    """Export a fine-tuned model."""
    try:
        console.print(f"[yellow]Exporting model '{model_name}'...[/yellow]")

        # Export model
        result = api.post(
            f"/api/v1/fine-tuning/models/{model_name}/export",
            json={"output_path": output_path},
        )

        console.print(
            format_success(
                "Model exported successfully!",
                {"Export Path": result.get("export_path", output_path)},
            )
        )

    except Exception as e:
        console.print(format_error("Failed to export model", str(e)))
