"""Infrastructure des agents pour Tawiza-V2.

Ce module fournit une architecture multi-agents pour l'automatisation web,
l'analyse de données, et l'intelligence territoriale.

Modules disponibles:
- advanced: Agents IA avancés (ML, Data, Code, etc.)
- autonomous: Agents autonomes avec planification LLM
- camel: Intégration CAMEL AI pour multi-agents
- ecocartographe: Cartographie d'écosystèmes territoriaux
- openmanus: Automatisation web intelligente
- skyvern: Automatisation basée sur la vision
- tajine: Meta-agent stratégique avec raisonnement cognitif
- tools: Système de plugins/outils dynamiques
- memory: Mémoire partagée entre agents
- resilience: Retry automatique et circuit breaker
- chains: Chaînage et orchestration d'agents

Composants principaux:
- BaseAgent: Classe de base pour les agents web
- AgentRegistry: Registre centralisé pour la gestion des agents
- TAJINEAgent: Meta-agent stratégique (4 couches, 5 niveaux cognitifs)
- AgentChain: Orchestration séquentielle d'agents
- ParallelChain: Exécution parallèle d'agents
- SharedMemory: Mémoire partagée inter-agents
- ToolRegistry: Registre d'outils dynamiques
- RetryHandler: Gestion des retries avec backoff
- CircuitBreaker: Protection contre les cascades de pannes
"""

from src.infrastructure.agents.base_agent import BaseAgent
from src.infrastructure.agents.chains import (
    AgentChain,
    AgentStep,
    ChainResult,
    ChainStatus,
    ChainStep,
    FunctionStep,
    MapReduceChain,
    ParallelChain,
)
from src.infrastructure.agents.registry import AgentRegistry, get_agent_registry

__all__ = [
    # Core
    "BaseAgent",
    "AgentRegistry",
    "get_agent_registry",
    # Chains
    "AgentChain",
    "ParallelChain",
    "MapReduceChain",
    "ChainStep",
    "AgentStep",
    "FunctionStep",
    "ChainResult",
    "ChainStatus",
    # Submodules (lazy loaded)
    "advanced",
    "autonomous",
    "camel",
    "ecocartographe",
    "openmanus",
    "skyvern",
    "tajine",
    "tools",
    "memory",
    "resilience",
    # Services
    "BrowserAgentService",
    "BrowserUseAdapter",
    "OllamaBrowserChatModel",
    # TAJINE convenience exports
    "TAJINEAgent",
    "create_tajine_agent",
]


def __getattr__(name: str):
    """Import lazy des sous-modules pour éviter les dépendances manquantes."""
    # Agent modules
    if name == "advanced":
        from src.infrastructure.agents import advanced
        return advanced
    elif name == "autonomous":
        from src.infrastructure.agents import autonomous
        return autonomous
    elif name == "camel":
        from src.infrastructure.agents import camel
        return camel
    elif name == "ecocartographe":
        from src.infrastructure.agents import ecocartographe
        return ecocartographe
    elif name == "openmanus":
        from src.infrastructure.agents import openmanus
        return openmanus
    elif name == "skyvern":
        from src.infrastructure.agents import skyvern
        return skyvern
    elif name == "tajine":
        from src.infrastructure.agents import tajine
        return tajine

    # TAJINE convenience exports
    elif name == "TAJINEAgent":
        from src.infrastructure.agents.tajine import TAJINEAgent
        return TAJINEAgent
    elif name == "create_tajine_agent":
        from src.infrastructure.agents.tajine import create_tajine_agent
        return create_tajine_agent

    # New capability modules
    elif name == "tools":
        from src.infrastructure.agents import tools
        return tools
    elif name == "memory":
        from src.infrastructure.agents import memory
        return memory
    elif name == "resilience":
        from src.infrastructure.agents import resilience
        return resilience

    # Services
    elif name == "BrowserAgentService":
        from src.infrastructure.agents.browser_agent_service import BrowserAgentService
        return BrowserAgentService
    elif name == "BrowserUseAdapter":
        from src.infrastructure.agents.browser_use_adapter import BrowserUseAdapter
        return BrowserUseAdapter
    elif name == "OllamaBrowserChatModel":
        from src.infrastructure.agents.ollama_browser_chat_model import OllamaBrowserChatModel
        return OllamaBrowserChatModel

    # Memory convenience exports
    elif name == "SharedMemory":
        from src.infrastructure.agents.memory import SharedMemory
        return SharedMemory
    elif name == "get_shared_memory":
        from src.infrastructure.agents.memory import get_shared_memory
        return get_shared_memory

    # Tools convenience exports
    elif name == "ToolRegistry":
        from src.infrastructure.agents.tools import ToolRegistry
        return ToolRegistry
    elif name == "get_tool_registry":
        from src.infrastructure.agents.tools import get_tool_registry
        return get_tool_registry

    # Resilience convenience exports
    elif name == "RetryHandler":
        from src.infrastructure.agents.resilience import RetryHandler
        return RetryHandler
    elif name == "CircuitBreaker":
        from src.infrastructure.agents.resilience import CircuitBreaker
        return CircuitBreaker
    elif name == "with_retry":
        from src.infrastructure.agents.resilience import with_retry
        return with_retry

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
