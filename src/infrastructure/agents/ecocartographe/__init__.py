"""
EcoCartographe - Agent de cartographie d'écosystèmes territoriaux
Utilise Ollama + spaCy + NetworkX + Folium/PyVis pour analyser et visualiser
les acteurs d'innovation et leurs relations.

Fonctionnalités:
- Collecte automatique de données (web scraping, APIs publiques)
- Extraction d'entités NLP (spaCy)
- Analyse de réseau (NetworkX)
- Visualisations interactives (Folium, PyVis)
"""

from .collecteur_donnees import CollecteurDonnees, EnrichisseurDonnees, ResultatRecherche
from .dashboard_generator import DashboardGenerator
from .ecocartographe_adapter import EcoCartographeAdapter
from .models import (
    Acteur,
    ActeurType,
    AnalyseReseau,
    Communaute,
    ConfigurationExtraction,
    ProjetCartographie,
    Relation,
    RelationType,
    ResultatCartographie,
)
from .services import (
    AnalyseurRelations,
    AnalyseurReseau,
    ExtracteurEntites,
    GenerateurVisualisations,
)

__all__ = [
    # Models
    "Acteur",
    "ActeurType",
    "Relation",
    "RelationType",
    "Communaute",
    "ProjetCartographie",
    "AnalyseReseau",
    "ConfigurationExtraction",
    "ResultatCartographie",
    # Adapter
    "EcoCartographeAdapter",
    # Services
    "ExtracteurEntites",
    "AnalyseurRelations",
    "AnalyseurReseau",
    "GenerateurVisualisations",
    # Collecteur
    "CollecteurDonnees",
    "EnrichisseurDonnees",
    "ResultatRecherche",
    # Dashboard
    "DashboardGenerator"
]
