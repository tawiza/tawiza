"""TAJINE Telemetry - Observability for the TAJINE agent."""

from src.infrastructure.agents.tajine.telemetry.config import TelemetryConfig
from src.infrastructure.agents.tajine.telemetry.instrumentor import (
    LANGFUSE_AVAILABLE,
    get_langfuse_context,
    # Langfuse helpers
    langfuse_available,
    record_bandit_pull,
    record_human_intervention,
    record_recommendation,
    # Recording functions
    record_score_3d,
    record_signal,
    record_theory,
    set_circuit_breaker,
    trace_bandit,
    trace_cognitive,
    # Decorators
    trace_hunt,
    trace_llm,
    # Context managers
    track_cache,
    track_fallback,
    update_autonomy,
    update_bandit_ucb,
    update_trust,
)
from src.infrastructure.agents.tajine.telemetry.metrics import (
    TAJINE_REGISTRY,
    autonomy_level,
    # Bandit
    bandit_pulls,
    bandit_rewards,
    bandit_ucb_score,
    cache_hits,
    cache_misses,
    circuit_breaker_state,
    # Cognitive
    cognitive_level_duration,
    cognitive_recommendations,
    cognitive_signals,
    cognitive_theories,
    fallbacks_used,
    human_interventions,
    hunt_duration,
    # DataHunter
    hunt_total,
    llm_cost_dollars,
    llm_errors,
    llm_latency,
    # LLM
    llm_tokens_total,
    score_alpha,
    score_coherence,
    score_combined,
    # Evaluator
    score_fiabilite,
    # Server
    start_metrics_server,
    # Autonomy
    trust_score,
)

__all__ = [
    "TelemetryConfig",
    # DataHunter
    "hunt_total",
    "hunt_duration",
    "cache_hits",
    "cache_misses",
    "fallbacks_used",
    "circuit_breaker_state",
    # Bandit
    "bandit_pulls",
    "bandit_rewards",
    "bandit_ucb_score",
    # Evaluator
    "score_fiabilite",
    "score_coherence",
    "score_alpha",
    "score_combined",
    # Cognitive
    "cognitive_level_duration",
    "cognitive_signals",
    "cognitive_theories",
    "cognitive_recommendations",
    # Autonomy
    "trust_score",
    "autonomy_level",
    "human_interventions",
    # LLM
    "llm_tokens_total",
    "llm_cost_dollars",
    "llm_latency",
    "llm_errors",
    # Server
    "start_metrics_server",
    "TAJINE_REGISTRY",
    # Langfuse helpers
    "langfuse_available",
    "get_langfuse_context",
    "LANGFUSE_AVAILABLE",
    # Decorators
    "trace_hunt",
    "trace_cognitive",
    "trace_llm",
    "trace_bandit",
    # Context managers
    "track_cache",
    "track_fallback",
    # Recording functions
    "record_score_3d",
    "record_bandit_pull",
    "update_bandit_ucb",
    "record_signal",
    "record_theory",
    "record_recommendation",
    "update_trust",
    "update_autonomy",
    "record_human_intervention",
    "set_circuit_breaker",
]
