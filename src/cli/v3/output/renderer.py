"""Output renderer with automatic format detection."""

import sys
from typing import Any, Optional

from rich.console import Console

from src.cli.v3.output.base import OutputFormat, OutputOptions
from src.cli.v3.output.formatters import CSVFormatter, JSONFormatter, TableFormatter

# Formatter registry
_formatters = {
    OutputFormat.JSON: JSONFormatter(),
    OutputFormat.TABLE: TableFormatter(),
    OutputFormat.CSV: CSVFormatter(),
}

console = Console()


def detect_format() -> OutputFormat:
    """Auto-detect the best output format.

    Returns:
        OutputFormat.TABLE if stdout is a TTY (human at terminal)
        OutputFormat.JSON if stdout is piped (machine processing)
    """
    if sys.stdout.isatty():
        return OutputFormat.TABLE
    return OutputFormat.JSON


def render(
    data: Any,
    format: OutputFormat = OutputFormat.AUTO,
    options: OutputOptions | None = None,
) -> str:
    """Render data to a formatted string.

    Args:
        data: Data to render
        format: Output format (AUTO for auto-detection)
        options: Formatting options

    Returns:
        Formatted string
    """
    if format == OutputFormat.AUTO:
        format = detect_format()

    formatter = _formatters.get(format)
    if not formatter:
        raise ValueError(f"Unknown format: {format}")

    return formatter.format(data, options)


def output(
    data: Any,
    format: OutputFormat = OutputFormat.AUTO,
    title: str | None = None,
    **kwargs,
) -> None:
    """Output data to console with automatic formatting.

    This is the main entry point for CLI output.

    Args:
        data: Data to output
        format: Output format (AUTO for auto-detection)
        title: Optional title for the output
        **kwargs: Additional options passed to OutputOptions

    Example:
        >>> output({"status": "ok", "count": 42})
        # If TTY: prints a formatted table
        # If pipe: prints {"status": "ok", "count": 42}

        >>> output(data, format=OutputFormat.JSON)
        # Always outputs JSON regardless of TTY
    """
    options = OutputOptions(title=title, **kwargs)

    if format == OutputFormat.AUTO:
        format = detect_format()

    rendered = render(data, format, options)

    # For JSON format to pipe, use print to avoid Rich formatting
    if format == OutputFormat.JSON and not sys.stdout.isatty():
        print(rendered)
    else:
        console.print(rendered, highlight=False)


def register_formatter(format: OutputFormat, formatter: Any) -> None:
    """Register a custom formatter.

    Args:
        format: The output format to register
        formatter: OutputFormatter instance
    """
    _formatters[format] = formatter
