"""
EcoCartographe Adapter - Agent de cartographie d'écosystèmes territoriaux
Intègre les services d'extraction, d'analyse et de visualisation
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.application.ports.agent_ports import AgentType, TaskStatus
from src.infrastructure.agents.base_agent import BaseAgent

from .collecteur_donnees import CollecteurDonnees
from .models import (
    Acteur,
    ConfigurationExtraction,
    ProjetCartographie,
    ResultatCartographie,
    SourceDonnees,
    StatutProjet,
)
from .services import (
    AnalyseurRelations,
    AnalyseurReseau,
    ExtracteurEntites,
    GenerateurVisualisations,
)


class EcoCartographeAdapter(BaseAgent):
    """
    Adapter pour l'agent EcoCartographe.
    Orchestre le pipeline complet de cartographie d'écosystèmes.

    Pipeline:
    1. Ingestion des sources (CSV, Excel, JSON, Web)
    2. Extraction des entités (spaCy)
    3. Détection des relations
    4. Analyse du réseau (NetworkX)
    5. Génération des visualisations (Folium, PyVis)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        # Créer un type d'agent personnalisé ou utiliser OPENMANUS comme base
        super().__init__(
            agent_type=AgentType.OPENMANUS,  # On réutilise ce type pour compatibilité
            config=config or {}
        )

        self.projets: dict[str, ProjetCartographie] = {}
        self.output_dir = Path(config.get('output_dir', './workspace/outputs')) if config else Path('./workspace/outputs')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("EcoCartographeAdapter initialisé")

    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """
        Exécute une tâche de cartographie.

        Args:
            task_config: Configuration de la tâche
                - action: 'creer_projet' | 'ingerer' | 'extraire' | 'analyser' | 'cartographier' | 'pipeline_complet'
                - projet_id: ID du projet (optionnel pour création)
                - sources: Liste des sources de données
                - configuration: Configuration d'extraction

        Returns:
            Résultat de la tâche
        """
        task_id = self._create_task(task_config)
        action = task_config.get('action', 'pipeline_complet')

        try:
            self._update_task(task_id, {"status": TaskStatus.RUNNING})
            self._update_progress(task_id, 0, f"Démarrage: {action}")

            if action == 'creer_projet':
                result = await self._creer_projet(task_id, task_config)
            elif action == 'ingerer':
                result = await self._ingerer_sources(task_id, task_config)
            elif action == 'extraire':
                result = await self._extraire_entites(task_id, task_config)
            elif action == 'analyser':
                result = await self._analyser_reseau(task_id, task_config)
            elif action == 'visualiser':
                result = await self._generer_visualisations(task_id, task_config)
            elif action == 'collecter':
                result = await self._collecter_donnees(task_id, task_config)
            elif action == 'pipeline_complet':
                result = await self._pipeline_complet(task_id, task_config)
            elif action == 'pipeline_auto':
                result = await self._pipeline_auto(task_id, task_config)
            else:
                raise ValueError(f"Action inconnue: {action}")

            self._update_task(task_id, {
                "status": TaskStatus.COMPLETED,
                "result": result
            })
            self._update_progress(task_id, 100, "Terminé")

            return result

        except Exception as e:
            logger.exception(f"Erreur dans la tâche {task_id}")
            self._update_task(task_id, {
                "status": TaskStatus.FAILED,
                "error": str(e)
            })
            raise

    async def _creer_projet(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Crée un nouveau projet de cartographie"""
        self._update_progress(task_id, 10, "Création du projet")

        extraction_config = ConfigurationExtraction(
            modele_spacy=config.get('modele_spacy', 'fr_core_news_lg'),
            modele_ollama=config.get('modele_ollama', 'mistral:latest'),
            seuil_proximite_km=config.get('seuil_proximite_km', 50.0),
            seuil_similarite_thematique=config.get('seuil_similarite', 0.7)
        )

        projet = ProjetCartographie(
            nom=config.get('nom', 'Cartographie sans nom'),
            description=config.get('description'),
            territoire=config.get('territoire'),
            thematique=config.get('thematique'),
            configuration=extraction_config
        )

        self.projets[projet.id] = projet
        self._add_log(task_id, f"Projet créé: {projet.id} - {projet.nom}")

        return {
            "projet_id": projet.id,
            "nom": projet.nom,
            "statut": projet.statut.value
        }

    async def _ingerer_sources(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Ingère les sources de données dans le projet"""
        projet_id = config.get('projet_id')
        sources_config = config.get('sources', [])

        if not projet_id or projet_id not in self.projets:
            raise ValueError(f"Projet non trouvé: {projet_id}")

        projet = self.projets[projet_id]
        projet.demarrer()

        for i, src_config in enumerate(sources_config):
            progress = 20 + (i * 30 // len(sources_config))
            self._update_progress(task_id, progress, f"Ingestion source {i+1}/{len(sources_config)}")

            source = SourceDonnees(
                type=src_config.get('type', 'csv'),
                chemin=src_config.get('chemin', ''),
                url=src_config.get('url'),
                configuration=src_config.get('configuration', {})
            )
            projet.ajouter_source(source)
            self._add_log(task_id, f"Source ajoutée: {source.type} - {source.chemin or source.url}")

        return {
            "projet_id": projet_id,
            "nb_sources": len(projet.sources),
            "sources": [{"type": s.type, "chemin": s.chemin} for s in projet.sources]
        }

    async def _extraire_entites(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Extrait les entités des sources"""
        projet_id = config.get('projet_id')

        if not projet_id or projet_id not in self.projets:
            raise ValueError(f"Projet non trouvé: {projet_id}")

        projet = self.projets[projet_id]
        projet.statut = StatutProjet.EXTRACTION

        extracteur = ExtracteurEntites(projet.configuration)
        await extracteur.initialiser()

        tous_acteurs: list[Acteur] = []
        textes_extraits: list[str] = []

        for i, source in enumerate(projet.sources):
            progress = 30 + (i * 30 // max(len(projet.sources), 1))
            self._update_progress(task_id, progress, f"Extraction depuis {source.type}")

            try:
                if source.type == 'csv':
                    acteurs = await extracteur.extraire_depuis_csv(source.chemin)
                elif source.type == 'excel':
                    acteurs = await extracteur.extraire_depuis_excel(source.chemin)
                elif source.type == 'json':
                    acteurs = await extracteur.extraire_depuis_json(source.chemin)
                elif source.type == 'texte':
                    # Lire le fichier texte
                    with open(source.chemin, encoding='utf-8') as f:
                        texte = f.read()
                    textes_extraits.append(texte)
                    acteurs = await extracteur.extraire_depuis_texte(texte, source.chemin)
                else:
                    logger.warning(f"Type de source non supporté: {source.type}")
                    continue

                tous_acteurs.extend(acteurs)
                source.nb_enregistrements = len(acteurs)
                source.statut = "completed"
                source.date_ingestion = datetime.utcnow()

            except Exception as e:
                source.statut = "error"
                source.erreur = str(e)
                self._add_log(task_id, f"Erreur extraction {source.chemin}: {e}", "error")

        # Dédupliquer les acteurs par nom
        acteurs_uniques = self._dedupliquer_acteurs(tous_acteurs)

        # Stocker temporairement
        projet.metadata = projet.metadata if hasattr(projet, 'metadata') else {}
        projet.metadata['acteurs'] = acteurs_uniques
        projet.metadata['textes'] = textes_extraits

        self._add_log(task_id, f"Extraction terminée: {len(acteurs_uniques)} acteurs uniques")

        return {
            "projet_id": projet_id,
            "nb_acteurs": len(acteurs_uniques),
            "acteurs_par_type": self._compter_par_type(acteurs_uniques)
        }

    async def _analyser_reseau(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Analyse le réseau et détecte les communautés"""
        projet_id = config.get('projet_id')

        if not projet_id or projet_id not in self.projets:
            raise ValueError(f"Projet non trouvé: {projet_id}")

        projet = self.projets[projet_id]
        projet.statut = StatutProjet.ANALYSE

        acteurs = projet.metadata.get('acteurs', [])
        textes = projet.metadata.get('textes', [])

        if not acteurs:
            raise ValueError("Aucun acteur extrait. Exécutez d'abord l'extraction.")

        # Détection des relations
        self._update_progress(task_id, 60, "Détection des relations")
        analyseur_rel = AnalyseurRelations(projet.configuration)
        await analyseur_rel.initialiser()
        relations = await analyseur_rel.detecter_relations(acteurs, textes)

        # Analyse du réseau
        self._update_progress(task_id, 75, "Analyse du réseau")
        analyseur_reseau = AnalyseurReseau()
        analyseur_reseau.construire_graphe(acteurs, relations)
        analyse = analyseur_reseau.analyser(acteurs)

        # Exporter GEXF
        gexf_path = self.output_dir / f"{projet_id}_graphe.gexf"
        analyseur_reseau.exporter_gexf(str(gexf_path))

        # Stocker les résultats
        projet.metadata['relations'] = relations
        projet.metadata['analyse'] = analyse
        projet.metadata['analyseur_reseau'] = analyseur_reseau

        self._add_log(task_id, f"Analyse terminée: {len(relations)} relations, {len(analyse.communautes)} communautés")

        return {
            "projet_id": projet_id,
            "nb_relations": len(relations),
            "analyse": {
                "nb_noeuds": analyse.nb_noeuds,
                "nb_aretes": analyse.nb_aretes,
                "densite": analyse.densite,
                "nb_communautes": len(analyse.communautes),
                "modularite": analyse.modularite,
                "acteurs_centraux": analyse.acteurs_centraux[:5]
            },
            "fichier_gexf": str(gexf_path)
        }

    async def _generer_visualisations(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Génère les visualisations (carte et graphe)"""
        projet_id = config.get('projet_id')

        if not projet_id or projet_id not in self.projets:
            raise ValueError(f"Projet non trouvé: {projet_id}")

        projet = self.projets[projet_id]
        projet.statut = StatutProjet.VISUALISATION

        acteurs = projet.metadata.get('acteurs', [])
        relations = projet.metadata.get('relations', [])
        analyse = projet.metadata.get('analyse')

        if not acteurs:
            raise ValueError("Aucun acteur. Exécutez d'abord l'extraction et l'analyse.")

        generateur = GenerateurVisualisations(str(self.output_dir))

        # Générer la carte
        self._update_progress(task_id, 85, "Génération de la carte")
        fichier_carte = await generateur.generer_carte(
            acteurs, relations,
            nom_fichier=f"{projet_id}_carte.html"
        )

        # Générer le graphe
        self._update_progress(task_id, 90, "Génération du graphe")
        fichier_graphe = await generateur.generer_graphe(
            acteurs, relations,
            nom_fichier=f"{projet_id}_graphe.html"
        )

        # Générer le rapport
        self._update_progress(task_id, 90, "Génération du rapport")
        fichier_rapport = await generateur.generer_rapport(
            projet.nom, acteurs, relations, analyse,
            nom_fichier=f"{projet_id}_rapport.md"
        )

        # Générer le dashboard interactif
        self._update_progress(task_id, 95, "Génération du dashboard interactif")
        from .dashboard_generator import DashboardGenerator
        dashboard_gen = DashboardGenerator(str(self.output_dir))
        fichier_dashboard = dashboard_gen.generer_dashboard(
            projet.nom, acteurs, relations, analyse,
            fichier_carte, fichier_graphe,
            nom_fichier=f"{projet_id}_dashboard.html"
        )

        # Créer le résultat final
        resultat = ResultatCartographie(
            acteurs=acteurs,
            relations=relations,
            analyse=analyse,
            fichier_carte=fichier_carte,
            fichier_graphe=fichier_graphe,
            fichier_rapport=fichier_rapport
        )

        projet.terminer(resultat)

        return {
            "projet_id": projet_id,
            "fichiers": {
                "carte": fichier_carte,
                "graphe": fichier_graphe,
                "rapport": fichier_rapport,
                "dashboard": fichier_dashboard
            },
            "resume": {
                "nb_acteurs": len(acteurs),
                "nb_relations": len(relations),
                "nb_communautes": len(analyse.communautes) if analyse else 0
            }
        }

    async def _pipeline_complet(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Exécute le pipeline complet de cartographie"""

        # 1. Créer le projet
        self._update_progress(task_id, 5, "Création du projet")
        result_creation = await self._creer_projet(task_id, config)
        projet_id = result_creation['projet_id']
        config['projet_id'] = projet_id

        # 2. Ingérer les sources
        self._update_progress(task_id, 15, "Ingestion des sources")
        await self._ingerer_sources(task_id, config)

        # 3. Extraire les entités
        self._update_progress(task_id, 35, "Extraction des entités")
        result_extraction = await self._extraire_entites(task_id, config)

        # 4. Analyser le réseau
        self._update_progress(task_id, 60, "Analyse du réseau")
        result_analyse = await self._analyser_reseau(task_id, config)

        # 5. Générer les visualisations
        self._update_progress(task_id, 85, "Génération des visualisations")
        result_visu = await self._generer_visualisations(task_id, config)

        return {
            "projet_id": projet_id,
            "statut": "termine",
            "extraction": result_extraction,
            "analyse": result_analyse['analyse'],
            "fichiers": result_visu['fichiers'],
            "resume": result_visu['resume']
        }

    async def _collecter_donnees(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        Collecte automatiquement des données sur les acteurs d'innovation.
        Recherche sur le web et les APIs publiques.
        """
        territoire = config.get('territoire', 'France')
        thematique = config.get('thematique')
        limite = config.get('limite', 100)
        projet_id = config.get('projet_id')

        self._update_progress(task_id, 10, f"Recherche d'acteurs: {territoire}")

        # Créer le projet si nécessaire
        if not projet_id:
            nom_projet = config.get('nom', f"Collecte {territoire} {thematique or ''}")
            result_creation = await self._creer_projet(task_id, {
                'nom': nom_projet,
                'territoire': territoire,
                'thematique': thematique
            })
            projet_id = result_creation['projet_id']
            config['projet_id'] = projet_id

        projet = self.projets[projet_id]

        # Initialiser le collecteur
        collecteur = CollecteurDonnees(
            config=projet.configuration,
            output_dir=str(self.output_dir / "datasets")
        )

        self._update_progress(task_id, 20, "Recherche via API Entreprises")
        self._add_log(task_id, f"Collecte pour {territoire}, thématique={thematique}")

        # Collecter les données
        resultat = await collecteur.rechercher_acteurs(
            territoire=territoire,
            thematique=thematique,
            limite=limite
        )

        self._update_progress(task_id, 70, f"Collecté {len(resultat.acteurs)} acteurs")

        # Sauvegarder le dataset
        nom_fichier = f"{projet_id}_dataset.json"
        chemin_dataset = await collecteur.sauvegarder_dataset(
            resultat, nom_fichier, format="json"
        )

        # Ajouter comme source au projet
        source = SourceDonnees(
            type="json",
            chemin=chemin_dataset,
            date_ingestion=datetime.utcnow(),
            nb_enregistrements=len(resultat.acteurs),
            statut="completed"
        )
        projet.ajouter_source(source)

        # Stocker les acteurs dans le projet
        projet.metadata = projet.metadata if hasattr(projet, 'metadata') else {}
        projet.metadata['acteurs'] = resultat.acteurs

        self._update_progress(task_id, 90, "Collecte terminée")

        return {
            "projet_id": projet_id,
            "nb_acteurs": len(resultat.acteurs),
            "sources_utilisees": resultat.sources_utilisees,
            "fichier_dataset": chemin_dataset,
            "acteurs_par_type": self._compter_par_type(resultat.acteurs),
            "erreurs": resultat.erreurs if resultat.erreurs else None
        }

    async def _pipeline_auto(self, task_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        Pipeline automatique: collecte les données si aucune source n'est fournie,
        puis exécute le pipeline complet.
        """
        territoire = config.get('territoire', 'France')
        thematique = config.get('thematique')
        sources = config.get('sources', [])

        # 1. Créer le projet
        self._update_progress(task_id, 5, "Création du projet")
        result_creation = await self._creer_projet(task_id, config)
        projet_id = result_creation['projet_id']
        config['projet_id'] = projet_id

        # 2. Collecter ou ingérer les données
        if not sources:
            # Pas de sources fournies -> collecte automatique
            self._update_progress(task_id, 10, "Collecte automatique des données")
            self._add_log(task_id, "Aucune source fournie, lancement de la collecte automatique")

            result_collecte = await self._collecter_donnees(task_id, {
                'projet_id': projet_id,
                'territoire': territoire,
                'thematique': thematique,
                'limite': config.get('limite', 100)
            })

            self._add_log(task_id, f"Collecté {result_collecte['nb_acteurs']} acteurs")
        else:
            # Sources fournies -> ingestion classique
            self._update_progress(task_id, 15, "Ingestion des sources")
            await self._ingerer_sources(task_id, config)

            # Extraction des entités
            self._update_progress(task_id, 35, "Extraction des entités")
            await self._extraire_entites(task_id, config)

        # 3. Analyser le réseau
        self._update_progress(task_id, 55, "Analyse du réseau")
        result_analyse = await self._analyser_reseau(task_id, config)

        # 4. Générer les visualisations
        self._update_progress(task_id, 80, "Génération des visualisations")
        result_visu = await self._generer_visualisations(task_id, config)

        return {
            "projet_id": projet_id,
            "statut": "termine",
            "mode": "auto" if not sources else "sources",
            "analyse": result_analyse['analyse'],
            "fichiers": result_visu['fichiers'],
            "resume": result_visu['resume']
        }

    def _dedupliquer_acteurs(self, acteurs: list[Acteur]) -> list[Acteur]:
        """Déduplique les acteurs par nom normalisé"""
        vus: dict[str, Acteur] = {}
        for acteur in acteurs:
            nom_normalise = acteur.nom.lower().strip()
            if nom_normalise not in vus:
                vus[nom_normalise] = acteur
            else:
                # Fusionner les métadonnées
                existant = vus[nom_normalise]
                existant.mots_cles = list(set(existant.mots_cles + acteur.mots_cles))
                existant.secteurs = list(set(existant.secteurs + acteur.secteurs))
        return list(vus.values())

    def _compter_par_type(self, acteurs: list[Acteur]) -> dict[str, int]:
        """Compte les acteurs par type"""
        comptage: dict[str, int] = {}
        for acteur in acteurs:
            type_str = acteur.type.value
            comptage[type_str] = comptage.get(type_str, 0) + 1
        return comptage

    # Méthodes utilitaires pour la CLI

    async def lister_projets(self) -> list[dict[str, Any]]:
        """Liste tous les projets"""
        return [p.to_dict() for p in self.projets.values()]

    async def obtenir_projet(self, projet_id: str) -> dict[str, Any] | None:
        """Obtient les détails d'un projet"""
        projet = self.projets.get(projet_id)
        if projet:
            return projet.to_dict()
        return None

    async def supprimer_projet(self, projet_id: str) -> bool:
        """Supprime un projet"""
        if projet_id in self.projets:
            del self.projets[projet_id]
            return True
        return False
