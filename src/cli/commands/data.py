"""Data management commands for Tawiza CLI."""

import typer
from rich.console import Console

from ..utils import api, format_error, format_table

console = Console()
app = typer.Typer(help="Data and dataset management")


@app.command()
def list(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json)"),
):
    """List all datasets."""
    try:
        data = api.get("/api/v1/datasets")
        datasets = data.get("datasets", data.get("items", []))

        if format_type == "json":
            console.print_json(data=data)
            return

        if not datasets:
            console.print("[yellow]No datasets found[/yellow]")
            return

        # Create table
        columns = [
            ("id", "ID", "cyan"),
            ("name", "Name", "magenta"),
            ("status", "Status", "green"),
            ("total_samples", "Samples", "yellow"),
            ("created_at", "Created", "dim"),
        ]

        table = format_table(datasets, columns, title="Datasets")
        console.print(table)

        console.print(f"\n[dim]Total: {data.get('total', len(datasets))} datasets[/dim]")

    except Exception as e:
        console.print(format_error("Failed to list datasets", str(e)))
        raise typer.Exit(1)


@app.command()
def show(
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
):
    """Show detailed information about a dataset."""
    try:
        dataset = api.get(f"/api/v1/datasets/{dataset_id}")

        from ..utils.formatters import format_tree

        tree = format_tree(dataset, title=f"Dataset: {dataset_id}")
        console.print(tree)

    except Exception as e:
        if "404" in str(e):
            console.print(format_error(f"Dataset '{dataset_id}' not found"))
        else:
            console.print(format_error("Failed to get dataset details", str(e)))
        raise typer.Exit(1)


@app.command()
def upload(
    file_path: str = typer.Argument(..., help="Path to dataset file"),
    name: str = typer.Option(None, "--name", "-n", help="Dataset name"),
):
    """Upload a new dataset."""
    console.print(f"[yellow]Uploading dataset from {file_path}...[/yellow]")
    console.print("[dim]Dataset upload endpoint not yet implemented[/dim]")
    console.print("[dim]Please use the API directly or Label Studio for now[/dim]")


@app.command()
def validate(
    dataset_id: str = typer.Argument(..., help="Dataset ID to validate"),
):
    """Validate a dataset."""
    console.print(f"[yellow]Validating dataset {dataset_id}...[/yellow]")
