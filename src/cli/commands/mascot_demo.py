"""
Démo des animations de mascotte Tawiza.

Montre toutes les animations disponibles:
- BreathingMascot (respiration subtile)
- MascotSpinner (spinner avec mascotte)
- MascotProgressBar (barre de progression avec expressions)
"""

import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.ui.animations import (
    BreathingMascot,
    MascotProgressBar,
    MascotSpinner,
)
from src.cli.ui.mascot import mascot_says, print_welcome
from src.cli.ui.mascot_config import MascotConfig, MascotStyle
from src.cli.ui.mascot_games import WaitingGames
from src.cli.ui.mascot_gpu_widget import MascotGPUWidget

app = typer.Typer(
    name="mascot-demo",
    help="Démonstration des animations de mascotte",
    add_completion=False,
)

console = Console()


@app.command("all")
def demo_all():
    """
    Démonstration de toutes les animations de mascotte.

    Affiche séquentiellement:
    1. Bienvenue avec mascotte
    2. BreathingMascot (respiration)
    3. MascotSpinner
    4. MascotProgressBar
    """
    console.print()
    console.print(Panel(
        "[bold magenta]Démonstration des Animations Mascotte Tawiza[/bold magenta]",
        border_style="magenta"
    ))
    console.print()

    # 1. Welcome mascot
    console.print("[bold cyan]1. Mascotte de bienvenue[/bold cyan]")
    print_welcome()
    time.sleep(1)

    # 2. Breathing mascot
    console.print("\n[bold cyan]2. BreathingMascot - Animation de respiration (3 sec)[/bold cyan]")
    with BreathingMascot("Chargement des données...", mode="breathing") as mascot:
        time.sleep(1.5)
        mascot.update_message("Analyse en cours...")
        time.sleep(1.5)
    console.print("[green]✓[/green] Animation terminée\n")

    # 3. Working mascot
    console.print("[bold cyan]3. BreathingMascot - Mode working (2 sec)[/bold cyan]")
    with BreathingMascot("Traitement...", mode="working") as mascot:
        time.sleep(2)
    console.print("[green]✓[/green] Animation terminée\n")

    # 4. Thinking mascot
    console.print("[bold cyan]4. BreathingMascot - Mode thinking (2 sec)[/bold cyan]")
    with BreathingMascot("Réflexion...", mode="thinking") as mascot:
        time.sleep(2)
    console.print("[green]✓[/green] Animation terminée\n")

    # 5. Spinner
    console.print("[bold cyan]5. MascotSpinner - Spinner avec mascotte (2 sec)[/bold cyan]")
    with MascotSpinner("Connexion au serveur...") as spinner:
        time.sleep(1)
        spinner.update("Authentification...")
        time.sleep(1)
    console.print("[green]✓[/green] Spinner terminé\n")

    # 6. Progress bar
    console.print("[bold cyan]6. MascotProgressBar - Barre avec expressions[/bold cyan]")
    with MascotProgressBar(total=50, task="Téléchargement") as bar:
        for _i in range(50):
            bar.update(1)
            time.sleep(0.05)
    console.print("[green]✓[/green] Progression terminée\n")

    # Final message
    mascot_says("Toutes les animations sont prêtes!", "success")

    console.print()
    console.print(Panel(
        "[bold green]Utilisation dans votre code:[/bold green]\n\n"
        "[cyan]from src.cli.ui.animations import BreathingMascot, MascotSpinner, MascotProgressBar[/cyan]\n\n"
        "[yellow]# Context manager[/yellow]\n"
        "with BreathingMascot('Message...', mode='working') as mascot:\n"
        "    # votre code ici\n"
        "    mascot.update_message('Nouveau message')\n\n"
        "[yellow]# Spinner[/yellow]\n"
        "with MascotSpinner('Chargement...') as spinner:\n"
        "    spinner.update('Progression...')\n\n"
        "[yellow]# Progress bar[/yellow]\n"
        "with MascotProgressBar(total=100, task='Téléchargement') as bar:\n"
        "    bar.update(10)",
        title="Guide d'utilisation",
        border_style="cyan"
    ))


@app.command("breathing")
def demo_breathing(
    message: str = typer.Option("Chargement...", "--message", "-m", help="Message à afficher"),
    mode: str = typer.Option("breathing", "--mode", help="Mode: breathing, working, thinking"),
    duration: int = typer.Option(5, "--duration", "-d", help="Durée en secondes"),
):
    """
    Démonstration du BreathingMascot.

    Modes disponibles:
    - breathing: Respiration subtile (clignement des yeux)
    - working: Animation de travail (engrenage)
    - thinking: Animation de réflexion (bulle de pensée)
    """
    console.print(f"\n[cyan]BreathingMascot - Mode: {mode}[/cyan]")
    with BreathingMascot(message, mode=mode):
        time.sleep(duration)
    console.print("[green]✓[/green] Terminé\n")


@app.command("spinner")
def demo_spinner(
    message: str = typer.Option("Chargement...", "--message", "-m", help="Message initial"),
    duration: int = typer.Option(5, "--duration", "-d", help="Durée en secondes"),
):
    """
    Démonstration du MascotSpinner.
    """
    console.print("\n[cyan]MascotSpinner[/cyan]")
    with MascotSpinner(message) as spinner:
        time.sleep(duration / 2)
        spinner.update("Presque fini...")
        time.sleep(duration / 2)
    console.print("[green]✓[/green] Terminé\n")


@app.command("progress")
def demo_progress(
    total: int = typer.Option(100, "--total", "-t", help="Total de la progression"),
    task: str = typer.Option("Téléchargement", "--task", help="Nom de la tâche"),
    speed: float = typer.Option(0.05, "--speed", "-s", help="Vitesse (secondes par étape)"),
):
    """
    Démonstration du MascotProgressBar.

    La mascotte change d'expression selon le pourcentage:
    - 0%: (=^･ω･^=) Neutre
    - 25%: (=^･ω･^=)✨ Content
    - 50%: (=^◡^=)✨ Souriant
    - 75%: (=^▽^=)🎉 Excité
    - 100%: (=^◡^=)🎊 Célébration
    """
    console.print(f"\n[cyan]MascotProgressBar - {task}[/cyan]")
    with MascotProgressBar(total=total, task=task) as bar:
        for _i in range(total):
            bar.update(1)
            time.sleep(speed)
    console.print("[green]✓[/green] Terminé\n")


@app.command("help")
def show_help():
    """
    Afficher l'aide sur les animations disponibles.
    """
    table = Table(title="Animations de Mascotte Disponibles", border_style="cyan")
    table.add_column("Animation", style="cyan")
    table.add_column("Description")
    table.add_column("Utilisation")

    table.add_row(
        "BreathingMascot",
        "Animation de respiration subtile\nModes: breathing, working, thinking",
        "with BreathingMascot('msg', mode='working'):\n    ..."
    )
    table.add_row(
        "MascotSpinner",
        "Spinner avec mascotte intégrée\nMise à jour du message possible",
        "with MascotSpinner('msg') as s:\n    s.update('new')"
    )
    table.add_row(
        "MascotProgressBar",
        "Barre de progression\nMascotte change d'expression",
        "with MascotProgressBar(100, task='X') as b:\n    b.update(10)"
    )

    console.print()
    console.print(table)
    console.print()

    console.print("[dim]Lancez 'tawiza mascot-demo all' pour voir toutes les animations[/dim]")


@app.command("config")
def configure_mascot(
    style: str = typer.Option(None, "--style", "-s", help="Style: kawaii, cyberpunk, minimal, neon, retro"),
    name: str = typer.Option(None, "--name", "-n", help="Nom de la mascotte"),
    color: str = typer.Option(None, "--color", "-c", help="Couleur principale"),
):
    """
    Configure ta mascotte personnalisée.

    Personnalise le style, le nom et la couleur de ta mascotte.
    La configuration est sauvegardée dans configs/mascot.yaml.
    """
    config = MascotConfig.load()

    if style:
        try:
            config.style = MascotStyle(style)
        except ValueError:
            console.print(f"[red]Erreur:[/red] Style '{style}' invalide. Styles disponibles: kawaii, cyberpunk, minimal, neon, retro")
            return
    if name:
        config.name = name
    if color:
        config.color = color

    config.save()
    console.print("\n[green]✓[/green] Configuration sauvegardée!")
    console.print(f"  Style: [bold]{config.style.value}[/bold]")
    console.print(f"  Nom: [bold]{config.name}[/bold]")
    console.print(f"  Couleur: [{config.color}]{config.color}[/{config.color}]")
    console.print()


@app.command("gpu")
def show_gpu_status(
    duration: int = typer.Option(5, "--duration", "-d", help="Durée d'affichage en secondes"),
    live: bool = typer.Option(False, "--live", "-l", help="Affichage live avec rafraîchissement"),
):
    """
    Affiche le statut GPU avec la mascotte.

    Montre l'utilisation de la mémoire GPU, la température et la localisation (host ou VM).
    Utilise --live pour un affichage en temps réel avec rafraîchissement automatique.
    """
    widget = MascotGPUWidget()

    if live:
        console.print("\n[cyan]Surveillance GPU en temps réel...[/cyan]")
        console.print("[dim]Appuyez sur Ctrl+C pour arrêter[/dim]\n")
        try:
            widget.live_display(duration=duration, message="Surveillance GPU en cours...")
        except KeyboardInterrupt:
            console.print("\n[yellow]Arrêt de la surveillance[/yellow]")
    else:
        console.print()
        console.print(widget.render("Statut GPU actuel"))
        console.print()


@app.command("game")
def play_waiting_game(
    duration: int = typer.Option(10, "--duration", "-d", help="Durée en secondes"),
    game_type: str = typer.Option("catch", "--type", "-t", help="Type de jeu: catch, typing"),
):
    """
    Lance un mini-jeu d'attente.

    Jeux disponibles:
    - catch: La mascotte attrape des objets qui tombent
    - typing: Effet machine à écrire avec messages aléatoires
    """
    games = WaitingGames(console)

    console.print()
    if game_type == "catch":
        console.print("[cyan]Jeu de catch - La mascotte attrape les étoiles![/cyan]")
        console.print("[dim]Les objets tombent automatiquement, regardez la mascotte les attraper![/dim]\n")
        score = games.play_catch(duration=duration, title="Attrape les étoiles!")
        console.print(f"\n[bold green]Score final: {score} ⭐[/bold green]")
    elif game_type == "typing":
        console.print("[cyan]Effet machine à écrire[/cyan]\n")
        games.typing_effect(duration=duration)
        console.print("\n[green]✓[/green] Terminé")
    else:
        console.print(f"[red]Erreur:[/red] Type de jeu '{game_type}' invalide. Utilisez 'catch' ou 'typing'")
    console.print()


if __name__ == "__main__":
    app()
