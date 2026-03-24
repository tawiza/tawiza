#!/usr/bin/env python3
"""
Commandes CLI EcoCartographe - Cartographie d'écosystèmes territoriaux

Permet de cartographier les acteurs d'innovation (entreprises, labs, clusters)
et leurs relations sur un territoire donné.

Usage:
    tawiza cartographie nouveau "Mon Projet" --territoire "Nouvelle-Aquitaine"
    tawiza cartographie ingerer <projet_id> --csv data/acteurs.csv
    tawiza cartographie analyser <projet_id>
    tawiza cartographie visualiser <projet_id>
    tawiza cartographie pipeline --csv data/acteurs.csv --nom "Ecosystème AgriTech"
"""

import contextlib
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from src.cli.ui.theme import SUNSET_THEME, theme_to_dict
from src.cli.utils.async_runner import run_async

console = Console()
THEME = theme_to_dict(SUNSET_THEME)

app = typer.Typer(
    name="cartographie",
    help="🗺️  Cartographie d'écosystèmes territoriaux d'innovation",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Instance globale de l'adapter
_adapter = None


def get_adapter():
    """Obtient l'instance de l'adapter EcoCartographe"""
    global _adapter
    if _adapter is None:
        from src.infrastructure.agents.ecocartographe import EcoCartographeAdapter

        _adapter = EcoCartographeAdapter()
    return _adapter


def show_header():
    """Affiche l'en-tête EcoCartographe"""
    header = """
╔═══════════════════════════════════════════════════════════════════╗
║   🗺️  EcoCartographe - Cartographie d'Écosystèmes Territoriaux   ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    console.print(f"[bold {THEME['header_color']}]{header}[/]")


@app.command("nouveau")
def nouveau_projet(
    nom: str = typer.Argument(..., help="Nom du projet de cartographie"),
    description: str | None = typer.Option(None, "--desc", "-d", help="Description du projet"),
    territoire: str | None = typer.Option(
        None, "--territoire", "-t", help="Territoire ciblé (ex: Nouvelle-Aquitaine)"
    ),
    thematique: str | None = typer.Option(
        None, "--thematique", help="Thématique (ex: AgriTech, HealthTech)"
    ),
    modele_spacy: str = typer.Option("fr_core_news_lg", "--spacy", help="Modèle spaCy à utiliser"),
    seuil_proximite: float = typer.Option(
        50.0, "--proximite", help="Seuil de proximité géographique en km"
    ),
    seuil_similarite: float = typer.Option(
        0.7, "--similarite", help="Seuil de similarité thématique (0-1)"
    ),
):
    """
    🆕 Crée un nouveau projet de cartographie

    Exemples:
        tawiza cartographie nouveau "Ecosystème AgriTech Bordeaux" --territoire "Gironde" --thematique "AgriTech"
        tawiza cartographie nouveau "Innovation Santé" -t "Ile-de-France" --thematique "HealthTech"
    """
    show_header()

    async def _creer():
        adapter = get_adapter()
        result = await adapter.execute_task(
            {
                "action": "creer_projet",
                "nom": nom,
                "description": description,
                "territoire": territoire,
                "thematique": thematique,
                "modele_spacy": modele_spacy,
                "seuil_proximite_km": seuil_proximite,
                "seuil_similarite": seuil_similarite,
            }
        )
        return result

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        task = progress.add_task("Création du projet...", total=None)
        result = run_async(_creer())
        progress.update(task, completed=True)

    # Afficher le résultat
    console.print()
    panel = Panel(
        f"""[bold green]✅ Projet créé avec succès![/]

[bold]ID:[/] {result["projet_id"]}
[bold]Nom:[/] {result["nom"]}
[bold]Statut:[/] {result["statut"]}

[dim]Prochaine étape: Ajoutez des sources de données avec:[/]
[bold cyan]tawiza cartographie ingerer {result["projet_id"]} --csv votre_fichier.csv[/]
        """,
        title="🗺️ Nouveau Projet",
        border_style=THEME["success_color"],
    )
    console.print(panel)


@app.command("ingerer")
def ingerer_sources(
    projet_id: str = typer.Argument(..., help="ID du projet"),
    csv: list[str] | None = typer.Option(None, "--csv", help="Fichier(s) CSV à ingérer"),
    excel: list[str] | None = typer.Option(None, "--excel", help="Fichier(s) Excel à ingérer"),
    json_file: list[str] | None = typer.Option(None, "--json", help="Fichier(s) JSON à ingérer"),
    texte: list[str] | None = typer.Option(None, "--texte", help="Fichier(s) texte à analyser"),
):
    """
    📥 Ingère des sources de données dans un projet

    Exemples:
        tawiza cartographie ingerer abc123 --csv data/entreprises.csv
        tawiza cartographie ingerer abc123 --csv acteurs1.csv --csv acteurs2.csv --json partenaires.json
    """
    show_header()

    # Construire la liste des sources
    sources = []
    for f in csv or []:
        sources.append({"type": "csv", "chemin": f})
    for f in excel or []:
        sources.append({"type": "excel", "chemin": f})
    for f in json_file or []:
        sources.append({"type": "json", "chemin": f})
    for f in texte or []:
        sources.append({"type": "texte", "chemin": f})

    if not sources:
        console.print(f"[bold {THEME['error_color']}]❌ Aucune source spécifiée![/]")
        console.print("Utilisez --csv, --excel, --json ou --texte pour ajouter des sources")
        raise typer.Exit(1)

    # Vérifier que les fichiers existent
    for src in sources:
        if not Path(src["chemin"]).exists():
            console.print(f"[bold {THEME['error_color']}]❌ Fichier non trouvé: {src['chemin']}[/]")
            raise typer.Exit(1)

    async def _ingerer():
        adapter = get_adapter()
        return await adapter.execute_task(
            {"action": "ingerer", "projet_id": projet_id, "sources": sources}
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Ingestion de {len(sources)} source(s)...", total=len(sources))
        result = run_async(_ingerer())
        progress.update(task, completed=len(sources))

    # Afficher le résultat
    table = Table(title="📥 Sources Ingérées", box=box.ROUNDED)
    table.add_column("Type", style="cyan")
    table.add_column("Fichier", style="white")
    table.add_column("Statut", style="green")

    for src in result.get("sources", []):
        table.add_row(src["type"], src["chemin"], "✅")

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[bold {THEME['info_color']}]💡 Prochaine étape:[/] tawiza cartographie extraire {projet_id}"
    )


@app.command("extraire")
def extraire_entites(projet_id: str = typer.Argument(..., help="ID du projet")):
    """
    🔍 Extrait les entités (acteurs) des sources avec spaCy

    Cette commande utilise le NLP pour identifier automatiquement:
    - Les organisations (entreprises, labs, clusters...)
    - Les lieux (villes, régions...)
    - Les personnes clés
    """
    show_header()

    async def _extraire():
        adapter = get_adapter()
        return await adapter.execute_task({"action": "extraire", "projet_id": projet_id})

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        progress.add_task("Extraction des entités avec spaCy...", total=None)
        result = run_async(_extraire())

    # Afficher les résultats
    console.print()
    console.print(
        Panel(
            f"[bold green]✅ Extraction terminée![/]\n\n"
            f"[bold]Acteurs trouvés:[/] {result['nb_acteurs']}",
            title="🔍 Résultat de l'Extraction",
            border_style=THEME["success_color"],
        )
    )

    # Table par type
    if result.get("acteurs_par_type"):
        table = Table(title="📊 Distribution par Type", box=box.ROUNDED)
        table.add_column("Type d'Acteur", style="cyan")
        table.add_column("Nombre", style="white", justify="right")
        table.add_column("Proportion", style="dim")

        total = sum(result["acteurs_par_type"].values())
        for type_acteur, count in sorted(
            result["acteurs_par_type"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = count * 100 / total if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            table.add_row(type_acteur, str(count), f"{bar} {pct:.1f}%")

        console.print(table)

    console.print()
    console.print(
        f"[bold {THEME['info_color']}]💡 Prochaine étape:[/] tawiza cartographie analyser {projet_id}"
    )


@app.command("analyser")
def analyser_reseau(projet_id: str = typer.Argument(..., help="ID du projet")):
    """
    🔬 Analyse le réseau et détecte les communautés avec NetworkX

    Cette commande:
    - Détecte les relations entre acteurs
    - Calcule les métriques de centralité
    - Identifie les communautés (Louvain)
    - Trouve les acteurs les plus influents
    """
    show_header()

    async def _analyser():
        adapter = get_adapter()
        return await adapter.execute_task({"action": "analyser", "projet_id": projet_id})

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        progress.add_task("Analyse du réseau avec NetworkX...", total=None)
        result = run_async(_analyser())

    analyse = result.get("analyse", {})

    # Panneau principal
    console.print()
    console.print(
        Panel(
            f"""[bold green]✅ Analyse terminée![/]

[bold]Relations détectées:[/] {result.get("nb_relations", 0)}
[bold]Densité du réseau:[/] {analyse.get("densite", 0):.3f}
[bold]Communautés:[/] {analyse.get("nb_communautes", 0)}
[bold]Modularité:[/] {analyse.get("modularite", 0):.3f}

[dim]Fichier GEXF exporté pour Gephi:[/]
{result.get("fichier_gexf", "N/A")}
        """,
            title="🔬 Analyse du Réseau",
            border_style=THEME["success_color"],
        )
    )

    # Top acteurs centraux
    if analyse.get("acteurs_centraux"):
        console.print()
        console.print(f"[bold {THEME['accent_color']}]🏆 Acteurs les Plus Centraux[/]")
        for i, acteur_id in enumerate(analyse["acteurs_centraux"][:5], 1):
            console.print(f"  {i}. {acteur_id[:20]}...")

    console.print()
    console.print(
        f"[bold {THEME['info_color']}]💡 Prochaine étape:[/] tawiza cartographie visualiser {projet_id}"
    )


@app.command("visualiser")
def generer_visualisations(
    projet_id: str = typer.Argument(..., help="ID du projet"),
    ouvrir: bool = typer.Option(True, "--ouvrir/--no-ouvrir", help="Ouvrir les fichiers générés"),
):
    """
    🎨 Génère les visualisations (carte et graphe interactif)

    Crée:
    - Une carte géographique interactive (Folium)
    - Un graphe de réseau interactif (PyVis)
    - Un rapport Markdown détaillé
    """
    show_header()

    async def _visualiser():
        adapter = get_adapter()
        return await adapter.execute_task({"action": "visualiser", "projet_id": projet_id})

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        progress.add_task("Génération des visualisations...", total=None)
        result = run_async(_visualiser())

    fichiers = result.get("fichiers", {})
    resume = result.get("resume", {})

    # Résultat
    console.print()
    tree = Tree(f"[bold {THEME['success_color']}]🎨 Visualisations Générées[/]")

    if fichiers.get("carte"):
        tree.add(f"[cyan]🗺️  Carte:[/] {fichiers['carte']}")
    if fichiers.get("graphe"):
        tree.add(f"[cyan]🕸️  Graphe:[/] {fichiers['graphe']}")
    if fichiers.get("rapport"):
        tree.add(f"[cyan]📄 Rapport:[/] {fichiers['rapport']}")

    console.print(tree)

    # Résumé
    console.print()
    console.print(
        Panel(
            f"""[bold]Résumé de la Cartographie[/]

• Acteurs cartographiés: {resume.get("nb_acteurs", 0)}
• Relations identifiées: {resume.get("nb_relations", 0)}
• Communautés détectées: {resume.get("nb_communautes", 0)}
        """,
            title="📊 Statistiques",
            border_style=THEME["info_color"],
        )
    )

    # Ouvrir les fichiers
    if ouvrir and fichiers.get("carte"):
        import webbrowser

        try:
            webbrowser.open(f"file://{Path(fichiers['carte']).absolute()}")
            console.print("\n[dim]Carte ouverte dans le navigateur[/]")
        except Exception:
            pass


@app.command("collecter")
def collecter_donnees(
    territoire: str = typer.Argument(
        ..., help="Territoire à cartographier (ex: Nouvelle-Aquitaine, Bordeaux)"
    ),
    thematique: str | None = typer.Option(
        None, "--thematique", "-t", help="Secteur/thématique (ex: AgriTech, HealthTech)"
    ),
    limite: int = typer.Option(100, "--limite", "-l", help="Nombre maximum d'acteurs à collecter"),
    nom: str | None = typer.Option(None, "--nom", "-n", help="Nom du projet"),
    output: str | None = typer.Option(None, "--output", "-o", help="Répertoire de sortie"),
):
    """
    🔎 Collecte automatique de données sur les acteurs d'innovation

    Recherche automatiquement sur:
    - API Annuaire des Entreprises (data.gouv.fr)
    - Sources web publiques
    - Analyse intelligente via Ollama (si disponible)

    Exemples:
        tawiza cartographie collecter "Nouvelle-Aquitaine" --thematique "AgriTech"
        tawiza cartographie collecter "Lyon" -t "HealthTech" -l 50
        tawiza cartographie collecter "Ile-de-France" --thematique "FinTech" --nom "Fintech IDF"
    """
    show_header()

    async def _collecter():
        adapter = get_adapter()
        if output:
            adapter.output_dir = Path(output)
            adapter.output_dir.mkdir(parents=True, exist_ok=True)

        return await adapter.execute_task(
            {
                "action": "collecter",
                "nom": nom or f"Collecte {territoire} {thematique or ''}",
                "territoire": territoire,
                "thematique": thematique,
                "limite": limite,
            }
        )

    console.print(f"\n[bold {THEME['info_color']}]🔎 Collecte automatique de données...[/]\n")
    console.print(f"  📍 Territoire: [bold]{territoire}[/]")
    if thematique:
        console.print(f"  🏷️  Thématique: [bold]{thematique}[/]")
    console.print(f"  📊 Limite: [bold]{limite}[/] acteurs\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Recherche en cours...", total=100)
        result = run_async(_collecter())
        progress.update(task, completed=100)

    # Afficher le résultat
    console.print()
    console.print(
        Panel(
            f"""[bold green]✅ Collecte terminée![/]

[bold]Projet ID:[/] {result["projet_id"]}
[bold]Acteurs trouvés:[/] {result["nb_acteurs"]}
[bold]Dataset:[/] {result.get("fichier_dataset", "N/A")}

[bold cyan]Sources utilisées:[/]
{chr(10).join(f"  • {s}" for s in result.get("sources_utilisees", []))}
        """,
            title="🔎 Résultat de la Collecte",
            border_style=THEME["success_color"],
        )
    )

    # Distribution par type
    if result.get("acteurs_par_type"):
        table = Table(title="📊 Distribution par Type", box=box.ROUNDED)
        table.add_column("Type", style="cyan")
        table.add_column("Nombre", style="white", justify="right")

        for type_acteur, count in sorted(
            result["acteurs_par_type"].items(), key=lambda x: x[1], reverse=True
        ):
            table.add_row(type_acteur, str(count))

        console.print(table)

    # Erreurs éventuelles
    if result.get("erreurs"):
        console.print(f"\n[{THEME['warning_color']}]⚠️  Avertissements:[/]")
        for err in result["erreurs"]:
            console.print(f"  • {err}")

    console.print()
    console.print(
        f"[bold {THEME['info_color']}]💡 Prochaine étape:[/] tawiza cartographie analyser {result['projet_id']}"
    )


@app.command("auto")
def pipeline_auto(
    territoire: str = typer.Argument(..., help="Territoire à cartographier"),
    thematique: str | None = typer.Option(None, "--thematique", "-t", help="Secteur/thématique"),
    limite: int = typer.Option(100, "--limite", "-l", help="Nombre d'acteurs à collecter"),
    nom: str | None = typer.Option(None, "--nom", "-n", help="Nom du projet"),
    output: str | None = typer.Option(None, "--output", "-o", help="Répertoire de sortie"),
    ouvrir: bool = typer.Option(True, "--ouvrir/--no-ouvrir", help="Ouvrir les résultats"),
):
    """
    🤖 Pipeline 100% automatique: collecte + analyse + visualisation

    Exécute automatiquement:
    1. Collecte des données (APIs + web scraping)
    2. Analyse des relations (NetworkX)
    3. Génération des visualisations (carte + graphe)

    Aucun fichier source requis - tout est collecté automatiquement!

    Exemples:
        tawiza cartographie auto "Bordeaux" --thematique "AgriTech"
        tawiza cartographie auto "Toulouse" -t "Aérospatiale" -l 150
        tawiza cartographie auto "Paris" --nom "Startup Nation"
    """
    show_header()

    async def _auto():
        adapter = get_adapter()
        if output:
            adapter.output_dir = Path(output)
            adapter.output_dir.mkdir(parents=True, exist_ok=True)

        return await adapter.execute_task(
            {
                "action": "pipeline_auto",
                "nom": nom or f"Cartographie {territoire} {thematique or ''}",
                "territoire": territoire,
                "thematique": thematique,
                "limite": limite,
            }
        )

    console.print(f"\n[bold {THEME['info_color']}]🤖 Pipeline Automatique...[/]\n")
    console.print(f"  📍 Territoire: [bold]{territoire}[/]")
    if thematique:
        console.print(f"  🏷️  Thématique: [bold]{thematique}[/]")
    console.print(f"  📊 Limite: [bold]{limite}[/] acteurs\n")
    console.print("[dim]Collecte automatique des données, analyse et visualisation...[/]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Pipeline en cours...", total=100)
        result = run_async(_auto())
        progress.update(task, completed=100)

    fichiers = result.get("fichiers", {})
    resume = result.get("resume", {})
    analyse = result.get("analyse", {})

    # Résultat final
    console.print()
    console.print(
        Panel(
            f"""[bold green]✅ Cartographie terminée![/]

[bold]Projet ID:[/] {result["projet_id"]}
[bold]Mode:[/] {result.get("mode", "auto").upper()}

[bold cyan]📊 Statistiques:[/]
  • Acteurs: {resume.get("nb_acteurs", 0)}
  • Relations: {resume.get("nb_relations", 0)}
  • Communautés: {resume.get("nb_communautes", 0)}

[bold cyan]📈 Métriques Réseau:[/]
  • Densité: {analyse.get("densite", 0):.3f}
  • Modularité: {analyse.get("modularite", 0):.3f}

[bold cyan]📁 Fichiers:[/]
  🗺️  {fichiers.get("carte", "N/A")}
  🕸️  {fichiers.get("graphe", "N/A")}
  📄 {fichiers.get("rapport", "N/A")}
        """,
            title="🤖 Cartographie Automatique",
            border_style=THEME["success_color"],
            box=box.DOUBLE,
        )
    )

    # Afficher les liens d'accès
    if fichiers.get("carte"):
        carte_path = Path(fichiers["carte"])
        console.print("\n[bold green]📍 Accès aux visualisations:[/]")
        console.print("\n[cyan]Serveur HTTP:[/] Lancez d'abord:")
        console.print("  [yellow]python3 scripts/serve_cartographies.py[/]")
        console.print("\nPuis accédez à: [link=http://localhost:8888/]http://localhost:8888/[/]")
        console.print(f"\n[dim]Fichier local:[/] file://{carte_path.absolute()}")


@app.command("pipeline")
def pipeline_complet(
    csv: list[str] | None = typer.Option(None, "--csv", help="Fichier(s) CSV"),
    excel: list[str] | None = typer.Option(None, "--excel", help="Fichier(s) Excel"),
    json_file: list[str] | None = typer.Option(None, "--json", help="Fichier(s) JSON"),
    nom: str = typer.Option("Cartographie", "--nom", "-n", help="Nom du projet"),
    territoire: str | None = typer.Option(None, "--territoire", "-t", help="Territoire"),
    thematique: str | None = typer.Option(None, "--thematique", help="Thématique"),
    output: str | None = typer.Option(None, "--output", "-o", help="Répertoire de sortie"),
):
    """
    🚀 Exécute le pipeline complet en une seule commande

    Enchaîne automatiquement:
    1. Création du projet
    2. Ingestion des sources
    3. Extraction des entités (spaCy)
    4. Analyse du réseau (NetworkX)
    5. Génération des visualisations (Folium + PyVis)

    Exemple:
        tawiza cartographie pipeline --csv data/acteurs.csv --nom "Mon Ecosystème" -t "Occitanie"
    """
    show_header()

    # Construire les sources
    sources = []
    for f in csv or []:
        if not Path(f).exists():
            console.print(f"[bold {THEME['error_color']}]❌ Fichier non trouvé: {f}[/]")
            raise typer.Exit(1)
        sources.append({"type": "csv", "chemin": f})
    for f in excel or []:
        if not Path(f).exists():
            console.print(f"[bold {THEME['error_color']}]❌ Fichier non trouvé: {f}[/]")
            raise typer.Exit(1)
        sources.append({"type": "excel", "chemin": f})
    for f in json_file or []:
        if not Path(f).exists():
            console.print(f"[bold {THEME['error_color']}]❌ Fichier non trouvé: {f}[/]")
            raise typer.Exit(1)
        sources.append({"type": "json", "chemin": f})

    if not sources:
        console.print(f"[bold {THEME['error_color']}]❌ Aucune source spécifiée![/]")
        console.print("Utilisez --csv, --excel ou --json pour ajouter des sources")
        raise typer.Exit(1)

    async def _pipeline():
        adapter = get_adapter()
        if output:
            adapter.output_dir = Path(output)
            adapter.output_dir.mkdir(parents=True, exist_ok=True)

        return await adapter.execute_task(
            {
                "action": "pipeline_complet",
                "nom": nom,
                "territoire": territoire,
                "thematique": thematique,
                "sources": sources,
            }
        )

    console.print(f"\n[bold {THEME['info_color']}]🚀 Lancement du pipeline complet...[/]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Pipeline de cartographie...", total=100)

        # Exécuter de manière synchrone avec mises à jour
        async def _run_with_progress():
            adapter = get_adapter()
            if output:
                adapter.output_dir = Path(output)
                adapter.output_dir.mkdir(parents=True, exist_ok=True)

            # Simuler les étapes avec mise à jour de la progress bar

            result = await adapter.execute_task(
                {
                    "action": "pipeline_complet",
                    "nom": nom,
                    "territoire": territoire,
                    "thematique": thematique,
                    "sources": sources,
                }
            )

            return result

        result = run_async(_run_with_progress())
        progress.update(task, completed=100)

    # Afficher le résultat final
    fichiers = result.get("fichiers", {})
    resume = result.get("resume", {})
    analyse = result.get("analyse", {})

    console.print()
    console.print(
        Panel(
            f"""[bold green]✅ Pipeline terminé avec succès![/]

[bold]Projet ID:[/] {result["projet_id"]}

[bold cyan]📊 Statistiques:[/]
  • Acteurs extraits: {resume.get("nb_acteurs", 0)}
  • Relations détectées: {resume.get("nb_relations", 0)}
  • Communautés identifiées: {resume.get("nb_communautes", 0)}

[bold cyan]📈 Métriques du Réseau:[/]
  • Densité: {analyse.get("densite", 0):.3f}
  • Modularité: {analyse.get("modularite", 0):.3f}
  • Composantes connexes: {analyse.get("nb_composantes", "N/A")}

[bold cyan]📁 Fichiers Générés:[/]
  🗺️  Carte: {fichiers.get("carte", "N/A")}
  🕸️  Graphe: {fichiers.get("graphe", "N/A")}
  📄 Rapport: {fichiers.get("rapport", "N/A")}
        """,
            title="🗺️ Cartographie Terminée",
            border_style=THEME["success_color"],
            box=box.DOUBLE,
        )
    )

    # Ouvrir la carte automatiquement
    if fichiers.get("carte"):
        import webbrowser

        with contextlib.suppress(Exception):
            webbrowser.open(f"file://{Path(fichiers['carte']).absolute()}")


@app.command("liste")
def lister_projets():
    """
    📋 Liste tous les projets de cartographie
    """
    show_header()

    async def _lister():
        adapter = get_adapter()
        return await adapter.lister_projets()

    projets = run_async(_lister())

    if not projets:
        console.print(f"\n[{THEME['warning_color']}]Aucun projet trouvé.[/]")
        console.print('Créez un nouveau projet avec: tawiza cartographie nouveau "Mon Projet"')
        return

    table = Table(title="📋 Projets de Cartographie", box=box.ROUNDED)
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("Nom", style="white")
    table.add_column("Territoire", style="dim")
    table.add_column("Statut", style="green")
    table.add_column("Acteurs", justify="right")
    table.add_column("Relations", justify="right")

    for p in projets:
        statut_emoji = {
            "brouillon": "📝",
            "en_cours": "⏳",
            "extraction": "🔍",
            "analyse": "🔬",
            "visualisation": "🎨",
            "termine": "✅",
            "erreur": "❌",
        }.get(p["statut"], "❓")

        table.add_row(
            p["id"][:10] + "...",
            p["nom"],
            p.get("territoire", "-"),
            f"{statut_emoji} {p['statut']}",
            str(p.get("nb_acteurs", 0)),
            str(p.get("nb_relations", 0)),
        )

    console.print()
    console.print(table)


@app.command("statut")
def statut_projet(projet_id: str = typer.Argument(..., help="ID du projet")):
    """
    📊 Affiche le statut détaillé d'un projet
    """
    show_header()

    async def _statut():
        adapter = get_adapter()
        return await adapter.obtenir_projet(projet_id)

    projet = run_async(_statut())

    if not projet:
        console.print(f"[bold {THEME['error_color']}]❌ Projet non trouvé: {projet_id}[/]")
        raise typer.Exit(1)

    console.print()
    console.print(
        Panel(
            f"""[bold]ID:[/] {projet["id"]}
[bold]Nom:[/] {projet["nom"]}
[bold]Description:[/] {projet.get("description", "-")}
[bold]Territoire:[/] {projet.get("territoire", "-")}
[bold]Thématique:[/] {projet.get("thematique", "-")}
[bold]Statut:[/] {projet["statut"]}
[bold]Progression:[/] {projet["progression"]}%
[bold]Étape:[/] {projet["etape_courante"]}

[bold]Sources:[/] {projet.get("nb_sources", 0)}
[bold]Acteurs:[/] {projet.get("nb_acteurs", 0)}
[bold]Relations:[/] {projet.get("nb_relations", 0)}

[bold]Créé le:[/] {projet["date_creation"]}
[bold]Modifié le:[/] {projet["date_modification"]}
        """,
            title=f"📊 Projet: {projet['nom']}",
            border_style=THEME["info_color"],
        )
    )

    if projet.get("erreur"):
        console.print(
            Panel(f"[bold red]{projet['erreur']}[/]", title="❌ Erreur", border_style="red")
        )


@app.command("supprimer")
def supprimer_projet(
    projet_id: str = typer.Argument(..., help="ID du projet à supprimer"),
    force: bool = typer.Option(False, "--force", "-f", help="Supprimer sans confirmation"),
):
    """
    🗑️  Supprime un projet de cartographie
    """
    if not force:
        confirm = typer.confirm(f"Êtes-vous sûr de vouloir supprimer le projet {projet_id}?")
        if not confirm:
            console.print("Annulé.")
            return

    async def _supprimer():
        adapter = get_adapter()
        return await adapter.supprimer_projet(projet_id)

    success = run_async(_supprimer())

    if success:
        console.print(f"[bold {THEME['success_color']}]✅ Projet supprimé: {projet_id}[/]")
    else:
        console.print(f"[bold {THEME['error_color']}]❌ Projet non trouvé: {projet_id}[/]")


@app.callback()
def callback():
    """
    🗺️ EcoCartographe - Cartographie d'écosystèmes territoriaux d'innovation

    Analysez et visualisez les acteurs d'innovation (entreprises, labs, clusters)
    et leurs relations sur un territoire donné.

    Utilise:
    • spaCy pour l'extraction d'entités
    • NetworkX pour l'analyse de réseau
    • Folium pour les cartes géographiques
    • PyVis pour les graphes interactifs
    """
    pass


if __name__ == "__main__":
    app()
