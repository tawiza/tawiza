"""Prompt management commands for Tawiza CLI."""


import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ..ui import ColorGradient, Icons, TextStyling, create_stars, icon
from ..utils import api, format_error, format_success

console = Console()
app = typer.Typer(help="Prompt template management")


@app.command("list")
def list_templates(
    format_filter: str | None = typer.Option(None, "--format", "-f", help="Filter by format (browser, alpaca, chatml, simple, system_user)"),
):
    """List all prompt templates with visual indicators.

    Examples:
        # List all templates
        tawiza prompts list

        # Filter browser templates
        tawiza prompts list --format browser
    """
    try:
        params = {}
        if format_filter:
            params["format_filter"] = format_filter

        data = api.get("/api/v1/prompts/templates", params=params)

        # Handle both list and dict responses
        if isinstance(data, dict):
            templates = data.get("templates", data.get("items", []))
        elif isinstance(data, list):
            templates = data
        else:
            templates = []

        if not templates:
            console.print("[yellow]No templates found[/yellow]")
            return

        # Header with gradient
        header = ColorGradient.create_gradient(
            f"Prompt Templates ({len(templates)})",
            "#FF1493",
            "#00CED1"
        )
        console.print()
        console.print(header, justify="center")
        console.print("=" * 80, style="dim cyan")
        console.print()

        # Create table with icons
        table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
        table.add_column(icon(Icons.TEMPLATE, "Template"), style="cyan", no_wrap=True)
        table.add_column(icon(Icons.INFO, "Format"), style="magenta")
        table.add_column(icon(Icons.VARIABLE, "Variables"), style="green")
        table.add_column(icon(Icons.STAR, "Popularity"), style="yellow", justify="center")
        table.add_column("Description", style="dim white")

        for template in templates:
            variables = ", ".join(template.get("variables", []))
            usage_count = template.get("usage_count", 0)

            # Create star rating based on usage
            stars = create_stars(usage_count, max_stars=5)

            table.add_row(
                template["name"],
                template["format"],
                variables or "-",
                stars,
                template.get("description", "")[:50],
            )

        console.print(table)
        console.print()

        # Footer tags
        console.print("[dim]Filter by format:[/dim]")
        tags = [
            TextStyling.create_tag("browser", bg_color="blue", fg_color="white"),
            TextStyling.create_tag("alpaca", bg_color="green", fg_color="white"),
            TextStyling.create_tag("chatml", bg_color="magenta", fg_color="white"),
            TextStyling.create_tag("system_user", bg_color="yellow", fg_color="black"),
        ]
        console.print("  ", *tags)
        console.print()

    except Exception as e:
        console.print(format_error(f"Failed to list templates: {e}"))
        raise typer.Exit(1)


@app.command("show")
def show_template(
    name: str = typer.Argument(..., help="Template name"),
):
    """Show details of a specific template.

    Examples:
        tawiza prompts show browser_navigation
    """
    try:
        template = api.get(f"/api/v1/prompts/templates/{name}")

        # Create info panel
        info = Text()
        info.append("Name: ", style="bold cyan")
        info.append(f"{template['name']}\n", style="white")
        info.append("Format: ", style="bold cyan")
        info.append(f"{template['format']}\n", style="magenta")
        info.append("Version: ", style="bold cyan")
        info.append(f"{template.get('version', '1.0')}\n", style="white")
        info.append("Usage: ", style="bold cyan")
        info.append(f"{template.get('usage_count', 0)} renders\n", style="yellow")
        info.append("Variables: ", style="bold cyan")
        info.append(f"{', '.join(template.get('variables', []))}\n", style="green")
        info.append("Description: ", style="bold cyan")
        info.append(f"{template.get('description', 'N/A')}\n", style="white")

        console.print(Panel(info, title=f"[bold]Template: {name}[/bold]", border_style="cyan"))

        # Show template content
        console.print("\n[bold cyan]Template:[/bold cyan]")
        syntax = Syntax(template["template"], "text", theme="monokai", line_numbers=False)
        console.print(syntax)

        # Show metadata if available
        if template.get("metadata"):
            console.print("\n[bold cyan]Metadata:[/bold cyan]")
            for key, value in template["metadata"].items():
                console.print(f"  {key}: {value}")

    except Exception as e:
        console.print(format_error(f"Failed to get template: {e}"))
        raise typer.Exit(1)


@app.command("create")
def create_template(
    name: str = typer.Argument(..., help="Template name"),
    format_type: str = typer.Option(..., "--format", "-f", help="Template format (browser, alpaca, chatml, simple, system_user)"),
    template: str = typer.Option(..., "--template", "-t", help="Template string with {variables}"),
    description: str = typer.Option("", "--description", "-d", help="Template description"),
    version: str = typer.Option("1.0", "--version", "-v", help="Template version"),
):
    """Create a new prompt template.

    Examples:
        # Create a browser template
        tawiza prompts create my_search --format browser \\
            --template "Go to {url} and search for {query}" \\
            --description "Custom search template"

        # Create a classification template
        tawiza prompts create sentiment --format alpaca \\
            --template "### Instruction:\\nClassify sentiment\\n\\n### Input:\\n{text}\\n\\n### Response:" \\
            --description "Sentiment analysis"
    """
    try:
        data = {
            "name": name,
            "format": format_type,
            "template": template,
            "description": description,
            "version": version,
        }

        result = api.post("/api/v1/prompts/templates", json=data)

        console.print(
            format_success(
                f"Template '{name}' created successfully!",
                {
                    "Name": result["name"],
                    "Format": result["format"],
                    "Variables": ", ".join(result.get("variables", [])),
                },
            )
        )

    except Exception as e:
        console.print(format_error(f"Failed to create template: {e}"))
        raise typer.Exit(1)


@app.command("render")
def render_template(
    name: str = typer.Argument(..., help="Template name"),
    variables: list[str] = typer.Option([], "--var", "-v", help="Variable in key=value format (can be used multiple times)"),
):
    """Render a template with variables.

    Examples:
        # Render browser template
        tawiza prompts render browser_navigation \\
            --var url=google.com \\
            --var action="search for Python"

        # Render classification template
        tawiza prompts render text_classification \\
            --var text="This is great!" \\
            --var categories="positive,negative,neutral"
    """
    try:
        # Parse variables
        var_dict = {}
        for var in variables:
            if "=" not in var:
                console.print(f"[red]Invalid variable format: {var}. Use key=value[/red]")
                raise typer.Exit(1)
            key, value = var.split("=", 1)
            var_dict[key.strip()] = value.strip()

        # Render template
        data = {
            "template_name": name,
            "variables": var_dict,
        }

        result = api.post("/api/v1/prompts/render", json=data)

        # Show rendered prompt
        console.print(f"\n[bold cyan]Template:[/bold cyan] {result['template_name']}")
        console.print(f"[bold cyan]Variables:[/bold cyan] {', '.join(f'{k}={v}' for k, v in result['variables_used'].items())}\n")

        console.print("[bold cyan]Rendered Prompt:[/bold cyan]")
        console.print(Panel(result["rendered_prompt"], border_style="green"))

    except Exception as e:
        console.print(format_error(f"Failed to render template: {e}"))
        raise typer.Exit(1)


@app.command("delete")
def delete_template(
    name: str = typer.Argument(..., help="Template name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a prompt template.

    Examples:
        tawiza prompts delete my_template
        tawiza prompts delete my_template --force
    """
    try:
        if not force:
            confirm = typer.confirm(f"Are you sure you want to delete template '{name}'?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)

        api.delete(f"/api/v1/prompts/templates/{name}")

        console.print(format_success(f"Template '{name}' deleted successfully!"))

    except Exception as e:
        console.print(format_error(f"Failed to delete template: {e}"))
        raise typer.Exit(1)


@app.command("stats")
def show_stats():
    """Show prompt usage statistics.

    Examples:
        tawiza prompts stats
    """
    try:
        stats = api.get("/api/v1/prompts/stats")

        # Create stats table
        table = Table(title="Prompt Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Templates", str(stats.get("total_templates", 0)))
        table.add_row("Total Renders", str(stats.get("total_renders", 0)))

        console.print(table)

        # Templates by format
        if stats.get("templates_by_format"):
            console.print("\n[bold cyan]Templates by Format:[/bold cyan]")
            format_table = Table(show_header=True, header_style="bold magenta")
            format_table.add_column("Format", style="magenta")
            format_table.add_column("Count", style="green", justify="right")

            for format_name, count in stats["templates_by_format"].items():
                format_table.add_row(format_name, str(count))

            console.print(format_table)

        # Renders by template
        if stats.get("renders_by_template"):
            console.print("\n[bold cyan]Most Used Templates:[/bold cyan]")
            render_table = Table(show_header=True, header_style="bold yellow")
            render_table.add_column("Template", style="cyan")
            render_table.add_column("Renders", style="yellow", justify="right")

            # Sort by renders (descending)
            sorted_renders = sorted(
                stats["renders_by_template"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10

            for template_name, render_count in sorted_renders:
                render_table.add_row(template_name, str(render_count))

            console.print(render_table)

    except Exception as e:
        console.print(format_error(f"Failed to get statistics: {e}"))
        raise typer.Exit(1)


@app.command("init-defaults")
def init_defaults():
    """Create default prompt templates.

    Examples:
        tawiza prompts init-defaults
    """
    try:
        result = api.post("/api/v1/prompts/templates/defaults")

        console.print(
            format_success(
                "Default templates created successfully!",
                {
                    "Status": result.get("status", "success"),
                    "Message": result.get("message", ""),
                    "Count": result.get("count", 0),
                },
            )
        )

    except Exception as e:
        console.print(format_error(f"Failed to create default templates: {e}"))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
