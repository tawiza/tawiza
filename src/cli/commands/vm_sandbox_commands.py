"""Commandes CLI pour VM Sandbox Management.

Ce module fournit des commandes CLI pour gérer les machines virtuelles sandbox,
exécuter des tâches automatisées, et surveiller les performances.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.ui.rich_components import create_error_panel, create_info_panel, create_success_panel
from src.infrastructure.agents.openmanus.vm_sandbox_adapter import VMSandboxAdapter
from src.infrastructure.agents.openmanus.vm_sandbox_api import VMSandboxAPI

app = typer.Typer(
    name="vm-sandbox",
    help="Gestion des machines virtuelles sandbox pour OpenManus",
    rich_markup_mode="rich"
)

console = Console()


class VMSandboxCLI:
    """CLI pour VM Sandbox Management."""

    def __init__(self):
        """Initialise le CLI."""
        self.adapter = None
        self.api = None

    async def initialize(self, provider: str = "docker", max_vms: int = 5):
        """Initialise l'adaptateur VM.

        Args:
            provider: Fournisseur VM
            max_vms: Nombre maximum de VMs
        """
        self.adapter = VMSandboxAdapter(
            vm_provider=provider,
            max_vms=max_vms
        )

        if provider == "api":
            self.api = VMSandboxAPI(self.adapter)


@app.command("list")
def list_vms(
    provider: str = typer.Option("docker", "--provider", "-p", help="Fournisseur VM"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Sortie JSON")
):
    """Liste toutes les VMs sandbox actives."""

    async def _list_vms():
        cli = VMSandboxCLI()
        await cli.initialize(provider)

        try:
            # Obtenir la liste des VMs
            vms = []
            for vm_id in cli.adapter.active_vms:
                try:
                    status = await cli.adapter.get_vm_status(vm_id)
                    vms.append(status)
                except Exception as e:
                    logger.warning(f"Erreur obtention statut VM {vm_id}: {e}")

            if json_output:
                console.print(json.dumps(vms, indent=2, default=str))
            else:
                if not vms:
                    console.print(create_info_panel("Aucune VM active"))
                    return

                # Créer le tableau
                table = Table(title="VMs Sandbox Actives")
                table.add_column("VM ID", style="cyan", no_wrap=True)
                table.add_column("Tâche ID", style="magenta")
                table.add_column("Statut", style="green")
                table.add_column("Créé", style="yellow")
                table.add_column("Uptime", style="blue")
                table.add_column("Provider", style="white")

                for vm in vms:
                    uptime_seconds = vm.get("uptime", 0)
                    uptime_str = f"{uptime_seconds:.0f}s"

                    # Couleur selon le statut
                    status = vm.get("runtime_status", {}).get("status", "unknown")
                    status_style = "green" if status == "running" else "red"

                    table.add_row(
                        vm["vm_id"][:20] + "..." if len(vm["vm_id"]) > 20 else vm["vm_id"],
                        vm["task_id"][:15] + "..." if len(vm["task_id"]) > 15 else vm["task_id"],
                        f"[{status_style}]{status}[/{status_style}]",
                        datetime.fromisoformat(vm["created_at"]).strftime("%H:%M:%S"),
                        uptime_str,
                        vm["config"].get("provider", "unknown")
                    )

                console.print(table)
                console.print(f"\nTotal: {len(vms)} VMs actives")

        except Exception as e:
            console.print(create_error_panel(f"Erreur liste VMs: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_list_vms())


@app.command("create")
def create_vm(
    provider: str = typer.Option("docker", "--provider", "-p", help="Fournisseur VM"),
    memory: str = typer.Option("2g", "--memory", "-m", help="Mémoire VM"),
    cpus: int = typer.Option(2, "--cpus", "-c", help="Nombre de CPUs"),
    disk_size: str = typer.Option("20g", "--disk", "-d", help="Taille disque"),
    image: str = typer.Option("ubuntu:22.04", "--image", "-i", help="Image Docker"),
    timeout: int = typer.Option(3600, "--timeout", "-t", help="Timeout VM (secondes)"),
    wait: bool = typer.Option(True, "--wait", help="Attendre la création")
):
    """Crée une nouvelle VM sandbox."""

    async def _create_vm():
        cli = VMSandboxCLI()
        await cli.initialize(provider)

        try:
            # Configuration VM
            vm_config = {
                "provider": provider,
                "memory": memory,
                "cpus": cpus,
                "disk_size": disk_size,
                "image": image,
                "timeout": timeout
            }

            # Générer un ID de tâche
            task_id = f"create-{int(time.time())}"

            console.print(create_info_panel(f"Création VM avec provider {provider}..."))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:

                task = progress.add_task("Création VM...", total=None)

                # Créer la VM
                vm_id = await cli.adapter.create_vm(task_id, vm_config)

                progress.update(task, description=f"VM créée: {vm_id}")

                if wait:
                    # Attendre que la VM soit prête
                    progress.update(task, description="Attente VM prête...")
                    await asyncio.sleep(5)  # Simuler l'attente

                    # Vérifier le statut
                    status = await cli.adapter.get_vm_status(vm_id)

                    if status["runtime_status"].get("status") == "running":
                        progress.update(task, description="VM prête!")
                    else:
                        progress.update(task, description="VM créée mais statut inconnu")

            console.print(create_success_panel(
                f"VM créée avec succès!\n"
                f"ID: {vm_id}\n"
                f"Provider: {provider}\n"
                f"Config: {memory}, {cpus} CPUs, {disk_size}"
            ))

            return vm_id

        except Exception as e:
            console.print(create_error_panel(f"Erreur création VM: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_create_vm())


@app.command("destroy")
def destroy_vm(
    vm_id: str = typer.Argument(..., help="ID de la VM à détruire"),
    force: bool = typer.Option(False, "--force", "-f", help="Forcer la destruction")
):
    """Détruit une VM sandbox."""

    async def _destroy_vm():
        cli = VMSandboxCLI()
        await cli.initialize()

        try:
            if not force:
                # Confirmer la destruction
                confirm = typer.confirm(f"Êtes-vous sûr de vouloir détruire la VM {vm_id}?")
                if not confirm:
                    console.print("Destruction annulée")
                    return

            console.print(create_info_panel(f"Destruction VM {vm_id}..."))

            await cli.adapter.destroy_vm(vm_id)

            console.print(create_success_panel(f"VM {vm_id} détruite avec succès"))

        except Exception as e:
            console.print(create_error_panel(f"Erreur destruction VM: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_destroy_vm())


@app.command("execute")
def execute_task(
    vm_config_file: Path | None = typer.Option(None, "--config", "-c", help="Fichier config VM (JSON)"),
    task_file: Path | None = typer.Option(None, "--task", "-t", help="Fichier tâche (JSON)"),
    url: str = typer.Option(None, "--url", "-u", help="URL cible"),
    action: str = typer.Option("navigate", "--action", "-a", help="Action à effectuer"),
    provider: str = typer.Option("docker", "--provider", "-p", help="Fournisseur VM"),
    cleanup: bool = typer.Option(True, "--cleanup", help="Nettoyer VM après exécution"),
    wait: bool = typer.Option(True, "--wait", help="Attendre la fin de l'exécution"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Sortie JSON")
):
    """Exécute une tâche automation dans une VM sandbox."""

    async def _execute_task():
        cli = VMSandboxCLI()
        await cli.initialize(provider)

        try:
            # Charger la configuration VM
            if vm_config_file:
                with open(vm_config_file) as f:
                    vm_config = json.load(f)
            else:
                # Configuration par défaut
                vm_config = {
                    "provider": provider,
                    "memory": "2g",
                    "cpus": 2,
                    "disk_size": "20g",
                    "image": "ubuntu:22.04",
                    "timeout": 3600
                }

            # Charger la tâche
            if task_file:
                with open(task_file) as f:
                    automation_task = json.load(f)
            elif url:
                automation_task = {
                    "url": url,
                    "action": action
                }
            else:
                console.print(create_error_panel("URL ou fichier tâche requis"))
                raise typer.Exit(1)

            # Configuration complète
            task_config = {
                "vm_config": vm_config,
                "automation_task": automation_task,
                "cleanup_vm": cleanup
            }

            console.print(create_info_panel("Exécution tâche dans VM sandbox..."))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:

                task = progress.add_task("Exécution tâche...", total=None)

                # Exécuter la tâche
                result = await cli.adapter.execute_task(task_config)

                progress.update(task, description="Tâche complétée!")

            if json_output:
                console.print(json.dumps(result, indent=2, default=str))
            else:
                # Afficher les résultats
                if result["status"] == "completed":
                    console.print(create_success_panel(
                        f"Tâche exécutée avec succès!\n"
                        f"VM ID: {result.get('vm_id', 'N/A')}\n"
                        f"Durée: {result.get('execution_time', 'N/A')}\n"
                        f"Screenshots: {len(result.get('screenshots', []))}"
                    ))

                    # Afficher les détails si disponibles
                    if result.get("result"):
                        console.print("\n[bold]Résultat détaillé:[/bold]")
                        console.print_json(json.dumps(result["result"], indent=2))
                else:
                    console.print(create_error_panel(
                        f"Tâche échouée: {result.get('error', 'Erreur inconnue')}"
                    ))

        except Exception as e:
            console.print(create_error_panel(f"Erreur exécution tâche: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_execute_task())


@app.command("status")
def vm_status(
    vm_id: str = typer.Argument(..., help="ID de la VM"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Mode surveillance"),
    interval: int = typer.Option(5, "--interval", "-i", help="Intervalle de rafraîchissement (secondes)")
):
    """Affiche le statut d'une VM."""

    async def _vm_status():
        cli = VMSandboxCLI()
        await cli.initialize()

        try:
            if watch:
                # Mode surveillance
                console.print(f"[bold]Surveillance VM {vm_id} (Ctrl+C pour arrêter)[/bold]\n")

                try:
                    while True:
                        # Effacer l'écran
                        console.clear()

                        # Obtenir le statut
                        status = await cli.adapter.get_vm_status(vm_id)

                        # Afficher le statut
                        console.print(f"[bold blue]VM {vm_id} - {datetime.now().strftime('%H:%M:%S')}[/bold blue]")
                        console.print(f"Statut: [green]{status['runtime_status'].get('status', 'unknown')}[/green]")
                        console.print(f"Uptime: {status['uptime']:.1f}s")
                        console.print(f"Créé: {status['created_at']}")

                        # Détails runtime
                        runtime = status.get('runtime_status', {})
                        if runtime:
                            console.print("\n[bold]Détails runtime:[/bold]")
                            for key, value in runtime.items():
                                console.print(f"  {key}: {value}")

                        # Attendre l'intervalle
                        await asyncio.sleep(interval)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Surveillance arrêtée[/yellow]")

            else:
                # Statut unique
                status = await cli.adapter.get_vm_status(vm_id)

                # Créer un panneau informatif
                content = f"""
VM ID: {vm_id}
Tâche ID: {status['task_id']}
Statut: {status['runtime_status'].get('status', 'unknown')}
Créé: {status['created_at']}
Uptime: {status['uptime']:.1f}s
Provider: {status['config'].get('provider', 'unknown')}
                """.strip()

                console.print(create_info_panel(content, title=f"Statut VM {vm_id}"))

        except Exception as e:
            console.print(create_error_panel(f"Erreur obtention statut VM: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_vm_status())


@app.command("cleanup")
def cleanup_vms(
    force: bool = typer.Option(False, "--force", "-f", help="Forcer le nettoyage"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulation sans action")
):
    """Nettoie les VMs expirées."""

    async def _cleanup_vms():
        cli = VMSandboxCLI()
        await cli.initialize()

        try:
            # Identifier les VMs expirées
            current_time = datetime.now()
            expired_vms = []

            for vm_id, vm_info in cli.adapter.active_vms.items():
                created_at = vm_info["created_at"]
                uptime = (current_time - created_at).total_seconds()

                if uptime > cli.adapter.vm_timeout:
                    expired_vms.append((vm_id, uptime))

            if not expired_vms:
                console.print(create_info_panel("Aucune VM expirée à nettoyer"))
                return

            # Afficher les VMs à nettoyer
            console.print(f"[yellow]VMs expirées trouvées: {len(expired_vms)}[/yellow]")

            for vm_id, uptime in expired_vms:
                console.print(f"  - {vm_id} (uptime: {uptime:.0f}s)")

            if not force and not dry_run:
                confirm = typer.confirm("Nettoyer ces VMs?")
                if not confirm:
                    console.print("Nettoyage annulé")
                    return

            if dry_run:
                console.print("[blue]Mode simulation - aucune action effectuée[/blue]")
                return

            # Nettoyer les VMs
            console.print("Nettoyage VMs expirées...")

            for vm_id, _ in expired_vms:
                try:
                    await cli.adapter.destroy_vm(vm_id)
                    console.print(f"✅ VM {vm_id} nettoyée")
                except Exception as e:
                    console.print(f"❌ Erreur nettoyage VM {vm_id}: {e}")

            console.print(create_success_panel(f"Nettoyage terminé - {len(expired_vms)} VMs supprimées"))

        except Exception as e:
            console.print(create_error_panel(f"Erreur nettoyage VMs: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_cleanup_vms())


@app.command("benchmark")
def benchmark_vms(
    provider: str = typer.Option("docker", "--provider", "-p", help="Fournisseur VM"),
    iterations: int = typer.Option(3, "--iterations", "-n", help="Nombre d'itérations"),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Fichier configuration")
):
    """Benchmark des performances VM."""

    async def _benchmark():
        cli = VMSandboxCLI()
        await cli.initialize(provider)

        try:
            console.print(f"[bold]Benchmark VM Sandbox - Provider: {provider}[/bold]\n")

            # Configuration de test
            if config_file:
                with open(config_file) as f:
                    vm_config = json.load(f)
            else:
                vm_config = {
                    "provider": provider,
                    "memory": "1g",
                    "cpus": 1,
                    "disk_size": "10g",
                    "image": "ubuntu:22.04"
                }

            # Tâche de test simple
            test_task = {
                "url": "https://example.com",
                "action": "navigate"
            }

            results = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:

                for i in range(iterations):
                    task = progress.add_task(f"Itération {i+1}/{iterations}...", total=None)

                    start_time = time.time()

                    try:
                        # Créer et exécuter
                        task_config = {
                            "vm_config": vm_config,
                            "automation_task": test_task,
                            "cleanup_vm": True
                        }

                        result = await cli.adapter.execute_task(task_config)

                        end_time = time.time()
                        execution_time = end_time - start_time

                        results.append({
                            "iteration": i + 1,
                            "execution_time": execution_time,
                            "success": result["status"] == "completed",
                            "error": result.get("error")
                        })

                        progress.update(task, description=f"Itération {i+1} complétée")

                    except Exception as e:
                        end_time = time.time()
                        execution_time = end_time - start_time

                        results.append({
                            "iteration": i + 1,
                            "execution_time": execution_time,
                            "success": False,
                            "error": str(e)
                        })

                        progress.update(task, description=f"Itération {i+1} échouée")

            # Analyser les résultats
            successful_runs = [r for r in results if r["success"]]
            failed_runs = [r for r in results if not r["success"]]

            if successful_runs:
                avg_time = sum(r["execution_time"] for r in successful_runs) / len(successful_runs)
                min_time = min(r["execution_time"] for r in successful_runs)
                max_time = max(r["execution_time"] for r in successful_runs)

                console.print(create_success_panel(
                    f"Benchmark terminé!\n\n"
                    f"Réussite: {len(successful_runs)}/{iterations}\n"
                    f"Temps moyen: {avg_time:.2f}s\n"
                    f"Temps min: {min_time:.2f}s\n"
                    f"Temps max: {max_time:.2f}s"
                ))
            else:
                console.print(create_error_panel("Aucune exécution réussie"))

            # Détails des échecs
            if failed_runs:
                console.print("\n[bold red]Échecs:[/bold red]")
                for run in failed_runs:
                    console.print(f"  Itération {run['iteration']}: {run['error']}")

        except Exception as e:
            console.print(create_error_panel(f"Erreur benchmark: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_benchmark())


@app.command("monitor")
def monitor_vms(
    interval: int = typer.Option(10, "--interval", "-i", help="Intervalle de rafraîchissement (secondes)"),
    metrics: bool = typer.Option(False, "--metrics", "-m", help="Afficher les métriques détaillées")
):
    """Surveillance en temps réel des VMs."""

    async def _monitor():
        cli = VMSandboxCLI()
        await cli.initialize()

        try:
            console.print("[bold]Surveillance VMs Sandbox (Ctrl+C pour arrêter)[/bold]\n")

            try:
                while True:
                    # Effacer l'écran
                    console.clear()

                    # Obtenir les métriques
                    active_vms = len(cli.adapter.active_vms)
                    max_vms = cli.adapter.max_vms
                    provider = cli.adapter.vm_provider

                    # Heure actuelle
                    current_time = datetime.now().strftime("%H:%M:%S")

                    console.print(f"[bold blue]VM Sandbox Monitor - {current_time}[/bold blue]")
                    console.print(f"Provider: [cyan]{provider}[/cyan]")
                    console.print(f"VMs actives: [green]{active_vms}/{max_vms}[/green]")

                    if active_vms > 0:
                        console.print("\n[bold]VMs actives:[/bold]")

                        # Tableau des VMs
                        table = Table()
                        table.add_column("VM ID", style="cyan", max_width=20)
                        table.add_column("Tâche", style="magenta", max_width=15)
                        table.add_column("Statut", style="green")
                        table.add_column("Uptime", style="yellow")
                        table.add_column("Provider", style="white")

                        for vm_id, vm_info in cli.adapter.active_vms.items():
                            try:
                                status = await cli.adapter.get_vm_status(vm_id)

                                uptime = status["uptime"]
                                uptime_str = f"{uptime:.0f}s"

                                runtime_status = status["runtime_status"].get("status", "unknown")

                                table.add_row(
                                    vm_id[:17] + "..." if len(vm_id) > 20 else vm_id,
                                    vm_info["task_id"][:12] + "..." if len(vm_info["task_id"]) > 15 else vm_info["task_id"],
                                    runtime_status,
                                    uptime_str,
                                    status["config"].get("provider", "unknown")
                                )
                            except Exception as e:
                                logger.warning(f"Erreur statut VM {vm_id}: {e}")

                        console.print(table)

                    if metrics:
                        # Métriques détaillées
                        console.print("\n[bold]Métriques:[/bold]")

                        # Compter par statut
                        status_counts = {}
                        for vm_info in cli.adapter.active_vms.values():
                            status = vm_info.get("status", "unknown")
                            status_counts[status] = status_counts.get(status, 0) + 1

                        for status, count in status_counts.items():
                            console.print(f"  {status}: {count}")

                    # Barre de progression
                    usage_percent = (active_vms / max_vms) * 100
                    usage_bar = "█" * int(usage_percent / 5) + "░" * (20 - int(usage_percent / 5))
                    console.print(f"\nUtilisation: [{usage_bar}] {usage_percent:.1f}%")

                    # Attendre l'intervalle
                    await asyncio.sleep(interval)

            except KeyboardInterrupt:
                console.print("\n[yellow]Surveillance arrêtée[/yellow]")

        except Exception as e:
            console.print(create_error_panel(f"Erreur surveillance: {e}"))
            raise typer.Exit(1)

        finally:
            if cli.adapter:
                await cli.adapter.cleanup()

    asyncio.run(_monitor())


if __name__ == "__main__":
    app()
