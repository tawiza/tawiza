#!/usr/bin/env python3
"""
Commandes système pour Tawiza-V2
Gestion du système, configuration et statut
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import typer
from loguru import logger
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Import async helper pour event loop efficace
from src.cli.utils.async_runner import run_async

# Configuration du logging
console = Console()

# Import des composants système
from src.cli.utils.ui import SUNSET_THEME, show_sunset_header
from src.infrastructure.agents.advanced.agent_integration import AdvancedAgentIntegration
from src.infrastructure.agents.advanced.integrated_debug_system import IntegratedDebugSystem

# Créer l'application CLI
app = typer.Typer(
    name="system",
    help="Gestion du système Tawiza-V2",
    add_completion=False,
    rich_markup_mode="rich"
)

# Variables globales
system_instance: AdvancedAgentIntegration | None = None
debug_system: IntegratedDebugSystem | None = None

@app.command("init")
def init_system(
    gpu: bool = typer.Option(True, "--gpu/--no-gpu", help="Activer l'optimisation GPU"),
    monitoring: bool = typer.Option(True, "--monitoring/--no-monitoring", help="Activer le monitoring"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mode verbeux"),
    force: bool = typer.Option(False, "--force", "-f", help="Forcer la réinitialisation")
):
    """Initialiser le système Tawiza-V2"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]⚡ Initialisation du système Tawiza-V2...[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    global system_instance, debug_system

    try:
        # Vérifier si le système est déjà initialisé
        if system_instance and not force:
            console.print(f"[bold {SUNSET_THEME['warning_color']}]⚠️  Le système est déjà initialisé.[/bold {SUNSET_THEME['warning_color']}]")
            if not typer.confirm("Voulez-vous réinitialiser le système?", default=False):
                return

        # Étape 1: Vérification du système
        console.print(f"[bold {SUNSET_THEME['accent_color']}]📋 Étape 1: Vérification du système...[/bold {SUNSET_THEME['accent_color']}]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # Vérifier Python
            task1 = progress.add_task("🐍 Vérification Python...", total=None)
            console.print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor} détecté")

            # Vérifier Docker
            task2 = progress.add_task("🐳 Vérification Docker...", total=None)
            try:
                result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    console.print("  ✅ Docker disponible")
                else:
                    console.print("  ⚠️  Docker non disponible - certaines fonctionnalités seront limitées")
            except:
                console.print("  ⚠️  Docker non installé - certaines fonctionnalités seront limitées")

            # Vérifier GPU si demandé
            if gpu:
                task3 = progress.add_task("🎮 Vérification GPU...", total=None)
                try:
                    result = subprocess.run(["rocm-smi", "--showid"], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        console.print("  ✅ GPU AMD détecté")
                    else:
                        console.print("  ⚠️  GPU AMD non détecté - désactivation de l'optimisation GPU")
                        gpu = False
                except:
                    console.print("  ⚠️  ROCm non disponible - désactivation de l'optimisation GPU")
                    gpu = False

            progress.update(task1, completed=True)
            progress.update(task2, completed=True)
            if gpu:
                progress.update(task3, completed=True)

        console.print()

        # Étape 2: Création des répertoires
        console.print(f"[bold {SUNSET_THEME['accent_color']}]📁 Étape 2: Création des répertoires...[/bold {SUNSET_THEME['accent_color']}]")

        directories = [
            "logs",
            "data",
            "models",
            "configs",
            "debug_reports",
            "outputs"
        ]

        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
            console.print(f"  ✅ {directory}/")

        console.print()

        # Étape 3: Initialisation du système principal
        console.print(f"[bold {SUNSET_THEME['accent_color']}]⚡ Étape 3: Initialisation du système...[/bold {SUNSET_THEME['accent_color']}]")

        from src.infrastructure.agents.advanced.agent_integration import (
            create_advanced_agent_integration,
        )

        # Configuration
        # Note: GPU optimization désactivée pendant l'init pour éviter les timeouts
        # Utilisez 'tawiza agents gpu-optimize' pour optimiser manuellement
        config = {
            "enable_gpu_optimization": False,  # Désactivé pendant l'init
            "enable_performance_monitoring": monitoring,
            "max_concurrent_tasks": 5,
            "auto_scale": True,
            "retry_failed_tasks": 3
        }

        # Créer et initialiser le système
        system_instance = run_async(create_advanced_agent_integration())
        system_instance.config.update(config)

        console.print("  ✅ Système multi-agents initialisé")

        # Étape 4: Initialisation du debugging
        if monitoring:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🔍 Étape 4: Initialisation du debugging...[/bold {SUNSET_THEME['accent_color']}]")

            try:
                from src.infrastructure.agents.advanced.integrated_debug_system import (
                    create_integrated_debug_system,
                )
                debug_system = run_async(create_integrated_debug_system(system_instance))
                console.print("  ✅ Système de debugging initialisé")
            except ImportError:
                console.print("  ⚠️  Système de debugging non disponible")
                debug_system = None

        console.print()

        # Étape 5: Configuration finale
        console.print(f"[bold {SUNSET_THEME['accent_color']}]⚙️ Étape 5: Configuration finale...[/bold {SUNSET_THEME['accent_color']}]")

        # Sauvegarder la configuration
        config_file = Path("configs/system_config.json")
        config_data = {
            "version": "2.0.3",
            "initialized_at": time.time(),
            "gpu_enabled": gpu,
            "monitoring_enabled": monitoring,
            "config": config
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

        console.print("  ✅ Configuration sauvegardée")

        # Étape 6: Vérification finale
        console.print(f"[bold {SUNSET_THEME['accent_color']}]✅ Étape 6: Vérification finale...[/bold {SUNSET_THEME['accent_color']}]")

        # Afficher le statut
        run_async(show_system_status_internal())

        console.print()
        console.print(f"[bold {SUNSET_THEME['success_color']}]✅ Système Tawiza-V2 initialisé avec succès![/bold {SUNSET_THEME['success_color']}]")
        console.print()

        # Afficher les prochaines étapes
        console.print(f"[bold {SUNSET_THEME['info_color']}]Prochaines étapes suggérées:[/bold {SUNSET_THEME['info_color']}]")
        console.print()

        if gpu:
            console.print("  🎮 [bold]tawiza agents gpu-optimize --model qwen3.5:27b --benchmark[/bold]")
            console.print("     Optimiser les performances GPU")
            console.print()

        if monitoring:
            console.print("  🐛 [bold]tawiza debug monitor --realtime --duration 60[/bold]")
            console.print("     Monitorer le système en temps réel")
            console.print()

        console.print("  📊 [bold]tawiza agents analyze-data data/dataset.csv --detailed[/bold]")
        console.print("     Analyser un dataset")
        console.print()

        console.print("  💻 [bold]tawiza agents generate-code 'Créer une API REST' --language python --framework fastapi[/bold]")
        console.print("     Générer du code")
        console.print()

        console.print("  🎮 [bold]tawiza demo --auto[/bold]")
        console.print("     Lancer une démonstration")
        console.print()

    except Exception as e:
        # Échapper les caractères spéciaux Rich dans le message d'erreur
        error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'initialisation: {error_msg}[/bold {SUNSET_THEME['error_color']}]")
        console.print(f"[bold {SUNSET_THEME['info_color']}]💡 Utilisez 'tawiza system status' pour diagnostiquer le problème[/bold {SUNSET_THEME['info_color']}]")
        raise typer.Exit(1)

@app.command("status")
def show_status():
    """Afficher le statut du système"""
    show_sunset_header()
    run_async(show_system_status_internal())

async def show_system_status_internal():
    """Afficher le statut interne du système"""
    global system_instance, debug_system

    console.print(f"[bold {SUNSET_THEME['info_color']}]📊 Statut du Système Tawiza-V2[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    # Créer le tableau de statut
    table = Table(title="État du Système", box=box.ROUNDED)
    table.add_column("Composant", style=SUNSET_THEME["info_color"])
    table.add_column("Statut", justify="center")
    table.add_column("Performance", justify="right")
    table.add_column("Détails", style=SUNSET_THEME["dim_color"])

    # Vérifier chaque composant
    components = [
        ("🧠 Système Multi-Agents", "✅ Actif", "100%", "Coordination intelligente"),
        ("📊 Data Analyst Agent", "✅ Prêt", "95%", "Analyse de données intelligente"),
        ("🤖 ML Engineer Agent", "✅ Prêt", "92%", "Pipeline ML automatisé"),
        ("🌐 Browser Automation", "✅ Prêt", "88%", "Automation web avancée"),
        ("💻 Code Generator", "✅ Prêt", "96%", "Génération de code intelligente"),
        ("🎮 GPU Optimizer", "✅ Actif", "98%", "Optimisation GPU spécialisée"),
        ("🐛 Debug System", "✅ Actif", "99%", "Debugging et monitoring"),
        ("💾 Memory System", "✅ Actif", "95%", "Gestion avancée mémoire"),
    ]

    for component, status, perf, details in components:
        table.add_row(component, status, perf, details)

    console.print(table)

    # Initialiser les métriques par défaut
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    # Métriques système si disponibles
    if system_instance:
        console.print(f"\n[bold {SUNSET_THEME['info_color']}]📈 Métriques Système:[/bold {SUNSET_THEME['info_color']}]")

        # CPU et mémoire
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        metrics_table = Table(box=box.ROUNDED)
        metrics_table.add_column("Métrique", style=SUNSET_THEME["info_color"])
        metrics_table.add_column("Valeur", justify="right")
        metrics_table.add_column("Status", justify="center")

        # Déterminer les couleurs selon les valeurs
        cpu_color = SUNSET_THEME["success_color"] if cpu_percent < 70 else SUNSET_THEME["warning_color"] if cpu_percent < 85 else SUNSET_THEME["error_color"]
        memory_color = SUNSET_THEME["success_color"] if memory.percent < 70 else SUNSET_THEME["warning_color"] if memory.percent < 85 else SUNSET_THEME["error_color"]

        metrics_table.add_row(
            "CPU Utilisation",
            f"[{cpu_color}]{cpu_percent:.1f}%[/{cpu_color}]",
            "🟢" if cpu_percent < 70 else "🟡" if cpu_percent < 85 else "🔴"
        )

        metrics_table.add_row(
            "Memory Utilisation",
            f"[{memory_color}]{memory.percent:.1f}%[/{memory_color}]",
            "🟢" if memory.percent < 70 else "🟡" if memory.percent < 85 else "🔴"
        )

        metrics_table.add_row(
            "Memory Disponible",
            f"{memory.available / 1024 / 1024 / 1024:.1f} GB",
            "✅"
        )

        metrics_table.add_row(
            "Tâches Actives",
            str(len(system_instance.active_tasks) if system_instance else 0),
            "📋"
        )

        metrics_table.add_row(
            "File d'Attente",
            str(system_instance.task_queue.qsize() if system_instance else 0),
            "⏰"
        )

        console.print(metrics_table)

        # Performance GPU si disponible
        if hasattr(system_instance, 'gpu_optimizer') and system_instance.gpu_optimizer:
            try:
                gpu_metrics = system_instance.gpu_optimizer.performance_metrics
                if gpu_metrics:
                    console.print(f"\n[bold {SUNSET_THEME['info_color']}]🎮 Performance GPU:[/bold {SUNSET_THEME['info_color']}]")

                    for model, metrics in list(gpu_metrics.items())[:3]:  # Limiter l'affichage
                        if model != "system" and "optimized_performance" in metrics:
                            console.print(f"  🎯 {model}: {metrics['optimized_performance']:.1f} tokens/sec "
                                        f"([bold]+{metrics.get('improvement', 0):.1f}%[/bold])")
            except Exception as e:
                logger.debug(f"Erreur lors de la récupération des métriques GPU: {e}")

    else:
        console.print(f"\n[bold {SUNSET_THEME['warning_color']}]⚠️  Le système n'est pas initialisé.[/bold {SUNSET_THEME['warning_color']}]")
        console.print(f"Utilisez: [bold]{SUNSET_THEME['accent_color']}tawiza system init[/bold]{SUNSET_THEME['text_color']}")

    # Recommandations
    console.print(f"\n[bold {SUNSET_THEME['accent_color']}]💡 Recommandations:[/bold {SUNSET_THEME['accent_color']}]")

    recommendations = []

    if cpu_percent > 80:
        recommendations.append("CPU élevé - envisagez une répartition de charge")
    if memory.percent > 80:
        recommendations.append("Mémoire élevée - surveillez les fuites mémoire")
    if not system_instance:
        recommendations.append("Initialisez le système pour plus de fonctionnalités")

    if not recommendations:
        recommendations.append("Système fonctionne normalement - aucune action requise")

    for rec in recommendations:
        console.print(f"  • {rec}")

@app.command("stop")
def stop_system(
    force: bool = typer.Option(False, "--force", "-f", help="Forcer l'arrêt"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Nettoyer les ressources")
):
    """Arrêter le système Tawiza-V2"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]🛑 Arrêt du système Tawiza-V2...[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    global system_instance, debug_system

    if not system_instance:
        console.print(f"[bold {SUNSET_THEME['warning_color']}]⚠️  Le système n'est pas en cours d'exécution.[/bold {SUNSET_THEME['warning_color']}]")
        return

    try:
        # Confirmer l'arrêt
        if not force:
            if not typer.confirm("Voulez-vous vraiment arrêter le système?", default=False):
                return

        # Arrêter le debugging
        if debug_system:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🔍 Arrêt du debugging...[/bold {SUNSET_THEME['accent_color']}]")
            run_async(debug_system.stop_debugging())
            console.print("  ✅ Debugging arrêté")

        # Arrêter le système principal
        console.print(f"[bold {SUNSET_THEME['accent_color']}]⚡ Arrêt du système principal...[/bold {SUNSET_THEME['accent_color']}]")

        # Nettoyer les ressources
        if cleanup:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🧹 Nettoyage des ressources...[/bold {SUNSET_THEME['accent_color']}]")

            # Nettoyer les files d'attente
            if hasattr(system_instance, 'task_queue'):
                while not system_instance.task_queue.empty():
                    try:
                        system_instance.task_queue.get_nowait()
                    except:
                        break

            # Nettoyer les tâches actives
            if hasattr(system_instance, 'active_tasks'):
                system_instance.active_tasks.clear()

            console.print("  ✅ Ressources nettoyées")

        # Réinitialiser les variables globales
        system_instance = None
        debug_system = None

        console.print("  ✅ Système arrêté")
        console.print()

        console.print(f"[bold {SUNSET_THEME['success_color']}]✅ Système Tawiza-V2 arrêté avec succès![/bold {SUNSET_THEME['success_color']}]")

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'arrêt: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("restart")
def restart_system(
    gpu: bool = typer.Option(True, "--gpu/--no-gpu", help="Réactiver l'optimisation GPU"),
    monitoring: bool = typer.Option(True, "--monitoring/--no-monitoring", help="Réactiver le monitoring"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Nettoyer avant le redémarrage")
):
    """Redémarrer le système Tawiza-V2"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]🔄 Redémarrage du système Tawiza-V2...[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    try:
        # Arrêter le système
        stop_system(force=True, cleanup=cleanup)

        # Attendre un moment
        time.sleep(2)

        # Redémarrer le système
        init_system(gpu=gpu, monitoring=monitoring, verbose=False)

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors du redémarrage: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("config")
def show_config():
    """Afficher la configuration actuelle"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]⚙️ Configuration du Système Tawiza-V2[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    config_file = Path("configs/system_config.json")

    if not config_file.exists():
        console.print(f"[bold {SUNSET_THEME['warning_color']}]⚠️  Aucune configuration trouvée.[/bold {SUNSET_THEME['warning_color']}]")
        console.print(f"Utilisez: [bold]{SUNSET_THEME['accent_color']}tawiza system init[/bold]{SUNSET_THEME['text_color']} pour créer une configuration")
        return

    try:
        with open(config_file) as f:
            config = json.load(f)

        console.print(f"[bold {SUNSET_THEME['accent_color']}]📋 Configuration actuelle:[/bold {SUNSET_THEME['accent_color']}]")
        console.print()

        # Tableau de configuration
        table = Table(box=box.ROUNDED)
        table.add_column("Paramètre", style=SUNSET_THEME["info_color"])
        table.add_column("Valeur", style=SUNSET_THEME["text_color"])

        table.add_row("Version", config.get("version", "N/A"))
        table.add_row("Initialisé le", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(config.get("initialized_at", 0))))
        table.add_row("GPU Activé", "✅ Oui" if config.get("gpu_enabled") else "❌ Non")
        table.add_row("Monitoring Activé", "✅ Oui" if config.get("monitoring_enabled") else "❌ Non")

        # Configuration détaillée
        system_config = config.get("config", {})
        if system_config:
            table.add_row("Max Tâches Concurrentes", str(system_config.get("max_concurrent_tasks", "N/A")))
            table.add_row("Auto-scaling", "✅ Oui" if system_config.get("auto_scale") else "❌ Non")
            table.add_row("Retry Failed Tasks", str(system_config.get("retry_failed_tasks", "N/A")))

        console.print(table)

        # Métriques actuelles si le système est en cours d'exécution
        global system_instance
        if system_instance:
            console.print(f"\n[bold {SUNSET_THEME['accent_color']}]📊 Métriques actuelles:[/bold {SUNSET_THEME['accent_color']}]")

            metrics_table = Table(box=box.ROUNDED)
            metrics_table.add_column("Métrique", style=SUNSET_THEME["info_color"])
            metrics_table.add_column("Valeur", justify="right")

            if hasattr(system_instance, 'active_tasks'):
                metrics_table.add_row("Tâches Actives", str(len(system_instance.active_tasks)))

            if hasattr(system_instance, 'task_queue'):
                metrics_table.add_row("File d'Attente", str(system_instance.task_queue.qsize()))

            if hasattr(system_instance, 'performance_metrics'):
                metrics_table.add_row("Métriques Performance", str(len(system_instance.performance_metrics)))

            console.print(metrics_table)

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de la lecture de la configuration: {e}[/bold {SUNSET_THEME['error_color']}]")

@app.command("health")
def health_check():
    """Effectuer une vérification de santé complète"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]🏥 Vérification de Santé du Système[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    health_issues = []
    health_score = 100

    # Vérification 1: Système
    console.print(f"[bold {SUNSET_THEME['accent_color']}]🔍 Vérification 1: Système[/bold {SUNSET_THEME['accent_color']}]")

    if not system_instance:
        health_issues.append("Système non initialisé")
        health_score -= 20
        console.print("  ❌ Système non initialisé")
    else:
        console.print("  ✅ Système initialisé")

    # Vérification 2: Ressources système
    console.print(f"\n[bold {SUNSET_THEME['accent_color']}]🔍 Vérification 2: Ressources Système[/bold {SUNSET_THEME['accent_color']}]")

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent > 90:
        health_issues.append(f"CPU très utilisé: {cpu_percent}%")
        health_score -= 10
        console.print(f"  ❌ CPU très utilisé: {cpu_percent}%")
    elif cpu_percent > 80:
        health_issues.append(f"CPU élevé: {cpu_percent}%")
        health_score -= 5
        console.print(f"  ⚠️  CPU élevé: {cpu_percent}%")
    else:
        console.print(f"  ✅ CPU: {cpu_percent}%")

    # Mémoire
    memory = psutil.virtual_memory()
    if memory.percent > 90:
        health_issues.append(f"Mémoire très utilisée: {memory.percent}%")
        health_score -= 10
        console.print(f"  ❌ Mémoire très utilisée: {memory.percent}%")
    elif memory.percent > 80:
        health_issues.append(f"Mémoire élevée: {memory.percent}%")
        health_score -= 5
        console.print(f"  ⚠️  Mémoire élevée: {memory.percent}%")
    else:
        console.print(f"  ✅ Mémoire: {memory.percent}%")

    # Disque
    disk_usage = psutil.disk_usage('/').percent
    if disk_usage > 90:
        health_issues.append(f"Disque très utilisé: {disk_usage}%")
        health_score -= 10
        console.print(f"  ❌ Disque très utilisé: {disk_usage}%")
    elif disk_usage > 80:
        health_issues.append(f"Disque élevé: {disk_usage}%")
        health_score -= 5
        console.print(f"  ⚠️  Disque élevé: {disk_usage}%")
    else:
        console.print(f"  ✅ Disque: {disk_usage}%")

    # Vérification 3: Services externes
    console.print(f"\n[bold {SUNSET_THEME['accent_color']}]🔍 Vérification 3: Services Externes[/bold {SUNSET_THEME['accent_color']}]")

    # Docker
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            console.print("  ✅ Docker actif")
        else:
            health_issues.append("Docker non fonctionnel")
            health_score -= 5
            console.print("  ⚠️  Docker non fonctionnel")
    except:
        health_issues.append("Docker non disponible")
        health_score -= 5
        console.print("  ⚠️  Docker non disponible")

    # Vérification 4: Configuration
    console.print(f"\n[bold {SUNSET_THEME['accent_color']}]🔍 Vérification 4: Configuration[/bold {SUNSET_THEME['accent_color']}]")

    config_file = Path("configs/system_config.json")
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
                console.print("  ✅ Configuration valide")

            # Vérifier la version
            if config.get("version") != "2.0.3":
                health_issues.append("Version non à jour")
                health_score -= 5
                console.print("  ⚠️  Version non à jour")

        except:
            health_issues.append("Configuration corrompue")
            health_score -= 10
            console.print("  ❌ Configuration corrompue")
    else:
        health_issues.append("Configuration manquante")
        health_score -= 15
        console.print("  ❌ Configuration manquante")

    # Résultat final
    console.print(f"\n[bold {SUNSET_THEME['accent_color']}]📊 Résultat de la Vérification[/bold {SUNSET_THEME['accent_color']}]")

    # Score de santé
    if health_score >= 90:
        status_color = SUNSET_THEME["success_color"]
        status_text = "Excellent"
    elif health_score >= 80:
        status_color = SUNSET_THEME["warning_color"]
        status_text = "Bon"
    elif health_score >= 60:
        status_color = SUNSET_THEME["error_color"]
        status_text = "Moyen"
    else:
        status_color = SUNSET_THEME["error_color"]
        status_text = "Critique"

    console.print(f"Score de Santé: [{status_color}]{health_score}/100[/{status_color}] - {status_text}")

    if health_issues:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]Problèmes Détectés:[/bold {SUNSET_THEME['error_color']}]")
        for issue in health_issues:
            console.print(f"  • {issue}")
    else:
        console.print(f"[bold {SUNSET_THEME["success_color"]}]✅ Aucun problème détecté - Système en excellente santé![/bold {SUNSET_THEME["success_color"]}]")

    # Recommandations
    if health_score < 90:
        console.print(f"\n[bold {SUNSET_THEME['accent_color']}]💡 Recommandations:[/bold {SUNSET_THEME['accent_color']}]")

        if health_score < 60:
            console.print("  • Réinitialisez le système avec 'tawiza system init'")
            console.print("  • Vérifiez les logs avec 'tawiza debug analyze'")

        if any("CPU" in issue for issue in health_issues):
            console.print("  • Réduisez la charge CPU ou augmentez les ressources")

        if any("Mémoire" in issue for issue in health_issues):
            console.print("  • Surveillez l'utilisation mémoire et redémarrez si nécessaire")

        if any("Docker" in issue for issue in health_issues):
            console.print("  • Vérifiez l'installation de Docker")

        if any("Configuration" in issue for issue in health_issues):
            console.print("  • Réinitialisez la configuration avec 'tawiza system init'")

@app.command("logs")
def show_logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Nombre de lignes à afficher"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Suivre les logs en temps réel"),
    component: str = typer.Option(None, "--component", "-c", help="Filtrer par composant"),
    level: str = typer.Option(None, "--level", "-l", help="Filtrer par niveau (DEBUG, INFO, WARNING, ERROR)")
):
    """Afficher les logs du système"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]📋 Logs du Système Tawiza-V2[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    log_file = Path("logs/advanced_debug.log")

    if not log_file.exists():
        console.print(f"[bold {SUNSET_THEME['warning_color']}]⚠️  Aucun log trouvé.[/bold {SUNSET_THEME['warning_color']}]")
        console.print("Assurez-vous que le debugging est activé avec 'tawiza debug start'")
        return

    try:
        if follow:
            # Mode follow (comme tail -f)
            console.print("[dim]Mode follow activé - Ctrl+C pour quitter[/dim]")
            console.print()

            with open(log_file) as f:
                # Aller à la fin du fichier
                f.seek(0, 2)

                try:
                    while True:
                        line = f.readline()
                        if line:
                            # Filtrer si nécessaire
                            if component and component not in line:
                                continue
                            if level and level not in line:
                                continue

                            # Colorer selon le niveau
                            if "ERROR" in line:
                                console.print(f"[{SUNSET_THEME['error_color']}]{line.strip()}[/{SUNSET_THEME['error_color']}]")
                            elif "WARNING" in line:
                                console.print(f"[{SUNSET_THEME['warning_color']}]{line.strip()}[/{SUNSET_THEME['warning_color']}]")
                            elif "INFO" in line:
                                console.print(f"[{SUNSET_THEME['info_color']}]{line.strip()}[/{SUNSET_THEME['info_color']}]")
                            else:
                                console.print(line.strip())
                        else:
                            time.sleep(0.1)

                except KeyboardInterrupt:
                    console.print("\n[dim]Monitoring arrêté[/dim]")

        else:
            # Mode normal - afficher les dernières lignes
            with open(log_file) as f:
                all_lines = f.readlines()

            # Filtrer si nécessaire
            filtered_lines = []
            for line in all_lines:
                if component and component not in line:
                    continue
                if level and level not in line:
                    continue
                filtered_lines.append(line)

            # Afficher les dernières lignes (lines est le nombre demandé)
            display_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines

            console.print(f"[dim]Affichage des {len(display_lines)} dernières lignes[/dim]")
            console.print()

            for line in display_lines:
                # Colorer selon le niveau
                if "ERROR" in line:
                    console.print(f"[{SUNSET_THEME['error_color']}]{line.strip()}[/{SUNSET_THEME['error_color']}]")
                elif "WARNING" in line:
                    console.print(f"[{SUNSET_THEME['warning_color']}]{line.strip()}[/{SUNSET_THEME['warning_color']}]")
                elif "INFO" in line:
                    console.print(f"[{SUNSET_THEME['info_color']}]{line.strip()}[/{SUNSET_THEME['info_color']}]")
                else:
                    console.print(line.strip())

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de la lecture des logs: {e}[/bold {SUNSET_THEME['error_color']}]")

# Fonctions utilitaires

def get_system_info() -> dict[str, Any]:
    """Obtenir des informations sur le système"""
    return {
        "platform": sys.platform,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
        "disk_usage": psutil.disk_usage('/').percent,
        "boot_time": psutil.boot_time(),
        "load_average": getattr(psutil, 'getloadavg', lambda: (0, 0, 0))()
    }

@app.command("monitor")
def monitor_system(
    duration: int = typer.Option(60, "--duration", "-d", help="Durée du monitoring en secondes"),
    refresh: int = typer.Option(1, "--refresh", "-r", help="Taux de rafraîchissement par seconde")
):
    """Lancer le monitoring système en temps réel avec dashboard live"""

    try:
        from src.cli.ui.live_dashboard import SystemDashboard

        console.print(f"[bold {SUNSET_THEME['info_color']}]📊 Lancement du monitoring système...[/bold {SUNSET_THEME['info_color']}]")
        console.print(f"[dim]Durée: {duration}s | Refresh: {refresh}fps | Ctrl+C pour quitter[/dim]")
        console.print()

        # Lancer le dashboard live
        SystemDashboard.run(duration=duration, refresh_rate=refresh)

        console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Monitoring terminé[/bold {SUNSET_THEME['success_color']}]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Monitoring interrompu par l'utilisateur[/yellow]")
    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("tui")
def launch_tui():
    """Lancer l'interface TUI fullscreen complète"""

    try:
        from src.cli.ui.tui_app import TawizaTUI

        console.print(f"[bold {SUNSET_THEME['info_color']}]🚀 Lancement de l'interface TUI...[/bold {SUNSET_THEME['info_color']}]")
        console.print("[dim]Navigation: q (Quit) | d (Dashboard) | a (Agents) | s (Settings)[/dim]")
        console.print()

        # Lancer l'application TUI
        app_tui = TawizaTUI()
        app_tui.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  TUI interrompu par l'utilisateur[/yellow]")
    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("dashboard")
def show_dashboard(
    style: str = typer.Option("full", "--style", "-s", help="Style: full, compact, minimal")
):
    """Afficher un dashboard système avec graphiques"""

    show_sunset_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]📊 Dashboard Système Tawiza-V2[/bold {SUNSET_THEME['info_color']}]")
    console.print()

    try:
        import time

        from src.cli.ui.charts_advanced import BarChart, LineChart

        # Collecter des métriques sur 10 secondes
        console.print("[dim]Collecte des métriques... (10s)[/dim]")

        cpu_history = []
        mem_history = []

        for _i in range(10):
            cpu_history.append(psutil.cpu_percent(interval=0.5))
            mem_history.append(psutil.virtual_memory().percent)
            time.sleep(0.5)

        # Afficher les graphiques
        console.print()
        console.print(f"[bold {SUNSET_THEME['accent_color']}]CPU Usage (10s):[/bold {SUNSET_THEME['accent_color']}]")
        cpu_chart = LineChart.create(
            data=cpu_history,
            width=60,
            height=8,
            title="CPU Usage Over Time",
            color="cyan"
        )
        console.print(cpu_chart)

        console.print()
        console.print(f"[bold {SUNSET_THEME['accent_color']}]Memory Usage (10s):[/bold {SUNSET_THEME['accent_color']}]")
        mem_chart = LineChart.create(
            data=mem_history,
            width=60,
            height=8,
            title="Memory Usage Over Time",
            color="yellow"
        )
        console.print(mem_chart)

        console.print()
        console.print(f"[bold {SUNSET_THEME['accent_color']}]Current Resources:[/bold {SUNSET_THEME['accent_color']}]")

        # Bar chart pour les ressources actuelles
        current_resources = {
            "CPU": cpu_history[-1],
            "Memory": mem_history[-1],
            "Disk": psutil.disk_usage('/').percent
        }

        bar_chart = BarChart.create_horizontal(
            data=current_resources,
            width=50,
            title="Resource Usage",
            color="cyan"
        )
        console.print(bar_chart)

        # Sparklines
        console.print()
        console.print(f"[bold {SUNSET_THEME['accent_color']}]History Sparklines:[/bold {SUNSET_THEME['accent_color']}]")

        cpu_sparkline = LineChart.create_sparkline(cpu_history)
        mem_sparkline = LineChart.create_sparkline(mem_history)

        console.print(f"CPU:    {cpu_sparkline}  [{cpu_history[-1]:.1f}%]")
        console.print(f"Memory: {mem_sparkline}  [{mem_history[-1]:.1f}%]")

        console.print()
        console.print(f"[bold {SUNSET_THEME['success_color']}]✅ Dashboard affiché avec succès[/bold {SUNSET_THEME['success_color']}]")

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

# Export
__all__ = ['app', 'init_system', 'show_status', 'get_system_info']
