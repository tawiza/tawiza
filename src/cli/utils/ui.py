#!/usr/bin/env python3
"""
Utilitaires UI pour Tawiza-V2 CLI
Thème sunset et composants d'interface
"""

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Configuration du thème sunset
SUNSET_THEME = {
    "header_color": "#FF6B35",  # Orange coucher de soleil
    "accent_color": "#F7931E",  # Orange doré
    "success_color": "#FFD23F",  # Jaune soleil
    "info_color": "#06FFA5",  # Turquoise
    "warning_color": "#FF8E53",  # Orange clair
    "error_color": "#FF5252",  # Rouge corail
    "text_color": "#F0F0F0",  # Blanc cassé
    "dim_color": "#B0B0B0",  # Gris clair
}

console = Console()


def show_sunset_header():
    """Afficher l'en-tête avec thème sunset"""
    header_text = Text()
    header_text.append("🌅 ", style=SUNSET_THEME["header_color"])
    header_text.append(
        "Tawiza-V2 Advanced AI Agents System", style=f"bold {SUNSET_THEME['header_color']}"
    )
    header_text.append(" 🤖", style=SUNSET_THEME["header_color"])

    console.print(
        Panel(
            Align.center(header_text),
            style=f"{SUNSET_THEME['header_color']}",
            box=box.DOUBLE,
            padding=1,
        )
    )

    # Sous-titre
    subtitle = Text(
        "Système Multi-Agents Intelligent avec Optimisation GPU", style=SUNSET_THEME["dim_color"]
    )
    console.print(Align.center(subtitle))
    console.print()


def show_sunset_footer():
    """Afficher le pied de page avec thème sunset"""
    footer_text = Text()
    footer_text.append("🌅 ", style=SUNSET_THEME["header_color"])
    footer_text.append("Tawiza-V2 ", style=f"bold {SUNSET_THEME['header_color']}")
    footer_text.append("v2.0.3", style=SUNSET_THEME["accent_color"])
    footer_text.append(" - ", style=SUNSET_THEME["dim_color"])
    footer_text.append("Performance: 52+ tokens/sec", style=SUNSET_THEME["success_color"])
    footer_text.append(" - ", style=SUNSET_THEME["dim_color"])
    footer_text.append("GPU: AMD RX 7900 XTX", style=SUNSET_THEME["info_color"])
    footer_text.append(" 🌅", style=SUNSET_THEME["header_color"])

    console.print(
        Panel(
            Align.center(footer_text),
            style=f"{SUNSET_THEME['header_color']}",
            box=box.ROUNDED,
            padding=1,
        )
    )


def create_sunset_table(title: str, show_header: bool = True) -> Table:
    """Créer un tableau avec le thème sunset"""
    return Table(
        title=title,
        box=box.ROUNDED,
        show_header=show_header,
        header_style=f"bold {SUNSET_THEME['accent_color']}",
        border_style=SUNSET_THEME["accent_color"],
    )


def create_status_panel(status: str, message: str, success: bool = True) -> Panel:
    """Créer un panneau de statut avec thème sunset"""
    if success:
        color = SUNSET_THEME["success_color"]
        icon = "✅"
    else:
        color = SUNSET_THEME["error_color"]
        icon = "❌"

    content = Text()
    content.append(f"{icon} ", style=color)
    content.append(f"{status}", style=f"bold {color}")
    content.append(f"\n{message}", style=SUNSET_THEME["text_color"])

    return Panel(content, style=color, box=box.ROUNDED, padding=1)


def create_progress_bar(description: str, total: int = 100) -> None:
    """Créer une barre de progression avec thème sunset"""
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            complete_style=SUNSET_THEME["success_color"],
            finished_style=SUNSET_THEME["success_color"],
        ),
        TaskProgressColumn(),
        console=console,
    )


def format_performance_metric(name: str, value: float, unit: str = "") -> str:
    """Formater une métrique de performance avec couleurs"""
    if value >= 90:
        color = SUNSET_THEME["success_color"]
        icon = "🟢"
    elif value >= 70:
        color = SUNSET_THEME["warning_color"]
        icon = "🟡"
    else:
        color = SUNSET_THEME["error_color"]
        icon = "🔴"

    return f"[{color}]{icon} {name}: {value:.1f}{unit}[/{color}]"


def create_agent_status_table() -> Table:
    """Créer un tableau de statut des agents"""
    table = create_sunset_table("Statut des Agents")
    table.add_column("Agent", style=SUNSET_THEME["info_color"])
    table.add_column("Statut", justify="center")
    table.add_column("Performance", justify="right")
    table.add_column("Détails", style=SUNSET_THEME["dim_color"])

    # Données de démonstration
    agents = [
        ("🧠 Multi-Agent System", "✅ Actif", "100%", "Coordination intelligente"),
        ("📊 Data Analyst Agent", "✅ Prêt", "95%", "Analyse de données intelligente"),
        ("🤖 ML Engineer Agent", "✅ Prêt", "92%", "Pipeline ML automatisé"),
        ("🌐 Browser Automation", "✅ Prêt", "88%", "Automation web avancée"),
        ("💻 Code Generator", "✅ Prêt", "96%", "Génération de code intelligente"),
        ("🎮 GPU Optimizer", "✅ Actif", "98%", "Optimisation GPU spécialisée"),
    ]

    for agent, status, perf, details in agents:
        table.add_row(agent, status, perf, details)

    return table


def create_system_metrics_table() -> Table:
    """Créer un tableau de métriques système"""
    table = create_sunset_table("Métriques Système")
    table.add_column("Métrique", style=SUNSET_THEME["info_color"])
    table.add_column("Valeur", justify="right")
    table.add_column("Status", justify="center")

    # Données de démonstration
    metrics = [
        ("CPU Utilisation", "72.3%", "🟢"),
        ("Memory Utilisation", "65.1%", "🟢"),
        ("GPU Utilisation", "85.2%", "🟡"),
        ("Tâches Actives", "3", "📋"),
        ("File d'Attente", "2", "⏰"),
    ]

    for metric, value, status in metrics:
        table.add_row(metric, value, status)

    return table


def show_loading_animation(message: str, duration: float = 2.0) -> None:
    """Afficher une animation de chargement"""
    import time

    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(
            f"[bold {SUNSET_THEME['info_color']}]{message}[/bold {SUNSET_THEME['info_color']}]",
            total=None,
        )
        time.sleep(duration)


def create_error_panel(error_message: str, suggestion: str = "") -> Panel:
    """Créer un panneau d'erreur avec suggestion"""
    content = Text()
    content.append("❌ ", style=SUNSET_THEME["error_color"])
    content.append(f"{error_message}", style=f"bold {SUNSET_THEME['error_color']}")

    if suggestion:
        content.append(f"\n💡 {suggestion}", style=SUNSET_THEME["info_color"])

    return Panel(content, style=SUNSET_THEME["error_color"], box=box.ROUNDED, padding=1)


def create_success_panel(success_message: str, next_steps: str = "") -> Panel:
    """Créer un panneau de succès avec étapes suivantes"""
    content = Text()
    content.append("✅ ", style=SUNSET_THEME["success_color"])
    content.append(f"{success_message}", style=f"bold {SUNSET_THEME['success_color']}")

    if next_steps:
        content.append(f"\n🎯 {next_steps}", style=SUNSET_THEME["accent_color"])

    return Panel(content, style=SUNSET_THEME["success_color"], box=box.ROUNDED, padding=1)


def format_agent_info(agent_type: str, status: str, performance: str, details: str) -> str:
    """Formater les informations d'un agent"""
    return f"[bold {SUNSET_THEME['info_color']}]{agent_type}[/bold {SUNSET_THEME['info_color']}] - {status} - {performance} - {details}"


def create_debug_info(component: str, level: str, message: str) -> str:
    """Créer une information de débogage formatée"""
    level_colors = {
        "DEBUG": SUNSET_THEME["dim_color"],
        "INFO": SUNSET_THEME["info_color"],
        "WARNING": SUNSET_THEME["warning_color"],
        "ERROR": SUNSET_THEME["error_color"],
    }

    color = level_colors.get(level, SUNSET_THEME["text_color"])
    return f"[{color}][{level}] {component}: {message}[/{color}]"


# Export des fonctions
__all__ = [
    "SUNSET_THEME",
    "console",
    "show_sunset_header",
    "show_sunset_footer",
    "create_sunset_table",
    "create_status_panel",
    "create_progress_bar",
    "format_performance_metric",
    "create_agent_status_table",
    "create_system_metrics_table",
    "show_loading_animation",
    "create_error_panel",
    "create_success_panel",
    "format_agent_info",
    "create_debug_info",
]
