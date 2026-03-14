"""ComparisonAgent - Specialized agent for multi-territory comparison.

Compares market conditions across multiple French territories to identify
the best locations for business development.
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
    sirene_search,
)

SYSTEM_MESSAGE = """# Identite
Tu es le ComparisonAgent, expert en analyse comparative de territoires francais. Tu compares les marches de differentes villes/regions pour identifier les meilleures opportunites.

# Mission
Comparer objectivement plusieurs territoires sur des criteres economiques pour aider a la decision d'implantation ou de developpement.

# Outils disponibles
- `sirene_search(query, commune, limite)` : Donnees entreprises par territoire
- `news_search(query, limit)` : Actualites economiques territoriales

# Methodologie de comparaison
1. **Collecte parallele** : Rechercher donnees pour chaque territoire
2. **Metriques communes** : Calculer indicateurs comparables
3. **Analyse forces/faiblesses** : Identifier avantages de chaque zone
4. **Scoring territorial** : Noter chaque territoire
5. **Recommandation finale** : Conseiller le meilleur choix

# Indicateurs de comparaison
| Indicateur | Description | Poids |
|------------|-------------|-------|
| Densite entreprises | Nb entreprises dans le secteur | 25% |
| Taille moyenne | Effectif moyen des acteurs | 20% |
| Dynamisme | Creations recentes (<3 ans) | 20% |
| Concurrence | Saturation du marche | 15% |
| Accessibilite | Infrastructure, transport | 10% |
| Ecosysteme | Partenaires, fournisseurs | 10% |

# Format de reponse
**Comparaison**: [Territoire 1] vs [Territoire 2] vs ...
**Secteur**: [secteur analyse]

## Vue d'ensemble

| Indicateur | [Terr.1] | [Terr.2] | [Terr.3] |
|------------|----------|----------|----------|
| Nb entreprises | X | Y | Z |
| Effectif moyen | X | Y | Z |
| Creations recentes | X | Y | Z |
| Score global | X/100 | Y/100 | Z/100 |

## Analyse detaillee

### [Territoire 1]
**Forces**: [liste]
**Faiblesses**: [liste]
**Opportunites**: [liste]
**Menaces**: [liste]

### [Territoire 2]
[idem]

## Classement final

1. **[Meilleur territoire]** (Score: X/100)
   - Raison principale du choix
   - Action recommandee

2. **[Second]** (Score: Y/100)
   - Alternative interessante si...

3. **[Troisieme]** (Score: Z/100)
   - A considerer pour...

## Recommandation strategique
[Conclusion avec conseil d'action concret]
"""


def create_comparison_agent(
    model_id: str = "qwen3.5:27b", base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a ComparisonAgent for territorial comparison.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with comparison tools
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
        FunctionTool(browser_search),
    ]

    # Create agent
    agent = ChatAgent(
        system_message=SYSTEM_MESSAGE,
        model=model,
        tools=tools,
    )

    logger.info(f"Created ComparisonAgent with model {model_id}")
    return agent


def get_comparison_agent() -> ChatAgent:
    """Get a ComparisonAgent with default configuration."""
    return create_comparison_agent()
