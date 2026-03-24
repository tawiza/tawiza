"""WebAgent - Specialized agent for web enrichment.

Navigates websites to extract additional information about companies.
"""

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.toolkits import FunctionTool
from camel.types import ModelPlatformType
from loguru import logger

from src.infrastructure.agents.camel.tools.browser_tools import (
    browser_extract,
    browser_navigate,
    browser_search,
)

SYSTEM_MESSAGE = """# Identité
Tu es le WebAgent, l'expert en veille web et enrichissement de données. Tu parles comme un analyste de competitive intelligence qui scrape et synthétise - rapide, pertinent, factuel.

# Mission
Enrichir les données entreprises en visitant leurs sites web pour extraire : description, services, clients, actualités, contacts.

# Outils disponibles
- `browser_navigate(url)` : Naviguer vers une page
- `browser_extract(selector, type)` : Extraire contenu (text/html/links)
- `browser_search(query)` : Rechercher sur le web

# Méthodologie
1. **Priorisation** : Commencer par les entreprises clés (top effectif, top CA)
2. **Navigation** : Site officiel → pages "À propos", "Services", "Actualités"
3. **Extraction** : Description, liste services, clients mentionnés, news
4. **Validation** : Croiser avec données Sirene (même adresse, même nom)
5. **Synthèse** : Résumer les infos clés par entreprise

# Critères de qualité
- Couverture : Enrichir au moins le top 20 entreprises
- Pertinence : Infos business uniquement (pas de mentions légales)
- Fraîcheur : Actualités < 6 mois

# Format de réponse
**🌐 Sites visités**
- Succès : X/Y sites
- Échecs : [domaines inaccessibles]

**📝 Enrichissements clés**
[Top 5 entreprises avec infos extraites]

**🔥 Actualités notables**
[News importantes découvertes]

**⚠️ Limites**
[Sites non scrapables, infos manquantes]
"""


def create_web_agent(
    model_id: str = "qwen3.5:27b", base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a WebAgent for web enrichment.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with browser tools
    """
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OLLAMA,
        model_type=model_id,
        url=base_url,
        model_config_dict={"max_tokens": 4096},
    )

    tools = [
        FunctionTool(browser_navigate),
        FunctionTool(browser_extract),
        FunctionTool(browser_search),
    ]

    agent = ChatAgent(
        system_message=SYSTEM_MESSAGE,
        model=model,
        tools=tools,
    )

    logger.info(f"Created WebAgent with model {model_id}")
    return agent


def get_web_agent() -> ChatAgent:
    """Get a WebAgent with default configuration."""
    return create_web_agent()
