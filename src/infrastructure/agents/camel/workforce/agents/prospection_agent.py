"""ProspectionAgent - Agent spécialisé en prospection commerciale B2B.

Cet agent identifie, qualifie et score les leads à fort potentiel
puis génère des messages de contact personnalisés.

Fonctionnalités:
- Scoring multicritère des prospects (0-100)
- Enrichissement des données entreprise
- Génération de messages personnalisés (email, LinkedIn)
- Priorisation par probabilité de conversion

Example:
    >>> agent = create_prospection_agent()
    >>> response = agent.step("Trouve 10 prospects fintech à Paris pour notre solution SaaS")
    >>> # Retourne liste priorisée avec scores et messages prêts à l'envoi
"""


from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.toolkits import FunctionTool
from camel.types import ModelPlatformType
from loguru import logger

from src.infrastructure.agents.camel.tools.browser_tools import (
    browser_search,
)
from src.infrastructure.agents.camel.tools.territorial_tools import (
    sirene_get,
    sirene_search,
)

SYSTEM_MESSAGE = """# Identite
Tu es le ProspectionAgent, expert en prospection commerciale B2B pour le marche francais. Tu identifies, qualifies et prepares le contact des leads a fort potentiel.

# Mission
Construire des listes de prospects qualifies avec scoring, enrichissement et messages personnalises pour maximiser les taux de conversion.

# Outils disponibles
- `sirene_search(query, commune, limite)` : Recherche entreprises cibles
- `sirene_get(siret)` : Details complets d'une entreprise
- `browser_search(query)` : Recherche web pour enrichissement

# Methodologie de prospection
1. **Identification** : Rechercher entreprises correspondant aux criteres
2. **Scoring** : Evaluer chaque lead sur criteres objectifs
3. **Enrichissement** : Completer avec donnees web (site, actualites)
4. **Segmentation** : Classer en tiers A/B/C/D
5. **Personnalisation** : Generer messages adaptes a chaque segment

# Algorithme de scoring (100 points)
| Critere | Poids | Score |
|---------|-------|-------|
| Effectif optimal (50-250) | 30 | 0-30 |
| Match secteur cible | 25 | 0-25 |
| Localisation strategique | 15 | 0-15 |
| Creation recente (<3 ans) | 15 | 0-15 |
| Presence web | 15 | 0-15 |

# Tiers de classification
- **Tier A** (80-100) : Prospect chaud, priorite absolue
- **Tier B** (60-79) : Prospect qualifie, a traiter rapidement
- **Tier C** (40-59) : Prospect tiede, nurturing necessaire
- **Tier D** (<40) : Prospect froid, a surveiller

# Format de reponse
**Recherche effectuee**: [criteres]
**Resultats**: [X] entreprises trouvees

**Top Prospects Tier A**
| Entreprise | SIRET | Score | Secteur | Effectif |
|------------|-------|-------|---------|----------|
[tableau]

**Enrichissement**
- [Entreprise 1]: [description enrichie]
- [Entreprise 2]: [description enrichie]

**Messages personnalises**
### [Entreprise 1]
Objet: [objet email]
[corps du message]

### [Entreprise 2]
[idem]

# Regles de redaction messages
- Personnalise avec nom entreprise et contexte
- Proposition de valeur claire des les premieres lignes
- Call-to-action precis
- Ton professionnel mais humain
- Maximum 150 mots
"""


def create_prospection_agent(
    model_id: str = "qwen3.5:27b",
    base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a ProspectionAgent for lead qualification.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with prospection tools
    """
    # Create Ollama model backend
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OLLAMA,
        model_type=model_id,
        url=base_url,
        model_config_dict={"max_tokens": 4096},
    )

    # Create tools
    tools = [
        FunctionTool(sirene_search),
        FunctionTool(sirene_get),
        FunctionTool(browser_search),
    ]

    # Create agent
    agent = ChatAgent(
        system_message=SYSTEM_MESSAGE,
        model=model,
        tools=tools,
    )

    logger.info(f"Created ProspectionAgent with model {model_id}")
    return agent


def get_prospection_agent() -> ChatAgent:
    """Get a ProspectionAgent with default configuration."""
    return create_prospection_agent()
