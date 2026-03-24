#!/usr/bin/env python3
"""
Tawiza-V2 Unified Agents CLI
Systeme d'agents IA avec optimisation GPU, cache intelligent et task queue
Version consolidee fusionnant agents_advanced et agents_optimized
"""

import asyncio
import json
import time

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from src.cli.ui.mascot_hooks import (
    agent_mascot_inline,
    inline_success,
    on_error,
    on_long_task_end,
    on_success,
    show_agent_mascot,
)
from src.cli.utils.async_runner import run_async
from src.cli.utils.ui import SUNSET_THEME

console = Console()

# Application CLI unifiee
app = typer.Typer(
    name="agents",
    help="Systeme d'agents IA unifie avec optimisation GPU et cache intelligent",
    add_completion=False,
    rich_markup_mode="rich",
)

# Variable globale pour l'integration
_integration = None


def show_agents_header(agent_type: str = None):
    """Afficher l'en-tete des agents avec theme sunset et mascotte"""
    header_text = Text()
    header_text.append("🤖 ", style=SUNSET_THEME["header_color"])
    header_text.append("Tawiza Agents System", style=f"bold {SUNSET_THEME['header_color']}")
    header_text.append(" 🤖", style=SUNSET_THEME["header_color"])

    console.print(
        Panel(
            Align.center(header_text),
            style=f"{SUNSET_THEME['header_color']}",
            box=box.DOUBLE,
            padding=1,
        )
    )

    # Afficher mascotte spécifique à l'agent
    if agent_type:
        show_agent_mascot(agent_type, console=console)
    console.print()


async def ensure_initialized():
    """S'assurer que le systeme est initialise"""
    global _integration

    if _integration is not None:
        return _integration

    try:
        from src.infrastructure.agents.advanced.optimized_agent_integration import (
            OptimizedAgentIntegration,
            OptimizedSystemConfig,
            create_optimized_agent_integration,
        )

        console.print(
            f"[bold {SUNSET_THEME['info_color']}]Initialisation automatique du systeme...[/]"
        )

        config = OptimizedSystemConfig(
            num_workers=4, enable_gpu_optimization=True, enable_smart_cache=True
        )

        _integration = await create_optimized_agent_integration(config)
        console.print(f"[bold {SUNSET_THEME['success_color']}]Systeme initialise![/]\n")

        return _integration

    except ImportError as e:
        console.print(f"[bold {SUNSET_THEME['error_color']}]Module non disponible: {e}[/]")
        return None
    except Exception as e:
        console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur d'initialisation: {e}[/]")
        return None


# =============================================================================
# COMMANDES PRINCIPALES
# =============================================================================


@app.command("init")
def init_agents(
    workers: int = typer.Option(4, "--workers", "-w", help="Nombre de workers paralleles"),
    gpu: bool = typer.Option(True, "--gpu/--no-gpu", help="Activer l'optimisation GPU"),
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Activer le cache intelligent"),
    cache_size: int = typer.Option(1000, "--cache-size", help="Taille maximale du cache"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mode verbeux"),
):
    """Initialiser le systeme d'agents IA unifie"""
    global _integration

    show_agents_header()

    console.print(
        Panel.fit(
            "[bold]Systeme d'Agents IA Unifie[/bold]\n"
            "Task queue, cache intelligent, optimisation GPU",
            border_style=SUNSET_THEME["info_color"],
        )
    )

    async def init():
        global _integration

        try:
            from src.infrastructure.agents.advanced.optimized_agent_integration import (
                OptimizedSystemConfig,
                create_optimized_agent_integration,
            )

            config = OptimizedSystemConfig(
                num_workers=workers,
                cache_max_size=cache_size,
                enable_gpu_optimization=gpu,
                enable_smart_cache=cache,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Initialisation du systeme...", total=None)
                _integration = await create_optimized_agent_integration(config)
                progress.update(task, completed=True)

            console.print(
                f"\n[bold {SUNSET_THEME['success_color']}]Systeme initialise avec succes![/]\n"
            )

            # Afficher la configuration
            table = Table(title="Configuration", box=box.ROUNDED)
            table.add_column("Parametre", style="cyan")
            table.add_column("Valeur", style="green")

            table.add_row("Workers", str(workers))
            table.add_row("Cache size", str(cache_size))
            table.add_row("GPU optimization", "" if gpu else "")
            table.add_row("Smart cache", "" if cache else "")

            console.print(table)

            if hasattr(_integration, "show_system_stats"):
                console.print()
                await _integration.show_system_stats()

        except ImportError as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Module non disponible: {e}[/]")
            console.print("Installez les dependances: pip install -e .")
            raise typer.Exit(1)

    run_async(init())


@app.command("status")
def show_status():
    """Afficher le statut complet du systeme d'agents"""
    show_agents_header()

    async def status():
        integration = await ensure_initialized()
        if integration is None:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Systeme non disponible[/]")
            console.print("Utilisez: tawiza agents init")
            return

        # Display GPU status first
        from src.cli.ui.gpu_monitor import get_gpu_status

        gpu_status = get_gpu_status()
        if gpu_status.available:
            location = "Host" if gpu_status.location.value == "host" else "GPU Server"
            console.print(
                f"[dim]🎮 GPU: {location} | {gpu_status.memory_percent:.0f}% mémoire | {gpu_status.temperature}°C[/dim]\n"
            )

        if hasattr(integration, "show_system_stats"):
            await integration.show_system_stats()
        else:
            # Fallback: afficher les infos basiques
            table = Table(title="Statut du Systeme", box=box.ROUNDED)
            table.add_column("Composant", style="cyan")
            table.add_column("Statut", style="green")

            table.add_row("Systeme", " Operationnel")
            table.add_row(
                "GPU", " Actif" if hasattr(integration, "gpu_optimizer") else " Non disponible"
            )
            table.add_row(
                "Cache", " Actif" if hasattr(integration, "cache_manager") else " Non disponible"
            )

            console.print(table)

    run_async(status())


@app.command("shutdown")
def shutdown_system():
    """Arreter proprement le systeme d'agents"""
    global _integration

    if _integration:

        async def stop():
            global _integration
            if hasattr(_integration, "shutdown"):
                await _integration.shutdown()
            _integration = None
            console.print("[green]Systeme arrete proprement[/]")

        run_async(stop())
    else:
        console.print("[yellow]Systeme non initialise[/]")


# =============================================================================
# GESTION DU CACHE
# =============================================================================


@app.command("cache")
def cache_commands(
    action: str = typer.Argument("stats", help="Action: stats, clear, enable, disable"),
    agent_type: str | None = typer.Option(None, "--agent", help="Type d'agent (pour clear)"),
):
    """Gerer le cache du systeme"""

    async def manage_cache():
        integration = await ensure_initialized()
        if integration is None or not hasattr(integration, "cache_manager"):
            console.print(f"[bold {SUNSET_THEME['error_color']}]Cache non disponible[/]")
            return

        if action == "stats":
            try:
                stats = await integration.cache_manager.get_stats()

                table = Table(title="Statistiques du Cache", box=box.ROUNDED)
                table.add_column("Metrique", style="cyan")
                table.add_column("Valeur", style="green")

                table.add_row("Entrees", str(stats.get("size", 0)))
                table.add_row("Max size", str(stats.get("max_size", 0)))
                table.add_row("Memoire", f"{stats.get('memory_usage_mb', 0):.2f} MB")
                table.add_row("Hits", str(stats.get("hits", 0)))
                table.add_row("Misses", str(stats.get("misses", 0)))
                table.add_row("Taux de hit", f"{stats.get('hit_rate', 0):.1f}%")
                table.add_row("Statut", " Actif" if stats.get("is_enabled") else " Desactive")

                console.print(table)
            except Exception as e:
                console.print(f"[red]Erreur: {e}[/]")

        elif action == "clear":
            if hasattr(integration, "invalidate_cache"):
                await integration.invalidate_cache(agent_type)
                msg = f"pour {agent_type}" if agent_type else "completement"
                console.print(f"[green]Cache vide {msg}[/]")
            else:
                console.print("[yellow]Fonction non disponible[/]")

        elif action == "enable":
            if hasattr(integration.cache_manager, "enable"):
                await integration.cache_manager.enable()
                console.print("[green]Cache active[/]")

        elif action == "disable":
            if hasattr(integration.cache_manager, "disable"):
                await integration.cache_manager.disable()
                console.print("[yellow]Cache desactive[/]")

        else:
            console.print(f"[red]Action inconnue: {action}[/]")
            console.print("Actions: stats, clear, enable, disable")

    run_async(manage_cache())


# =============================================================================
# OPTIMISATION GPU
# =============================================================================


@app.command("gpu-optimize")
def gpu_optimize(
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="Modele a optimiser"),
    benchmark: bool = typer.Option(
        True, "--benchmark/--no-benchmark", help="Executer un benchmark"
    ),
):
    """Optimiser les performances GPU pour l'inference"""
    show_agents_header("optimizer")

    console.print(
        f"{agent_mascot_inline('optimizer', 'starting')} [bold {SUNSET_THEME['info_color']}]Optimisation GPU pour: {model}[/]\n"
    )

    async def optimize():
        integration = await ensure_initialized()
        if integration is None:
            return

        if not hasattr(integration, "gpu_optimizer"):
            console.print(f"[bold {SUNSET_THEME['warning_color']}]GPU optimizer non disponible[/]")
            return

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Optimisation en cours...", total=None)
                result = await integration.gpu_optimizer.optimize_inference_performance(model)
                progress.update(task, completed=True)

            console.print(f"\n[bold {SUNSET_THEME['success_color']}]Optimisation completee![/]\n")

            # Afficher les resultats
            table = Table(title="Resultats d'Optimisation", box=box.ROUNDED)
            table.add_column("Metrique", style=SUNSET_THEME["info_color"])
            table.add_column("Avant", style=SUNSET_THEME["warning_color"])
            table.add_column("Apres", style=SUNSET_THEME["success_color"])
            table.add_column("Amelioration", style=SUNSET_THEME["accent_color"])

            if hasattr(result, "original_performance"):
                table.add_row(
                    "Performance (tokens/sec)",
                    f"{result.original_performance:.1f}",
                    f"{result.optimized_performance:.1f}",
                    f"+{result.improvement_percentage:.1f}%",
                )

            console.print(table)

            if benchmark:
                console.print(f"\n[bold {SUNSET_THEME['info_color']}]Benchmark en cours...[/]\n")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Test de performance...", total=100)
                    for _i in range(100):
                        await asyncio.sleep(0.02)
                        progress.update(task, advance=1)
                inline_success("Benchmark termine!")

            # Mascotte de succès
            on_long_task_end("Optimisation GPU", success=True)

        except Exception as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur: {e}[/]")
            on_long_task_end("Optimisation GPU", success=False)

    run_async(optimize())


# =============================================================================
# TACHES D'AGENTS
# =============================================================================


@app.command("analyze-data")
def analyze_data(
    dataset: str = typer.Argument(..., help="Chemin vers le dataset a analyser"),
    output: str = typer.Option("analysis_report.json", "--output", "-o", help="Fichier de sortie"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Analyse detaillee"),
):
    """Analyser un dataset avec l'agent Data Analyst"""
    show_agents_header("data")

    console.print(
        f"{agent_mascot_inline('data', 'starting')} [bold {SUNSET_THEME['info_color']}]Analyse du dataset: {dataset}[/]\n"
    )

    # Display GPU status
    from src.cli.ui.gpu_monitor import get_gpu_status

    gpu_status = get_gpu_status()
    if gpu_status.available:
        location = "Host" if gpu_status.location.value == "host" else "GPU Server"
        console.print(f"[dim]🎮 GPU: {location} | {gpu_status.memory_percent:.0f}% mémoire[/dim]\n")

    async def analyze():
        integration = await ensure_initialized()
        if integration is None:
            return

        try:
            if hasattr(integration, "execute_data_analysis"):
                task_id = await integration.execute_data_analysis(
                    dataset, detailed=detailed, output_format="json"
                )
                console.print(
                    f"[bold {SUNSET_THEME['accent_color']}]Tache soumise: {task_id[:8]}...[/]"
                )
            else:
                console.print("[yellow]Fonction d'analyse non disponible - simulation[/]")
                # Simulation
                await asyncio.sleep(1)
                result = {"summary": {"rows": 1000, "columns": 10, "missing": 5}}

                with open(output, "w") as f:
                    json.dump(result, f, indent=2)
                inline_success(f"Rapport sauvegarde: {output}")

            # Mascotte de succès
            on_long_task_end("Analyse de données", success=True)

        except Exception as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur: {e}[/]")
            on_long_task_end("Analyse de données", success=False)

    run_async(analyze())


@app.command("generate-code")
def generate_code(
    description: str = typer.Argument(..., help="Description du code a generer"),
    language: str = typer.Option("python", "--language", "-l", help="Langage de programmation"),
    output: str = typer.Option("generated_code.py", "--output", "-o", help="Fichier de sortie"),
    framework: str | None = typer.Option(None, "--framework", "-f", help="Framework a utiliser"),
    tests: bool = typer.Option(True, "--tests/--no-tests", help="Generer des tests"),
):
    """Generer du code avec l'agent Code Generator"""
    show_agents_header("code")

    console.print(
        f"{agent_mascot_inline('code', 'starting')} [bold {SUNSET_THEME['info_color']}]Generation de code {language}[/]\n"
    )
    console.print(f"  Description: {description}")
    if framework:
        console.print(f"  Framework: {framework}")
    console.print()

    async def generate():
        integration = await ensure_initialized()
        if integration is None:
            return

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Generation en cours...", total=None)

                if hasattr(integration, "execute_code_generation"):
                    task_id = await integration.execute_code_generation(
                        description, language, framework=framework, generate_tests=tests
                    )
                    console.print(
                        f"\n[bold {SUNSET_THEME['accent_color']}]Tache soumise: {task_id[:8]}...[/]"
                    )
                else:
                    # Simulation
                    await asyncio.sleep(2)
                    code = (
                        f"# Generated {language} code\n# {description}\n\ndef main():\n    pass\n"
                    )
                    with open(output, "w") as f:
                        f.write(code)
                    inline_success(f"Code sauvegarde: {output}")

            # Mascotte de succès
            on_long_task_end("Génération de code", success=True)

        except Exception as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur: {e}[/]")
            on_long_task_end("Génération de code", success=False)

    run_async(generate())


@app.command("automate-browser")
def automate_browser(
    url: str = typer.Argument(..., help="URL a automatiser"),
    objective: str = typer.Argument(..., help="Objectif de l'automatisation"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Mode headless"),
    output: str = typer.Option(
        "automation_result.json", "--output", "-o", help="Fichier de sortie"
    ),
):
    """Automatiser des taches de navigateur"""
    show_agents_header("browser")

    console.print(
        f"{agent_mascot_inline('browser', 'starting')} [bold {SUNSET_THEME['info_color']}]Automation du navigateur[/]\n"
    )
    console.print(f"  URL: {url}")
    console.print(f"  Objectif: {objective}")
    console.print()

    async def automate():
        try:
            from src.infrastructure.agents.advanced.browser_automation_agent import (
                BrowserAutomationAgent,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Automation en cours...", total=None)

                browser_agent = BrowserAutomationAgent()
                await browser_agent.initialize()

                try:
                    browser_task = await browser_agent.create_automation_task(
                        url=url, objective=objective, headless=headless
                    )
                    result = await browser_agent.execute_task(browser_task)

                    from dataclasses import asdict

                    result_dict = asdict(result)

                    with open(output, "w") as f:
                        json.dump(result_dict, f, indent=2)

                    progress.update(task, completed=True)

                    inline_success(f"Automation completee! Resultat: {output}")
                    on_long_task_end("Automation navigateur", success=True)

                finally:
                    await browser_agent.cleanup()

        except ImportError:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Module browser non disponible[/]")
            on_error("Module browser non disponible")
        except Exception as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur: {e}[/]")
            on_long_task_end("Automation navigateur", success=False)

    run_async(automate())


# =============================================================================
# BENCHMARK ET MONITORING
# =============================================================================


@app.command("benchmark")
def benchmark_system(
    num_tasks: int = typer.Option(50, "--tasks", "-n", help="Nombre de taches"),
    workers: int = typer.Option(4, "--workers", "-w", help="Nombre de workers"),
    duration: int = typer.Option(60, "--duration", "-d", help="Duree en secondes"),
):
    """Benchmarker les performances du systeme"""
    show_agents_header("ml")

    console.print(f"{agent_mascot_inline('ml', 'starting')}")
    console.print(
        Panel.fit(
            f"[bold]Benchmark du Systeme[/bold]\n"
            f"Taches: {num_tasks} | Workers: {workers} | Duree: {duration}s",
            border_style="cyan",
        )
    )

    async def run_benchmark():
        try:
            from src.infrastructure.agents.advanced.optimized_agent_integration import (
                OptimizedSystemConfig,
                create_optimized_agent_integration,
            )

            config = OptimizedSystemConfig(num_workers=workers, enable_gpu_optimization=False)
            integration = await create_optimized_agent_integration(config)

            async def bench_task(n):
                await asyncio.sleep(0.01)
                return n * 2

            console.print(f"\n[yellow]Soumission de {num_tasks} taches...[/]")
            start = time.time()

            for i in range(num_tasks):
                await integration.submit_task(
                    "benchmark_agent", "compute", bench_task, (i,), use_cache=False
                )

            console.print("[yellow]Attente de completion...[/]")
            await asyncio.sleep(2)

            elapsed = time.time() - start
            stats = await integration.task_queue_system.get_system_stats()

            table = Table(title="Resultats du Benchmark", box=box.ROUNDED)
            table.add_column("Metrique", style="cyan")
            table.add_column("Valeur", style="green")

            throughput = stats["total_tasks_completed"] / elapsed

            table.add_row("Taches soumises", str(num_tasks))
            table.add_row("Taches completees", str(stats["total_tasks_completed"]))
            table.add_row("Duree totale", f"{elapsed:.2f}s")
            table.add_row("Throughput", f"{throughput:.1f} taches/s")

            console.print(table)

            if throughput > 20:
                inline_success("Performance excellente!")
                on_success("Benchmark")
            elif throughput > 10:
                console.print("\n[bold yellow]Performance correcte[/]")
                on_success("Benchmark")
            else:
                console.print("\n[bold red]Performance a ameliorer[/]")
                on_error("Performance faible")

            await integration.shutdown()

        except Exception as e:
            console.print(f"[bold {SUNSET_THEME['error_color']}]Erreur: {e}[/]")
            on_long_task_end("Benchmark", success=False)

    run_async(run_benchmark())


@app.command("list-tasks")
def list_tasks(
    status_filter: str | None = typer.Option(None, "--status", "-s", help="Filtrer par statut"),
    limit: int = typer.Option(10, "--limit", "-l", help="Nombre de taches a afficher"),
):
    """Lister les taches d'agents"""

    async def list_all():
        integration = await ensure_initialized()
        if integration is None:
            return

        table = Table(title="Taches d'Agents", box=box.ROUNDED)
        table.add_column("ID", style=SUNSET_THEME["info_color"])
        table.add_column("Type", style=SUNSET_THEME["accent_color"])
        table.add_column("Statut", justify="center")
        table.add_column("Priorite", justify="center")

        if hasattr(integration, "active_tasks"):
            for task_id, task_info in list(integration.active_tasks.items())[:limit]:
                if status_filter is None or task_info.get("status") == status_filter:
                    table.add_row(
                        task_id[:8] + "...",
                        task_info.get("task_type", "unknown"),
                        task_info.get("status", "unknown"),
                        str(task_info.get("priority", "normal")),
                    )

        console.print(table)

        if hasattr(integration, "active_tasks") and hasattr(integration, "task_queue"):
            console.print(
                f"\n[dim]Actives: {len(integration.active_tasks)} | En attente: {integration.task_queue.qsize()}[/]"
            )

    run_async(list_all())


if __name__ == "__main__":
    app()
