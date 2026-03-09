"""Browser automation commands for Tawiza CLI using OpenManus."""


import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from ..utils import api, format_error, format_success, format_table, format_tree

console = Console()
app = typer.Typer(help="Browser automation with OpenManus")


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural language task description"),
    url: str | None = typer.Option(None, "--url", "-u", help="Starting URL"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode"),
    max_actions: int = typer.Option(50, "--max-actions", "-m", help="Maximum actions"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Timeout in seconds"),
):
    """Execute a browser automation task with OpenManus.

    Examples:
        # Navigate and extract data
        tawiza browser run "Go to news.ycombinator.com and get top 5 articles"

        # Start from specific URL
        tawiza browser run "Find the pricing page" --url https://example.com

        # Fill a form
        tawiza browser run "Fill the contact form with name John and email john@test.com" --url https://example.com/contact
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("Starting browser automation...", total=None)

            # Prepare task config
            task_config = {
                "description": task,
                "max_actions": max_actions,
                "timeout": timeout,
                "headless": headless,
            }

            if url:
                task_config["url"] = url

            console.print(f"\n[dim]Task: {task}[/dim]")
            if url:
                console.print(f"[dim]Starting URL: {url}[/dim]")
            console.print(f"[dim]Mode: {'Headless' if headless else 'Headed'}[/dim]")
            console.print(f"[dim]Max actions: {max_actions}, Timeout: {timeout}s[/dim]\n")

            # Execute task
            result = api.post("/api/v1/browser/tasks", json=task_config)

            progress.update(task_id, description="✓ Task completed")

        # Show results
        console.print(
            format_success(
                "Browser task completed!",
                {
                    "Task ID": result.get("task_id", "N/A"),
                    "Status": result.get("status", "N/A"),
                    "Actions": result.get("actions_taken", 0),
                },
            )
        )

        # Show extracted data if available
        if result.get("data"):
            console.print("\n[cyan bold]Extracted Data:[/cyan bold]")
            tree = format_tree(result["data"], title="Results")
            console.print(tree)

        # Show screenshots if available
        if result.get("screenshots"):
            console.print(f"\n[dim]Screenshots saved: {len(result['screenshots'])} files[/dim]")

    except Exception as e:
        console.print(format_error("Browser task failed", str(e)))
        raise typer.Exit(1)


@app.command()
def navigate(
    url: str = typer.Argument(..., help="URL to navigate to"),
    screenshot: bool = typer.Option(True, "--screenshot/--no-screenshot", help="Take screenshot"),
):
    """Navigate to a URL and optionally take a screenshot."""
    try:
        console.print(f"[yellow]Navigating to {url}...[/yellow]")

        task_config = {
            "url": url,
            "action": "navigate",
            "options": {"screenshot": screenshot},
        }

        result = api.post("/api/v1/browser/tasks", json=task_config)

        console.print(format_success(f"Navigated to {url}"))

        if screenshot and result.get("screenshot"):
            console.print(f"[dim]Screenshot: {result['screenshot']}[/dim]")

    except Exception as e:
        console.print(format_error("Navigation failed", str(e)))
        raise typer.Exit(1)


@app.command()
def extract(
    url: str = typer.Argument(..., help="URL to extract data from"),
    target: str = typer.Argument(..., help="What to extract (e.g., 'article titles', 'prices')"),
    selector: str | None = typer.Option(None, "--selector", "-s", help="CSS selector (optional)"),
):
    """Extract data from a webpage using AI.

    Examples:
        tawiza browser extract https://news.ycombinator.com "top 10 article titles"
        tawiza browser extract https://example.com "all product prices" --selector ".price"
    """
    try:
        console.print(f"[yellow]Extracting '{target}' from {url}...[/yellow]")

        task_config = {
            "url": url,
            "action": "extract",
            "data": {"target": target},
        }

        if selector:
            task_config["selectors"] = {"main": selector}

        result = api.post("/api/v1/browser/tasks", json=task_config)

        console.print(format_success("Data extracted successfully!"))

        # Show extracted data
        if result.get("data"):
            console.print("\n[cyan bold]Extracted Data:[/cyan bold]")

            # Format as JSON with syntax highlighting
            import json
            json_str = json.dumps(result["data"], indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
            console.print(syntax)

    except Exception as e:
        console.print(format_error("Data extraction failed", str(e)))
        raise typer.Exit(1)


@app.command()
def tasks(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of tasks to show"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table, json)"),
):
    """List recent browser automation tasks."""
    try:
        response = api.get("/api/v1/browser/tasks", params={"limit": limit})
        tasks_list = response.get("tasks", [])

        if format_type == "json":
            console.print_json(data=response)
            return

        if not tasks_list:
            console.print("[yellow]No browser tasks found[/yellow]")
            return

        # Create table
        columns = [
            ("task_id", "Task ID", "cyan"),
            ("description", "Description", "magenta"),
            ("status", "Status", "green"),
            ("actions_taken", "Actions", "yellow"),
            ("created_at", "Created", "dim"),
        ]

        table = format_table(tasks_list, columns, title="Browser Tasks")
        console.print(table)

        console.print(f"\n[dim]Total: {len(tasks_list)} tasks[/dim]")

    except Exception as e:
        console.print(format_error("Failed to list tasks", str(e)))
        raise typer.Exit(1)


@app.command()
def status(
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Get status and details of a browser task."""
    try:
        task = api.get(f"/api/v1/browser/tasks/{task_id}")

        tree = format_tree(task, title=f"Browser Task: {task_id}")
        console.print(tree)

        # Show logs if available
        if task.get("logs"):
            console.print("\n[cyan bold]Task Logs:[/cyan bold]")
            for log in task["logs"][-10:]:  # Show last 10 logs
                console.print(f"[dim]{log}[/dim]")

    except Exception as e:
        if "404" in str(e):
            console.print(format_error(f"Task '{task_id}' not found"))
        else:
            console.print(format_error("Failed to get task status", str(e)))
        raise typer.Exit(1)


@app.command()
def screenshot(
    url: str = typer.Argument(..., help="URL to screenshot"),
    output: str = typer.Option("screenshot.png", "--output", "-o", help="Output file path"),
    full_page: bool = typer.Option(False, "--full-page", help="Capture full page"),
):
    """Take a screenshot of a webpage."""
    try:
        console.print(f"[yellow]Taking screenshot of {url}...[/yellow]")

        task_config = {
            "url": url,
            "action": "screenshot",
            "options": {
                "output": output,
                "full_page": full_page,
            },
        }

        result = api.post("/api/v1/browser/tasks", json=task_config)

        console.print(
            format_success(
                "Screenshot captured!",
                {"File": result.get("screenshot", output)},
            )
        )

    except Exception as e:
        console.print(format_error("Screenshot failed", str(e)))
        raise typer.Exit(1)


@app.command()
def fill_form(
    url: str = typer.Argument(..., help="URL of the form"),
    fields: str = typer.Argument(..., help="Form fields as JSON (e.g., '{\"name\":\"John\",\"email\":\"john@test.com\"}')" ),
    submit: bool = typer.Option(False, "--submit", help="Submit the form after filling"),
):
    """Fill a web form with provided data.

    Example:
        tawiza browser fill-form https://example.com/contact '{"name":"John","email":"john@test.com"}' --submit
    """
    try:
        import json

        console.print(f"[yellow]Filling form at {url}...[/yellow]")

        # Parse JSON fields
        try:
            fields_dict = json.loads(fields)
        except json.JSONDecodeError:
            console.print(format_error("Invalid JSON format for fields"))
            raise typer.Exit(1)

        task_config = {
            "url": url,
            "action": "fill_form",
            "data": fields_dict,
            "options": {"submit": submit},
        }

        result = api.post("/api/v1/browser/tasks", json=task_config)

        action = "filled and submitted" if submit else "filled"
        console.print(format_success(f"Form {action} successfully!"))

        if result.get("screenshot"):
            console.print(f"[dim]Screenshot: {result['screenshot']}[/dim]")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(format_error("Form filling failed", str(e)))
        raise typer.Exit(1)


@app.command()
def click(
    url: str = typer.Argument(..., help="URL of the page"),
    selector: str = typer.Argument(..., help="CSS selector of element to click"),
    wait_after: int = typer.Option(1000, "--wait", "-w", help="Wait time after click (ms)"),
):
    """Click an element on a webpage.

    Example:
        tawiza browser click https://example.com "#submit-button"
    """
    try:
        console.print(f"[yellow]Clicking element '{selector}' at {url}...[/yellow]")

        task_config = {
            "url": url,
            "action": "click",
            "selectors": {"target": selector},
            "options": {"wait_after": wait_after},
        }

        result = api.post("/api/v1/browser/tasks", json=task_config)

        console.print(format_success("Element clicked successfully!"))

        if result.get("screenshot"):
            console.print(f"[dim]Screenshot: {result['screenshot']}[/dim]")

    except Exception as e:
        console.print(format_error("Click action failed", str(e)))
