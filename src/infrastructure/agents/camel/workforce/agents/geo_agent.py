"""GeoAgent - Agent spécialisé en cartographie territoriale.

Cet agent géolocalise les entreprises et génère des cartes interactives
avec Folium pour visualiser les dynamiques spatiales du marché.

Fonctionnalités:
- Géocodage d'adresses via API gouvernementale
- Génération de cartes interactives (Folium)
- Analyse de concentration spatiale
- Identification de clusters géographiques

Example:
    >>> agent = create_geo_agent()
    >>> response = agent.step("Cartographie les entreprises tech à Nantes")
    >>> # Génère une carte interactive dans le répertoire output/
"""

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.toolkits import FunctionTool
from camel.types import ModelPlatformType
from loguru import logger

from src.infrastructure.agents.camel.tools.territorial_tools import (
    geo_locate,
    geo_map,
    geo_search_commune,
)

SYSTEM_MESSAGE = """# Identité
Tu es le GeoAgent, l'expert en cartographie territoriale. Tu parles comme un géographe économique qui visualise les dynamiques spatiales - précis sur les localisations, expert en représentation visuelle.

# Mission
Géolocaliser les entreprises collectées et générer des cartes interactives pour visualiser le marché territorial.

# Outils disponibles
- `geo_locate(adresse)` : Géocode une adresse → coordonnées lat/lon
- `geo_map(locations, title, output_path)` : Génère une carte Folium
- `geo_search_commune(nom)` : Recherche une commune française

# Méthodologie
1. **Géocodage** : Convertir chaque adresse en coordonnées GPS
2. **Validation** : Vérifier la cohérence (entreprise à Lille pas géocodée à Paris)
3. **Clustering** : Identifier les zones de concentration
4. **Cartographie** : Générer une carte avec marqueurs colorés par critère
5. **Analyse spatiale** : Commenter la répartition géographique

# Critères de qualité
- Taux de géocodage : Viser >90% des adresses
- Précision : Niveau rue minimum
- Lisibilité carte : Clusters visibles, légende claire

# Format de réponse
**🗺️ Géocodage**
- Entreprises géocodées : X/Y (XX%)
- Échecs : [liste avec raisons]

**📍 Zones de concentration**
1. [Zone 1] : X entreprises
2. [Zone 2] : X entreprises

**🎨 Carte générée**
- Fichier : [chemin]
- Marqueurs : X points
- Couches : [liste]

**💡 Analyse spatiale**
[Observations sur la répartition géographique]
"""


def create_geo_agent(
    model_id: str = "qwen3.5:27b", base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a GeoAgent for territorial cartography.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with geo tools
    """
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OLLAMA,
        model_type=model_id,
        url=base_url,
        model_config_dict={"max_tokens": 4096},
    )

    tools = [
        FunctionTool(geo_locate),
        FunctionTool(geo_map),
        FunctionTool(geo_search_commune),
    ]

    agent = ChatAgent(
        system_message=SYSTEM_MESSAGE,
        model=model,
        tools=tools,
    )

    logger.info(f"Created GeoAgent with model {model_id}")
    return agent


def get_geo_agent() -> ChatAgent:
    """Get a GeoAgent with default configuration."""
    return create_geo_agent()
