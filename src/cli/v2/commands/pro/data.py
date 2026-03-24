"""Data commands for Tawiza CLI v2 pro."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.spinners import create_spinner
from src.cli.v2.ui.theme import THEME, footer, header

console = Console()


def register(app: typer.Typer) -> None:
    """Register data commands."""

    @app.command("data-import")
    def data_import(
        file: Path = typer.Argument(..., help="File to import (csv, json, parquet)"),
        name: str | None = typer.Option(None, "--name", "-n", help="Dataset name"),
        format: str | None = typer.Option(None, "--format", "-f", help="Force format"),
    ):
        """Import a dataset."""
        console.print(header("data import", 40))

        if not file.exists():
            msg = MessageBox()
            console.print(msg.error(f"File not found: {file}"))
            console.print(footer(40))
            return

        # Detect format
        if format is None:
            format = file.suffix.lstrip(".")

        dataset_name = name or file.stem

        console.print(f"  [bold]File:[/] {file}")
        console.print(f"  [bold]Name:[/] {dataset_name}")
        console.print(f"  [bold]Format:[/] {format}")
        console.print()

        with create_spinner(f"Importing {file.name}...", "dots"):
            try:
                if format == "csv":
                    import pandas as pd

                    df = pd.read_csv(file)
                    rows, cols = df.shape
                elif format == "json":
                    import pandas as pd

                    df = pd.read_json(file)
                    rows, cols = df.shape
                elif format == "parquet":
                    import pandas as pd

                    df = pd.read_parquet(file)
                    rows, cols = df.shape
                else:
                    msg = MessageBox()
                    console.print(msg.error(f"Unsupported format: {format}"))
                    console.print(footer(40))
                    return

                # Save to cache
                from src.cli.v2.utils.config import get_cache_dir

                cache_path = get_cache_dir() / f"{dataset_name}.parquet"
                df.to_parquet(cache_path)

                msg = MessageBox()
                console.print(msg.success("Dataset imported!", f"{rows} rows, {cols} columns"))

            except Exception as e:
                msg = MessageBox()
                console.print(msg.error(str(e)))

        console.print(footer(40))

    @app.command("data-export")
    def data_export(
        name: str = typer.Argument(..., help="Dataset name to export"),
        output: Path = typer.Argument(..., help="Output file"),
        format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
    ):
        """Export a dataset."""
        console.print(header("data export", 40))

        from src.cli.v2.utils.config import get_cache_dir

        cache_path = get_cache_dir() / f"{name}.parquet"

        if not cache_path.exists():
            msg = MessageBox()
            console.print(msg.error(f"Dataset not found: {name}"))
            console.print(footer(40))
            return

        # Detect format
        if format is None:
            format = output.suffix.lstrip(".")

        with create_spinner(f"Exporting to {output}...", "dots"):
            try:
                import pandas as pd

                df = pd.read_parquet(cache_path)

                if format == "csv":
                    df.to_csv(output, index=False)
                elif format == "json":
                    df.to_json(output, orient="records", indent=2)
                elif format == "parquet":
                    df.to_parquet(output)
                else:
                    msg = MessageBox()
                    console.print(msg.error(f"Unsupported format: {format}"))
                    console.print(footer(40))
                    return

                msg = MessageBox()
                console.print(msg.success(f"Exported to {output}"))

            except Exception as e:
                msg = MessageBox()
                console.print(msg.error(str(e)))

        console.print(footer(40))

    @app.command("data-list")
    def data_list():
        """List available datasets."""
        console.print(header("datasets", 40))

        from src.cli.v2.utils.config import get_cache_dir

        cache_dir = get_cache_dir()

        datasets = list(cache_dir.glob("*.parquet"))

        if not datasets:
            console.print("  [dim]No datasets found.[/]")
            console.print("  [dim]Import one with: tawiza pro data-import file.csv[/]")
        else:
            table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
            table.add_column("Name")
            table.add_column("Size")

            for ds in datasets:
                name = ds.stem
                size = f"{ds.stat().st_size / 1024:.1f} KB"
                table.add_row(name, size)

            console.print(table)

        console.print(footer(40))

    @app.command("data-delete")
    def data_delete(
        name: str = typer.Argument(..., help="Dataset name to delete"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Delete a dataset."""
        console.print(header("data delete", 40))

        from src.cli.v2.utils.config import get_cache_dir

        cache_path = get_cache_dir() / f"{name}.parquet"

        if not cache_path.exists():
            msg = MessageBox()
            console.print(msg.error(f"Dataset not found: {name}"))
            console.print(footer(40))
            return

        if not force:
            from rich.prompt import Confirm

            if not Confirm.ask(f"  Delete dataset '{name}'?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

        cache_path.unlink()
        msg = MessageBox()
        console.print(msg.success(f"Dataset '{name}' deleted"))
        console.print(footer(40))
