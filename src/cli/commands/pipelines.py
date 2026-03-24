"""
Pipelines - Automated workflow execution system.

Allows defining and running multi-step automation pipelines via YAML files.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.ui.theme import SUNSET_THEME

app = typer.Typer(
    name="pipelines",
    help="Automated workflow pipelines",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()

# Pipeline storage directory
PIPELINES_DIR = Path.home() / ".tawiza" / "pipelines"
PIPELINES_DIR.mkdir(parents=True, exist_ok=True)


# ===== Pipeline Models =====


class PipelineStep:
    """A single step in a pipeline."""

    def __init__(self, name: str, action: str, params: dict[str, Any] = None):
        self.name = name
        self.action = action
        self.params = params or {}
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.duration = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "duration": self.duration,
        }


class Pipeline:
    """A pipeline containing multiple steps."""

    def __init__(self, name: str, description: str = "", steps: list[PipelineStep] = None):
        self.name = name
        self.description = description
        self.steps = steps or []
        self.status = "pending"
        self.started_at = None
        self.completed_at = None

    @classmethod
    def from_dict(cls, data: dict) -> "Pipeline":
        """Create pipeline from dictionary."""
        steps = [
            PipelineStep(
                name=s.get("name", f"Step {i + 1}"),
                action=s.get("action", "shell"),
                params=s.get("params", {}),
            )
            for i, s in enumerate(data.get("steps", []))
        ]
        return cls(
            name=data.get("name", "Unnamed Pipeline"),
            description=data.get("description", ""),
            steps=steps,
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Pipeline":
        """Load pipeline from YAML file."""
        try:
            import yaml

            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        except ImportError:
            # Fallback to simple parsing if PyYAML not available
            raise ImportError("PyYAML required. Install with: pip install pyyaml")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ===== Pipeline Executor =====


class PipelineExecutor:
    """Executes pipeline steps."""

    def __init__(self, pipeline: Pipeline, dry_run: bool = False):
        self.pipeline = pipeline
        self.dry_run = dry_run
        self.actions = {
            "shell": self._action_shell,
            "python": self._action_python,
            "http": self._action_http,
            "wait": self._action_wait,
            "browser": self._action_browser,
            "notify": self._action_notify,
            "condition": self._action_condition,
        }

    async def execute(self, console: Console, progress: Progress = None) -> bool:
        """Execute the pipeline."""
        self.pipeline.status = "running"
        self.pipeline.started_at = datetime.now().isoformat()
        success = True

        for _i, step in enumerate(self.pipeline.steps):
            step.status = "running"
            start_time = time.time()

            try:
                if self.dry_run:
                    console.print(
                        f"[dim][DRY RUN] Would execute: {step.action}({step.params})[/dim]"
                    )
                    step.result = {"dry_run": True}
                    step.status = "completed"
                else:
                    action_fn = self.actions.get(step.action)
                    if action_fn:
                        step.result = await action_fn(step.params)
                        step.status = "completed"
                    else:
                        raise ValueError(f"Unknown action: {step.action}")

            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                success = False
                # Don't break - continue to show failure in progress

            step.duration = time.time() - start_time

            if progress:
                progress.update(
                    progress.task_ids[0], advance=1, description=f"[cyan]{step.name}[/cyan]"
                )

            # Stop on failure unless continue_on_error is set
            if not success and not step.params.get("continue_on_error"):
                break

        self.pipeline.status = "completed" if success else "failed"
        self.pipeline.completed_at = datetime.now().isoformat()
        return success

    async def _action_shell(self, params: dict) -> dict:
        """Execute shell command."""
        import subprocess

        cmd = params.get("command", "echo 'No command specified'")
        timeout = params.get("timeout", 60)

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

        return {
            "returncode": result.returncode,
            "stdout": result.stdout[:1000],  # Limit output
            "stderr": result.stderr[:500],
        }

    async def _action_python(self, params: dict) -> dict:
        """Execute Python code."""
        code = params.get("code", "print('Hello')")
        exec_globals = {"__builtins__": __builtins__}

        exec(code, exec_globals)

        return {"executed": True}

    async def _action_http(self, params: dict) -> dict:
        """Make HTTP request."""
        import httpx

        url = params.get("url")
        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        data = params.get("data")
        timeout = params.get("timeout", 30)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data if isinstance(data, dict) else None,
                content=data if isinstance(data, str) else None,
            )

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text[:2000],  # Limit output
        }

    async def _action_wait(self, params: dict) -> dict:
        """Wait for specified duration."""
        seconds = params.get("seconds", 1)
        await asyncio.sleep(seconds)
        return {"waited": seconds}

    async def _action_browser(self, params: dict) -> dict:
        """Browser automation action."""
        task = params.get("task", "Navigate to page")
        url = params.get("url", "https://google.com")

        # This would integrate with browser agents
        console.print(f"[dim]Browser task: {task} at {url}[/dim]")

        return {"task": task, "url": url, "status": "simulated"}

    async def _action_notify(self, params: dict) -> dict:
        """Send notification."""
        message = params.get("message", "Pipeline notification")
        channel = params.get("channel", "console")

        console.print(f"[bold cyan]NOTIFY:[/bold cyan] {message}")

        return {"message": message, "channel": channel}

    async def _action_condition(self, params: dict) -> dict:
        """Conditional step."""
        condition = params.get("condition", "True")
        result = eval(condition)  # Be careful with eval in production!

        return {"condition": condition, "result": result}


# ===== CLI Commands =====


@app.command("run")
def run_pipeline(
    pipeline_file: str = typer.Argument(..., help="Path to pipeline YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show steps without executing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """
    Execute a pipeline from YAML file

    Examples:
        # Run a pipeline
        tawiza pipelines run my-pipeline.yaml

        # Dry run (preview only)
        tawiza pipelines run my-pipeline.yaml --dry-run
    """
    pipeline_path = Path(pipeline_file)

    if not pipeline_path.exists():
        # Check in default directory
        pipeline_path = PIPELINES_DIR / pipeline_file
        if not pipeline_path.exists():
            console.print(f"[red]Pipeline not found: {pipeline_file}[/red]")
            return

    try:
        pipeline = Pipeline.from_yaml(str(pipeline_path))
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]Error loading pipeline: {e}[/red]")
        return

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{pipeline.name}[/bold cyan]\n"
            f"[dim]{pipeline.description}[/dim]\n"
            f"[dim]Steps: {len(pipeline.steps)}[/dim]",
            title="Pipeline",
            border_style=SUNSET_THEME.accent_color,
        )
    )
    console.print()

    # Execute with progress
    executor = PipelineExecutor(pipeline, dry_run=dry_run)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        progress.add_task("Starting...", total=len(pipeline.steps))

        success = asyncio.run(executor.execute(console, progress))

    # Results
    console.print()

    if verbose:
        for step in pipeline.steps:
            status_icon = "✓" if step.status == "completed" else "✗"
            status_color = "green" if step.status == "completed" else "red"
            console.print(
                f"[{status_color}]{status_icon}[/{status_color}] {step.name} ({step.duration:.2f}s)"
            )

            if step.error:
                console.print(f"  [red]Error: {step.error}[/red]")

    # Summary
    completed = sum(1 for s in pipeline.steps if s.status == "completed")
    failed = sum(1 for s in pipeline.steps if s.status == "failed")

    if success:
        console.print(
            Panel(
                f"[green]Pipeline completed successfully[/green]\n"
                f"Steps: {completed}/{len(pipeline.steps)}",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]Pipeline failed[/red]\nCompleted: {completed}, Failed: {failed}",
                border_style="red",
            )
        )


@app.command("list")
def list_pipelines():
    """
    List available pipelines

    Examples:
        tawiza pipelines list
    """
    console.print()

    # Check default directory
    yaml_files = list(PIPELINES_DIR.glob("*.yaml")) + list(PIPELINES_DIR.glob("*.yml"))

    if not yaml_files:
        console.print("[yellow]No pipelines found[/yellow]")
        console.print(f"[dim]Create pipelines in: {PIPELINES_DIR}[/dim]")
        console.print("[dim]Or use: tawiza pipelines create <name>[/dim]")
        return

    table = Table(
        title="Available Pipelines", border_style=SUNSET_THEME.accent_color, show_header=True
    )
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Steps", justify="right")

    for yaml_file in yaml_files:
        try:
            pipeline = Pipeline.from_yaml(str(yaml_file))
            table.add_row(
                yaml_file.stem,
                pipeline.description[:40] + "..."
                if len(pipeline.description) > 40
                else pipeline.description,
                str(len(pipeline.steps)),
            )
        except Exception:
            table.add_row(yaml_file.stem, "[red]Error loading[/red]", "?")

    console.print(table)


@app.command("create")
def create_pipeline(
    name: str = typer.Argument(..., help="Pipeline name"),
    template: str = typer.Option(
        "basic", "--template", "-t", help="Template: basic, web-scrape, data-process"
    ),
):
    """
    Create a new pipeline from template

    Examples:
        # Create basic pipeline
        tawiza pipelines create my-pipeline

        # Create web scraping pipeline
        tawiza pipelines create scraper --template web-scrape
    """
    templates = {
        "basic": {
            "name": name,
            "description": f"Basic pipeline: {name}",
            "steps": [
                {"name": "Start", "action": "notify", "params": {"message": "Pipeline started"}},
                {
                    "name": "Main Task",
                    "action": "shell",
                    "params": {"command": "echo 'Hello from pipeline'"},
                },
                {
                    "name": "Complete",
                    "action": "notify",
                    "params": {"message": "Pipeline completed"},
                },
            ],
        },
        "web-scrape": {
            "name": name,
            "description": f"Web scraping pipeline: {name}",
            "steps": [
                {
                    "name": "Initialize",
                    "action": "notify",
                    "params": {"message": "Starting web scrape"},
                },
                {
                    "name": "Fetch Page",
                    "action": "http",
                    "params": {"url": "https://example.com", "method": "GET"},
                },
                {
                    "name": "Process Data",
                    "action": "python",
                    "params": {"code": "print('Processing data...')"},
                },
                {
                    "name": "Save Results",
                    "action": "shell",
                    "params": {"command": "echo 'Saving results'"},
                },
                {
                    "name": "Complete",
                    "action": "notify",
                    "params": {"message": "Scraping completed"},
                },
            ],
        },
        "data-process": {
            "name": name,
            "description": f"Data processing pipeline: {name}",
            "steps": [
                {
                    "name": "Load Data",
                    "action": "shell",
                    "params": {"command": "echo 'Loading data...'"},
                },
                {
                    "name": "Validate",
                    "action": "python",
                    "params": {"code": "print('Validating data...')"},
                },
                {
                    "name": "Transform",
                    "action": "python",
                    "params": {"code": "print('Transforming data...')"},
                },
                {
                    "name": "Export",
                    "action": "shell",
                    "params": {"command": "echo 'Exporting results...'"},
                },
                {
                    "name": "Notify",
                    "action": "notify",
                    "params": {"message": "Data processing complete"},
                },
            ],
        },
    }

    if template not in templates:
        console.print(f"[yellow]Unknown template: {template}[/yellow]")
        console.print(f"[dim]Available: {', '.join(templates.keys())}[/dim]")
        return

    pipeline_data = templates[template]
    output_path = PIPELINES_DIR / f"{name}.yaml"

    try:
        import yaml

        with open(output_path, "w") as f:
            yaml.dump(pipeline_data, f, default_flow_style=False, allow_unicode=True)

        console.print(f"[green]✓[/green] Pipeline created: {output_path}")
        console.print(f"[dim]Run with: tawiza pipelines run {name}.yaml[/dim]")

    except ImportError:
        # Fallback to JSON if PyYAML not available
        output_path = PIPELINES_DIR / f"{name}.json"
        with open(output_path, "w") as f:
            json.dump(pipeline_data, f, indent=2)

        console.print(f"[green]✓[/green] Pipeline created: {output_path}")
        console.print("[yellow]Note: PyYAML not installed, created JSON format[/yellow]")


@app.command("show")
def show_pipeline(pipeline_file: str = typer.Argument(..., help="Pipeline file to show")):
    """
    Show pipeline details

    Examples:
        tawiza pipelines show my-pipeline.yaml
    """
    pipeline_path = Path(pipeline_file)

    if not pipeline_path.exists():
        pipeline_path = PIPELINES_DIR / pipeline_file
        if not pipeline_path.exists():
            console.print(f"[red]Pipeline not found: {pipeline_file}[/red]")
            return

    try:
        pipeline = Pipeline.from_yaml(str(pipeline_path))
    except Exception as e:
        console.print(f"[red]Error loading pipeline: {e}[/red]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{pipeline.name}[/bold cyan]\n[dim]{pipeline.description}[/dim]",
            title="Pipeline Details",
            border_style=SUNSET_THEME.accent_color,
        )
    )

    # Steps table
    table = Table(title="Steps", border_style="dim", show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("Action")
    table.add_column("Parameters")

    for i, step in enumerate(pipeline.steps, 1):
        params_str = ", ".join(f"{k}={v}" for k, v in list(step.params.items())[:2])
        if len(step.params) > 2:
            params_str += "..."
        table.add_row(str(i), step.name, step.action, params_str[:40])

    console.print(table)


if __name__ == "__main__":
    app()
