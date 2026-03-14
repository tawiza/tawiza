"""Rich table output formatter."""

from dataclasses import asdict, is_dataclass
from io import StringIO
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.v3.output.base import OutputFormatter, OutputOptions


class TableFormatter(OutputFormatter):
    """Formats output as Rich tables."""

    def __init__(self):
        self.console = Console(file=StringIO(), force_terminal=True)

    def format(self, data: Any, options: OutputOptions | None = None) -> str:
        """Format data as Rich table.

        Args:
            data: Data to format (dict or list of dicts)
            options: Formatting options

        Returns:
            Rendered table string
        """
        opts = options or OutputOptions()

        # Convert dataclasses to dicts
        if is_dataclass(data) and not isinstance(data, type):
            data = asdict(data)

        # Create console for rendering
        buffer = StringIO()
        console = Console(
            file=buffer,
            force_terminal=opts.colors,
            width=opts.max_width or 120,
        )

        if isinstance(data, list):
            table = self._list_to_table(data, opts)
        elif isinstance(data, dict):
            table = self._dict_to_table(data, opts)
        else:
            # Fallback for other types
            console.print(str(data))
            return buffer.getvalue()

        if opts.title:
            console.print(Panel(table, title=opts.title, border_style="cyan"))
        else:
            console.print(table)

        return buffer.getvalue()

    def supports_streaming(self) -> bool:
        """Tables can be streamed row by row."""
        return True

    def _list_to_table(self, data: list, opts: OutputOptions) -> Table:
        """Convert list of dicts to Rich table."""
        if not data:
            return Table()

        # Get columns from first item
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            columns = ["Value"]
            data = [{"Value": item} for item in data]

        table = Table(
            show_header=opts.show_header,
            header_style="bold cyan",
        )

        for col in columns:
            table.add_column(col.replace("_", " ").title())

        for row in data:
            if isinstance(row, dict):
                table.add_row(*[self._format_value(row.get(col, "")) for col in columns])
            else:
                table.add_row(str(row))

        return table

    def _dict_to_table(self, data: dict, opts: OutputOptions) -> Table:
        """Convert dict to key-value table."""
        table = Table(
            show_header=opts.show_header,
            header_style="bold cyan",
        )

        table.add_column("Property", style="cyan")
        table.add_column("Value")

        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            table.add_row(formatted_key, self._format_value(value))

        return table

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a single value for display."""
        if value is None:
            return "[dim]—[/dim]"
        if isinstance(value, bool):
            return "[green]Yes[/green]" if value else "[red]No[/red]"
        if isinstance(value, float):
            return f"{value:.2f}"
        if isinstance(value, list):
            return ", ".join(str(v) for v in value[:5])
        if isinstance(value, dict):
            return f"{{...}} ({len(value)} items)"
        return str(value)
