"""Data Command Group - Import, Annotate, Export."""

import typer

from src.cli.commands.annotate import app as annotate_app
from src.cli.commands.data import app as data_core_app

app = typer.Typer(
    name="data",
    help="Gestion des Donnees - Import, Annotation, Export",
    rich_markup_mode="rich"
)

# Ajouter les sous-commandes
app.add_typer(data_core_app, name="manage", help="Gestion des datasets")
app.add_typer(annotate_app, name="annotate", help="Annotation de donnees")


@app.command("status")
def data_status():
    """Afficher le statut des services de donnees"""
    from rich.console import Console
    from rich.table import Table

    from src.cli.ui.theme import SUNSET_THEME

    console = Console()
    table = Table(title="Statut des Services Data", border_style=SUNSET_THEME.accent_color)
    table.add_column("Service", style="cyan")
    table.add_column("Statut", style="green")

    table.add_row("Datasets", "Disponible")
    table.add_row("Annotation", "Disponible")

    console.print(table)
