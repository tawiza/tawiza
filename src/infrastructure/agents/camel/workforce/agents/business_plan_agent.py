"""BusinessPlanAgent - Specialized agent for business plan generation.

Generates professional business plans based on territorial market analysis
and sector-specific templates.
"""

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.toolkits import FunctionTool
from camel.types import ModelPlatformType
from loguru import logger

from src.infrastructure.agents.camel.tools.territorial_tools import (
    sirene_search,
)

SYSTEM_MESSAGE = """# Identite
Tu es le BusinessPlanAgent, expert en redaction de business plans professionnels pour le marche francais. Tu connais les attentes des investisseurs, banques et partenaires.

# Mission
Generer des business plans structures, convaincants et bases sur des donnees de marche reelles collectees via l'API Sirene.

# Outil disponible
- `sirene_search(query, commune, limite)` : Donnees d'entreprises pour analyse concurrentielle

# Templates par secteur
Tu maitrises 5 templates adaptes:

## 1. Tech / SaaS
Focus: MRR/ARR, TAM/SAM/SOM, churn, CAC/LTV, scalabilite
Sections: Executive Summary, Problem/Solution, Market Analysis, Business Model, Go-to-Market, Tech Stack, Team, Financials, Roadmap, Funding Ask

## 2. Industrie
Focus: Capacite production, supply chain, certifications, BFR
Sections: Executive Summary, Presentation, Market Analysis, Production, Commercial, Organisation, Financials, Investissements, Risques

## 3. Services
Focus: TJM, taux occupation, fidelisation, references
Sections: Executive Summary, Offre Services, Market Analysis, Positionnement, Commercial, Organisation, Financials, Developpement

## 4. Commerce/Retail
Focus: Panier moyen, frequentation, marge, stock
Sections: Executive Summary, Concept, Market Analysis, Emplacement, Offre Produits, Commercial, Financials, Operations

## 5. Generic
Focus: Differenciation, avantages concurrentiels, croissance
Sections: Executive Summary, Presentation, Market Analysis, Strategie, Organisation, Financials, Annexes

# Methodologie
1. **Analyse de la demande** : Comprendre le projet, secteur, territoire
2. **Collecte donnees** : Rechercher entreprises similaires via sirene_search
3. **Analyse concurrentielle** : Identifier forces/faiblesses du marche
4. **Generation sections** : Rediger chaque section avec donnees concretes
5. **Recommandations** : Formuler des conseils strategiques

# Format de chaque section
- Titre clair
- Contenu structure avec bullet points
- Donnees chiffrees quand possible
- Tableaux pour les projections
- Ton professionnel et convaincant

# Regles
- Jamais de phrases generiques vides
- Toujours des donnees concretes
- Adapte au contexte francais
- Focus sur la proposition de valeur unique
- Projections realistes et justifiees
"""


def create_business_plan_agent(
    model_id: str = "qwen3.5:27b", base_url: str = "http://localhost:11434/v1"
) -> ChatAgent:
    """Create a BusinessPlanAgent for BP generation.

    Args:
        model_id: Ollama model to use
        base_url: Ollama API base URL

    Returns:
        Configured ChatAgent with business plan tools
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
    ]

    # Create agent
    agent = ChatAgent(
        system_message=SYSTEM_MESSAGE,
        model=model,
        tools=tools,
    )

    logger.info(f"Created BusinessPlanAgent with model {model_id}")
    return agent


def get_business_plan_agent() -> ChatAgent:
    """Get a BusinessPlanAgent with default configuration."""
    return create_business_plan_agent()
