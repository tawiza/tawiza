"""Config commands for Tawiza CLI v2 pro."""


import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.cli.v2.ui.components import MessageBox
from src.cli.v2.ui.theme import THEME, footer, header
from src.cli.v2.utils.config import CONFIG, DEFAULT_CONFIG

console = Console()


def register(app: typer.Typer) -> None:
    """Register config commands."""

    @app.command("config-show")
    def config_show(
        key: str | None = typer.Argument(None, help="Specific key to show"),
    ):
        """Show current configuration."""
        console.print(header("config", 40))

        if key:
            value = CONFIG.get(key)
            if value is not None:
                console.print(f"  {key} = {value}")
            else:
                msg = MessageBox()
                console.print(msg.error(f"Unknown key: {key}"))
        else:
            table = Table(show_header=True, header_style=f"bold {THEME['accent']}")
            table.add_column("Key")
            table.add_column("Value")
            table.add_column("Default")

            for key, value in CONFIG.items():
                default = DEFAULT_CONFIG.get(key, "")
                is_default = value == default
                value_str = str(value)
                if not is_default:
                    value_str = f"[{THEME['warning']}]{value_str}[/]"
                table.add_row(key, value_str, str(default))

            console.print(table)

        console.print(footer(40))

    @app.command("config-set")
    def config_set(
        key: str = typer.Argument(..., help="Configuration key"),
        value: str = typer.Argument(..., help="New value"),
    ):
        """Set a configuration value."""
        console.print(header("config set", 40))

        old_value = CONFIG.get(key)
        if old_value is None:
            msg = MessageBox()
            console.print(msg.error(
                f"Unknown key: {key}",
                [f"Available keys: {', '.join(DEFAULT_CONFIG.keys())}"]
            ))
            console.print(footer(40))
            return

        if CONFIG.set(key, value):
            new_value = CONFIG.get(key)
            console.print(f"  [dim]Old:[/] {key} = {old_value}")
            console.print(f"  [bold]New:[/] {key} = {new_value}")
            console.print()
            msg = MessageBox()
            console.print(msg.success("Configuration updated"))
        else:
            msg = MessageBox()
            console.print(msg.error("Failed to set configuration"))

        console.print(footer(40))

    @app.command("config-reset")
    def config_reset(
        key: str | None = typer.Argument(None, help="Key to reset (or all if not specified)"),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    ):
        """Reset configuration to defaults."""
        console.print(header("config reset", 40))

        if key:
            # Reset single key
            if key not in DEFAULT_CONFIG:
                msg = MessageBox()
                console.print(msg.error(f"Unknown key: {key}"))
                console.print(footer(40))
                return

            if not force and not Confirm.ask(f"  Reset '{key}' to default?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

            default_value = DEFAULT_CONFIG[key]
            CONFIG.set(key, default_value)
            console.print(f"  {key} = {default_value}")
            msg = MessageBox()
            console.print(msg.success(f"Key '{key}' reset"))
        else:
            # Reset all
            if not force and not Confirm.ask("  Reset ALL configuration to defaults?"):
                console.print("  [dim]Cancelled.[/]")
                console.print(footer(40))
                return

            CONFIG.reset()
            msg = MessageBox()
            console.print(msg.success("Configuration reset to defaults"))

        console.print(footer(40))

    @app.command("config-edit")
    def config_edit():
        """Interactive configuration editor."""
        console.print(header("config editor", 40))
        console.print()
        console.print("  [bold]Interactive Configuration Editor[/]")
        console.print("  [dim]Press Enter to keep current value[/]")
        console.print()

        for key, default in DEFAULT_CONFIG.items():
            current = CONFIG.get(key)
            value_type = type(default).__name__

            if isinstance(default, bool):
                # Boolean prompt
                new_value = Confirm.ask(
                    f"  {key}",
                    default=current
                )
            else:
                # Text prompt
                prompt_text = f"  {key} [{value_type}]"
                new_value = Prompt.ask(
                    prompt_text,
                    default=str(current)
                )

            if str(new_value) != str(current):
                CONFIG.set(key, new_value)
                console.print("    [green]→ Updated[/]")

        console.print()
        msg = MessageBox()
        console.print(msg.success("Configuration saved"))
        console.print(footer(40))

    @app.command("config-path")
    def config_path():
        """Show configuration file paths."""
        console.print(header("config paths", 40))

        from src.cli.v2.utils.config import (
            CACHE_DIR,
            CONFIG_DIR,
            CONFIG_FILE,
            HISTORY_DIR,
            LOGS_DIR,
        )

        console.print(f"  [bold]Config dir:[/]  {CONFIG_DIR}")
        console.print(f"  [bold]Config file:[/] {CONFIG_FILE}")
        console.print(f"  [bold]Cache dir:[/]   {CACHE_DIR}")
        console.print(f"  [bold]History dir:[/] {HISTORY_DIR}")
        console.print(f"  [bold]Logs dir:[/]    {LOGS_DIR}")

        console.print(footer(40))
