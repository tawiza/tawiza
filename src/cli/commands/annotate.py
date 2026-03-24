"""Annotation management CLI commands."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.config.defaults import API_BASE_URL

app = typer.Typer(
    name="annotate",
    help="📝 Annotation and labeling management",
)

console = Console()


def get_api_url(endpoint: str) -> str:
    """Get full API URL."""
    return f"{API_BASE_URL}{endpoint}"


def handle_api_error(e: Exception, action: str = "operation"):
    """Handle API errors with helpful messages."""
    if isinstance(e, httpx.ConnectError):
        console.print(
            Panel(
                "[red]❌ Impossible de se connecter au backend API[/red]\n\n"
                "[cyan]Solutions:[/cyan]\n"
                "  1. Démarrer le backend: [green]tawiza system start[/green]\n"
                "  2. Vérifier Label Studio: http://localhost:8082",
                title="🔌 Backend Non Disponible",
                border_style="red",
            )
        )
    elif isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            console.print(
                Panel(
                    "[yellow]⚠️ Endpoint non disponible[/yellow]\n\n"
                    "[cyan]Label Studio n'est pas configuré ou accessible.[/cyan]\n"
                    "URL: http://localhost:8082",
                    title="📡 Service Non Trouvé",
                    border_style="yellow",
                )
            )
        else:
            console.print(f"[red]❌ API Error: {e.response.status_code}[/red]")
            console.print(f"[red]{e.response.text}[/red]")
    else:
        console.print(f"[red]❌ Error during {action}: {e}[/red]")


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Project name"),
    description: str = typer.Option("", "--desc", "-d", help="Project description"),
    task_type: str = typer.Option("classification", "--type", "-t", help="Task type"),
):
    """
    ➕ Create a new annotation project in Label Studio.

    Example:
        tawiza annotate create --name "Product Reviews" --desc "Classify product sentiment" --type classification
        tawiza annotate create -n "Named Entities" -d "Extract entities" -t ner
    """
    console.print(
        Panel.fit("[bold cyan]📝 Create Annotation Project[/bold cyan]", border_style="cyan")
    )

    request_data = {
        "name": name,
        "description": description,
        "task_type": task_type,
    }

    console.print(f"\n[cyan]Creating project '{name}'...[/cyan]")

    try:
        response = httpx.post(get_api_url("/annotations/projects"), json=request_data, timeout=30.0)
        response.raise_for_status()
        project = response.json()

        # Display project info
        table = Table(title="Project Created", border_style="green")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Project ID", str(project["id"]))
        table.add_row("Name", project["title"])
        table.add_row("Description", project.get("description", "N/A"))
        table.add_row("Task Type", task_type)
        table.add_row("Created At", project.get("created_at", "N/A"))

        console.print(table)
        console.print("\n[green]✅ Project created successfully![/green]")
        console.print("[cyan]💡 Access Label Studio at: http://localhost:8082[/cyan]")

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "create project")
        raise typer.Exit(1)


@app.command("list")
def list_projects(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of projects to show"),
):
    """
    📋 List all annotation projects.

    Example:
        tawiza annotate list
        tawiza annotate list --limit 50
    """
    console.print("[cyan]Fetching annotation projects...[/cyan]\n")

    try:
        response = httpx.get(
            get_api_url("/annotations/projects"), params={"limit": limit}, timeout=10.0
        )
        response.raise_for_status()
        projects = response.json()

        if not projects:
            console.print("[yellow]No projects found[/yellow]")
            return

        # Display projects table
        table = Table(title=f"Annotation Projects ({len(projects)})", border_style="cyan")
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Name", style="green bold")
        table.add_column("Description", style="white")
        table.add_column("Tasks", justify="right")
        table.add_column("Labeled", justify="right")
        table.add_column("Created", style="dim")

        for project in projects:
            # Format created time
            try:
                created = datetime.fromisoformat(project["created_at"].replace("Z", "+00:00"))
                created_str = created.strftime("%Y-%m-%d %H:%M")
            except (ValueError, KeyError, AttributeError):
                created_str = project.get("created_at", "N/A")

            table.add_row(
                str(project["id"]),
                project["title"],
                project.get("description", "")[:50],
                str(project.get("task_number", 0)),
                str(project.get("total_annotations_number", 0)),
                created_str,
            )

        console.print(table)

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "list projects")
        raise typer.Exit(1)


@app.command()
def export(
    project_id: str = typer.Argument(..., help="Project ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output JSON file"),
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv)"),
):
    """
    📤 Export annotations from a project.

    Example:
        tawiza annotate export 1
        tawiza annotate export 1 --output annotations.json
        tawiza annotate export 1 -o data.csv -f csv
    """
    console.print(f"[cyan]Exporting annotations from project {project_id}...[/cyan]\n")

    try:
        response = httpx.get(
            get_api_url(f"/annotations/projects/{project_id}/export"),
            params={"format": format},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        count = len(data) if isinstance(data, list) else 1

        # Save to file if specified
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w") as f:
                json.dump(data, f, indent=2)
            console.print(f"[green]✅ Exported {count} annotations to {output}[/green]")
        else:
            # Print to console
            console.print(json.dumps(data, indent=2))
            console.print(f"\n[green]✅ Exported {count} annotations[/green]")

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "export annotations")
        raise typer.Exit(1)


@app.command()
def stats(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """
    📊 Show annotation statistics for a project.

    Example:
        tawiza annotate stats 1
    """
    console.print(f"[cyan]Fetching statistics for project {project_id}...[/cyan]\n")

    try:
        # Get project info
        response = httpx.get(get_api_url(f"/annotations/projects/{project_id}"), timeout=10.0)
        response.raise_for_status()
        project = response.json()

        # Display statistics
        table = Table(title=f"Project Stats: {project['title']}", border_style="cyan")
        table.add_column("Metric", style="cyan bold")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Tasks", str(project.get("task_number", 0)))
        table.add_row("Total Annotations", str(project.get("total_annotations_number", 0)))
        table.add_row("Labeled Tasks", str(project.get("num_tasks_with_annotations", 0)))
        table.add_row("Predictions", str(project.get("total_predictions_number", 0)))

        # Calculate completion rate
        total_tasks = project.get("task_number", 0)
        labeled_tasks = project.get("num_tasks_with_annotations", 0)
        if total_tasks > 0:
            completion_rate = (labeled_tasks / total_tasks) * 100
            table.add_row("Completion Rate", f"{completion_rate:.1f}%")

        console.print(table)

        # Additional info
        console.print("\n[bold]Project Info:[/bold]")
        console.print(f"  Name: {project['title']}")
        console.print(f"  Description: {project.get('description', 'N/A')}")
        console.print(f"  Created: {project.get('created_at', 'N/A')}")
        console.print(f"  URL: http://localhost:8082/projects/{project['id']}")

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "get stats")
        raise typer.Exit(1)


@app.command()
def upload(
    project_id: str = typer.Argument(..., help="Project ID"),
    data_file: Path = typer.Option(..., "--file", "-f", help="JSON file with tasks"),
):
    """
    📥 Upload tasks to an annotation project.

    Example:
        tawiza annotate upload 1 --file tasks.json
        tawiza annotate upload 1 -f data.json
    """
    console.print(f"[cyan]Uploading tasks to project {project_id}...[/cyan]\n")

    # Load tasks
    try:
        with open(data_file) as f:
            tasks = json.load(f)

        if not isinstance(tasks, list):
            tasks = [tasks]

        console.print(f"[cyan]Loaded {len(tasks)} tasks from {data_file}[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Error loading file: {e}[/red]")
        raise typer.Exit(1)

    # Upload tasks
    try:
        response = httpx.post(
            get_api_url(f"/annotations/projects/{project_id}/tasks"),
            json={"tasks": tasks},
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

        console.print(
            f"[green]✅ Uploaded {result.get('imported', len(tasks))} tasks successfully[/green]"
        )

        # Show summary
        table = Table(title="Upload Summary", border_style="green")
        table.add_column("Status", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Imported", str(result.get("imported", 0)))
        if result.get("skipped"):
            table.add_row("Skipped", str(result.get("skipped", 0)))
        if result.get("errors"):
            table.add_row("Errors", str(len(result.get("errors", []))))

        console.print(table)

        if result.get("errors"):
            console.print("\n[yellow]Errors:[/yellow]")
            for error in result.get("errors", [])[:5]:  # Show first 5 errors
                console.print(f"  - {error}")

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "upload tasks")
        raise typer.Exit(1)


@app.command()
def delete(
    project_id: str = typer.Argument(..., help="Project ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    🗑️ Delete an annotation project.

    Example:
        tawiza annotate delete 1
        tawiza annotate delete 1 --yes
    """
    if not confirm:
        confirmed = typer.confirm(
            f"Are you sure you want to delete project {project_id}? This cannot be undone."
        )
        if not confirmed:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    console.print(f"[cyan]Deleting project {project_id}...[/cyan]")

    try:
        response = httpx.delete(get_api_url(f"/annotations/projects/{project_id}"), timeout=10.0)
        response.raise_for_status()

        console.print(f"[green]✅ Project {project_id} deleted successfully[/green]")

    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as e:
        handle_api_error(e, "delete project")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
