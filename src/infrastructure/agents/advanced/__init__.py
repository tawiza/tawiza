#!/usr/bin/env python3
"""
Agents IA avancés pour Tawiza-V2
"""

from .agent_integration import AdvancedAgentIntegration, create_advanced_agent_integration
from .browser_automation_agent import BrowserAutomationAgent
from .code_generator_agent import CodeGeneratorAgent
from .conversation_memory import (
    AdvancedConversationMemory,
    ContextManager,
    ConversationContext,
    LongTermMemory,
    PersonalizationEngine,
    ShortTermMemory,
)
from .deep_research_agent import (
    DeepResearchAgent,
    ResearchQuery,
    ResearchResult,
    create_research_agent,
)
from .gpu_optimizer import GPUOptimizer, create_gpu_optimizer
from .data_analyst_agent import DataAnalystAgent

try:
    from .ml_engineer_agent import MLEngineerAgent
except ImportError:
    MLEngineerAgent = None  # type: ignore[assignment,misc]  # optuna is optional
from .multi_agent_system import (
    AgentCoordinator,
    AgentMetrics,
    AgentPriority,
    AgentStatus,
    AgentTask,
    BaseAgent,
    MultiAgentSystem,
)
from .s3_storage_agent import S3StorageAgent, get_s3_agent
from .web_crawler_agent import CrawlConfig, WebCrawlerAgent, create_crawler

__all__ = [
    # Multi-agent system
    "BaseAgent",
    "AgentCoordinator",
    "MultiAgentSystem",
    "AgentTask",
    "AgentStatus",
    "AgentPriority",
    "AgentMetrics",
    # Memory system
    "AdvancedConversationMemory",
    "ConversationContext",
    "ShortTermMemory",
    "LongTermMemory",
    "ContextManager",
    "PersonalizationEngine",
    # Agents
    "DataAnalystAgent",
    "MLEngineerAgent",
    "BrowserAutomationAgent",
    "CodeGeneratorAgent",
    "GPUOptimizer",
    "create_gpu_optimizer",
    # Integration
    "AdvancedAgentIntegration",
    "create_advanced_agent_integration",
    # S3 Storage Agent
    "S3StorageAgent",
    "get_s3_agent",
    # Web Crawler Agent
    "WebCrawlerAgent",
    "CrawlConfig",
    "create_crawler",
    # Deep Research Agent
    "DeepResearchAgent",
    "ResearchQuery",
    "ResearchResult",
    "create_research_agent",
]
