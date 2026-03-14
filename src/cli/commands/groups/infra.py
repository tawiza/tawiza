"""Infrastructure Command Group - System, VM, Docker."""

import typer

from src.cli.commands.docker import app as docker_app
from src.cli.commands.system import app as system_app
from src.cli.commands.vm_sandbox_commands import app as vm_app

app = typer.Typer(
    name="infra", help="Infrastructure - Systeme, VMs et Docker", rich_markup_mode="rich"
)

# Ajouter les sous-commandes
app.add_typer(system_app, name="system", help="Gestion du systeme")
app.add_typer(vm_app, name="vm", help="Gestion des VMs sandbox")
app.add_typer(docker_app, name="docker", help="Gestion des containers Docker")


@app.command("status")
def infra_status():
    """Afficher le statut de l'infrastructure"""
    from rich.console import Console
    from rich.table import Table

    from src.cli.ui.theme import SUNSET_THEME

    console = Console()
    table = Table(title="Statut Infrastructure", border_style=SUNSET_THEME.accent_color)
    table.add_column("Composant", style="cyan")
    table.add_column("Statut", style="green")

    table.add_row("System", "Disponible")
    table.add_row("VM Sandbox", "Disponible")

    console.print(table)
