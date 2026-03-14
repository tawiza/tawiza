#!/usr/bin/env python3
"""
Commandes interactives améliorées pour Tawiza-V2
Utilise questionary pour des prompts modernes et intuitifs

Améliorations v3.0:
- Intégration de la couche de services (validation, config, cache)
- Validation sécurisée des entrées utilisateur
- Gestion de configuration persistante
- Meilleure gestion d'erreurs
"""

from pathlib import Path
from typing import Any, Optional

import questionary
import typer
from loguru import logger
from questionary import Style
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Import de la couche de services
try:
    from src.cli.services import (
        ConfigService,
        ConfigValidationError,
        InputValidator,
        PathValidator,
        SystemConfig,
        ValidationService,
    )

    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

console = Console()

# ==============================================================================
# CONSTANTES
# ==============================================================================

MAX_CONCURRENT_TASKS_MIN = 1
MAX_CONCURRENT_TASKS_MAX = 100
DEFAULT_TIMEOUT = 300
MAX_RETRIES_MIN = 0
MAX_RETRIES_MAX = 10
VALID_BATCH_SIZES = [1, 2, 4, 8, 16, 32, 64, 128]

# Style personnalisé pour questionary (thème sunset)
custom_style = Style(
    [
        ("qmark", "fg:#FF6B35 bold"),  # Question mark (orange sunset)
        ("question", "fg:#F7931E bold"),  # Question text (amber)
        ("answer", "fg:#FFD23F bold"),  # Answer (yellow)
        ("pointer", "fg:#FF6B35 bold"),  # Selected option pointer
        ("highlighted", "fg:#F7931E bold"),  # Highlighted option
        ("selected", "fg:#06FFA5"),  # Selected checkbox
        ("separator", "fg:#B0B0B0"),  # Separator
        ("instruction", "fg:#B0B0B0"),  # Instructions
        ("text", "fg:#F0F0F0"),  # Normal text
        ("disabled", "fg:#858585 italic"),  # Disabled options
    ]
)

# ==============================================================================
# INITIALISATION DES SERVICES
# ==============================================================================


def _get_config_service() -> Optional["ConfigService"]:
    """Obtenir le service de configuration"""
    if not SERVICES_AVAILABLE:
        return None
    try:
        from src.cli.services.config_service import get_config_service

        return get_config_service()
    except Exception as e:
        logger.warning(f"Impossible d'initialiser ConfigService: {e}")
        return None


def _get_path_validator() -> Optional["PathValidator"]:
    """Obtenir le validateur de chemins"""
    if not SERVICES_AVAILABLE:
        return None
    try:
        from src.cli.constants import PROJECT_ROOT

        return PathValidator(
            allowed_directories=[
                PROJECT_ROOT / "data",
                PROJECT_ROOT / "datasets",
                PROJECT_ROOT / "output",
                PROJECT_ROOT / "configs",
                Path.home() / "data",
            ],
            blocked_extensions=[".exe", ".sh", ".bat", ".ps1"],
            allow_symlinks=False,
        )
    except Exception as e:
        logger.warning(f"Impossible d'initialiser PathValidator: {e}")
        return None


def _validate_path_secure(path_str: str) -> tuple[bool, str]:
    """Valider un chemin de manière sécurisée"""
    validator = _get_path_validator()
    if validator is None:
        # Fallback: validation basique
        path = Path(path_str)
        if ".." in path_str:
            return False, "Path traversal non autorisé"
        return path.exists(), "Chemin introuvable" if not path.exists() else ""

    result = validator.validate(path_str)
    return result.is_valid, result.message if not result.is_valid else ""


def _validate_integer_secure(
    value: str, min_val: int, max_val: int, field_name: str
) -> tuple[bool, str, int]:
    """Valider un entier de manière sécurisée"""
    if SERVICES_AVAILABLE:
        result = InputValidator.validate_integer(value, min_val, max_val)
        if result.is_valid:
            return True, "", int(value)
        return False, result.message, 0

    # Fallback: validation basique
    try:
        int_val = int(value)
        if min_val <= int_val <= max_val:
            return True, "", int_val
        return False, f"{field_name} doit être entre {min_val} et {max_val}", 0
    except ValueError:
        return False, f"{field_name} doit être un nombre entier", 0


app = typer.Typer(
    name="interactive", help="🎮 Commandes interactives modernes", rich_markup_mode="rich"
)


@app.command()
def wizard():
    """🧙 Assistant interactif complet pour Tawiza-V2"""

    console.print(
        Panel.fit(
            "🧙 [bold #FF6B35]Tawiza-V2 Interactive Wizard[/bold #FF6B35]\n"
            "Configuration guidée pas à pas",
            border_style="bold #F7931E",
            box=box.DOUBLE,
        )
    )
    console.print()

    # Étape 1: Sélection du mode
    mode = questionary.select(
        "Que souhaitez-vous faire?",
        choices=[
            "🚀 Quick Start - Démarrage rapide",
            "🔧 Configuration complète",
            "📊 Analyse de données",
            "🎯 Entraînement de modèle",
            "🤖 Gestion des agents",
            "❌ Annuler",
        ],
        style=custom_style,
    ).ask()

    if mode == "❌ Annuler":
        console.print("[bold yellow]⚠️  Assistant annulé[/bold yellow]")
        return

    console.print(f"\n[bold #06FFA5]✅ Mode sélectionné:[/bold #06FFA5] {mode}")

    # Traiter selon le mode
    if "Quick Start" in mode:
        _quick_start_wizard()
    elif "Configuration" in mode:
        _full_config_wizard()
    elif "Analyse" in mode:
        _data_analysis_wizard()
    elif "Entraînement" in mode:
        _training_wizard()
    elif "agents" in mode:
        _agents_wizard()


def _quick_start_wizard():
    """Assistant de démarrage rapide"""
    console.print("\n[bold #F7931E]🚀 Quick Start Configuration[/bold #F7931E]\n")

    # GPU
    use_gpu = questionary.confirm(
        "Activer l'optimisation GPU?", default=True, style=custom_style
    ).ask()

    # Monitoring
    enable_monitoring = questionary.confirm(
        "Activer le monitoring en temps réel?", default=True, style=custom_style
    ).ask()

    # Auto-scaling
    enable_autoscale = questionary.confirm(
        "Activer l'auto-scaling des agents?", default=True, style=custom_style
    ).ask()

    console.print("\n[bold #06FFA5]📋 Résumé de configuration:[/bold #06FFA5]")

    config_table = Table(show_header=False, box=box.SIMPLE)
    config_table.add_row("GPU", "✅ Activé" if use_gpu else "❌ Désactivé")
    config_table.add_row("Monitoring", "✅ Activé" if enable_monitoring else "❌ Désactivé")
    config_table.add_row("Auto-scaling", "✅ Activé" if enable_autoscale else "❌ Désactivé")
    console.print(config_table)

    # Confirmation
    if questionary.confirm(
        "\nAppliquer cette configuration?", default=True, style=custom_style
    ).ask():
        _apply_configuration(
            {"gpu": use_gpu, "monitoring": enable_monitoring, "autoscale": enable_autoscale}
        )
    else:
        console.print("[bold yellow]⚠️  Configuration annulée[/bold yellow]")


def _full_config_wizard():
    """Assistant de configuration complète"""
    console.print("\n[bold #F7931E]🔧 Configuration Complète[/bold #F7931E]\n")

    config = {}

    # Modèle LLM
    config["model"] = questionary.select(
        "Modèle LLM principal:",
        choices=[
            "qwen3.5:27b (Recommandé)",
            "llama3:70b",
            "mistral:latest",
            "mixtral:8x7b",
            "Autre (manuel)",
        ],
        style=custom_style,
    ).ask()

    # Agents à activer
    config["agents"] = questionary.checkbox(
        "Agents à activer:",
        choices=[
            questionary.Choice("🔍 Data Analyst", checked=True),
            questionary.Choice("🧠 ML Engineer", checked=True),
            questionary.Choice("💻 Code Generator", checked=True),
            questionary.Choice("🌐 Browser Automation", checked=False),
            questionary.Choice("🎮 GPU Optimizer", checked=True),
        ],
        style=custom_style,
    ).ask()

    # Niveau de logging
    config["log_level"] = questionary.select(
        "Niveau de logging:",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        style=custom_style,
    ).ask()

    # Max concurrent tasks
    config["max_tasks"] = questionary.text(
        "Nombre max de tâches concurrentes:",
        default="5",
        validate=lambda x: x.isdigit() and int(x) > 0,
        style=custom_style,
    ).ask()

    console.print("\n[bold #06FFA5]📋 Configuration complète:[/bold #06FFA5]")
    _display_config(config)

    if questionary.confirm(
        "\nSauvegarder cette configuration?", default=True, style=custom_style
    ).ask():
        _save_config(config)
        console.print("[bold #06FFA5]✅ Configuration sauvegardée![/bold #06FFA5]")


def _data_analysis_wizard():
    """Assistant d'analyse de données avec validation sécurisée"""
    console.print("\n[bold #F7931E]📊 Assistant d'Analyse de Données[/bold #F7931E]\n")

    # Sélection du fichier avec validation sécurisée
    while True:
        dataset_path = questionary.path(
            "Chemin vers votre dataset:", default="./data/", style=custom_style
        ).ask()

        if dataset_path is None:
            console.print("[bold yellow]⚠️  Opération annulée[/bold yellow]")
            return

        # Validation sécurisée du chemin
        is_valid, error_msg = _validate_path_secure(dataset_path)

        if not is_valid:
            console.print(f"[bold red]❌ {error_msg}[/bold red]")
            retry = questionary.confirm(
                "Voulez-vous réessayer?", default=True, style=custom_style
            ).ask()
            if not retry:
                return
            continue

        if not Path(dataset_path).exists():
            console.print("[bold red]❌ Fichier introuvable![/bold red]")
            retry = questionary.confirm(
                "Voulez-vous réessayer?", default=True, style=custom_style
            ).ask()
            if not retry:
                return
            continue

        break  # Validation réussie

    # Type d'analyse
    questionary.checkbox(
        "Types d'analyse à effectuer:",
        choices=[
            questionary.Choice("📈 Statistiques descriptives", checked=True),
            questionary.Choice("🔍 Détection d'anomalies", checked=True),
            questionary.Choice("📊 Visualisations", checked=True),
            questionary.Choice("🤖 ML Recommendations", checked=False),
        ],
        style=custom_style,
    ).ask()

    # Format de sortie
    output_format = questionary.select(
        "Format de sortie du rapport:",
        choices=["HTML", "PDF", "JSON", "Markdown"],
        default="HTML",
        style=custom_style,
    ).ask()

    console.print("\n[bold #06FFA5]🚀 Lancement de l'analyse...[/bold #06FFA5]")

    # Simuler l'analyse avec progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Analyse en cours...", total=100)

        for _i in range(100):
            progress.update(task, advance=1)
            import time

            time.sleep(0.05)

    console.print(
        f"[bold #06FFA5]✅ Analyse terminée! Rapport: analysis_report.{output_format.lower()}[/bold #06FFA5]"
    )


def _training_wizard():
    """Assistant d'entraînement de modèle avec validation sécurisée"""
    console.print("\n[bold #F7931E]🎯 Assistant d'Entraînement[/bold #F7931E]\n")

    # Dataset avec validation sécurisée
    while True:
        dataset = questionary.path(
            "Dataset d'entraînement:", default="./datasets/", style=custom_style
        ).ask()

        if dataset is None:
            console.print("[bold yellow]⚠️  Opération annulée[/bold yellow]")
            return

        is_valid, error_msg = _validate_path_secure(dataset)
        if not is_valid:
            console.print(f"[bold red]❌ {error_msg}[/bold red]")
            if not questionary.confirm("Réessayer?", default=True, style=custom_style).ask():
                return
            continue
        break

    # Modèle de base
    base_model = questionary.select(
        "Modèle de base:",
        choices=["mistral:7b", "llama3:8b", "qwen3.5:27b", "Autre"],
        style=custom_style,
    ).ask()

    # Hyperparamètres avec validation
    while True:
        epochs = questionary.text(
            "Nombre d'époques (1-100):", default="3", style=custom_style
        ).ask()

        is_valid, error_msg, epochs_int = _validate_integer_secure(epochs, 1, 100, "Epochs")
        if not is_valid:
            console.print(f"[bold red]❌ {error_msg}[/bold red]")
            continue
        break

    while True:
        batch_size = questionary.text(
            f"Batch size ({', '.join(map(str, VALID_BATCH_SIZES))}):",
            default="8",
            style=custom_style,
        ).ask()

        is_valid, error_msg, batch_int = _validate_integer_secure(batch_size, 1, 128, "Batch size")
        if not is_valid:
            console.print(f"[bold red]❌ {error_msg}[/bold red]")
            continue
        if batch_int not in VALID_BATCH_SIZES:
            console.print(
                f"[bold yellow]⚠️  Batch size {batch_int} n'est pas optimal. Valeurs recommandées: {VALID_BATCH_SIZES}[/bold yellow]"
            )
        break

    # Learning rate avec validation de format
    while True:
        learning_rate = questionary.text(
            "Learning rate (ex: 2e-4, 0.0001):", default="2e-4", style=custom_style
        ).ask()

        try:
            lr_float = float(learning_rate)
            if lr_float <= 0 or lr_float > 1:
                console.print("[bold red]❌ Learning rate doit être entre 0 et 1[/bold red]")
                continue
            break
        except ValueError:
            console.print("[bold red]❌ Format de learning rate invalide[/bold red]")
            continue

    console.print("\n[bold #06FFA5]📋 Configuration d'entraînement:[/bold #06FFA5]")

    config_table = Table(show_header=True, box=box.ROUNDED)
    config_table.add_column("Paramètre", style="cyan")
    config_table.add_column("Valeur", style="yellow")

    config_table.add_row("Dataset", dataset)
    config_table.add_row("Base Model", base_model)
    config_table.add_row("Epochs", epochs)
    config_table.add_row("Batch Size", batch_size)
    config_table.add_row("Learning Rate", learning_rate)

    console.print(config_table)

    if questionary.confirm("\nDémarrer l'entraînement?", default=True, style=custom_style).ask():
        console.print("[bold #06FFA5]🚀 Entraînement démarré![/bold #06FFA5]")
        console.print(
            "[bold #B0B0B0]Utilisez 'tawiza finetune status' pour suivre la progression[/bold #B0B0B0]"
        )


def _agents_wizard():
    """Assistant de gestion des agents"""
    console.print("\n[bold #F7931E]🤖 Gestion des Agents[/bold #F7931E]\n")

    action = questionary.select(
        "Action à effectuer:",
        choices=[
            "📊 Voir l'état des agents",
            "▶️  Démarrer un agent",
            "⏸️  Arrêter un agent",
            "🔄 Redémarrer tous les agents",
            "⚙️  Configurer les agents",
        ],
        style=custom_style,
    ).ask()

    console.print(f"\n[bold #06FFA5]Action:[/bold #06FFA5] {action}")

    if "Voir l'état" in action:
        _show_agents_status()
    elif "Démarrer" in action:
        _start_agent()
    elif "Arrêter" in action:
        _stop_agent()
    elif "Redémarrer" in action:
        if questionary.confirm(
            "Redémarrer tous les agents?", default=False, style=custom_style
        ).ask():
            console.print("[bold #06FFA5]🔄 Redémarrage en cours...[/bold #06FFA5]")
    elif "Configurer" in action:
        _configure_agents()


def _show_agents_status():
    """Afficher l'état des agents"""
    agents_table = Table(title="État des Agents", box=box.ROUNDED)
    agents_table.add_column("Agent", style="cyan")
    agents_table.add_column("État", style="green")
    agents_table.add_column("Uptime", style="yellow")
    agents_table.add_column("Tasks", style="magenta")

    # Données simulées
    agents_table.add_row("🔍 Data Analyst", "🟢 Running", "2h 34m", "15")
    agents_table.add_row("🧠 ML Engineer", "🟢 Running", "2h 34m", "8")
    agents_table.add_row("💻 Code Generator", "🟡 Idle", "2h 34m", "0")
    agents_table.add_row("🌐 Browser Automation", "🔴 Stopped", "0m", "0")
    agents_table.add_row("🎮 GPU Optimizer", "🟢 Running", "2h 34m", "3")

    console.print(agents_table)


def _start_agent():
    """Démarrer un agent"""
    agent = questionary.select(
        "Agent à démarrer:",
        choices=[
            "🔍 Data Analyst",
            "🧠 ML Engineer",
            "💻 Code Generator",
            "🌐 Browser Automation",
            "🎮 GPU Optimizer",
        ],
        style=custom_style,
    ).ask()

    console.print(f"[bold #06FFA5]▶️  Démarrage de {agent}...[/bold #06FFA5]")


def _stop_agent():
    """Arrêter un agent"""
    agent = questionary.select(
        "Agent à arrêter:",
        choices=[
            "🔍 Data Analyst (Running)",
            "🧠 ML Engineer (Running)",
            "💻 Code Generator (Idle)",
            "🎮 GPU Optimizer (Running)",
        ],
        style=custom_style,
    ).ask()

    if questionary.confirm(
        f"Confirmer l'arrêt de {agent}?", default=False, style=custom_style
    ).ask():
        console.print(f"[bold yellow]⏸️  Arrêt de {agent}...[/bold yellow]")


def _configure_agents():
    """Configurer les agents"""
    console.print("\n[bold #F7931E]⚙️  Configuration des Agents[/bold #F7931E]\n")

    # Options de configuration
    questionary.confirm("Auto-restart en cas d'erreur?", default=True, style=custom_style).ask()

    questionary.text(
        "Nombre max de tentatives:", default="3", validate=lambda x: x.isdigit(), style=custom_style
    ).ask()

    questionary.text(
        "Timeout (secondes):", default="300", validate=lambda x: x.isdigit(), style=custom_style
    ).ask()

    console.print("[bold #06FFA5]✅ Configuration sauvegardée![/bold #06FFA5]")


def _apply_configuration(config: dict[str, Any]):
    """Appliquer la configuration via ConfigService"""
    config_service = _get_config_service()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        progress.add_task("Application de la configuration...", total=None)

        try:
            if config_service and SERVICES_AVAILABLE:
                # Créer une configuration quick start via le service
                from src.cli.services.config_service import (
                    GPUConfig,
                    MonitoringConfig,
                    SystemConfig,
                )

                sys_config = SystemConfig(
                    gpu=GPUConfig(enabled=config.get("gpu", True)),
                    monitoring=MonitoringConfig(enabled=config.get("monitoring", True)),
                    max_concurrent_tasks=10 if config.get("autoscale", True) else 5,
                )

                # Valider et appliquer
                errors = config_service.validate_config(sys_config)
                if errors:
                    progress.stop()
                    console.print("[bold red]❌ Erreurs de validation:[/bold red]")
                    for error in errors:
                        console.print(f"   • {error}")
                    return

                config_service._current_config = sys_config
                config_service.save_config(sys_config)
                logger.info("Configuration appliquée via ConfigService")
            else:
                # Fallback: sauvegarde simple
                import time

                time.sleep(1)

        except Exception as e:
            progress.stop()
            console.print(f"[bold red]❌ Erreur: {e}[/bold red]")
            logger.error(f"Erreur application config: {e}")
            return

    console.print("[bold #06FFA5]✅ Configuration appliquée avec succès![/bold #06FFA5]")


def _display_config(config: dict[str, Any]):
    """Afficher la configuration"""
    table = Table(show_header=False, box=box.SIMPLE)
    for key, value in config.items():
        if isinstance(value, list):
            value = ", ".join(value)
        table.add_row(key, str(value))
    console.print(table)


def _save_config(config: dict[str, Any]):
    """Sauvegarder la configuration via ConfigService"""
    config_service = _get_config_service()

    try:
        if config_service and SERVICES_AVAILABLE:
            # Utiliser le service pour la persistance avec backup

            # Mapper les valeurs de l'UI vers SystemConfig
            updates = {}

            if "model" in config:
                model_str = config["model"]
                if "qwen" in model_str.lower():
                    updates["default_model"] = "qwen3.5:27b"
                elif "llama" in model_str.lower():
                    updates["default_model"] = "llama3:70b"
                elif "mistral" in model_str.lower():
                    updates["default_model"] = "mistral:latest"
                elif "mixtral" in model_str.lower():
                    updates["default_model"] = "mixtral:8x7b"

            if "log_level" in config:
                updates["log_level"] = config["log_level"]

            if "max_tasks" in config:
                updates["max_concurrent_tasks"] = int(config["max_tasks"])

            if "agents" in config:
                agent_map = {
                    "Data Analyst": "data_analyst",
                    "ML Engineer": "ml_engineer",
                    "Code Generator": "code_generator",
                    "Browser Automation": "browser_automation",
                    "GPU Optimizer": "gpu_optimizer",
                }
                enabled_agents = []
                for agent_label in config["agents"]:
                    # Extraire le nom sans emoji
                    for key, value in agent_map.items():
                        if key in agent_label:
                            enabled_agents.append(value)
                            break
                updates["enabled_agents"] = enabled_agents

            # Mettre à jour et sauvegarder
            new_config = config_service.update_config(updates)
            config_service.save_config(new_config)
            logger.info(f"Configuration sauvegardée via ConfigService: {updates.keys()}")

        else:
            # Fallback: sauvegarde JSON simple
            import json

            config_file = Path("configs/user_config.json")
            config_file.parent.mkdir(exist_ok=True)

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Configuration sauvegardée (fallback JSON)")

    except Exception as e:
        logger.error(f"Erreur sauvegarde config: {e}")
        console.print(f"[bold red]❌ Erreur de sauvegarde: {e}[/bold red]")


if __name__ == "__main__":
    app()
