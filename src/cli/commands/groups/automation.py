"""Automation Command Group - Browser, Live, Pipelines."""

import typer

from src.cli.commands.browser import app as browser_app
from src.cli.commands.live import app as live_app
from src.cli.commands.pipelines import app as pipelines_app

app = typer.Typer(
    name="automation",
    help="Automation - Browser, Live, Pipelines",
    rich_markup_mode="rich"
)

# Ajouter les sous-commandes
app.add_typer(browser_app, name="browser", help="Automation navigateur")
app.add_typer(live_app, name="live", help="Automation live interactive")
app.add_typer(pipelines_app, name="pipelines", help="Pipelines automatises")


@app.command("status")
def automation_status():
    """Afficher le statut des services d'automation"""
    from rich.console import Console
    from rich.table import Table

    from src.cli.ui.theme import SUNSET_THEME

    console = Console()
    table = Table(title="Statut des Services Automation", border_style=SUNSET_THEME.accent_color)
    table.add_column("Service", style="cyan")
    table.add_column("Statut", style="green")

    table.add_row("Browser", "Disponible")
    table.add_row("Live", "Disponible")

    console.print(table)
