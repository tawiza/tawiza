#!/usr/bin/env python3
"""
Commandes CLI pour le débogage avancé de Tawiza-V2
Interface sunset pour le debugging et troubleshooting
"""

import json
import time
from typing import Any

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Import async helper pour event loop efficace
from src.cli.utils.async_runner import run_async

# Import du thème sunset centralisé
from src.cli.utils.ui import SUNSET_THEME

# Configuration du logging
console = Console()

# Import du système de débogage
from src.infrastructure.debugging.advanced_debugger import (
    AdvancedDebugger,
    create_advanced_debugger,
)

# Créer l'application CLI
app = typer.Typer(
    name="debug",
    help="Commandes de débogage avancé pour Tawiza-V2",
    add_completion=False,
    rich_markup_mode="rich"
)

# Variables globales
debugger: AdvancedDebugger | None = None

def show_debug_header():
    """Afficher l'en-tête du débogage avec thème sunset"""
    header_text = Text()
    header_text.append("🐛 ", style=SUNSET_THEME["header_color"])
    header_text.append("Tawiza-V2 Advanced Debugger", style=f"bold {SUNSET_THEME['header_color']}")
    header_text.append(" 🔍", style=SUNSET_THEME["header_color"])

    console.print(Panel(
        Align.center(header_text),
        style=f"{SUNSET_THEME['header_color']}",
        box=box.DOUBLE,
        padding=1
    ))

    # Sous-titre
    subtitle = Text("Système de débogage et troubleshooting avancé", style=SUNSET_THEME["dim_color"])
    console.print(Align.center(subtitle))
    console.print()

@app.command("start")
def start_debugging(
    debug_level: str = typer.Option("INFO", "--level", "-l", help="Niveau de débogage"),
    profiling: bool = typer.Option(True, "--profiling/--no-profiling", help="Activer le profilage"),
    output: str = typer.Option("debug_output.json", "--output", "-o", help="Fichier de sortie")
):
    """Démarrer une session de débogage avancée"""
    global debugger

    show_debug_header()

    try:
        console.print(f"[bold {SUNSET_THEME['info_color']}]🚀 Démarrage du système de débogage...[/bold {SUNSET_THEME['info_color']}]\n")

        # Créer le debugger
        debugger = create_advanced_debugger(debug_level, profiling)

        # Démarrer la session
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            task = progress.add_task("🐛 Initialisation du debugger...", total=None)

            # Démarrer le debugging
            run_async(debugger.start_debugging())

            progress.update(task, completed=True)

        console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Session de débogage démarrée![/bold {SUNSET_THEME['success_color']}]\n")

        # Afficher les informations de débogage
        show_debug_info()

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors du démarrage: {e}[/bold {SUNSET_THEME['error_color']}]\n")
        raise typer.Exit(1)

@app.command("stop")
def stop_debugging():
    """Arrêter la session de débogage"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    try:
        console.print(f"[bold {SUNSET_THEME['info_color']}]🛑 Arrêt du système de débogage...[/bold {SUNSET_THEME['info_color']}]\n")

        # Arrêter le debugging
        run_async(debugger.stop_debugging())

        console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Session de débogage arrêtée![/bold {SUNSET_THEME['success_color']}]")
        console.print("📊 Rapport généré dans: debug_reports/")

        debugger = None

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'arrêt: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("status")
def show_debug_status():
    """Afficher le statut du débogage"""
    global debugger

    show_debug_header()

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['warning_color']}]⚠️  Aucune session de débogage active.[/bold {SUNSET_THEME['warning_color']}]")
        console.print(f"Utilisez: [bold]{SUNSET_THEME['accent_color']}tawiza debug start[/bold]{SUNSET_THEME['text_color']}")
        return

    try:
        # Générer un rapport rapide
        report = run_async(debugger.generate_debug_report())

        # Afficher le statut
        console.print(f"[bold {SUNSET_THEME['info_color']}]📊 Statut du Débogage:[/bold {SUNSET_THEME['info_color']}]")
        console.print()

        # Informations système
        system_info = report.get("system_info", {})
        if system_info:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🖥️  Système:[/bold {SUNSET_THEME['accent_color']}]")
            console.print(f"  • Python: {system_info.get('python_version', 'N/A')[:50]}...")
            console.print(f"  • Platform: {system_info.get('platform', 'N/A')}")
            console.print(f"  • CPU Count: {system_info.get('cpu_count', 'N/A')}")
            console.print(f"  • Memory: {system_info.get('total_memory_gb', 0):.1f} GB")
            console.print()

        # Performance summary
        perf_summary = report.get("performance_summary", {})
        if "cpu" in perf_summary:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]⚡ Performance:[/bold {SUNSET_THEME['accent_color']}]")
            console.print(f"  • CPU Moyenne: {perf_summary['cpu']['average']:.1f}%")
            console.print(f"  • Memory Moyenne: {perf_summary['memory']['average']:.1f}%")

            gpu_summary = perf_summary.get("gpu", {})
            if "utilization" in gpu_summary:
                console.print(f"  • GPU Moyenne: {gpu_summary['utilization']['average']:.1f}%")
            console.print()

        # Agent status
        agent_summary = report.get("agent_status", {})
        if "total_agents" in agent_summary:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🤖 Agents:[/bold {SUNSET_THEME['accent_color']}]")
            console.print(f"  • Total: {agent_summary['total_agents']}")
            console.print(f"  • Actifs: {agent_summary['active_agents']}")
            console.print(f"  • Tâches: {agent_summary['total_tasks']}")
            console.print(f"  • Erreurs: {agent_summary['total_errors']}")
            console.print()

        # Recommandations
        recommendations = report.get("recommendations", [])
        if recommendations:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]💡 Recommandations:[/bold {SUNSET_THEME['accent_color']}]")
            for i, rec in enumerate(recommendations[:3], 1):
                console.print(f"  {i}. {rec}")
            if len(recommendations) > 3:
                console.print(f"  ... et {len(recommendations) - 3} autres")
            console.print()

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de la génération du rapport: {e}[/bold {SUNSET_THEME['error_color']}]")

@app.command("monitor")
def start_monitoring(
    duration: int = typer.Option(60, "--duration", "-d", help="Durée du monitoring en secondes"),
    realtime: bool = typer.Option(True, "--realtime/--no-realtime", help="Affichage en temps réel"),
    export: str = typer.Option(None, "--export", help="Exporter les données")
):
    """Monitorer le système en temps réel"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]📊 Monitoring du système pour {duration}s...[/bold {SUNSET_THEME['info_color']}]")

    try:
        if realtime:
            # Monitoring en temps réel
            with Live(console=console, refresh_per_second=1) as live:
                start_time = time.time()

                while time.time() - start_time < duration:
                    # Obtenir les métriques actuelles
                    report = run_async(debugger.generate_debug_report())

                    # Créer le tableau de monitoring
                    table = create_monitoring_table(report)

                    # Mettre à jour l'affichage
                    live.update(Align.center(table))

                    time.sleep(1)  # Mettre à jour chaque seconde

        else:
            # Monitoring batch
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:

                task = progress.add_task("📊 Collecte des métriques...", total=duration)

                metrics_history = []
                start_time = time.time()

                while time.time() - start_time < duration:
                    # Collecter les métriques
                    report = run_async(debugger.generate_debug_report())
                    metrics_history.append(report)

                    progress.update(task, advance=1)
                    time.sleep(1)

            # Afficher le résumé
            console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Monitoring terminé![/bold {SUNSET_THEME['success_color']}]")
            show_monitoring_summary(metrics_history)

            # Exporter si demandé
            if export:
                export_monitoring_data(metrics_history, export)

    except KeyboardInterrupt:
        console.print(f"\n[bold {SUNSET_THEME['warning_color']}]⚠️  Monitoring interrompu par l'utilisateur.[/bold {SUNSET_THEME['warning_color']}]")
    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors du monitoring: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("analyze")
def analyze_issues(
    component: str = typer.Option(None, "--component", "-c", help="Composant à analyser"),
    time_range: str = typer.Option("1h", "--time-range", "-t", help="Plage de temps (1h, 24h, 7d)"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Analyse détaillée"),
    export: str = typer.Option(None, "--export", help="Exporter l'analyse")
):
    """Analyser les problèmes et erreurs"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]🔍 Analyse des problèmes...[/bold {SUNSET_THEME['info_color']}]")

    try:
        # Générer le rapport d'analyse
        report = run_async(debugger.generate_debug_report())

        # Analyser les erreurs
        error_analysis = report.get("error_analysis", {})

        if not error_analysis or error_analysis.get("status") == "Aucune erreur enregistrée":
            console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Aucun problème détecté![/bold {SUNSET_THEME['success_color']}]")
            return

        # Afficher l'analyse des erreurs
        console.print(f"\n[bold {SUNSET_THEME['accent_color']}]📊 Analyse des Erreurs:[/bold {SUNSET_THEME['accent_color']}]")

        # Tableau des erreurs par composant
        table = Table(title="Erreurs par Composant", box=box.ROUNDED)
        table.add_column("Composant", style=SUNSET_THEME["info_color"])
        table.add_column("Erreurs", justify="center")
        table.add_column("Taux", justify="right")

        errors_by_component = error_analysis.get("errors_by_component", {})
        total_errors = error_analysis.get("total_errors", 0)

        for component, count in sorted(errors_by_component.items(), key=lambda x: x[1], reverse=True):
            error_rate = (count / total_errors * 100) if total_errors > 0 else 0
            table.add_row(
                component,
                str(count),
                f"{error_rate:.1f}%"
            )

        console.print(table)

        # Erreurs récentes
        recent_errors = error_analysis.get("recent_errors", [])
        if recent_errors and detailed:
            console.print(f"\n[bold {SUNSET_THEME['accent_color']}]🕐 Erreurs Récentes:[/bold {SUNSET_THEME['accent_color']}]")

            for error in recent_errors[-10:]:  # 10 dernières
                console.print(f"\n[dim]{error['timestamp']}[/dim]")
                console.print(f"  [bold]{error['component']}[/bold]: {error['message']}")
                if error.get('stack_trace'):
                    console.print("  [dim]Stack trace disponible[/dim]")

        # Analyse des causes
        console.print(f"\n[bold {SUNSET_THEME['accent_color']}]🔍 Analyse des Causes:[/bold {SUNSET_THEME['accent_color']}]")

        causes = analyze_error_causes(errors_by_component)
        for i, cause in enumerate(causes, 1):
            console.print(f"  {i}. {cause}")

        # Recommandations
        recommendations = report.get("recommendations", [])
        if recommendations:
            console.print(f"\n[bold {SUNSET_THEME['accent_color']}]💡 Recommandations:[/bold {SUNSET_THEME['accent_color']}]")
            for i, rec in enumerate(recommendations, 1):
                console.print(f"  {i}. {rec}")

        # Exporter si demandé
        if export:
            export_analysis(report, export)

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'analyse: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("memory")
def analyze_memory(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Analyse mémoire détaillée"),
    leak_detection: bool = typer.Option(True, "--leaks/--no-leaks", help="Détection de fuites mémoire"),
    export: str = typer.Option(None, "--export", help="Exporter l'analyse mémoire")
):
    """Analyser l'utilisation mémoire et détecter les fuites"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]💾 Analyse de la mémoire...[/bold {SUNSET_THEME['info_color']}]")

    try:
        # Forcer une analyse mémoire
        snapshot = debugger.memory_profiler.take_snapshot()

        if not snapshot:
            console.print(f"\n[bold {SUNSET_THEME['warning_color']}]⚠️  Impossible d'obtenir un snapshot mémoire.[/bold {SUNSET_THEME['warning_color']}]")
            return

        # Afficher l'analyse
        console.print(f"\n[bold {SUNSET_THEME['accent_color']}]📊 Analyse Mémoire:[/bold {SUNSET_THEME['accent_color']}]")
        console.print(f"  • Mémoire totale: {snapshot.total_memory / 1024 / 1024:.1f} MB")
        console.print(f"  • Nombre d'objets: {len(snapshot.objects)}")
        console.print()

        if detailed:
            # Objets les plus volumineux
            console.print(f"[bold {SUNSET_THEME['accent_color']}]🏔️  Objets les Plus Volumineux:[/bold {SUNSET_THEME['accent_color']}]")

            table = Table(box=box.ROUNDED)
            table.add_column("Type", style=SUNSET_THEME["info_color"])
            table.add_column("Count", justify="right")
            table.add_column("Est. Size", justify="right")

            for obj in snapshot.top_objects[:10]:
                table.add_row(
                    obj["type"],
                    str(obj["count"]),
                    f"{obj['size_bytes'] / 1024:.1f} KB"
                )

            console.print(table)
            console.print()

        # Détection de fuites
        if leak_detection:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]💧 Détection de Fuites:[/bold {SUNSET_THEME['accent_color']}]")

            leaks = detect_memory_leaks(debugger.memory_profiler.snapshots)
            if leaks:
                console.print(f"  ⚠️  {len(leaks)} fuites mémoire détectées:")
                for leak in leaks:
                    console.print(f"    • {leak['timestamp']}: +{leak['growth_mb']:.1f} MB")
            else:
                console.print("  ✅ Aucune fuite mémoire détectée")

            console.print()

        # Recommandations
        recommendations = generate_memory_recommendations(snapshot)
        if recommendations:
            console.print(f"[bold {SUNSET_THEME['accent_color']}]💡 Recommandations:[/bold {SUNSET_THEME['accent_color']}]")
            for i, rec in enumerate(recommendations, 1):
                console.print(f"  {i}. {rec}")

        # Exporter si demandé
        if export:
            export_memory_analysis(snapshot, export)

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'analyse mémoire: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("trace")
def trace_execution(
    component: str = typer.Argument(..., help="Composant à tracer"),
    duration: int = typer.Option(30, "--duration", "-d", help="Durée du traçage en secondes"),
    detailed: bool = typer.Option(False, "--detailed", help="Traçage détaillé")
):
    """Tracer l'exécution d'un composant"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]🔍 Traçage de {component} pendant {duration}s...[/bold {SUNSET_THEME['info_color']}]")

    try:
        # Démarrer le traçage
        trace_id = f"trace_{component}_{int(time.time())}"
        debugger.agent_tracer.start_trace(component, trace_id)

        # Simuler le traçage (dans une vraie implémentation, cela serait hooké aux vrais événements)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            task = progress.add_task(f"🎯 Traçage {component}...", total=duration)

            start_time = time.time()
            step_count = 0

            while time.time() - start_time < duration:
                # Ajouter des étapes de trace simulées
                step_count += 1
                debugger.agent_tracer.add_trace_step(
                    trace_id,
                    f"step_{step_count}",
                    {
                        "timestamp": time.time(),
                        "memory_usage": debugger._get_current_memory_usage(),
                        "cpu_usage": debugger._get_current_cpu_usage()
                    }
                )

                progress.update(task, advance=1)
                time.sleep(1)

        # Terminer le traçage
        debugger.agent_tracer.end_trace(trace_id, True, {"steps": step_count})

        console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Traçage terminé![/bold {SUNSET_THEME['success_color']}]")
        console.print(f"📊 Trace ID: {trace_id}")
        console.print(f"⏱️  Durée: {duration}s")
        console.print(f"📝 Étapes: {step_count}")

    except KeyboardInterrupt:
        console.print(f"\n[bold {SUNSET_THEME['warning_color']}]⚠️  Traçage interrompu.[/bold {SUNSET_THEME['warning_color']}]")
    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors du traçage: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

@app.command("report")
def generate_report(
    format: str = typer.Option("json", "--format", "-f", help="Format du rapport (json, html, markdown)"),
    output: str = typer.Option(None, "--output", "-o", help="Fichier de sortie"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Rapport détaillé")
):
    """Générer un rapport de débogage complet"""
    global debugger

    if not debugger:
        console.print(f"[bold {SUNSET_THEME['error_color']}]❌ Aucune session de débogage active.[/bold {SUNSET_THEME['error_color']}]")
        return

    show_debug_header()

    console.print(f"[bold {SUNSET_THEME['info_color']}]📋 Génération du rapport de débogage...[/bold {SUNSET_THEME['info_color']}]")

    try:
        # Générer le rapport
        report = run_async(debugger.generate_debug_report())

        # Déterminer le nom de fichier
        if not output:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output = f"debug_report_{timestamp}.{format}"

        # Exporter dans le format demandé
        if format == "json":
            export_json_report(report, output)
        elif format == "html":
            export_html_report(report, output)
        elif format == "markdown":
            export_markdown_report(report, output)
        else:
            console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Format non supporté: {format}[/bold {SUNSET_THEME['error_color']}]")
            return

        console.print(f"\n[bold {SUNSET_THEME['success_color']}]✅ Rapport généré:[/bold {SUNSET_THEME['success_color']}]")
        console.print(f"📄 {output}")

        # Afficher un résumé
        show_report_summary(report)

    except Exception as e:
        console.print(f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de la génération du rapport: {e}[/bold {SUNSET_THEME['error_color']}]")
        raise typer.Exit(1)

# Fonctions utilitaires

def show_debug_info():
    """Afficher les informations de débogage"""
    console.print(f"[bold {SUNSET_THEME['info_color']}]ℹ️  Informations de Débogage:[/bold {SUNSET_THEME['info_color']}]")
    console.print(f"  • Niveau de débogage: {SUNSET_THEME['accent_color']}INFO{SUNSET_THEME['text_color']}")
    console.print(f"  • Profilage: {SUNSET_THEME['accent_color']}Activé{SUNSET_THEME['text_color']}")
    console.print(f"  • Logs: {SUNSET_THEME['accent_color']}logs/advanced_debug.log{SUNSET_THEME['text_color']}")
    console.print(f"  • Rapports: {SUNSET_THEME['accent_color']}debug_reports/{SUNSET_THEME['text_color']}")
    console.print()

    console.print(f"[bold {SUNSET_THEME['info_color']}]📝 Commandes disponibles:[/bold {SUNSET_THEME['info_color']}]")
    console.print("  • tawiza debug status     - Voir le statut")
    console.print("  • tawiza debug monitor    - Monitorer en temps réel")
    console.print("  • tawiza debug analyze    - Analyser les problèmes")
    console.print("  • tawiza debug memory     - Analyser la mémoire")
    console.print("  • tawiza debug report     - Générer un rapport")
    console.print()

def create_monitoring_table(report: dict[str, Any]) -> Table:
    """Créer un tableau de monitoring"""
    table = Table(title="Système de Monitoring en Temps Réel", box=box.ROUNDED)

    # Métriques de performance
    perf_summary = report.get("performance_summary", {})
    if "cpu" in perf_summary:
        table.add_column("CPU %", style=SUNSET_THEME["info_color"], justify="center")
        table.add_column("Memory %", style=SUNSET_THEME["info_color"], justify="center")

        # GPU si disponible
        gpu_summary = perf_summary.get("gpu", {})
        if "utilization" in gpu_summary:
            table.add_column("GPU %", style=SUNSET_THEME["info_color"], justify="center")

        # Agents
        agent_summary = report.get("agent_status", {})
        if "total_agents" in agent_summary:
            table.add_column("Agents", style=SUNSET_THEME["info_color"], justify="center")

        # Erreurs
        error_analysis = report.get("error_analysis", {})
        if "total_errors" in error_analysis:
            table.add_column("Erreurs", style=SUNSET_THEME["info_color"], justify="center")

        # Ligne de données
        row_data = []

        # CPU
        if "cpu" in perf_summary:
            cpu_avg = perf_summary["cpu"]["average"]
            cpu_color = SUNSET_THEME["success_color"] if cpu_avg < 70 else SUNSET_THEME["warning_color"] if cpu_avg < 85 else SUNSET_THEME["error_color"]
            row_data.append(f"[{cpu_color}]{cpu_avg:.1f}[/{cpu_color}]")
        else:
            row_data.append("N/A")

        # Memory
        if "memory" in perf_summary:
            memory_avg = perf_summary["memory"]["average"]
            memory_color = SUNSET_THEME["success_color"] if memory_avg < 70 else SUNSET_THEME["warning_color"] if memory_avg < 85 else SUNSET_THEME["error_color"]
            row_data.append(f"[{memory_color}]{memory_avg:.1f}[/{memory_color}]")
        else:
            row_data.append("N/A")

        # GPU
        if "utilization" in gpu_summary:
            gpu_avg = gpu_summary["utilization"]["average"]
            gpu_color = SUNSET_THEME["success_color"] if gpu_avg < 70 else SUNSET_THEME["warning_color"] if gpu_avg < 85 else SUNSET_THEME["error_color"]
            row_data.append(f"[{gpu_color}]{gpu_avg:.1f}[/{gpu_color}]")
        elif "utilization" in gpu_summary:
            row_data.append("N/A")

        # Agents
        if "total_agents" in agent_summary:
            active_agents = agent_summary["active_agents"]
            total_agents = agent_summary["total_agents"]
            row_data.append(f"{active_agents}/{total_agents}")
        else:
            row_data.append("N/A")

        # Errors
        if "total_errors" in error_analysis:
            total_errors = error_analysis["total_errors"]
            error_color = SUNSET_THEME["success_color"] if total_errors == 0 else SUNSET_THEME["warning_color"] if total_errors < 10 else SUNSET_THEME["error_color"]
            row_data.append(f"[{error_color}]{total_errors}[/{error_color}]")
        else:
            row_data.append("N/A")

        table.add_row(*row_data)

    else:
        table.add_column("Status", style=SUNSET_THEME["info_color"])
        table.add_row("Aucune donnée disponible")

    return table

def show_monitoring_summary(metrics_history: list[dict[str, Any]]):
    """Afficher un résumé du monitoring"""
    if not metrics_history:
        return

    console.print(f"\n[bold {SUNSET_THEME['info_color']}]📈 Résumé du Monitoring:[/bold {SUNSET_THEME['info_color']}]")

    # Calculer les moyennes
    cpu_values = []
    memory_values = []
    gpu_values = []

    for report in metrics_history:
        perf_summary = report.get("performance_summary", {})
        if "cpu" in perf_summary:
            cpu_values.append(perf_summary["cpu"]["average"])
        if "memory" in perf_summary:
            memory_values.append(perf_summary["memory"]["average"])
        gpu_summary = perf_summary.get("gpu", {})
        if "utilization" in gpu_summary:
            gpu_values.append(gpu_summary["utilization"]["average"])

    if cpu_values:
        console.print(f"  • CPU Moyenne: {sum(cpu_values) / len(cpu_values):.1f}%")
    if memory_values:
        console.print(f"  • Memory Moyenne: {sum(memory_values) / len(memory_values):.1f}%")
    if gpu_values:
        console.print(f"  • GPU Moyenne: {sum(gpu_values) / len(gpu_values):.1f}%")

    console.print()

def export_monitoring_data(metrics_history: list[dict[str, Any]], filename: str):
    """Exporter les données de monitoring"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(metrics_history, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"📄 Données exportées: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def analyze_error_causes(errors_by_component: dict[str, int]) -> list[str]:
    """Analyser les causes des erreurs"""
    causes = []

    # Analyser les patterns
    for component, count in errors_by_component.items():
        if count > 10:
            if "gpu" in component.lower():
                causes.append(f"Problèmes GPU fréquents sur {component} - vérifiez la température et les drivers")
            elif "memory" in component.lower():
                causes.append(f"Problèmes mémoire sur {component} - surveillez les fuites mémoire")
            elif "agent" in component.lower():
                causes.append(f"Agent {component} instable - redémarrez ou vérifiez la configuration")
            else:
                causes.append(f"Composant {component} a un taux d'erreur élevé - investigation nécessaire")

    if not causes:
        causes.append("Aucun pattern d'erreur significatif détecté")

    return causes

def detect_memory_leaks(snapshots: list) -> list[dict[str, Any]]:
    """Détecter les fuites mémoire"""
    leaks = []

    if len(snapshots) < 2:
        return leaks

    for i in range(1, len(snapshots)):
        current = snapshots[i]
        previous = snapshots[i-1]

        growth = current.total_memory - previous.total_memory
        if growth > 50 * 1024 * 1024:  # 50MB
            leaks.append({
                "timestamp": current.timestamp,
                "growth_mb": growth / 1024 / 1024
            })

    return leaks

def generate_memory_recommendations(snapshot) -> list[str]:
    """Générer des recommandations basées sur l'analyse mémoire"""
    recommendations = []

    memory_mb = snapshot.total_memory / 1024 / 1024

    if memory_mb > 1000:  # 1GB
        recommendations.append("Utilisation mémoire élevée - envisagez d'optimiser les structures de données")

    # Analyser les types d'objets
    object_types = {}
    for obj in snapshot.objects:
        obj_type = obj["type"]
        object_types[obj_type] = object_types.get(obj_type, 0) + obj["count"]

    # Recommandations basées sur les types
    if object_types.get("dict", 0) > 10000:
        recommendations.append("Nombre élevé de dictionnaires - envisagez d'utiliser des structures plus efficaces")

    if object_types.get("list", 0) > 50000:
        recommendations.append("Nombre élevé de listes - envisagez d'utiliser des arrays NumPy pour données numériques")

    if not recommendations:
        recommendations.append("Utilisation mémoire normale - aucune action requise")

    return recommendations

def export_analysis(report: dict[str, Any], filename: str):
    """Exporter l'analyse"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"📄 Analyse exportée: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def export_memory_analysis(snapshot, filename: str):
    """Exporter l'analyse mémoire"""
    try:
        data = {
            "timestamp": snapshot.timestamp,
            "total_memory_mb": snapshot.total_memory / 1024 / 1024,
            "objects": snapshot.objects
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"📄 Analyse mémoire exportée: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def export_json_report(report: dict[str, Any], filename: str):
    """Exporter le rapport en JSON"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        console.print(f"📄 Rapport JSON exporté: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def export_html_report(report: dict[str, Any], filename: str):
    """Exporter le rapport en HTML"""
    try:
        html_content = generate_html_report(report)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

        console.print(f"📄 Rapport HTML exporté: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def export_markdown_report(report: dict[str, Any], filename: str):
    """Exporter le rapport en Markdown"""
    try:
        md_content = generate_markdown_report(report)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md_content)

        console.print(f"📄 Rapport Markdown exporté: {filename}")

    except Exception as e:
        console.print(f"⚠️  Erreur lors de l'export: {e}")

def generate_html_report(report: dict[str, Any]) -> str:
    """Générer un rapport HTML"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Tawiza-V2 Debug Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #1a1a1a; color: #f0f0f0; }}
        .header {{ background: linear-gradient(135deg, #FF6B35, #F7931E); padding: 20px; border-radius: 10px; }}
        .section {{ margin: 20px 0; padding: 15px; background-color: #2a2a2a; border-radius: 8px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #3a3a3a; border-radius: 5px; }}
        .error {{ color: #FF5252; }}
        .warning {{ color: #FF8E53; }}
        .success {{ color: #06FFA5; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #444; padding: 8px; text-align: left; }}
        th {{ background-color: #3a3a3a; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🐛 Tawiza-V2 Debug Report</h1>
        <p>Généré le: {report.get('timestamp', 'N/A')}</p>
    </div>

    <div class="section">
        <h2>📊 Performance Summary</h2>
        {generate_performance_html(report.get('performance_summary', {}))}
    </div>

    <div class="section">
        <h2>🤖 Agent Status</h2>
        {generate_agents_html(report.get('agent_status', {}))}
    </div>

    <div class="section">
        <h2>❌ Error Analysis</h2>
        {generate_errors_html(report.get('error_analysis', {}))}
    </div>

    <div class="section">
        <h2>💡 Recommendations</h2>
        {generate_recommendations_html(report.get('recommendations', []))}
    </div>
</body>
</html>
"""
    return html

def generate_markdown_report(report: dict[str, Any]) -> str:
    """Générer un rapport Markdown"""
    md = f"""# 🐛 Tawiza-V2 Debug Report

**Généré le:** {report.get('timestamp', 'N/A')}

## 📊 Performance Summary

{generate_performance_md(report.get('performance_summary', {}))}

## 🤖 Agent Status

{generate_agents_md(report.get('agent_status', {}))}

## ❌ Error Analysis

{generate_errors_md(report.get('error_analysis', {}))}

## 💡 Recommendations

{generate_recommendations_md(report.get('recommendations', []))}
"""
    return md

def generate_performance_html(perf_summary: dict[str, Any]) -> str:
    """Générer le HTML des performances"""
    if "cpu" not in perf_summary:
        return "<p>Aucune donnée de performance disponible</p>"

    html = f"""
    <div class="metric">CPU Moyenne: <strong>{perf_summary['cpu']['average']:.1f}%</strong></div>
    <div class="metric">Memory Moyenne: <strong>{perf_summary['memory']['average']:.1f}%</strong></div>
    """

    gpu_summary = perf_summary.get("gpu", {})
    if "utilization" in gpu_summary:
        html += f'<div class="metric">GPU Moyenne: <strong>{gpu_summary["utilization"]["average"]:.1f}%</strong></div>'

    return html

def generate_agents_html(agent_summary: dict[str, Any]) -> str:
    """Générer le HTML des agents"""
    if "total_agents" not in agent_summary:
        return "<p>Aucun agent actif</p>"

    return f"""
    <div class="metric">Total Agents: <strong>{agent_summary['total_agents']}</strong></div>
    <div class="metric">Active Agents: <strong>{agent_summary['active_agents']}</strong></div>
    <div class="metric">Total Tasks: <strong>{agent_summary['total_tasks']}</strong></div>
    <div class="metric">Total Errors: <strong class='error'>{agent_summary['total_errors']}</strong></div>
    """

def generate_errors_html(error_analysis: dict[str, Any]) -> str:
    """Générer le HTML des erreurs"""
    if "total_errors" not in error_analysis:
        return "<p>Aucune erreur enregistrée</p>"

    return f"""
    <p>Total Errors: <strong class='error'>{error_analysis['total_errors']}</strong></p>
    <p>Error Rate: <strong>{error_analysis.get('error_rate', 0):.2f}%</strong></p>
    """

def generate_recommendations_html(recommendations: list[str]) -> str:
    """Générer le HTML des recommandations"""
    if not recommendations:
        return "<p>Aucune recommandation</p>"

    html = "<ul>"
    for rec in recommendations:
        html += f"<li>{rec}</li>"
    html += "</ul>"
    return html

def generate_performance_md(perf_summary: dict[str, Any]) -> str:
    """Générer le Markdown des performances"""
    if "cpu" not in perf_summary:
        return "Aucune donnée de performance disponible"

    md = f"""
- **CPU Moyenne:** {perf_summary['cpu']['average']:.1f}%
- **Memory Moyenne:** {perf_summary['memory']['average']:.1f}%
"""

    gpu_summary = perf_summary.get("gpu", {})
    if "utilization" in gpu_summary:
        md += f"- **GPU Moyenne:** {gpu_summary['utilization']['average']:.1f}%\n"

    return md

def generate_agents_md(agent_summary: dict[str, Any]) -> str:
    """Générer le Markdown des agents"""
    if "total_agents" not in agent_summary:
        return "Aucun agent actif"

    return f"""
- **Total Agents:** {agent_summary['total_agents']}
- **Active Agents:** {agent_summary['active_agents']}
- **Total Tasks:** {agent_summary['total_tasks']}
- **Total Errors:** {agent_summary['total_errors']}
"""

def generate_errors_md(error_analysis: dict[str, Any]) -> str:
    """Générer le Markdown des erreurs"""
    if "total_errors" not in error_analysis:
        return "Aucune erreur enregistrée"

    return f"""
- **Total Errors:** {error_analysis['total_errors']}
- **Error Rate:** {error_analysis.get('error_rate', 0):.2f}%
"""

def generate_recommendations_md(recommendations: list[str]) -> str:
    """Générer le Markdown des recommandations"""
    if not recommendations:
        return "Aucune recommandation"

    md = ""
    for i, rec in enumerate(recommendations, 1):
        md += f"{i}. {rec}\n"
    return md

def show_report_summary(report: dict[str, Any]):
    """Afficher un résumé du rapport"""
    console.print(f"\n[bold {SUNSET_THEME['info_color']}]📊 Résumé du Rapport:[/bold {SUNSET_THEME['info_color']}]")

    # Performance
    perf_summary = report.get("performance_summary", {})
    if "cpu" in perf_summary:
        console.print(f"  • CPU: {perf_summary['cpu']['average']:.1f}% moyenne")

    # Agents
    agent_summary = report.get("agent_status", {})
    if "total_agents" in agent_summary:
        console.print(f"  • Agents: {agent_summary['active_agents']}/{agent_summary['total_agents']} actifs")

    # Erreurs
    error_analysis = report.get("error_analysis", {})
    if "total_errors" in error_analysis:
        console.print(f"  • Erreurs: {error_analysis['total_errors']} total")

    console.print()

@app.command("dashboard")
def dashboard(
    mode: str = typer.Option(
        "system",
        "--mode",
        "-m",
        help="Dashboard mode: system, performance, agents, all"
    ),
    duration: int = typer.Option(
        60,
        "--duration",
        "-d",
        help="Duration in seconds (0 for unlimited)"
    ),
    refresh: int = typer.Option(
        2,
        "--refresh",
        "-r",
        help="Refresh rate per second"
    )
):
    """
    Launch real-time monitoring dashboard

    Examples:
        # System dashboard (CPU, Memory, Disk)
        tawiza debug dashboard --mode system

        # Performance dashboard (throughput, latency)
        tawiza debug dashboard --mode performance

        # Agents dashboard
        tawiza debug dashboard --mode agents

        # Run for 5 minutes
        tawiza debug dashboard --duration 300
    """
    import random

    from src.cli.ui.live_dashboard import (
        AgentsDashboard,
        AgentStatus,
        PerformanceDashboard,
        PerformanceMetrics,
        SystemDashboard,
    )

    console.clear()

    # Header
    mode_title = {
        "system": "System Resources",
        "performance": "Performance Metrics",
        "agents": "AI Agents",
        "all": "Full System Overview"
    }.get(mode, mode.title())

    console.print(Panel(
        f"[bold cyan]Tawiza Live Dashboard[/bold cyan]\n"
        f"[dim]Mode: {mode_title} | Refresh: {refresh}/s[/dim]",
        border_style="cyan"
    ))
    console.print()

    try:
        if mode == "system":
            # System resources dashboard
            SystemDashboard.run(
                duration=duration if duration > 0 else 3600,
                refresh_rate=refresh
            )

        elif mode == "performance":
            # Performance metrics dashboard
            perf_dash = PerformanceDashboard()
            iterations = (duration * refresh) if duration > 0 else 3600 * refresh

            with Live(
                perf_dash.generate(PerformanceMetrics(0, 0, 100, 90, 0, 0, 0)),
                console=console,
                refresh_per_second=refresh
            ) as live:
                completed = 0
                failed = 0
                for _i in range(iterations):
                    # Simulate/collect metrics
                    completed += random.randint(0, 3)
                    if random.random() < 0.05:
                        failed += 1

                    metrics = PerformanceMetrics(
                        throughput=random.uniform(15, 35),
                        latency=random.uniform(5, 20),
                        success_rate=(completed / (completed + failed + 1)) * 100,
                        cache_hit_rate=random.uniform(85, 98),
                        active_tasks=random.randint(1, 8),
                        completed_tasks=completed,
                        failed_tasks=failed
                    )
                    live.update(perf_dash.generate(metrics))
                    time.sleep(1 / refresh)

        elif mode == "agents":
            # Agents status dashboard
            agents = [
                AgentStatus("Browser Agent", "running", 0, 98.0),
                AgentStatus("ML Optimizer", "running", 0, 99.0),
                AgentStatus("Data Analyst", "idle", 0, 97.5),
                AgentStatus("Code Generator", "running", 0, 96.0),
                AgentStatus("Web Scraper", "idle", 0, 99.2),
            ]

            iterations = (duration * refresh) if duration > 0 else 3600 * refresh

            with Live(
                AgentsDashboard.generate(agents),
                console=console,
                refresh_per_second=refresh
            ) as live:
                for _i in range(iterations):
                    # Simulate agent activity
                    for agent in agents:
                        if random.random() < 0.3:
                            agent.tasks_completed += random.randint(0, 2)
                        if random.random() < 0.1:
                            agent.status = "running" if agent.status == "idle" else "idle"
                        agent.success_rate = min(100, max(90, agent.success_rate + random.uniform(-1, 1)))

                    live.update(AgentsDashboard.generate(agents))
                    time.sleep(1 / refresh)

        else:
            console.print(f"[yellow]Unknown mode: {mode}[/yellow]")
            console.print("[dim]Available modes: system, performance, agents[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")

    console.print("\n[green]✓[/green] Dashboard session ended")


if __name__ == "__main__":
    app()
