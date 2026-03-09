"""Unified Adaptive Agent - Self-improving multi-tool agent."""

from .config import AutonomyLevel, LearningConfig, ToolConfig, TrustConfig, UnifiedAgentConfig
from .tool_router import ExecutionPlan, PlanStep, TaskAnalysis, ToolRouter
from .trust_manager import TrustManager
from .unified_agent import TaskRequest, TaskResult, TaskStatus, UnifiedAdaptiveAgent

__all__ = [
    "UnifiedAdaptiveAgent",
    "TaskRequest",
    "TaskResult",
    "TaskStatus",
    "ToolRouter",
    "TaskAnalysis",
    "ExecutionPlan",
    "PlanStep",
    "TrustManager",
    "UnifiedAgentConfig",
    "TrustConfig",
    "ToolConfig",
    "LearningConfig",
    "AutonomyLevel",
]
