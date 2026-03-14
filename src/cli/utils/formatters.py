"""Rich formatting utilities for CLI output."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()


def format_table(
    data: list[dict[str, Any]],
    columns: list[tuple],
    title: str | None = None,
    show_lines: bool = False,
) -> Table:
    """Create a Rich table from data.

    Args:
        data: List of dictionaries containing row data
        columns: List of (key, header, style) tuples
        title: Optional table title
        show_lines: Show lines between rows

    Returns:
        Rich Table object
    """
    table = Table(title=title, show_lines=show_lines)

    # Add columns
    for key, header, style in columns:
        table.add_column(header, style=style)

    # Add rows
    for item in data:
        row = []
        for key, _, _ in columns:
            value = item.get(key, "")
            # Handle nested keys (e.g., "metrics.accuracy")
            if "." in key:
                keys = key.split(".")
                value = item
                for k in keys:
                    value = value.get(k, "") if isinstance(value, dict) else ""
            row.append(str(value) if value is not None else "")
        table.add_row(*row)

    return table


def format_status(
    title: str,
    items: dict[str, Any],
    success: bool = True,
) -> Panel:
    """Create a status panel.

    Args:
        title: Panel title
        items: Dictionary of status items
        success: Whether status is successful

    Returns:
        Rich Panel object
    """
    text = Text()
    for key, value in items.items():
        text.append(f"{key}: ", style="cyan bold")
        text.append(f"{value}\n", style="green" if success else "red")

    border_style = "green" if success else "red"
    return Panel(text, title=f"[bold]{title}[/bold]", border_style=border_style)


def format_error(message: str, details: str | None = None) -> Panel:
    """Create an error panel.

    Args:
        message: Error message
        details: Optional error details

    Returns:
        Rich Panel object
    """
    text = Text()
    text.append(f"{message}\n", style="red bold")
    if details:
        text.append(f"\n{details}", style="red")

    return Panel(text, title="[bold red]Error[/bold red]", border_style="red")


def format_success(message: str, details: dict[str, Any] | None = None) -> Panel:
    """Create a success panel.

    Args:
        message: Success message
        details: Optional success details

    Returns:
        Rich Panel object
    """
    text = Text()
    text.append(f"{message}\n", style="green bold")

    if details:
        text.append("\n")
        for key, value in details.items():
            text.append(f"{key}: ", style="cyan")
            text.append(f"{value}\n", style="white")

    return Panel(text, title="[bold green]Success[/bold green]", border_style="green")


def format_health_status(services: dict[str, dict[str, Any]]) -> Panel:
    """Format health check status for multiple services.

    Args:
        services: Dictionary of service name -> health status

    Returns:
        Rich Panel with health status
    """
    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Service", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    all_healthy = True
    for service, status in services.items():
        is_healthy = status.get("status") == "healthy" or status.get("healthy", False)
        all_healthy = all_healthy and is_healthy

        status_icon = "✓" if is_healthy else "✗"
        status_style = "green" if is_healthy else "red"

        details = status.get("details", "")
        if isinstance(details, dict):
            details = ", ".join(f"{k}={v}" for k, v in details.items())

        table.add_row(
            service,
            f"[{status_style}]{status_icon}[/{status_style}]",
            str(details) or "-",
        )

    border_style = "green" if all_healthy else "red"
    title = (
        "[bold green]All Services Healthy[/bold green]"
        if all_healthy
        else "[bold red]Some Services Unhealthy[/bold red]"
    )

    return Panel(table, title=title, border_style=border_style)


def format_tree(data: dict[str, Any], title: str = "Data") -> Tree:
    """Create a Rich tree from nested data.

    Args:
        data: Nested dictionary
        title: Tree title

    Returns:
        Rich Tree object
    """
    tree = Tree(f"[bold cyan]{title}[/bold cyan]")

    def add_items(node: Tree, items: dict[str, Any]):
        for key, value in items.items():
            if isinstance(value, dict):
                branch = node.add(f"[cyan]{key}[/cyan]")
                add_items(branch, value)
            elif isinstance(value, list):
                branch = node.add(f"[cyan]{key}[/cyan] ({len(value)} items)")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        sub_branch = branch.add(f"[dim]Item {i}[/dim]")
                        add_items(sub_branch, item)
                    else:
                        branch.add(f"[dim]{item}[/dim]")
            else:
                node.add(f"[cyan]{key}[/cyan]: [green]{value}[/green]")

    add_items(tree, data)
    return tree


def print_table(table: Table):
    """Print a Rich table to console.

    Args:
        table: Rich Table object
    """
    console.print(table)


def print_panel(panel: Panel):
    """Print a Rich panel to console.

    Args:
        panel: Rich Panel object
    """
    console.print(panel)


def print_tree(tree: Tree):
    """Print a Rich tree to console.

    Args:
        tree: Rich Tree object
    """
    console.print(tree)
