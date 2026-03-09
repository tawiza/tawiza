#!/usr/bin/env python3
"""
Composants Rich UI pour Tawiza-V2 CLI
Fonctions utilitaires pour créer des panneaux colorés
"""


from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def create_success_panel(message: str, title: str = "Succès") -> Panel:
    """Créer un panneau de succès vert"""
    return Panel(
        Text(message, style="green"),
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        padding=1
    )

def create_error_panel(message: str, title: str = "Erreur") -> Panel:
    """Créer un panneau d'erreur rouge"""
    return Panel(
        Text(message, style="red"),
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=1
    )

def create_info_panel(message: str, title: str = "Information") -> Panel:
    """Créer un panneau d'information bleu"""
    return Panel(
        Text(message, style="blue"),
        title=f"[bold blue]{title}[/bold blue]",
        border_style="blue",
        padding=1
    )

def create_warning_panel(message: str, title: str = "Avertissement") -> Panel:
    """Créer un panneau d'avertissement jaune"""
    return Panel(
        Text(message, style="yellow"),
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        padding=1
    )
