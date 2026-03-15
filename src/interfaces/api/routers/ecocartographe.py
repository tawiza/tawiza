"""
API Router pour EcoCartographe - Cartographie d'écosystèmes territoriaux

Endpoints REST pour créer et gérer des projets de cartographie d'innovation.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.infrastructure.security.validators import safe_path

router = APIRouter(
    prefix="/ecocartographe",
    tags=["EcoCartographe"],
    responses={404: {"description": "Projet non trouvé"}},
)

# Instance globale de l'adapter
_adapter = None


def get_adapter():
    """Obtient l'instance singleton de l'adapter"""
    global _adapter
    if _adapter is None:
        from src.infrastructure.agents.ecocartographe import EcoCartographeAdapter

        _adapter = EcoCartographeAdapter()
    return _adapter


# ==================== Modèles Pydantic ====================


class SourceDonneesRequest(BaseModel):
    """Requête pour une source de données"""

    type: str = Field(..., description="Type de source: csv, excel, json, texte, web")
    chemin: str | None = Field(None, description="Chemin vers le fichier")
    url: str | None = Field(None, description="URL de la source web")
    configuration: dict[str, Any] = Field(
        default_factory=dict, description="Configuration additionnelle"
    )


class ConfigurationExtractionRequest(BaseModel):
    """Configuration pour l'extraction"""

    modele_spacy: str = Field("fr_core_news_lg", description="Modèle spaCy pour l'extraction NLP")
    modele_ollama: str = Field(
        "llama3.2:latest", description="Modèle Ollama pour l'analyse sémantique"
    )
    seuil_proximite_km: float = Field(50.0, description="Seuil de proximité géographique en km")
    seuil_similarite_thematique: float = Field(
        0.7, description="Seuil de similarité thématique (0-1)"
    )
    types_entites: list[str] = Field(
        ["ORG", "LOC", "PERSON"], description="Types d'entités à extraire"
    )


class CreerProjetRequest(BaseModel):
    """Requête pour créer un nouveau projet"""

    nom: str = Field(..., description="Nom du projet")
    description: str | None = Field(None, description="Description du projet")
    territoire: str | None = Field(None, description="Territoire ciblé (ex: Nouvelle-Aquitaine)")
    thematique: str | None = Field(None, description="Thématique (ex: AgriTech, HealthTech)")
    configuration: ConfigurationExtractionRequest | None = Field(
        None, description="Configuration d'extraction"
    )


class IngererSourcesRequest(BaseModel):
    """Requête pour ingérer des sources"""

    sources: list[SourceDonneesRequest] = Field(..., description="Liste des sources à ingérer")


class PipelineCompletRequest(BaseModel):
    """Requête pour le pipeline complet"""

    nom: str = Field(..., description="Nom du projet")
    description: str | None = Field(None)
    territoire: str | None = Field(None)
    thematique: str | None = Field(None)
    sources: list[SourceDonneesRequest] = Field(..., description="Sources de données")
    configuration: ConfigurationExtractionRequest | None = Field(None)


class ProjetResponse(BaseModel):
    """Réponse avec les informations d'un projet"""

    id: str
    nom: str
    description: str | None
    territoire: str | None
    thematique: str | None
    statut: str
    progression: int
    etape_courante: str
    nb_sources: int
    nb_acteurs: int
    nb_relations: int
    date_creation: str
    date_modification: str
    date_completion: str | None
    erreur: str | None


class TaskResponse(BaseModel):
    """Réponse pour une tâche asynchrone"""

    task_id: str
    projet_id: str
    status: str
    message: str


class AnalyseReseauResponse(BaseModel):
    """Réponse avec l'analyse du réseau"""

    nb_noeuds: int
    nb_aretes: int
    densite: float
    nb_communautes: int
    modularite: float
    coefficient_clustering_moyen: float
    acteurs_centraux: list[str]


class VisualisationsResponse(BaseModel):
    """Réponse avec les fichiers de visualisation"""

    projet_id: str
    fichier_carte: str | None
    fichier_graphe: str | None
    fichier_rapport: str | None


# ==================== Endpoints ====================


@router.post("/projets", response_model=TaskResponse, status_code=202)
async def creer_projet(request: CreerProjetRequest, background_tasks: BackgroundTasks):
    """
    Crée un nouveau projet de cartographie.

    Le projet est créé de manière synchrone et retourne immédiatement.
    """
    adapter = get_adapter()

    config = {
        "action": "creer_projet",
        "nom": request.nom,
        "description": request.description,
        "territoire": request.territoire,
        "thematique": request.thematique,
    }

    if request.configuration:
        config.update(
            {
                "modele_spacy": request.configuration.modele_spacy,
                "modele_ollama": request.configuration.modele_ollama,
                "seuil_proximite_km": request.configuration.seuil_proximite_km,
                "seuil_similarite": request.configuration.seuil_similarite_thematique,
            }
        )

    try:
        result = await adapter.execute_task(config)
        return TaskResponse(
            task_id="sync",
            projet_id=result["projet_id"],
            status="created",
            message=f"Projet '{request.nom}' créé avec succès",
        )
    except Exception as e:
        logger.exception("Erreur création projet")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projets", response_model=list[ProjetResponse])
async def lister_projets(
    statut: str | None = Query(None, description="Filtrer par statut"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Liste tous les projets de cartographie.
    """
    adapter = get_adapter()
    projets = await adapter.lister_projets()

    if statut:
        projets = [p for p in projets if p["statut"] == statut]

    return projets[offset : offset + limit]


@router.get("/projets/{projet_id}", response_model=ProjetResponse)
async def obtenir_projet(projet_id: str):
    """
    Obtient les détails d'un projet.
    """
    adapter = get_adapter()
    projet = await adapter.obtenir_projet(projet_id)

    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    return projet


@router.delete("/projets/{projet_id}")
async def supprimer_projet(projet_id: str):
    """
    Supprime un projet de cartographie.
    """
    adapter = get_adapter()
    success = await adapter.supprimer_projet(projet_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    return {"message": f"Projet {projet_id} supprimé"}


@router.post("/projets/{projet_id}/ingest", response_model=TaskResponse, status_code=202)
async def ingerer_sources(
    projet_id: str, request: IngererSourcesRequest, background_tasks: BackgroundTasks
):
    """
    Ingère des sources de données dans un projet existant.

    Types de sources supportés:
    - csv: Fichier CSV
    - excel: Fichier Excel (.xlsx, .xls)
    - json: Fichier JSON
    - texte: Fichier texte brut pour extraction NLP
    """
    adapter = get_adapter()

    # Vérifier que le projet existe
    projet = await adapter.obtenir_projet(projet_id)
    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    sources = [
        {"type": s.type, "chemin": s.chemin, "url": s.url, "configuration": s.configuration}
        for s in request.sources
    ]

    async def _ingerer():
        try:
            await adapter.execute_task(
                {"action": "ingerer", "projet_id": projet_id, "sources": sources}
            )
        except Exception:
            logger.exception(f"Erreur ingestion projet {projet_id}")

    background_tasks.add_task(_ingerer)

    return TaskResponse(
        task_id="background",
        projet_id=projet_id,
        status="processing",
        message=f"Ingestion de {len(sources)} source(s) démarrée",
    )


@router.post("/projets/{projet_id}/extract", response_model=TaskResponse, status_code=202)
async def extraire_entites(projet_id: str, background_tasks: BackgroundTasks):
    """
    Lance l'extraction des entités avec spaCy.

    Extrait automatiquement:
    - Organisations (entreprises, labs, clusters)
    - Lieux (villes, régions)
    - Personnes clés
    """
    adapter = get_adapter()

    projet = await adapter.obtenir_projet(projet_id)
    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    async def _extraire():
        try:
            await adapter.execute_task({"action": "extraire", "projet_id": projet_id})
        except Exception:
            logger.exception(f"Erreur extraction projet {projet_id}")

    background_tasks.add_task(_extraire)

    return TaskResponse(
        task_id="background",
        projet_id=projet_id,
        status="processing",
        message="Extraction des entités démarrée",
    )


@router.post("/projets/{projet_id}/analyze", response_model=TaskResponse, status_code=202)
async def analyser_reseau(projet_id: str, background_tasks: BackgroundTasks):
    """
    Lance l'analyse du réseau avec NetworkX.

    Calcule:
    - Métriques de centralité
    - Détection de communautés (Louvain)
    - Identification des ponts stratégiques
    """
    adapter = get_adapter()

    projet = await adapter.obtenir_projet(projet_id)
    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    async def _analyser():
        try:
            await adapter.execute_task({"action": "analyser", "projet_id": projet_id})
        except Exception:
            logger.exception(f"Erreur analyse projet {projet_id}")

    background_tasks.add_task(_analyser)

    return TaskResponse(
        task_id="background",
        projet_id=projet_id,
        status="processing",
        message="Analyse du réseau démarrée",
    )


@router.get("/projets/{projet_id}/network", response_model=dict[str, Any])
async def obtenir_donnees_reseau(projet_id: str):
    """
    Obtient les données du réseau au format JSON (pour D3.js/vis.js).

    Retourne:
    - nodes: Liste des nœuds avec leurs attributs
    - links: Liste des liens avec leurs poids
    """
    adapter = get_adapter()

    projet = await adapter.obtenir_projet(projet_id)
    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    # Récupérer le projet complet avec les métadonnées
    projet_complet = adapter.projets.get(projet_id)
    if not projet_complet or not hasattr(projet_complet, "metadata"):
        raise HTTPException(
            status_code=400, detail="Données réseau non disponibles. Exécutez d'abord l'analyse."
        )

    analyseur = projet_complet.metadata.get("analyseur_reseau")
    if not analyseur:
        raise HTTPException(status_code=400, detail="Analyse non effectuée")

    return analyseur.exporter_json()


@router.post(
    "/projets/{projet_id}/visualize", response_model=VisualisationsResponse, status_code=202
)
async def generer_visualisations(projet_id: str, background_tasks: BackgroundTasks):
    """
    Génère les visualisations (carte et graphe).

    Crée:
    - Carte géographique interactive (Folium)
    - Graphe de réseau interactif (PyVis)
    - Rapport Markdown détaillé
    """
    adapter = get_adapter()

    projet = await adapter.obtenir_projet(projet_id)
    if not projet:
        raise HTTPException(status_code=404, detail=f"Projet {projet_id} non trouvé")

    try:
        result = await adapter.execute_task({"action": "visualiser", "projet_id": projet_id})

        return VisualisationsResponse(
            projet_id=projet_id,
            fichier_carte=result["fichiers"].get("carte"),
            fichier_graphe=result["fichiers"].get("graphe"),
            fichier_rapport=result["fichiers"].get("rapport"),
        )
    except Exception as e:
        logger.exception(f"Erreur visualisation projet {projet_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projets/{projet_id}/visualizations/map")
async def telecharger_carte(projet_id: str):
    """
    Télécharge la carte HTML générée.
    """
    adapter = get_adapter()
    projet_complet = adapter.projets.get(projet_id)

    if not projet_complet or not projet_complet.resultat:
        raise HTTPException(status_code=404, detail="Carte non disponible")

    fichier = projet_complet.resultat.fichier_carte
    if not fichier or not Path(fichier).exists():
        raise HTTPException(status_code=404, detail="Fichier carte non trouvé")

    return FileResponse(fichier, media_type="text/html", filename=f"{projet_id}_carte.html")


@router.get("/projets/{projet_id}/visualizations/graph")
async def telecharger_graphe(projet_id: str):
    """
    Télécharge le graphe HTML généré.
    """
    adapter = get_adapter()
    projet_complet = adapter.projets.get(projet_id)

    if not projet_complet or not projet_complet.resultat:
        raise HTTPException(status_code=404, detail="Graphe non disponible")

    fichier = projet_complet.resultat.fichier_graphe
    if not fichier or not Path(fichier).exists():
        raise HTTPException(status_code=404, detail="Fichier graphe non trouvé")

    return FileResponse(fichier, media_type="text/html", filename=f"{projet_id}_graphe.html")


@router.get("/projets/{projet_id}/visualizations/report")
async def telecharger_rapport(projet_id: str):
    """
    Télécharge le rapport Markdown généré.
    """
    adapter = get_adapter()
    projet_complet = adapter.projets.get(projet_id)

    if not projet_complet or not projet_complet.resultat:
        raise HTTPException(status_code=404, detail="Rapport non disponible")

    fichier = projet_complet.resultat.fichier_rapport
    if not fichier or not Path(fichier).exists():
        raise HTTPException(status_code=404, detail="Fichier rapport non trouvé")

    return FileResponse(fichier, media_type="text/markdown", filename=f"{projet_id}_rapport.md")


@router.post("/pipeline", response_model=TaskResponse, status_code=202)
async def pipeline_complet(request: PipelineCompletRequest, background_tasks: BackgroundTasks):
    """
    Exécute le pipeline complet de cartographie.

    Enchaîne automatiquement:
    1. Création du projet
    2. Ingestion des sources
    3. Extraction des entités (spaCy)
    4. Analyse du réseau (NetworkX)
    5. Génération des visualisations (Folium + PyVis)
    """
    adapter = get_adapter()

    sources = [
        {"type": s.type, "chemin": s.chemin, "url": s.url, "configuration": s.configuration}
        for s in request.sources
    ]

    config = {
        "action": "pipeline_complet",
        "nom": request.nom,
        "description": request.description,
        "territoire": request.territoire,
        "thematique": request.thematique,
        "sources": sources,
    }

    if request.configuration:
        config.update(
            {
                "modele_spacy": request.configuration.modele_spacy,
                "modele_ollama": request.configuration.modele_ollama,
                "seuil_proximite_km": request.configuration.seuil_proximite_km,
                "seuil_similarite": request.configuration.seuil_similarite_thematique,
            }
        )

    # Exécuter en arrière-plan
    async def _pipeline():
        try:
            result = await adapter.execute_task(config)
            logger.info(f"Pipeline terminé: {result['projet_id']}")
        except Exception:
            logger.exception("Erreur pipeline")

    # Créer d'abord le projet pour obtenir l'ID
    result_creation = await adapter.execute_task(
        {
            "action": "creer_projet",
            "nom": request.nom,
            "description": request.description,
            "territoire": request.territoire,
            "thematique": request.thematique,
        }
    )

    projet_id = result_creation["projet_id"]
    config["projet_id"] = projet_id

    # Lancer le reste en arrière-plan
    async def _suite_pipeline():
        try:
            # Ingestion
            config["action"] = "ingerer"
            await adapter.execute_task(config)

            # Extraction
            config["action"] = "extraire"
            await adapter.execute_task(config)

            # Analyse
            config["action"] = "analyser"
            await adapter.execute_task(config)

            # Visualisation
            config["action"] = "visualiser"
            await adapter.execute_task(config)

            logger.info(f"Pipeline terminé: {projet_id}")
        except Exception:
            logger.exception(f"Erreur pipeline projet {projet_id}")

    background_tasks.add_task(_suite_pipeline)

    return TaskResponse(
        task_id="background",
        projet_id=projet_id,
        status="processing",
        message=f"Pipeline démarré pour le projet '{request.nom}'",
    )


class PipelineAutoRequest(BaseModel):
    """Requête pour le pipeline automatique avec collecte"""

    nom: str | None = Field(None, description="Nom du projet")
    territoire: str = Field(..., description="Territoire à cartographier")
    thematique: str | None = Field(None, description="Thématique (ex: AgriTech)")
    limite: int = Field(20, ge=1, le=100, description="Nombre d'acteurs à collecter")
    configuration: ConfigurationExtractionRequest | None = Field(None)


@router.post("/auto", response_model=dict[str, Any], status_code=200)
async def pipeline_auto(request: PipelineAutoRequest):
    """
    Exécute le pipeline automatique avec collecte de données.

    Ce pipeline collecte automatiquement les données via:
    - API Annuaire des Entreprises
    - Web scraping
    - Génération LLM (Ollama)

    Puis analyse et génère les visualisations.
    """
    adapter = get_adapter()

    config = {
        "action": "pipeline_auto",
        "nom": request.nom
        or f"Cartographie {request.territoire} {request.thematique or ''}".strip(),
        "territoire": request.territoire,
        "thematique": request.thematique,
        "limite": request.limite,
    }

    if request.configuration:
        config.update(
            {
                "modele_spacy": request.configuration.modele_spacy,
                "modele_ollama": request.configuration.modele_ollama,
                "seuil_proximite_km": request.configuration.seuil_proximite_km,
                "seuil_similarite": request.configuration.seuil_similarite_thematique,
            }
        )

    try:
        result = await adapter.execute_task(config)
        return {
            "projet_id": result.get("projet_id"),
            "status": "completed",
            "statistiques": result.get("statistiques", {}),
            "fichiers": result.get("fichiers", {}),
            "message": f"Cartographie de {request.territoire} terminée",
        }
    except Exception as e:
        logger.exception("Erreur pipeline auto")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outputs")
async def lister_fichiers_sortie():
    """
    Liste tous les fichiers de sortie générés.
    """
    output_dir = Path("workspace/outputs")
    if not output_dir.exists():
        return {"fichiers": []}

    fichiers = []
    for fichier in output_dir.glob("*.*"):
        if fichier.suffix in [".html", ".md", ".gexf", ".json"]:
            fichiers.append(
                {
                    "nom": fichier.name,
                    "type": fichier.suffix[1:],
                    "taille": fichier.stat().st_size,
                    "date_modification": fichier.stat().st_mtime,
                    "url": f"/ecocartographe/outputs/{fichier.name}",
                }
            )

    # Trier par date (plus récent d'abord)
    fichiers.sort(key=lambda f: f["date_modification"], reverse=True)

    return {"fichiers": fichiers}


@router.get("/outputs/{filename}")
async def telecharger_fichier_sortie(filename: str):
    """
    Télécharge un fichier de sortie par son nom.
    """
    output_dir = Path("workspace/outputs")
    try:
        fichier_path = safe_path(output_dir, filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    if not fichier_path.exists() or not fichier_path.is_file():
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Déterminer le type MIME
    media_types = {
        ".html": "text/html",
        ".md": "text/markdown",
        ".gexf": "application/xml",
        ".json": "application/json",
    }

    media_type = media_types.get(fichier_path.suffix, "application/octet-stream")

    return FileResponse(str(fichier_path), media_type=media_type, filename=fichier_path.name)


@router.get("/health")
async def health_check():
    """
    Vérifie l'état du service EcoCartographe.
    """
    return {
        "status": "healthy",
        "service": "EcoCartographe",
        "version": "1.0.0",
        "capabilities": [
            "auto_data_collection",
            "entity_extraction",
            "relationship_detection",
            "network_analysis",
            "geographic_mapping",
            "interactive_visualization",
        ],
    }
