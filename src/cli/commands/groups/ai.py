"""AI Command Group - Chat, Agents, Models."""

import typer

from src.cli.commands.agents import app as agents_app
from src.cli.commands.chat import app as chat_app
from src.cli.commands.models import app as models_app

app = typer.Typer(
    name="ai", help="Intelligence Artificielle - Chat, Agents et Modeles", rich_markup_mode="rich"
)

# Ajouter les sous-commandes
app.add_typer(chat_app, name="chat", help="Chat avec l'assistant IA")
app.add_typer(agents_app, name="agents", help="Système d'agents IA")
app.add_typer(models_app, name="models", help="Gestion des modèles ML")


@app.command("status")
def ai_status():
    """Afficher le statut des services IA"""
    from rich.console import Console
    from rich.table import Table

    from src.cli.ui.theme import SUNSET_THEME

    console = Console()
    table = Table(title="Statut des Services IA", border_style=SUNSET_THEME.accent_color)
    table.add_column("Service", style="cyan")
    table.add_column("Statut", style="green")

    table.add_row("Chat", "Disponible")
    table.add_row("Agents", "Disponible")
    table.add_row("Models", "Disponible")

    console.print(table)
