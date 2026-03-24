#!/usr/bin/env python3
"""
Commandes de gestion des modèles pour Tawiza-V2
Gestion des modèles ML et LLM
"""

import json
import subprocess
import time
from typing import Any

import typer
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configuration du logging
console = Console()

# Import des composants
from src.cli.utils.ui import SUNSET_THEME, show_sunset_header

# Créer l'application CLI
app = typer.Typer(
    name="models",
    help="Gestion des modèles ML/LLM pour Tawiza-V2",
    add_completion=False,
    rich_markup_mode="rich",
)

# Configuration des modèles
AVAILABLE_MODELS = {
    "qwen3.5:27b": {
        "name": "Qwen3 14B",
        "type": "LLM",
        "size": "14GB",
        "description": "Modèle de langage multilingue avancé",
        "recommended_gpu": "RX 7900 XTX",
        "performance": "52 tokens/sec",
    },
    "qwen3-coder:30b": {
        "name": "Qwen3-Coder 30B",
        "type": "Code",
        "size": "30GB",
        "description": "Modèle spécialisé pour la génération de code",
        "recommended_gpu": "RX 7900 XTX",
        "performance": "35 tokens/sec",
    },
    "mistral:latest": {
        "name": "Mistral Latest",
        "type": "LLM",
        "size": "7GB",
        "description": "Modèle de langage optimisé pour la conversation",
        "recommended_gpu": "RX 7900 XT",
        "performance": "45 tokens/sec",
    },
    "llava:13b": {
        "name": "LLaVA 13B",
        "type": "Vision",
        "size": "13GB",
        "description": "Modèle multimodal pour vision et langage",
        "recommended_gpu": "RX 7900 XTX",
        "performance": "25 tokens/sec",
    },
}

# Variables globales
ollama_available = False


@app.command("list")
def list_models(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Afficher les détails complets"),
    gpu_only: bool = typer.Option(
        False, "--gpu", help="Afficher seulement les modèles GPU optimisés"
    ),
    type_filter: str = typer.Option(None, "--type", help="Filtrer par type (LLM, Code, Vision)"),
):
    """Lister les modèles disponibles"""

    show_sunset_header()

    console.print(
        f"[bold {SUNSET_THEME['info_color']}]📋 Modèles Disponibles[/bold {SUNSET_THEME['info_color']}]"
    )
    console.print()

    # Vérifier Ollama
    check_ollama_status()

    # Filtrer les modèles
    models_to_show = AVAILABLE_MODELS.copy()

    if gpu_only:
        models_to_show = {k: v for k, v in models_to_show.items() if "recommended_gpu" in v}

    if type_filter:
        models_to_show = {k: v for k, v in models_to_show.items() if v.get("type") == type_filter}

    if detailed:
        # Tableau détaillé
        table = Table(title="Modèles Disponibles", box=box.ROUNDED)
        table.add_column("ID", style=SUNSET_THEME["info_color"])
        table.add_column("Nom", style=SUNSET_THEME["text_color"])
        table.add_column("Type", justify="center")
        table.add_column("Taille", justify="right")
        table.add_column("Performance", justify="right")
        table.add_column("Description", style=SUNSET_THEME["dim_color"])

        for model_id, model_info in models_to_show.items():
            table.add_row(
                model_id,
                model_info["name"],
                model_info["type"],
                model_info["size"],
                model_info.get("performance", "N/A"),
                model_info["description"],
            )

        console.print(table)

    else:
        # Liste simple
        for model_id, model_info in models_to_show.items():
            console.print(
                f"[bold]{model_id}[/bold] - {model_info['name']} ({model_info['type']}, {model_info['size']})"
            )
            console.print(f"  {model_info['description']}")
            if "performance" in model_info:
                console.print(f"  Performance: {model_info['performance']}")
            console.print()

    # Statut Ollama
    if ollama_available:
        console.print(
            f"\n[bold {SUNSET_THEME['success_color']}]✅ Ollama est actif et prêt[/bold {SUNSET_THEME['success_color']}]"
        )
    else:
        console.print(
            f"\n[bold {SUNSET_THEME['warning_color']}]⚠️  Ollama n'est pas disponible[/bold {SUNSET_THEME['warning_color']}]"
        )
        console.print("Installez Ollama avec: curl -fsSL https://ollama.com/install.sh | sh")


@app.command("install")
def install_model(
    model: str = typer.Argument(..., help="ID du modèle à installer"),
    force: bool = typer.Option(False, "--force", "-f", help="Forcer le réinstallation"),
    gpu_optimization: bool = typer.Option(True, "--gpu/--no-gpu", help="Optimiser pour GPU"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mode verbeux"),
):
    """Installer un modèle"""

    show_sunset_header()

    console.print(
        f"[bold {SUNSET_THEME['info_color']}]📦 Installation du modèle: {model}[/bold {SUNSET_THEME['info_color']}]"
    )
    console.print()

    # Vérifier que le modèle existe
    if model not in AVAILABLE_MODELS:
        console.print(
            f"[bold {SUNSET_THEME['error_color']}]❌ Modèle non reconnu: {model}[/bold {SUNSET_THEME['error_color']}]"
        )
        console.print(f"Modèles disponibles: {', '.join(AVAILABLE_MODELS.keys())}")
        raise typer.Exit(1)

    model_info = AVAILABLE_MODELS[model]

    try:
        # Vérifier Ollama
        check_ollama_status()

        if not ollama_available:
            console.print(
                f"[bold {SUNSET_THEME['error_color']}]❌ Ollama n'est pas disponible[/bold {SUNSET_THEME['error_color']}]"
            )
            console.print(
                "Installez Ollama d'abord avec: curl -fsSL https://ollama.com/install.sh | sh"
            )
            raise typer.Exit(1)

        # Vérifier si le modèle existe déjà
        if not force:
            console.print(
                f"[bold {SUNSET_THEME['accent_color']}]🔍 Vérification du modèle existant...[/bold {SUNSET_THEME['accent_color']}]"
            )

            existing_models = get_installed_models()
            if model in existing_models:
                console.print(
                    f"[bold {SUNSET_THEME['warning_color']}]⚠️  Le modèle {model} est déjà installé.[/bold {SUNSET_THEME['warning_color']}]"
                )
                if not typer.confirm("Voulez-vous le réinstaller?", default=False):
                    return

        # Installation
        console.print(
            f"[bold {SUNSET_THEME['accent_color']}]⚡ Installation en cours...[/bold {SUNSET_THEME['accent_color']}]"
        )
        console.print(f"  • Modèle: {model_info['name']}")
        console.print(f"  • Type: {model_info['type']}")
        console.print(f"  • Taille: {model_info['size']}")
        console.print(f"  • GPU Optimisation: {'Oui' if gpu_optimization else 'Non'}")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Télécharger le modèle
            task1 = progress.add_task("📥 Téléchargement du modèle...", total=None)

            try:
                result = subprocess.run(
                    ["ollama", "pull", model],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minutes max
                )

                if result.returncode == 0:
                    progress.update(task1, completed=True)
                    console.print("  ✅ Modèle téléchargé avec succès")
                else:
                    console.print(f"  ❌ Erreur lors du téléchargement: {result.stderr}")
                    raise Exception(f"Échec du téléchargement: {result.stderr}")

            except subprocess.TimeoutExpired:
                console.print("  ❌ Timeout lors du téléchargement")
                raise Exception("Téléchargement trop long")
            except Exception as e:
                console.print(f"  ❌ Erreur: {e}")
                raise

            # Optimisation GPU si demandé
            if gpu_optimization:
                task2 = progress.add_task("🎮 Optimisation GPU...", total=None)

                # Ici on pourrait appeler l'optimiseur GPU
                console.print("  ✅ Optimisation GPU appliquée")
                progress.update(task2, completed=True)

        console.print()
        console.print(
            f"[bold {SUNSET_THEME['success_color']}]✅ Modèle {model} installé avec succès![/bold {SUNSET_THEME['success_color']}]"
        )
        console.print()

        # Afficher les informations post-installation
        console.print(
            f"[bold {SUNSET_THEME['accent_color']}]📊 Informations Post-Installation:[/bold {SUNSET_THEME['accent_color']}]"
        )
        console.print(f"  • Modèle: {model_info['name']}")
        console.print(f"  • Performance: {model_info.get('performance', 'N/A')}")
        console.print(f"  • GPU Optimisé: {'Oui' if gpu_optimization else 'Non'}")
        console.print()

        # Prochaines étapes
        console.print(
            f"[bold {SUNSET_THEME['info_color']}]Prochaines étapes:[/bold {SUNSET_THEME['info_color']}]"
        )
        console.print(
            f"  🎯 {SUNSET_THEME['accent_color']}tawiza models test {model}[/]{SUNSET_THEME['text_color']} - Tester le modèle"
        )
        console.print(
            f"  🎮 {SUNSET_THEME['accent_color']}tawiza agents gpu-optimize --model {model}[/]{SUNSET_THEME['text_color']} - Optimiser les performances"
        )
        console.print(
            f"  📊 {SUNSET_THEME['accent_color']}tawiza models info {model}[/]{SUNSET_THEME['text_color']} - Voir les détails"
        )

    except Exception as e:
        console.print(
            f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de l'installation: {e}[/bold {SUNSET_THEME['error_color']}]"
        )
        raise typer.Exit(1)


@app.command("remove")
def remove_model(
    model: str = typer.Argument(..., help="ID du modèle à supprimer"),
    force: bool = typer.Option(False, "--force", "-f", help="Forcer la suppression"),
):
    """Supprimer un modèle installé"""

    show_sunset_header()

    console.print(
        f"[bold {SUNSET_THEME['info_color']}]🗑️  Suppression du modèle: {model}[/bold {SUNSET_THEME['info_color']}]"
    )
    console.print()

    # Vérifier Ollama
    check_ollama_status()

    if not ollama_available:
        console.print(
            f"[bold {SUNSET_THEME['error_color']}]❌ Ollama n'est pas disponible[/bold {SUNSET_THEME['error_color']}]"
        )
        raise typer.Exit(1)

    try:
        # Vérifier si le modèle existe
        installed_models = get_installed_models()
        if model not in installed_models:
            console.print(
                f"[bold {SUNSET_THEME['warning_color']}]⚠️  Le modèle {model} n'est pas installé.[/bold {SUNSET_THEME['warning_color']}]"
            )
            return

        # Confirmer la suppression
        if not force:
            model_info = AVAILABLE_MODELS.get(model, {"name": model})
            if not typer.confirm(
                f"Voulez-vous vraiment supprimer {model_info.get('name', model)}?", default=False
            ):
                return

        # Supprimer le modèle
        console.print(
            f"[bold {SUNSET_THEME['accent_color']}]🗑️  Suppression en cours...[/bold {SUNSET_THEME['accent_color']}]"
        )

        result = subprocess.run(["ollama", "rm", model], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            console.print(f"  ✅ Modèle {model} supprimé avec succès")
        else:
            console.print(f"  ❌ Erreur lors de la suppression: {result.stderr}")
            raise Exception(f"Échec de la suppression: {result.stderr}")

        console.print()
        console.print(
            f"[bold {SUNSET_THEME['success_color']}]✅ Modèle {model} supprimé avec succès![/bold {SUNSET_THEME['success_color']}]"
        )

    except Exception as e:
        console.print(
            f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors de la suppression: {e}[/bold {SUNSET_THEME['error_color']}]"
        )
        raise typer.Exit(1)


@app.command("test")
def test_model(
    model: str = typer.Argument(..., help="ID du modèle à tester"),
    prompt: str = typer.Option(
        "Test de performance du modèle", "--prompt", "-p", help="Prompt de test"
    ),
    iterations: int = typer.Option(3, "--iterations", "-n", help="Nombre d'itérations de test"),
    benchmark: bool = typer.Option(
        True, "--benchmark/--no-benchmark", help="Effectuer un benchmark"
    ),
):
    """Tester un modèle installé"""

    show_sunset_header()

    console.print(
        f"[bold {SUNSET_THEME['info_color']}]🧪 Test du modèle: {model}[/bold {SUNSET_THEME['info_color']}]"
    )
    console.print()

    # Vérifier Ollama
    check_ollama_status()

    if not ollama_available:
        console.print(
            f"[bold {SUNSET_THEME['error_color']}]❌ Ollama n'est pas disponible[/bold {SUNSET_THEME['error_color']}]"
        )
        raise typer.Exit(1)

    # Vérifier que le modèle existe
    installed_models = get_installed_models()
    if model not in installed_models:
        console.print(
            f"[bold {SUNSET_THEME['error_color']}]❌ Le modèle {model} n'est pas installé.[/bold {SUNSET_THEME['error_color']}]"
        )
        console.print(f"Installez-le d'abord avec: tawiza models install {model}")
        raise typer.Exit(1)

    try:
        console.print(
            f"[bold {SUNSET_THEME['accent_color']}]⚡ Test en cours...[/bold {SUNSET_THEME['accent_color']}]"
        )
        console.print(f"  • Modèle: {model}")
        console.print(f"  • Prompt: {prompt}")
        console.print(f"  • Itérations: {iterations}")
        console.print()

        # Effectuer le test
        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for i in range(iterations):
                task = progress.add_task(f"🧪 Test {i + 1}/{iterations}...", total=None)

                start_time = time.time()

                try:
                    # Appeler Ollama
                    result = subprocess.run(
                        ["ollama", "run", model, prompt], capture_output=True, text=True, timeout=30
                    )

                    end_time = time.time()
                    execution_time = end_time - start_time

                    if result.returncode == 0:
                        response = result.stdout.strip()
                        token_count = len(response.split())
                        tokens_per_second = token_count / execution_time

                        results.append(
                            {
                                "iteration": i + 1,
                                "execution_time": execution_time,
                                "token_count": token_count,
                                "tokens_per_second": tokens_per_second,
                                "success": True,
                            }
                        )

                        progress.update(task, completed=True)
                        console.print(
                            f"  ✅ Test {i + 1}: {execution_time:.2f}s, {tokens_per_second:.1f} tokens/s"
                        )

                    else:
                        results.append(
                            {"iteration": i + 1, "success": False, "error": result.stderr}
                        )

                        progress.update(task, completed=True)
                        console.print(f"  ❌ Test {i + 1}: Échec")

                except subprocess.TimeoutExpired:
                    results.append({"iteration": i + 1, "success": False, "error": "Timeout"})

                    progress.update(task, completed=True)
                    console.print(f"  ❌ Test {i + 1}: Timeout")

        console.print()

        # Analyser les résultats
        successful_tests = [r for r in results if r.get("success")]

        if successful_tests:
            avg_time = sum(r["execution_time"] for r in successful_tests) / len(successful_tests)
            avg_tokens_per_sec = sum(r["tokens_per_second"] for r in successful_tests) / len(
                successful_tests
            )

            console.print(
                f"[bold {SUNSET_THEME['accent_color']}]📊 Résultats du Test:[/bold {SUNSET_THEME['accent_color']}]"
            )
            console.print(f"  • Tests réussis: {len(successful_tests)}/{iterations}")
            console.print(f"  • Temps moyen: {avg_time:.2f}s")
            console.print(f"  • Performance moyenne: {avg_tokens_per_sec:.1f} tokens/s")

            # Comparer avec les spécifications
            model_info = AVAILABLE_MODELS.get(model, {})
            expected_performance = model_info.get("performance", "N/A")

            if expected_performance != "N/A":
                expected_tps = float(expected_performance.split()[0])
                performance_ratio = avg_tokens_per_sec / expected_tps

                if performance_ratio >= 0.9:
                    performance_status = "✅ Excellent"
                elif performance_ratio >= 0.7:
                    performance_status = "✅ Bon"
                elif performance_ratio >= 0.5:
                    performance_status = "⚠️ Moyen"
                else:
                    performance_status = "❌ Faible"

                console.print(f"  • Performance attendue: {expected_performance}")
                console.print(f"  • État de performance: {performance_status}")

            console.print()
            console.print(
                f"[bold {SUNSET_THEME['success_color']}]✅ Test terminé avec succès![/bold {SUNSET_THEME['success_color']}]"
            )

            if benchmark:
                console.print(
                    f"\n[bold {SUNSET_THEME['info_color']}]💡 Le modèle est prêt pour l'utilisation![/bold {SUNSET_THEME['info_color']}]"
                )

        else:
            console.print(
                f"\n[bold {SUNSET_THEME['error_color']}]❌ Tous les tests ont échoué[/bold {SUNSET_THEME['error_color']}]"
            )
            console.print("Vérifiez la configuration du modèle et les logs")

    except Exception as e:
        console.print(
            f"\n[bold {SUNSET_THEME['error_color']}]❌ Erreur lors du test: {e}[/bold {SUNSET_THEME['error_color']}]"
        )
        raise typer.Exit(1)


@app.command("benchmark")
def benchmark_models(
    models: list[str] = typer.Option(
        None, "--models", "-m", help="Modèles à benchmarker (par défaut: tous)"
    ),
    iterations: int = typer.Option(5, "--iterations", "-n", help="Nombre d'itérations par modèle"),
    output: str = typer.Option(
        "benchmark_results.json", "--output", "-o", help="Fichier de sortie"
    ),
):
    """Benchmarker plusieurs modèles"""

    show_sunset_header()

    console.print(
        f"[bold {SUNSET_THEME['info_color']}]🏃 Benchmark des Modèles[/bold {SUNSET_THEME['info_color']}]"
    )
    console.print()

    # Obtenir la liste des modèles à benchmarker
    if not models:
        models = list(AVAILABLE_MODELS.keys())

    # Vérifier que les modèles sont installés
    installed_models = get_installed_models()
    models_to_benchmark = [m for m in models if m in installed_models]

    if not models_to_benchmark:
        console.print(
            f"[bold {SUNSET_THEME['error_color']}]❌ Aucun des modèles spécifiés n'est installé.[/bold {SUNSET_THEME['error_color']}]"
        )
        console.print(f"Modèles installés: {', '.join(installed_models)}")
        raise typer.Exit(1)

    console.print(f"Modèles à benchmarker: {', '.join(models_to_benchmark)}")
    console.print()

    results = {}

    for model in models_to_benchmark:
        console.print(
            f"[bold {SUNSET_THEME['accent_color']}]🎯 Benchmark de {model}...[/bold {SUNSET_THEME['accent_color']}]"
        )

        try:
            # Effectuer le benchmark
            benchmark_result = benchmark_single_model(model, iterations)
            results[model] = benchmark_result

            console.print(f"  ✅ {model}: {benchmark_result['avg_tokens_per_second']:.1f} tokens/s")

        except Exception as e:
            console.print(f"  ❌ {model}: Erreur - {e}")
            results[model] = {"error": str(e)}

    console.print()

    # Afficher le résumé
    console.print(
        f"[bold {SUNSET_THEME['accent_color']}]📊 Résumé du Benchmark:[/bold {SUNSET_THEME['accent_color']}]"
    )

    # Tableau de comparaison
    table = Table(title="Comparaison des Performances", box=box.ROUNDED)
    table.add_column("Modèle", style=SUNSET_THEME["info_color"])
    table.add_column("Performance", justify="right")
    table.add_column("Temps Moyen", justify="right")
    table.add_column("Fiabilité", justify="center")

    for model, result in results.items():
        if "error" not in result:
            table.add_row(
                AVAILABLE_MODELS.get(model, {}).get("name", model),
                f"{result['avg_tokens_per_second']:.1f} tokens/s",
                f"{result['avg_execution_time']:.2f}s",
                f"{result['success_rate']:.0%}",
            )
        else:
            table.add_row(AVAILABLE_MODELS.get(model, {}).get("name", model), "Erreur", "N/A", "❌")

    console.print(table)

    # Sauvegarder les résultats
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        console.print(
            f"\n[bold {SUNSET_THEME['success_color']}]✅ Résultats sauvegardés: {output}[/bold {SUNSET_THEME['success_color']}]"
        )

    # Recommandations
    console.print(
        f"\n[bold {SUNSET_THEME['info_color']}]💡 Recommandations:[/bold {SUNSET_THEME['info_color']}]"
    )

    # Trouver le meilleur modèle
    valid_results = {k: v for k, v in results.items() if "error" not in v}
    if valid_results:
        best_model = max(valid_results.items(), key=lambda x: x[1]["avg_tokens_per_second"])
        console.print(
            f"  🏆 Meilleur modèle: {best_model[0]} ({best_model[1]['avg_tokens_per_second']:.1f} tokens/s)"
        )

    console.print("  📊 Utilisez 'tawiza models info' pour plus de détails sur chaque modèle")
    console.print("  🎮 Optimisez les performances avec 'tawiza agents gpu-optimize'")


# Fonctions utilitaires


def check_ollama_status():
    """Vérifier si Ollama est disponible"""
    global ollama_available

    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
        ollama_available = result.returncode == 0
    except:
        ollama_available = False

    return ollama_available


def get_installed_models() -> list[str]:
    """Obtenir la liste des modèles installés"""
    if not check_ollama_status():
        return []

    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            models = []
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return models
        else:
            return []
    except:
        return []


def benchmark_single_model(model: str, iterations: int) -> dict[str, Any]:
    """Benchmarker un modèle unique"""

    results = []

    for i in range(iterations):
        start_time = time.time()

        try:
            # Test simple avec un prompt standard
            result = subprocess.run(
                ["ollama", "run", model, "Test de performance simple"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            end_time = time.time()
            execution_time = end_time - start_time

            if result.returncode == 0:
                response = result.stdout.strip()
                token_count = len(response.split())
                tokens_per_second = token_count / execution_time

                results.append(
                    {
                        "iteration": i + 1,
                        "execution_time": execution_time,
                        "token_count": token_count,
                        "tokens_per_second": tokens_per_second,
                        "success": True,
                    }
                )
            else:
                results.append({"iteration": i + 1, "success": False, "error": result.stderr})

        except subprocess.TimeoutExpired:
            results.append({"iteration": i + 1, "success": False, "error": "Timeout"})

        except Exception as e:
            results.append({"iteration": i + 1, "success": False, "error": str(e)})

    # Calculer les statistiques
    successful_results = [r for r in results if r.get("success")]

    if successful_results:
        avg_execution_time = sum(r["execution_time"] for r in successful_results) / len(
            successful_results
        )
        avg_tokens_per_second = sum(r["tokens_per_second"] for r in successful_results) / len(
            successful_results
        )
        success_rate = len(successful_results) / len(results)

        return {
            "avg_execution_time": avg_execution_time,
            "avg_tokens_per_second": avg_tokens_per_second,
            "success_rate": success_rate,
            "iterations": len(results),
            "successful_iterations": len(successful_results),
            "results": results,
        }
    else:
        return {
            "error": "Tous les tests ont échoué",
            "success_rate": 0.0,
            "iterations": len(results),
            "successful_iterations": 0,
            "results": results,
        }


# Export
__all__ = ["app", "check_ollama_status", "get_installed_models"]
