"""
TAJINE - Territorial Analysis & Joint Intelligence for Networked Environments

Strategic meta-agent with cognitive reasoning capabilities.

Components:
- TAJINEAgent: Strategic meta-agent with PPDSL cycle
- CognitiveEngine: 5-level cognitive processing system
- ValidationEngine: Anti-hallucination validation pipeline
- TrustManager: Adaptive autonomy management
- StrategicPlanner: Task decomposition and planning
- HybridLLMRouter: Intelligent routing between local and cloud LLMs
"""

from src.infrastructure.agents.tajine.cognitive import (
    CausalLevel,
    CognitiveEngine,
    DiscoveryLevel,
    ScenarioLevel,
    StrategyLevel,
    TheoreticalLevel,
)
from src.infrastructure.agents.tajine.llm_router import (
    HybridLLMRouter,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ModelTier,
    OllamaProvider,
    OumiProvider,
    RoutingDecision,
    TaskComplexity,
    create_hybrid_router,
)
from src.infrastructure.agents.tajine.planning import StrategicPlanner
from src.infrastructure.agents.tajine.tajine_agent import (
    TAJINEAgent,
    create_tajine_agent,
)
from src.infrastructure.agents.tajine.trust import AutonomyLevel, TrustManager
from src.infrastructure.agents.tajine.validation import ValidationEngine

__all__ = [
    # Core Agent
    "TAJINEAgent",
    "create_tajine_agent",
    # Cognitive Engine
    "CognitiveEngine",
    "DiscoveryLevel",
    "CausalLevel",
    "ScenarioLevel",
    "StrategyLevel",
    "TheoreticalLevel",
    # Validation
    "ValidationEngine",
    # Trust Management
    "TrustManager",
    "AutonomyLevel",
    # Planning
    "StrategicPlanner",
    # LLM Router
    "HybridLLMRouter",
    "LLMRequest",
    "LLMResponse",
    "LLMProvider",
    "OllamaProvider",
    "OumiProvider",
    "ModelTier",
    "TaskComplexity",
    "RoutingDecision",
    "create_hybrid_router",
]
