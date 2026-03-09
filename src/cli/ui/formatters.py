"""
Formatters - Beautiful output formatting

Provides elegant formatters for various data types:
- Tables with borders and styling
- Trees for hierarchical data
- Charts (bar, line, sparkline)
- JSON with syntax highlighting
- Diffs with color coding
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from .theme import get_theme


class TableFormatter:
    """
    Elegant table formatter with themes

    Examples:
        >>> formatter = TableFormatter(theme="cyberpunk")
        >>> formatter.add_column("Name", style="bold")
        >>> formatter.add_row("template1", "100", "⭐⭐⭐⭐⭐")
        >>> formatter.render()
    """

    def __init__(
        self,
        theme: str = "cyberpunk",
        title: str | None = None,
        show_header: bool = True,
        show_lines: bool = True,
        expand: bool = False,
    ):
        self.theme = get_theme(theme)
        self.table = Table(
            title=title,
            show_header=show_header,
            show_lines=show_lines,
            expand=expand,
            border_style=self.theme.primary,
            header_style=f"bold {self.theme.accent}",
        )

    def add_column(
        self,
        name: str,
        *,
        style: str | None = None,
        justify: str = "left",
        width: int | None = None,
    ) -> None:
        """Add a column to the table"""
        self.table.add_column(
            name,
            style=style or self.theme.foreground,
            justify=justify,
            width=width,
        )

    def add_row(self, *values: Any, style: str | None = None) -> None:
        """Add a row to the table"""
        self.table.add_row(*[str(v) for v in values], style=style)

    def render(self, console: Console | None = None) -> None:
        """Render the table"""
        if console is None:
            console = Console(theme=self.theme.to_rich_theme())
        console.print(self.table)

    def to_string(self) -> str:
        """Get table as string"""
        console = Console(theme=self.theme.to_rich_theme(), record=True)
        console.print(self.table)
        return console.export_text()


class TreeFormatter:
    """
    Tree formatter for hierarchical data

    Examples:
        >>> formatter = TreeFormatter("Prompts", theme="ocean")
        >>> ml_branch = formatter.add("🤖 Machine Learning")
        >>> ml_branch.add("📊 text_classification")
        >>> formatter.render()
    """

    def __init__(
        self,
        label: str,
        theme: str = "cyberpunk",
        guide_style: str = "dim",
    ):
        self.theme = get_theme(theme)
        self.tree = Tree(
            label,
            guide_style=guide_style,
            style=self.theme.primary,
        )

    def add(
        self,
        label: str,
        *,
        style: str | None = None,
    ) -> Tree:
        """Add a branch to the tree"""
        return self.tree.add(
            label,
            style=style or self.theme.foreground,
        )

    def render(self, console: Console | None = None) -> None:
        """Render the tree"""
        if console is None:
            console = Console(theme=self.theme.to_rich_theme())
        console.print(self.tree)


class ChartFormatter:
    """
    ASCII art charts formatter

    Supports:
    - Bar charts (horizontal and vertical)
    - Sparklines (compact trend visualization)
    - Simple line charts
    """

    def __init__(self, theme: str = "cyberpunk"):
        self.theme = get_theme(theme)

    def bar_chart(
        self,
        data: dict[str, float],
        *,
        max_width: int = 40,
        char: str = "█",
        show_values: bool = True,
    ) -> str:
        """
        Create horizontal bar chart

        Args:
            data: Dict of label: value pairs
            max_width: Maximum bar width in characters
            char: Character to use for bars
            show_values: Show numeric values

        Returns:
            Formatted bar chart as string
        """
        if not data:
            return ""

        max_value = max(data.values())
        lines = []

        for label, value in data.items():
            # Calculate bar length
            bar_length = int(value / max_value * max_width) if max_value > 0 else 0

            # Create bar
            bar = char * bar_length

            # Format line
            line = f"{label:20} {bar} {value}" if show_values else f"{label:20} {bar}"

            lines.append(line)

        return "\n".join(lines)

    def sparkline(self, values: list[float], *, chars: str = "▁▂▃▄▅▆▇█") -> str:
        """
        Create sparkline visualization

        Args:
            values: List of numeric values
            chars: Characters for different levels

        Returns:
            Sparkline string
        """
        if not values:
            return ""

        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val

        if range_val == 0:
            return chars[0] * len(values)

        # Map values to character indices
        spark_chars = []
        for value in values:
            # Normalize to 0-1 range
            normalized = (value - min_val) / range_val
            # Map to character index
            char_index = int(normalized * (len(chars) - 1))
            spark_chars.append(chars[char_index])

        return "".join(spark_chars)

    def percentage_bar(
        self,
        value: float,
        *,
        total: float = 100.0,
        width: int = 20,
        filled_char: str = "█",
        empty_char: str = "░",
        show_percentage: bool = True,
    ) -> str:
        """
        Create percentage progress bar

        Args:
            value: Current value
            total: Total/max value
            width: Bar width in characters
            filled_char: Character for filled portion
            empty_char: Character for empty portion
            show_percentage: Show percentage text

        Returns:
            Formatted percentage bar
        """
        percentage = (value / total) * 100 if total > 0 else 0
        filled_width = int((value / total) * width) if total > 0 else 0
        empty_width = width - filled_width

        bar = filled_char * filled_width + empty_char * empty_width

        if show_percentage:
            return f"{bar} {percentage:.1f}%"
        return bar


class JsonFormatter:
    """
    JSON formatter with syntax highlighting

    Examples:
        >>> formatter = JsonFormatter(theme="dracula")
        >>> formatter.render({"key": "value"})
    """

    def __init__(self, theme: str = "cyberpunk", indent: int = 2):
        self.theme = get_theme(theme)
        self.indent = indent

    def render(
        self,
        data: Any,
        *,
        console: Console | None = None,
        line_numbers: bool = False,
    ) -> None:
        """Render JSON with syntax highlighting"""
        import json

        json_str = json.dumps(data, indent=self.indent, ensure_ascii=False)

        syntax = Syntax(
            json_str,
            "json",
            theme="monokai",
            line_numbers=line_numbers,
            word_wrap=True,
        )

        if console is None:
            console = Console(theme=self.theme.to_rich_theme())

        console.print(syntax)


class PanelFormatter:
    """
    Panel formatter for boxed content

    Examples:
        >>> formatter = PanelFormatter(theme="nord")
        >>> formatter.render("Important message", title="Notice")
    """

    def __init__(self, theme: str = "cyberpunk"):
        self.theme = get_theme(theme)

    def render(
        self,
        content: Any,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        border_style: str | None = None,
        console: Console | None = None,
    ) -> None:
        """Render content in a panel"""
        panel = Panel(
            str(content),
            title=title,
            subtitle=subtitle,
            border_style=border_style or self.theme.primary,
        )

        if console is None:
            console = Console(theme=self.theme.to_rich_theme())

        console.print(panel)


def create_stars(count: int, max_stars: int = 5) -> str:
    """
    Create star rating visualization

    Args:
        count: Usage count
        max_stars: Maximum number of stars

    Returns:
        Star string (e.g., "⭐⭐⭐⭐⭐")
    """
    # Logarithmic scale for stars
    if count == 0:
        stars = 0
    elif count < 100:
        stars = 1
    elif count < 500:
        stars = 2
    elif count < 1000:
        stars = 3
    elif count < 2000:
        stars = 4
    else:
        stars = 5

    return "⭐" * min(stars, max_stars)


def format_number(num: float, precision: int = 1) -> str:
    """
    Format large numbers with K/M/B suffixes

    Examples:
        >>> format_number(1234)
        '1.2K'
        >>> format_number(1234567)
        '1.2M'
    """
    if num < 1000:
        return str(int(num))
    elif num < 1_000_000:
        return f"{num/1000:.{precision}f}K"
    elif num < 1_000_000_000:
        return f"{num/1_000_000:.{precision}f}M"
    else:
        return f"{num/1_000_000_000:.{precision}f}B"
