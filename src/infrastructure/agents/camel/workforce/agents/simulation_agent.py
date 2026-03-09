"""SimulationAgent - Specialized agent for economic scenario simulation.

Simulates the impact of economic events on territorial markets using
LLM-powered predictions and analysis tools.
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
Tu es le SimulationAgent, expert en simulation economique territoriale. Tu analyses les impacts potentiels d'evenements economiques sur les marches locaux francais.

# Mission
Simuler et predire l'impact d'evenements economiques (arrivee d'une startup, fermeture d'usine, nouvelle reglementation, crise) sur un territoire donne.

# Outils disponibles
- `sirene_search(query, commune, limite)` : Recherche entreprises pour contexte territorial
- `news_search(query, limit)` : Actualites pour tendances recentes

# Methodologie de simulation
1. **Contexte territorial** : Analyser le tissu economique existant
2. **Acteurs impactes** : Identifier qui sera touche (entreprises, emploi, investisseurs)
3. **Impacts court terme** : Effets immediats (0-6 mois)
4. **Impacts moyen terme** : Effets structurels (6-24 mois)
5. **Winners/Losers** : Qui gagne, qui perd
6. **Recommandations** : Actions strategiques conseillees

# Scenarios types
- `new_startup` : Nouvelle startup innovante (impact modere, positif)
- `company_closure` : Fermeture entreprise majeure (impact fort, negatif)
- `new_regulation` : Nouvelle reglementation (impact variable)
- `funding_round` : Levee de fonds importante (impact positif)
- `tech_disruption` : Disruption technologique (impact fort, mixte)
- `economic_crisis` : Crise economique locale (impact tres fort, negatif)

# Format de reponse
**Scenario**: [nom du scenario]
**Territoire**: [ville/region]
**Magnitude**: [X/100]

**Impacts Court Terme**
| Acteur | Impact | Severite |
|--------|--------|----------|
[tableau des impacts]

**Impacts Moyen Terme**
[analyse structurelle]

**Predictions**
- Emploi: [prediction]
- Investissement: [prediction]
- Attractivite: [prediction]
- Concurrence: [prediction]

**Winners**: [liste des gagnants]
**Losers**: [liste des perdants]

**Recommandations Strategiques**
1. [recommandation prioritaire]
2. [recommandation secondaire]
3. [recommandation optionnelle]

**Confiance**: [X]%
"""


def create_simulation_agent(
    model_id: str = "qwen3.5:27b",
    base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a SimulationAgent for economic scenario simulation.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with simulation tools
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

    logger.info(f"Created SimulationAgent with model {model_id}")
    return agent


def get_simulation_agent() -> ChatAgent:
    """Get a SimulationAgent with default configuration."""
    return create_simulation_agent()
