#!/usr/bin/env python3
"""
Tawiza-V2 CLI Principale avec intégration complète des agents et debugging
Interface unifiée avec thème sunset
"""

import json
import logging
import sys
import tempfile
import time
from pathlib import Path

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.cli.ui.theme import SUNSET_THEME, Emoji, theme_to_dict

# Import refactored modules
from src.core.constants import APP_DESCRIPTION, APP_NAME

# Configuration du logging
logging.basicConfig(level=logging.INFO)
console = Console()

# Import des groupes de commandes (structure hybride)
from src.cli.commands.agent import app as agent_app

# Import des commandes directes (retrocompatibilite)
from src.cli.commands.agents import app as agents_app
from src.cli.commands.annotate import app as annotate_app
from src.cli.commands.browser import app as browser_app
from src.cli.commands.captcha import app as captcha_app
from src.cli.commands.chat import app as chat_app
from src.cli.commands.completion_cmd import app as completion_app
from src.cli.commands.credentials import app as credentials_app
from src.cli.commands.debug import app as debug_app
from src.cli.commands.ecocartographe import app as cartographie_app
from src.cli.commands.finetune import app as finetune_app
from src.cli.commands.groups.ai import app as ai_group
from src.cli.commands.groups.automation import app as automation_group
from src.cli.commands.groups.data import app as data_group
from src.cli.commands.groups.infra import app as infra_group
from src.cli.commands.learning import app as learning_app
from src.cli.commands.live import app as live_app
from src.cli.commands.models import app as models_app
from src.cli.commands.prompts import app as prompts_app
from src.cli.commands.system import app as system_app
from src.cli.commands.training import app as training_app
from src.cli.commands.unified_agent import app as unified_agent_app
from src.cli.commands.vm_sandbox_commands import app as vm_sandbox_app
from src.cli.ui.mascot import (
    get_detailed_mascot,
    mascot_says,
    print_banner,
    print_mascot,
    print_welcome,
)
from src.cli.utils.ui import show_sunset_header
from src.cli.v2.commands.simple.tajine import app as tajine_app

# Convert theme to dict for backward compatibility with existing code
THEME_DICT = theme_to_dict(SUNSET_THEME)

# Créer l'application CLI principale
app = typer.Typer(
    name="tawiza",
    help=f"{APP_NAME} - {APP_DESCRIPTION}",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Groupes de commandes (structure hybride)
app.add_typer(ai_group, name="ai", help="Intelligence Artificielle (chat, agents, models)")
app.add_typer(data_group, name="data", help="Gestion des Données (import, annotate)")
app.add_typer(automation_group, name="automation", help="Automation (browser, live)")
app.add_typer(infra_group, name="infra", help="Infrastructure (system, vm)")

# Commandes directes (rétrocompatibilité et accès rapide)
app.add_typer(agents_app, name="agents", help="Agents IA (raccourci)")
app.add_typer(debug_app, name="debug", help="Débogage et monitoring")
app.add_typer(system_app, name="system", help="Gestion du système")
app.add_typer(models_app, name="models", help="Gestion des modèles ML")
app.add_typer(chat_app, name="chat", help="Chat avec l'assistant IA")
app.add_typer(browser_app, name="browser", help="Automation navigateur")
app.add_typer(live_app, name="live", help="Automation live")
app.add_typer(agent_app, name="agent", help="Agent autonome avec planification IA")
app.add_typer(unified_agent_app, name="uaa", help="Unified Adaptive Agent (self-improving)")
app.add_typer(
    learning_app, name="learning", help="Learning Pipeline (Label Studio + LLaMA-Factory)"
)
app.add_typer(tajine_app, name="tajine", help="TAJINE meta-agent territorial intelligence")

# Commandes secondaires
app.add_typer(vm_sandbox_app, name="vm-sandbox", help="VMs sandbox")
app.add_typer(completion_app, name="completion", help="Autocompletion shell")
app.add_typer(cartographie_app, name="cartographie", help="EcoCartographe")
app.add_typer(prompts_app, name="prompts", help="Templates de prompts")
app.add_typer(training_app, name="training", help="Entrainement")
app.add_typer(credentials_app, name="credentials", help="Credentials")
app.add_typer(annotate_app, name="annotate", help="Annotation")
app.add_typer(finetune_app, name="finetune", help="Fine-tuning")
app.add_typer(captcha_app, name="captcha", help="Captchas")

# Nouvelles commandes améliorées
try:
    from src.cli.commands.interactive_enhanced import app as interactive_app

    app.add_typer(interactive_app, name="interactive", help="🎮 Commandes interactives modernes")
except ImportError:
    pass  # Module optionnel

# Démo des animations de mascotte
try:
    from src.cli.commands.mascot_demo import app as mascot_demo_app

    app.add_typer(
        mascot_demo_app, name="mascot-demo", help="🐱 Démonstration des animations mascotte"
    )
except ImportError:
    pass  # Module optionnel


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Afficher la version"),
    verbose: bool = typer.Option(False, "--verbose", help="Mode verbeux"),
    no_color: bool = typer.Option(False, "--no-color", help="Désactiver les couleurs"),
):
    """Tawiza-V2 - Système Multi-Agents IA Avancé avec Optimisation GPU"""

    if version:
        show_version()
        raise typer.Exit()

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if no_color:
        # Désactiver les couleurs pour les environnements sans support
        from src.cli.ui.theme import NO_COLOR_THEME

        global THEME_DICT
        THEME_DICT = theme_to_dict(NO_COLOR_THEME)


@app.command("quickstart")
def quickstart(
    gpu: bool = typer.Option(True, "--gpu/--no-gpu", help="Utiliser l'optimisation GPU"),
    monitoring: bool = typer.Option(
        True, "--monitoring/--no-monitoring", help="Activer le monitoring"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Mode interactif"
    ),
):
    """Démarrage rapide avec configuration optimale"""

    show_sunset_header()

    console.print(
        f"[bold {THEME_DICT['info_color']}]{Emoji.ROCKET} Démarrage rapide de {APP_NAME}...[/bold {THEME_DICT['info_color']}]"
    )
    console.print()

    try:
        # Étape 1: Vérifier la configuration système
        console.print(
            f"[bold {THEME_DICT['accent_color']}]📋 Étape 1: Vérification du système...[/bold {THEME_DICT['accent_color']}]"
        )

        import subprocess

        # Vérifier ROCm
        try:
            result = subprocess.run(
                ["rocm-smi", "--showid"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                console.print("  ✅ GPU AMD détecté")
            else:
                console.print("  ⚠️  GPU AMD non détecté ou non configuré")
                gpu = False
        except:
            console.print("  ⚠️  ROCm non disponible")
            gpu = False

        # Vérifier Docker
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                console.print("  ✅ Docker disponible")
            else:
                console.print(
                    "  ⚠️  Docker non disponible - certaines fonctionnalités seront limitées"
                )
        except:
            console.print("  ⚠️  Docker non installé - certaines fonctionnalités seront limitées")

        console.print()

        # Étape 2: Initialiser le système
        console.print(
            f"[bold {THEME_DICT['accent_color']}]⚡ Étape 2: Initialisation du système...[/bold {THEME_DICT['accent_color']}]"
        )

        # Appeler la commande system init
        from src.cli.commands.system import init_system

        init_system(gpu=gpu, monitoring=monitoring, verbose=False)

        console.print()

        # Étape 3: Démarrer le debugging si demandé
        if monitoring:
            console.print(
                f"[bold {THEME_DICT['accent_color']}]🔍 Étape 3: Démarrage du monitoring...[/bold {THEME_DICT['accent_color']}]"
            )

            from src.cli.commands.debug import start_debugging

            start_debugging(debug_level="INFO", profiling=True)

            console.print()

        # Étape 4: Afficher les commandes de démarrage
        console.print(
            f"[bold {THEME_DICT['accent_color']}]🎯 Étape 4: Commandes de démarrage...[/bold {THEME_DICT['accent_color']}]"
        )
        console.print()

        console.print(
            f"[bold {THEME_DICT['info_color']}]Votre système est prêt! Voici quelques commandes pour commencer:[/bold {THEME_DICT['info_color']}]"
        )
        console.print()

        if gpu:
            console.print(
                f"  🎮 {THEME_DICT['accent_color']}tawiza agents gpu-optimize --model qwen3.5:27b --benchmark[/]{THEME_DICT['text_color']}"
            )
            console.print("     Optimiser les performances GPU")
            console.print()

        console.print(
            f"  📊 {THEME_DICT['accent_color']}tawiza agents analyze-data data/dataset.csv[/]{THEME_DICT['text_color']}"
        )
        console.print("     Analyser un dataset")
        console.print()

        console.print(
            f"  💻 {THEME_DICT['accent_color']}tawiza agents generate-code 'Créer une API REST' --language python --framework fastapi[/]{THEME_DICT['text_color']}"
        )
        console.print("     Générer du code")
        console.print()

        if monitoring:
            console.print(
                f"  🐛 {THEME_DICT['accent_color']}tawiza debug monitor --realtime --duration 60[/]{THEME_DICT['text_color']}"
            )
            console.print("     Monitorer en temps réel")
            console.print()

        console.print(
            f"  📚 {THEME_DICT['accent_color']}tawiza --help[/]{THEME_DICT['text_color']}"
        )
        console.print("     Voir toutes les commandes disponibles")
        console.print()

        if interactive:
            console.print(
                f"[bold {THEME_DICT['success_color']}]✅ Démarrage rapide terminé avec succès![/bold {THEME_DICT['success_color']}]"
            )
            console.print()
            console.print(
                f"[bold {THEME_DICT['info_color']}]💡 Astuce: Utilisez 'tawiza quickstart --interactive' pour un guide guidé[/bold {THEME_DICT['info_color']}]"
            )
        else:
            console.print(
                f"[bold {THEME_DICT['success_color']}]✅ Démarrage rapide terminé![/bold {THEME_DICT['success_color']}]"
            )

    except Exception as e:
        console.print(
            f"\n[bold {THEME_DICT['error_color']}]❌ Erreur lors du démarrage rapide: {e}[/bold {THEME_DICT['error_color']}]"
        )
        console.print(
            f"[bold {THEME_DICT['info_color']}]💡 Utilisez 'tawiza system status' pour diagnostiquer le problème[/bold {THEME_DICT['info_color']}]"
        )
        raise typer.Exit(1)


@app.command("demo")
def demo(
    auto: bool = typer.Option(False, "--auto", help="Mode automatique sans interaction"),
    duration: int = typer.Option(60, "--duration", "-d", help="Durée de la démo en secondes"),
):
    """Démonstration interactive des capacités du système"""

    show_sunset_header()

    console.print(
        f"[bold {THEME_DICT['info_color']}]🎮 Démonstration interactive de Tawiza-V2[/bold {THEME_DICT['info_color']}]"
    )
    console.print()

    try:
        # Vérifier que le système est initialisé
        console.print(
            f"[bold {THEME_DICT['accent_color']}]📋 Vérification du système...[/bold {THEME_DICT['accent_color']}]"
        )

        # Appeler system status pour vérifier
        from src.cli.commands.system import show_status as system_status

        system_status()

        console.print()

        if not auto:
            # Mode interactif
            console.print(
                f"[bold {THEME_DICT['info_color']}]🎯 Démonstration interactive[/bold {THEME_DICT['info_color']}"
            )
            console.print()

            # Menu de démonstration
            demo_options = [
                ("1", "Analyse de données", "data_analysis"),
                ("2", "Génération de code", "code_generation"),
                ("3", "Optimisation GPU", "gpu_optimization"),
                ("4", "Monitoring temps réel", "real_time_monitoring"),
                ("5", "Tous les tests", "all_tests"),
            ]

            console.print("Sélectionnez une démonstration:")
            for option, description, _ in demo_options:
                console.print(f"  {option}. {description}")

            choice = typer.prompt("Votre choix", default="5")

        else:
            # Mode automatique
            choice = "5"

        # Exécuter la démonstration sélectionnée
        run_demo(choice, duration, auto)

    except KeyboardInterrupt:
        console.print(
            f"\n[bold {THEME_DICT['warning_color']}]⚠️  Démonstration interrompue[/bold {THEME_DICT['warning_color']}]"
        )
    except Exception as e:
        console.print(
            f"\n[bold {THEME_DICT['error_color']}]❌ Erreur lors de la démonstration: {e}[/bold {THEME_DICT['error_color']}]"
        )
        raise typer.Exit(1)


def run_demo(choice: str, duration: int, auto: bool):
    """Exécuter la démonstration sélectionnée"""

    demo_functions = {
        "1": demo_data_analysis,
        "2": demo_code_generation,
        "3": demo_gpu_optimization,
        "4": demo_real_time_monitoring,
        "5": demo_all_tests,
    }

    demo_function = demo_functions.get(choice, demo_all_tests)
    demo_function(duration, auto)


def demo_data_analysis(duration: int, auto: bool):
    """Démonstration de l'analyse de données"""
    console.print(
        f"\n[bold {THEME_DICT['info_color']}]📊 Démonstration: Analyse de Données[/bold {THEME_DICT['info_color']}]"
    )

    # Créer un dataset de démonstration
    demo_data = {
        "temperature": [22, 24, 25, 23, 26, 27, 25, 24, 23, 25],
        "humidity": [60, 65, 70, 68, 72, 75, 70, 68, 65, 70],
        "pressure": [1013, 1015, 1012, 1014, 1011, 1009, 1012, 1014, 1015, 1013],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(demo_data, f)
        dataset_path = f.name

    try:
        console.print(
            f"  • Dataset créé: {len(demo_data)} colonnes, {len(demo_data['temperature'])} lignes"
        )

        # Appeler la commande d'analyse
        from src.cli.commands.agents_advanced import analyze_data

        analyze_data(dataset=dataset_path, output="demo_analysis.json", detailed=True, wait=True)

    finally:
        Path(dataset_path).unlink()


def demo_code_generation(duration: int, auto: bool):
    """Démonstration de la génération de code"""
    console.print(
        f"\n[bold {THEME_DICT['info_color']}]💻 Démonstration: Génération de Code[/bold {THEME_DICT['info_color']}]"
    )

    description = "Créer une fonction qui calcule la moyenne mobile d'une série temporelle avec gestion des valeurs manquantes"

    # Appeler la commande de génération
    from src.cli.commands.agents_advanced import generate_code

    generate_code(
        description=description,
        language="python",
        output="demo_generated_code.py",
        framework=None,
        requirements=["Gestion des valeurs manquantes", "Optimisation des performances"],
        tests=True,
        documentation=True,
    )


def demo_gpu_optimization(duration: int, auto: bool):
    """Démonstration de l'optimisation GPU"""
    console.print(
        f"\n[bold {THEME_DICT['info_color']}]🎮 Démonstration: Optimisation GPU[/bold {THEME_DICT['info_color']}]"
    )

    # Appeler la commande d'optimisation
    from src.cli.commands.agents_advanced import gpu_optimize

    gpu_optimize(model="qwen3.5:27b", benchmark=True, verbose=False)


def demo_real_time_monitoring(duration: int, auto: bool):
    """Démonstration du monitoring temps réel"""
    console.print(
        f"\n[bold {THEME_DICT['info_color']}]📊 Démonstration: Monitoring Temps Réel[/bold {THEME_DICT['info_color']}]"
    )

    # Appeler la commande de monitoring
    from src.cli.commands.debug import start_monitoring

    start_monitoring(
        duration=min(duration, 30),  # Limiter pour la démo
        realtime=True,
        export=None,
    )


def demo_all_tests(duration: int, auto: bool):
    """Démonstration de tous les tests"""
    console.print(
        f"\n[bold {THEME_DICT['info_color']}]🎯 Démonstration: Tous les Tests[/bold {THEME_DICT['info_color']}]"
    )

    tests = [
        ("Analyse de données", demo_data_analysis),
        ("Génération de code", demo_code_generation),
        ("Optimisation GPU", demo_gpu_optimization),
        ("Monitoring temps réel", demo_real_time_monitoring),
    ]

    for test_name, test_func in tests:
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Test: {test_name}[/bold {THEME_DICT['accent_color']}]"
        )

        if not auto and not typer.confirm(f"Exécuter {test_name}?", default=True):
            continue

        try:
            test_func(duration // len(tests), auto)
        except Exception as e:
            console.print(f"  ⚠️  Erreur dans {test_name}: {e}")

        if not auto:
            time.sleep(1)  # Pause entre les tests


@app.command("tui")
def tui():
    """🖥️  Lancer l'interface TUI complète (Terminal User Interface)"""

    show_sunset_header()

    console.print(
        f"[bold {THEME_DICT['info_color']}]🖥️  Lancement de l'interface TUI...[/bold {THEME_DICT['info_color']}]"
    )
    console.print()

    try:
        from src.cli.ui.tui_app import main as run_tui

        run_tui()
    except ImportError:
        console.print(
            f"[bold {THEME_DICT['error_color']}]❌ TUI dependencies not installed[/bold {THEME_DICT['error_color']}]"
        )
        console.print(
            f"[bold {THEME_DICT['info_color']}]→ Run: pip install textual psutil[/bold {THEME_DICT['info_color']}]"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(
            f"[bold {THEME_DICT['error_color']}]❌ Erreur lors du lancement du TUI: {e}[/bold {THEME_DICT['error_color']}]"
        )
        raise typer.Exit(1)


@app.command("wizard")
def wizard():
    """Assistant guidé pour configurer et utiliser le système"""

    show_sunset_header()

    console.print(
        f"[bold {THEME_DICT['info_color']}]🧙 Assistant de configuration Tawiza-V2[/bold {THEME_DICT['info_color']}]"
    )
    console.print()

    try:
        # Étape 1: Présentation
        console.print(
            f"[bold {THEME_DICT['accent_color']}]Bienvenue dans l'assistant Tawiza-V2![/bold {THEME_DICT['accent_color']}]"
        )
        console.print()
        console.print("Cet assistant va vous guider à travers:")
        console.print("  • La configuration initiale du système")
        console.print("  • Le choix des agents à activer")
        console.print("  • La configuration du debugging")
        console.print("  • Votre première utilisation")
        console.print()

        if not typer.confirm("Voulez-vous continuer?", default=True):
            return

        # Étape 2: Configuration GPU
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Configuration GPU[/bold {THEME_DICT['accent_color']}]"
        )

        gpu_enabled = typer.confirm("Voulez-vous activer l'optimisation GPU?", default=True)

        if gpu_enabled:
            console.print("  • Vérification de la compatibilité GPU...")
            # Vérifier ROCm
            import subprocess

            try:
                result = subprocess.run(
                    ["rocm-smi", "--showid"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    console.print("  ✅ GPU AMD détecté et compatible")
                else:
                    console.print("  ⚠️  Problème avec GPU - désactivation")
                    gpu_enabled = False
            except:
                console.print("  ⚠️  ROCm non disponible - désactivation")
                gpu_enabled = False

        # Étape 3: Configuration des agents
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Configuration des agents[/bold {THEME_DICT['accent_color']}]"
        )

        agents_config = {
            "data_analyst": typer.confirm("Activer l'agent d'analyse de données?", default=True),
            "ml_engineer": typer.confirm("Activer l'agent ML engineer?", default=True),
            "browser_automation": typer.confirm("Activer l'agent d'automation web?", default=True),
            "code_generator": typer.confirm("Activer l'agent de génération de code?", default=True),
        }

        # Étape 4: Configuration du debugging
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Configuration du debugging[/bold {THEME_DICT['accent_color']}]"
        )

        debug_enabled = typer.confirm("Activer le système de debugging?", default=True)
        debug_level = "INFO"

        if debug_enabled:
            console.print("  Niveaux disponibles: DEBUG, INFO, WARNING, ERROR")
            debug_level = typer.prompt("Niveau de debugging", default="INFO").upper()

            # Valider le niveau
            if debug_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                console.print("  ⚠️  Niveau invalide, utilisation de INFO par défaut")
                debug_level = "INFO"

        # Étape 5: Appliquer la configuration
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Application de la configuration...[/bold {THEME_DICT['accent_color']}]"
        )

        # Appeler les commandes appropriées
        if gpu_enabled:
            console.print("  • Configuration GPU...")
            # Appeler system init avec GPU
            from src.cli.commands.system import init_system

            init_system(gpu=True, monitoring=debug_enabled, verbose=False)
        else:
            console.print("  • Configuration CPU...")
            from src.cli.commands.system import init_system

            init_system(gpu=False, monitoring=debug_enabled, verbose=False)

        if debug_enabled:
            console.print("  • Configuration debugging...")
            from src.cli.commands.debug import start_debugging

            start_debugging(debug_level=debug_level, profiling=True)

        # Étape 6: Test de configuration
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Test de la configuration...[/bold {THEME_DICT['accent_color']}]"
        )

        # Vérifier le statut
        from src.cli.commands.system import show_status

        show_status()

        # Étape 7: Recommandations personnalisées
        console.print(
            f"\n[bold {THEME_DICT['accent_color']}]Recommandations personnalisées[/bold {THEME_DICT['accent_color']}]"
        )
        console.print()

        if gpu_enabled:
            console.print(
                f"  🎮 {THEME_DICT['accent_color']}tawiza agents gpu-optimize --model qwen3.5:27b[/]{THEME_DICT['text_color']}"
            )
            console.print("     Optimiser les performances GPU")
            console.print()

        if agents_config["data_analyst"]:
            console.print(
                f"  📊 {THEME_DICT['accent_color']}tawiza agents analyze-data data/dataset.csv[/]{THEME_DICT['text_color']}"
            )
            console.print("     Analyser vos données")
            console.print()

        if agents_config["code_generator"]:
            console.print(
                f"  💻 {THEME_DICT['accent_color']}tawiza agents generate-code 'Créer une API REST' --language python --framework fastapi[/]{THEME_DICT['text_color']}"
            )
            console.print("     Générer du code")
            console.print()

        console.print(
            f"[bold {THEME_DICT['success_color']}]✅ Configuration terminée avec succès![/bold {THEME_DICT['success_color']}]"
        )
        console.print()
        console.print(
            f"[bold {THEME_DICT['info_color']}]💡 Vous pouvez maintenant utiliser toutes les commandes Tawiza-V2![/bold {THEME_DICT['info_color']}]"
        )

    except Exception as e:
        console.print(
            f"\n[bold {THEME_DICT['error_color']}]❌ Erreur dans l'assistant: {e}[/bold {THEME_DICT['error_color']}]"
        )
        console.print(
            f"[bold {THEME_DICT['info_color']}]💡 Réessayez ou utilisez 'tawiza system status' pour diagnostiquer[/bold {THEME_DICT['info_color']}]"
        )
        raise typer.Exit(1)


def show_version():
    """Afficher la version complète"""
    try:
        from src import __version__

        version_text = Text()
        version_text.append("Tawiza-V2 ", style=f"bold {THEME_DICT['header_color']}")
        version_text.append(f"v{__version__}", style=f"bold {THEME_DICT['accent_color']}")
        version_text.append("\n\n", style=SUNSET_THEME["text_color"])
        version_text.append("Système Multi-Agents IA Avancé\n", style=SUNSET_THEME["info_color"])
        version_text.append("avec Optimisation GPU AMD ROCm\n\n", style=SUNSET_THEME["dim_color"])
        version_text.append("🌅 Thème Sunset Interface\n", style=SUNSET_THEME["warning_color"])
        version_text.append("🤖 Agents IA Spécialisés\n", style=SUNSET_THEME["info_color"])
        version_text.append("🎮 Optimisation GPU Avancée\n", style=SUNSET_THEME["success_color"])
        version_text.append(
            "🐛 Système de Débogage Intelligent\n", style=SUNSET_THEME["info_color"]
        )

        console.print(
            Panel(
                Align.center(version_text),
                style=f"{THEME_DICT['header_color']}",
                box=box.ROUNDED,
                padding=1,
            )
        )

    except ImportError:
        console.print(
            f"[bold {THEME_DICT['error_color']}]❌ Impossible de déterminer la version[/bold {THEME_DICT['error_color']}]"
        )


@app.command("mascot")
def show_mascot_cmd(
    style: str = typer.Option(
        "welcome",
        "--style",
        "-s",
        help="Style de mascotte: welcome, banner, coder, hacker, realistic, laptop",
    ),
    mood: str = typer.Option(
        None, "--mood", "-m", help="Humeur: default, happy, thinking, working, success, error"
    ),
    message: str = typer.Option(None, "--say", help="Message pour la mascotte"),
    gallery: bool = typer.Option(False, "--gallery", "-g", help="Afficher toute la galerie"),
):
    """🐱 Afficher la mascotte Tawiza"""

    if gallery:
        # Afficher la galerie complète
        console.print("\n[bold magenta]═══ 🐱 Tawiza Mascot Gallery ═══[/bold magenta]\n")

        console.print("[bold cyan]▸ Styles détaillés:[/bold cyan]\n")
        for s in ["realistic", "coder", "hacker", "laptop"]:
            console.print(f"[yellow]{s.upper()}:[/yellow]")
            console.print(get_detailed_mascot(s), style="cyan")
            console.print()

        console.print("[bold cyan]▸ Humeurs:[/bold cyan]\n")
        for m in ["default", "happy", "thinking", "working", "success", "error"]:
            console.print(f"[yellow]{m}:[/yellow]")
            print_mascot(m)
        return

    if message:
        # Mascotte qui parle
        mascot_says(message, mood or "happy")
    elif mood:
        # Afficher avec humeur spécifique
        print_mascot(mood)
    elif style == "welcome":
        print_welcome()
    elif style == "banner":
        print_banner()
    else:
        console.print(get_detailed_mascot(style), style="yellow")


# Ajouter la commande version au help principal
@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Callback principal pour gérer --version"""
    if ctx.invoked_subcommand is None and "--version" in sys.argv:
        show_version()
        raise typer.Exit()


if __name__ == "__main__":
    app()
